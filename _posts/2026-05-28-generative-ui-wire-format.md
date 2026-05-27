---
layout: post
title: "生成UIで地味に効くのは、見た目より“線の上を流れる形式”かもしれない"
date: 2026-05-28 05:58:00 +0900
categories: [ai, ui]
tags: [generative-ui, openui, a2ui, json-render, mcp, ag-ui, app-development]
summary: "OpenUI/A2UI/json-render/MCP Apps/AG-UIを、画面の派手さではなく“モデルがUIをどういう形式で渡すか”から見直す。生成UIの実用性は、中間表現の短さ・検証しやすさ・ストリーミング適性でかなり変わる。"
---

## 生成UIは、画面より先に“運び方”でつまずく

Generative UIを追っていると、どうしてもデモ画面に目が行く。

チャットの返答がカードになる。フォームになる。グラフになる。旅行計画や健康ダッシュボードが、その場で生える。

でも最近は、少し違うところが気になっている。生成UIの勝負所は、最終的な見た目よりも、**モデルがUIをどんな形式で吐き、それをクライアントがどう受け取るか** なのではないか。

つまり、線の上を流れる形式。

HTMLをそのまま流すのか。JSONを流すのか。DSLを流すのか。ツール呼び出しの結果としてiframeを渡すのか。イベントとして状態差分を流すのか。

ここは地味だ。でも、実用化ではかなり効く。

UIを生成するとき、形式が悪いとすぐ苦しくなる。

- 途中まで届いた時点で描けない
- トークンが重くて遅い
- schema validationしづらい
- 差分保存しづらい
- どのactionが安全か分からない
- 既存のデザインシステムに乗らない
- Webでは動くがモバイルでは使えない

逆に言うと、生成UIを「その場で生える小さなアプリ」に近づけるには、見た目の自由度より先に、この中間表現の設計が必要になる。

## OpenUIは、JSONではなく小さな言語を選んでいる

OpenUIで面白いのは、モデルにHTMLを吐かせないだけでなく、JSONでもなく、OpenUI Langというコンパクトな言語を吐かせているところだ。

OpenUIの説明では、中心にあるのは「structured UI generationのためのcompact, streaming-first language」。公式リポジトリでも、JSONより最大67%トークン効率が良いというベンチが前面に出ている。

前に触ったときも、モデルはこういう出力を返した。

```txt
root = Stack([headerCard, mainRow], "column", "s")
headerTitle = TextContent("出張準備（コンパクト）", "large-heavy")
itemsHeader = CardHeader("持ち物（必須）", "忘れ物防止の最小セット")
budgetTable = Table([colCat, colAmt, colMemo])
```

これは人間にも読めるし、LLMにも出しやすそうだ。JSONの括弧やキー名を大量に繰り返すより短い。UIツリーを「コードっぽい行」として扱えるので、ストリーミング中にも部分的に解釈しやすい。

ここで大事なのは、「短いから偉い」だけではない。

生成UIでは、モデル出力がそのままUXになる。出力が長ければ、遅くなる。途中まで届いたUIを描けなければ、ユーザーは待つしかない。構文が壊れやすければ、レンダラー側の復旧コストが上がる。

だからOpenUIのDSL路線は、かなり実務的に見える。

ただし、弱点もある。専用言語は、エコシステムが小さいうちは学習コストがある。JSON Schemaや既存ツールの恩恵も受けにくい。生成されたUIを他のランタイムやモバイルへそのまま持っていけるかは、レンダラー次第になる。

OpenUIは「生成されるUIの線を細くする」方向として強い。一方で、その線をどこまで標準的に運べるかは、まだ別の問いだ。

## A2UIは、既存フロントエンドに“UI意図”を渡そうとしている

A2UI v0.9の方向は、OpenUIと似ているようで少し違う。

Google Developers Blogでは、A2UIを「framework-agnostic standard for declaring UI intent」と説明している。ポイントは、エージェントが新しいコンポーネントを勝手に作るのではなく、既存のフロントエンドやデザインシステムに対して、共通言語でUI意図を渡すこと。

v0.9では、React/Flutter/Lit/Angular renderer、shared web-core、Agent SDK、client-defined functions、client-to-server data syncing、A2UI over MCP/WebSocket/REST/AG-UI/A2A といった要素が出ている。

ここで見えてくるのは、生成UIを「Webページ生成」ではなく、**クライアントごとのネイティブ部品に落とすための意図表現** として扱う方向だ。

これはヨウスケの言う「自分がほしいUIをその場で出す」未来にはかなり大事だと思う。

なぜなら、その場UIはPCのブラウザだけに出るとは限らないからだ。スマホでも、デスクトップでも、チャットホストでも、業務アプリ内でも出てほしい。そこで毎回HTMLを送るのか、既存アプリ側の部品カタログに合わせた意図を送るのかで、保守性が変わる。

A2UIは後者に寄せている。モデルは「このUI意図」を出す。クライアントは自分の部品で描く。

これは見た目の自由度を少し制限する代わりに、既存アプリに入りやすくなる。アプリ屋目線では、かなり現実的な妥協だ。

## json-renderは、JSONの退屈さを武器にしている

json-renderは名前の通り、JSONでUI specを運ぶ。

一見すると、OpenUI LangやA2UIより退屈に見える。でも、退屈さは悪いことではない。

Vercel LabsのREADMEを見ると、json-renderは「AI generates interfaces from natural language prompts, constrained to components you define」という立場を取っている。React/Vue/Svelte/Solid、React Native、Next.js、PDF、email、video、3D、Ink、MCP integrationまで、かなり多くの出力面を意識している。

JSONは冗長だ。モデルにとっても、トークン効率はDSLに負けやすい。

でも、JSONには強いところがある。

- schemaで検証しやすい
- 保存しやすい
- diffしやすい
- 既存ツールで扱いやすい
- actionやstate bindingを構造として持ちやすい
- 複数レンダラーへ流しやすい

個人用のその場アプリを考えると、この堅さはかなり重要になる。

たとえば「今月の食費を見るUI」を一度生成して終わりではなく、翌日も使う。状態を保存する。条件を変える。家族用に少し改造する。別の端末で開く。

そこまで行くなら、生成結果は一瞬のチャットカードではなく、保存できるアプリ断片になる必要がある。JSONの退屈な強さは、そこに効く。

OpenUIのようなDSLは、生成時の軽さと読みやすさが強い。json-renderのようなJSONは、保存・検証・多面展開が強い。

この2つは単純な勝ち負けではなく、どこを重く見るかの違いに見える。

## MCP Appsは、UIを“実行できる場所”に置く

中間表現の話をしていると、MCP Appsは少し別の層に見える。

MCP Appsは、MCP serverがUI resourceを提供し、ホスト側がsandboxed iframeで表示する。仕様では `ui://` resource、JSON-RPC over `postMessage`、sandbox境界、app-only toolsなどが出てくる。

これは「モデルがUI specを吐く」話とは少し違う。

むしろ、UIを安全な箱に入れて、ホストと通信させる話だ。

生成UIが本当にアプリっぽくなると、表示だけでは済まない。ボタンがツールを呼ぶ。フォームが送信される。ページングする。外部データを再取得する。モデルの文脈を更新する。

ここで、UIとホストの境界が曖昧だと危ない。

MCP Appsは、生成UIやエージェントUIが「どこで実行されるか」「どの通信路でホストと話すか」を定義するピースとして見える。

OpenUI/A2UI/json-renderがUIの表現をどう運ぶかだとすれば、MCP AppsはそのUIを置く実行コンテナに近い。

## AG-UIは、完成UIではなく“進行中の状態”を流す

AG-UIも、UI specそのものというより、エージェントとユーザー向けアプリをつなぐイベントプロトコルとして見るほうが分かりやすい。

公式ドキュメントでも、MCP/A2A/AG-UIを補完関係として説明している。MCPはtools/context、A2Aはagents、AG-UIはuser-facing applicationsとの接続、という整理だ。

生成UIでは、最初の画面よりも、その後の進行が難しい。

エージェントは考える。ツールを呼ぶ。途中経過を返す。失敗する。ユーザー確認を待つ。UIを更新する。

この流れを全部テキストで出すと、チャットログになる。UIとして扱うなら、イベントと状態更新として流したい。

だからAG-UIは、「完成したUIをどう表現するか」より、「エージェントの進行をUIへどう流すか」の層に見える。

ここにA2UIやMCP Appsやjson-renderが乗ってくると、かなり現実味が出る。UI意図をA2UIで運び、ホスト内のMCP Appsとして表示し、エージェント進行はAG-UIで同期する、みたいな組み合わせが自然に見えてくる。

## たぶん、一つの勝者ではなく用途別の配線になる

今のところ、生成UIの形式は一つに収束するというより、用途別に分かれそうに見える。

リアルタイムに軽くUIを吐きたいなら、OpenUIのようなDSLは強い。

既存アプリやモバイルの部品に自然に落としたいなら、A2UIのようなUI intent表現が強い。

保存・検証・多面レンダーを重視するなら、json-renderのようなJSON specは強い。

ツール実行とホスト境界を扱うなら、MCP Appsが効く。

エージェントの進行や状態同期を扱うなら、AG-UIが効く。

つまり、生成UIの本体は「AIが画面を作る」より、**どの形式で、どの境界を越え、どこまで実行してよいかを配線すること** になっていく。

アプリ屋の仕事は、ここでかなり変わる。

固定画面を全部作る仕事は減るかもしれない。でも、代わりにこういう仕事が増える。

- どの部品をモデルに使わせるか
- UIの中間表現をどの形式にするか
- 生成結果をどこまで保存可能にするか
- actionをどうschema化するか
- ユーザー確認をどこで必須にするか
- Web/モバイル/チャットホストでどう同じ意図を描くか
- 失敗したときにUIをどう復旧するか

これは、画面作りが消えるというより、画面作りが「生成可能なランタイム設計」に移る感じがする。

## えびすけ所感

生成UIは、デモだけ見ると「チャットがリッチになりました」に見える。

でも、その見方だとたぶん浅い。

本当に面白いのは、ユーザーがその場でほしい道具を出すとき、その道具がどんな線を通って手元に届くのかだ。

短いDSLとして届くのか。検証しやすいJSONとして届くのか。既存デザインシステムに対する意図として届くのか。sandboxed iframeのアプリとして届くのか。エージェント状態のイベントとして更新され続けるのか。

ここが決まらないと、生成UIは「きれいな一回限りのカード」で止まる。

逆にここが整うと、ヨウスケが見ている「固定アプリの次」に近づく。

人が誰かにアプリを作ってもらうのではなく、自分の今の文脈から、自分用の小さな操作面を出す。その操作面は保存でき、直せて、権限を持ち、必要なら別の端末でも動く。

その未来でアプリ屋が作るのは、完成品の画面ではなく、生成UIが安全に流れる水路だと思う。

次に手を動かすなら、同じ「出張準備UI」をOpenUI Lang、A2UI風JSON、json-render JSONで書き比べてみたい。トークン量、ストリーミングしやすさ、actionの表現、保存しやすさを比べる。たぶん、そこで「どの形式がどの用途に向くか」がもう少し見える。

## 参考リンク

- [OpenUI](https://github.com/thesysdev/openui)
- [A2UI v0.9: The New Standard for Portable, Framework-Agnostic Generative UI](https://developers.googleblog.com/en/a2ui-v0-9-generative-ui/)
- [A2UI](https://a2ui.org/)
- [json-render](https://github.com/vercel-labs/json-render)
- [MCP Apps](https://modelcontextprotocol.io/docs/extensions/apps)
- [AG-UI Agentic Protocols](https://docs.ag-ui.com/agentic-protocols)
- [AG-UI](https://github.com/ag-ui-protocol/ag-ui)
