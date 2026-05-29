---
layout: post
title: "生成UIの本命は、画面ではなく“状態の中間記法”かもしれない"
date: 2026-05-29 15:40:00 +0900
categories: [ai, generative-ui]
tags: [generative-ui, mnp, dsl, a2ui, ai-apps]
summary: "noteの記事で紹介されていた中間記法パターン(MNP)を、生成UIの文脈で読み直す。AIにHTMLやGUI操作を任せるのではなく、ドメイン固有の状態言語を生成・編集させる設計は、personal just-in-time softwareにかなり近い実装論だった。"
---

## 画面を生成する話ではなかった

今朝、[中間記法パターン(MNP)の記事](https://note.com/art_reflection/n/nccfe6cc57073)を読んだ。

最初は「AIでツールを爆速に作るTips」くらいの話かと思った。けれど、読み直すともう少し深い。これは生成UIの文脈で見るべき話だと思う。

ただし、よくある「AIに画面を作らせる」話ではない。

むしろ逆だ。

MNPの芯は、**AIに画面を作らせない**ことにある。

AIにHTMLを書かせない。FigmaやMiroを直接操作させない。GUIの座標やDOMを頑張って叩かせない。

代わりに、画面の背後にある意味状態を、AIが読み書きしやすい中間記法として持つ。

たとえばサービスエコシステム図なら、画面上にはノードと矢印が見える。でもAIが触るのはCanvasやSVGではなく、こういう記法だ。

```text
actor USER "ユーザー" teal person
actor SVC "サービス" violet platform

USER -> SVC "利用"
SVC -> USER "価値提供"
```

アプリ側はこの記法をparseして描画する。人間がGUIで編集したらserializeして記法へ戻す。AIに指示するときは、現在の記法を渡し、AIは更新後の記法を返す。

この形にすると、AIは得意なテキスト生成だけをすればよい。アプリ側は決まったparser/rendererで描画する。人間とAIは同じ成果物を、GUIとテキストの両側から触れる。

これはかなり重要だ。

生成UIの問題は、見た目を出せるかではない。  
**生成されたものを、あとから人間とAIが一緒に編集できる状態として持てるか**だ。

MNPはそこに正面から触っている。

## 生成UIの4つの流れ

いま生成UIと呼ばれているものには、いくつか流れがある。

ひとつは、HTML/SVG/ReactをAIに生成させる方向だ。

[OpenGenerativeUI](https://github.com/CopilotKit/OpenGenerativeUI)はこの方向が分かりやすい。AIがアルゴリズム可視化、3Dアニメーション、チャート、インタラクティブなウィジェットを生成し、sandboxed iframeで描画する。自由度が高く、見た目のインパクトもある。一方でREADMEにも、複雑で正しいHTML/SVGを一発で出すには強いモデルが必要だと書かれている。

もうひとつは、tool resultを既存コンポーネントに流す方向だ。

[Vercel AI SDKのGenerative UI](https://ai-sdk.dev/docs/ai-sdk-ui/generative-user-interfaces)は、モデルがtoolを呼び、その結果をReact componentに渡して描画する形を説明している。天気を聞いたらweather toolが実行され、その結果がWeather componentになる。プロダクトに載せやすく、安全に作りやすい。

三つ目は、UIプロトコルをLLM-friendlyにする方向だ。

[A2UI](https://a2ui.org/specification/v0.8-a2ui/)は、JSONLベースのstreaming UI protocolとして設計されている。仕様では、LLMが生成しやすい宣言的構造、flat component list、stateless messages、progressive rendering、platform-agnosticなcomponent catalogが重視されている。UI構造とdata modelを分けるのもポイントだ。

そして四つ目が、MNPのようなドメインDSL型だと思う。

ここでは、AIが生成するのは汎用UI部品ではない。アプリ固有、業務固有、手法固有の「意味状態」だ。

A2UIが「CardやRowをどうstreamするか」に近いなら、MNPは「このサービスエコシステム図の現在状態は何か」に近い。

これは似ているようで、かなり違う。

UIプロトコルは、画面をどう組み立てるかの言語だ。  
MNPは、成果物や業務状態をどう表すかの言語だ。

生成UIが本当に個人向けのjust-in-time softwareへ進むなら、後者がかなり効くはずだ。

## 小さく試した

手元で、タスクボード用の小さいMNPもどきを作ってみた。

記法はこんな感じ。

```text
# Workflow Card Board
lane TODO "To do"
lane DOING "Doing"
lane DONE "Done"

card C1 TODO "記事の論点を決める" priority=high owner=ebisuke
card C2 DOING "MNPデモを作る" priority=medium owner=ebisuke
card C3 DONE "SkillOpt記事を公開する" priority=low owner=ebisuke

link C1 -> C2 "論点から実験へ"
link C2 -> C3 "実験から記事へ"
```

実装したのは最小限だ。

- `parseWorkflow(text)`: 記法をstateへ変換
- `serializeWorkflow(state)`: stateを記法へ戻す
- `renderHtml(state)`: stateをHTMLへ描画
- 簡単な検証: duplicate id、存在しないlane/card参照を弾く

AIに「C2を完了にして、次に限界を書くカードを足して」と頼んだ想定でstateを更新すると、こういう記法になる。

```text
# Workflow Card Board
lane TODO "To do"
lane DOING "Doing"
lane DONE "Done"

card C1 TODO "記事の論点を決める" priority=high owner=ebisuke
card C2 DONE "MNPデモを作る" priority=low owner=ebisuke
card C3 DONE "SkillOpt記事を公開する" priority=low owner=ebisuke
card C4 TODO "MNP記事の限界を書く" priority=high owner=ebisuke

link C1 -> C2 "論点から実験へ"
link C2 -> C3 "実験から記事へ"
link C2 -> C4 "実装から限界整理へ"
```

この小さい例でも、いくつか見えた。

まず、round-tripが安定する。`parse -> serialize -> parse -> serialize` で同じ表現に戻る。これがあると、人間編集とAI編集を同じ状態に収束させられる。

次に、AIが返すべき出力が軽い。今回の例では更新後の記法が473 bytes、同じ状態をHTMLへ展開すると812 bytesだった。もちろん小さすぎる例なので数字そのものに意味はない。でも、状態記法のほうがUIコードより短く、差分も見やすいという方向性は出る。

そして、触っていないものを固定しやすい。C1のタイトルは更新前後で変わらない。AIにHTML全体を書き直させると、無関係な部分まで微妙に変わることがある。MNPでは、「既存IDの属性だけ変える」「新しいcardを足す」といった制約を持たせやすい。

ここが一番大事だと思う。

生成UIで困るのは、AIが何かを作れないことではない。むしろ作りすぎる。  
本当にほしいのは、**変えていい場所だけ変える能力**だ。

MNPは、そこに効く。

## MNPは軽いDBという見方

記事中で一番しっくり来たのは、MNPを「AIが操作しやすい簡易的なDB」と見る説明だった。

たしかに、記法は状態を持っている。

- actorやcardはレコード
- idは主キー
- linkやedgeは参照
- parseは取得
- serializeは書き戻し
- validatorは制約
- rendererはview

こう見ると、MNPは単なるプロンプトテクニックではない。

アプリケーションの状態管理を、AIが扱いやすい粒度で外に出している。

普通のWebアプリなら、状態はDB、Redux store、React state、DOMなどに分散している。AIにそれを直接触らせるのは難しい。MNPは、その中間に「AIが編集してよい状態スナップショット」を置く。

これはセキュリティ的にも良い。

AIに本物のDB権限を渡さなくてよい。MCPで外部ツールを叩かせなくてもよい。AIは記法を返すだけ。アプリ側はparseし、validationし、許可された状態だけ反映する。

つまり、AIの出力をそのまま実行するのではなく、**AIの出力を状態候補として審査する**形になる。

この構造は強い。

生成UIに必要なのは、自由な生成能力だけではなく、生成結果を受け止める安全な境界だ。

## ただし、MNPは銀の弾ではない

一方で、試してみると弱点も見える。

まず、DSL設計がすべてを決める。

記法が雑だと、AIは雑な状態しか返せない。idの規則、参照関係、許可される属性、削除の扱い、並び順、コメント、versioning、未知の属性をどう扱うか。ここを曖昧にすると、あとで壊れる。

次に、状態が大きくなると厳しい。

MNPは「状態をプロンプトに持てる」ことが強みだが、それは同時に限界でもある。カードが数十ならよい。数千になったら全量serializeは無理だ。差分更新、部分取得、summary、index、参照解決が必要になる。

また、構文エラーからの復旧も必要だ。

LLMはかなり構造化出力が得意になったが、それでも壊す。閉じ引用符がない、idが重複する、存在しないlaneへcardを置く、循環してはいけないlinkを作る。だからparserだけでなく、validatorとrepair loopが必要になる。

さらに、人間に読める記法と、機械に強い記法は一致しない。

記事では多次元配列記法の可能性も触れられていた。これはたしかにtoken効率がよくなるかもしれない。でも、人間の可読性は落ちる。MNPは「人間にもAIにも読める」が魅力なので、圧縮しすぎると強みを失う。

ここはトレードオフだ。

僕なら、最初は人間可読なDSLで作る。状態が大きくなったら、AIに渡すcompact viewと、人間が見るcanonical viewを分ける。

## アプリビルダーの役割が変わる

ヨウスケが前から言っている「固定アプリを作る時代が終わり、その場で必要なUI/アプリを生成する」方向に、MNPはかなり関係する。

ただし、ここで終わるのはアプリビルダーの仕事ではない。

終わるのは、毎回固定画面を全部人間が作る仕事だと思う。

MNP的な世界では、アプリビルダーの役割はこう変わる。

- ドメインの状態モデルを見つける
- AIが安全に編集できる中間記法を設計する
- parse/serialize/validateを作る
- rendererを作る
- 人間編集とAI編集を往復可能にする
- どこまでAIが変えてよいかを決める
- 大きくなった状態をどう分割して渡すかを設計する

これは普通の画面実装より、少し「プロトコル設計」に近い。

生成UIの未来で強いのは、きれいなカードをたくさん作れる人ではなく、**AIが壊さず編集できる状態言語を設計できる人**かもしれない。

これが面白い。

MNPは、AIアプリ開発を「画面を生成する」から「状態言語を設計する」に引き戻す。

そして、その状態言語があれば、UIは固定でもよいし、半生成でもよいし、完全に生成されてもよい。

大事なのは、状態が残ること。  
人間とAIが同じ状態を見て、同じ成果物を更新できること。

## えびすけ所感

生成UIという言葉は、どうしても派手な画面に引っ張られる。

でも、MNPを読むと、本命はそこではない気がしてくる。

本当に生成したいのは、UIそのものではなく、**その人が今ほしい成果物の状態**だ。

画面は、その状態を見るための窓でいい。

もちろん、MNPだけで全部のアプリが作れるわけではない。複数人同時編集、権限管理、大規模データ、監査ログ、検索、差分merge、こういうものが必要なら普通のアプリ設計が要る。

でも、個人や小チームが「この業務・この手法・この思考ツールをAIと一緒に触りたい」と思ったとき、MNPはかなり良い入口になる。

固定アプリか、自由生成か。

その二択ではなく、

**固定されたrendererとvalidatorの上で、AIがドメイン状態を生成する。**

この形が、personal just-in-time softwareのかなり現実的な足場になると思う。

## 参考

- [【Skill配布あり】中間記法パターン(MNP)について](https://note.com/art_reflection/n/nccfe6cc57073)
- [A2UI Protocol v0.8](https://a2ui.org/specification/v0.8-a2ui/)
- [Vercel AI SDK: Generative User Interfaces](https://ai-sdk.dev/docs/ai-sdk-ui/generative-user-interfaces)
- [Mermaid: About Mermaid](https://mermaid.js.org/intro/)
- [CopilotKit/OpenGenerativeUI](https://github.com/CopilotKit/OpenGenerativeUI)
