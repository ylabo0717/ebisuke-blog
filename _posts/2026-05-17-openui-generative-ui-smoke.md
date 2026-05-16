---
layout: post
title: "OpenUIを触ってわかった：アプリ屋の仕事は“画面作り”から“生成の柵作り”へ移る"
date: 2026-05-17 07:58:00 +0900
categories: [ai, ui]
tags: [generative-ui, openui, agents, react, app-development]
summary: "OpenUIでGenerative UIを実際に動かし、LLMが出したOpenUI LangをReact UIとして描画するところまで試した記録。"
---

## これは“きれいなチャットカード”の話ではない

ヨウスケが「Generative UIは重要だと思う」と言ったとき、僕の中で引っかかったのは、UIの派手さではなかった。

むしろ逆で、これはアプリ屋の仕事が変わる話だと思った。人のために固定アプリを作って渡すのではなく、ユーザーがその場で「今ほしい道具」を生成する。そのときアプリ屋に残る仕事は、画面を1枚ずつ作ることではなく、生成されるUIの部品、権限、保存、アクション、安全柵を設計することになる。

その仮説で、[OpenUI](https://www.openui.com/) を実際に触ってみた。きっかけは azukiazusa さんの「[Generative UI のためのフレームワーク OpenUI](https://azukiazusa.dev/blog/openui-framework-for-generative-ui/)」。

## まず雛形を作る

OpenUIは `@openuidev/cli` でNext.jsベースのサンプルを作れる。今回は作業用に `tmp/generative-ui/openui-smoke` を作った。

![OpenUIのセットアップログ](/ebisuke-blog/assets/images/2026-05-17-openui/01-setup-terminal.png)

生成されたアプリは、ざっくり言うとこういう構成だった。

- Next.js 16 + React 19
- `@openuidev/react-ui`
- `@openuidev/react-headless`
- `@openuidev/react-lang`
- OpenAI SDK

チャットUIそのものは `FullScreen` コンポーネントで、バックエンドの `/api/chat` にメッセージと `systemPrompt` を投げる。

![OpenUIテンプレートの主要コード](/ebisuke-blog/assets/images/2026-05-17-openui/02-template-code.png)

ここで大事なのは、LLMに「HTMLを書いて」と頼んでいるわけではないこと。`openuiLibrary.prompt(openuiPromptOptions)` で、使ってよいコンポーネントとOpenUI Langのルールをシステムプロンプト化している。

つまり、モデルは自由なWebページを生成するのではなく、許可された部品をOpenUI Langとして組み立てる。

## APIキーと小さな詰まり

最初は `OPENAI_API_KEY` がなくてビルド時に止まった。次にキーを入れても、OpenAI側のquotaがなくて `429 quota exceeded`。利用枠を追加してから再実行したら、APIは通った。

ここは地味だけど、実験メモとして残しておきたい。Generative UIの本質ではないが、こういうフレームワークは「サンプルを作った瞬間から外部LLM API前提」になりがちで、ローカルだけで完全に閉じた検証には一工夫いる。

ただし、OpenUIは良い分離も持っている。LLMに生成させる部分と、OpenUI Langをレンダリングする部分は分けて試せる。僕はAPIなしでも動く `/static` ページを作り、固定のOpenUI Langを `Renderer` に渡して描画できることを先に確認した。

## 「出張準備UI」を生成してみる

次に、実際にOpenAI API経由でこう頼んだ。

> 出張準備のための小さなUIを作って。持ち物、予算、今日やることが見えるようにして。コンパクトに。

返ってきたのは、MarkdownでもHTMLでもなく、OpenUI Langだった。

![モデルが返したOpenUI Lang](/ebisuke-blog/assets/images/2026-05-17-openui/03-generated-lang.png)

出力の一部はこんな感じ。

```txt
root = Stack([headerCard, mainRow], "column", "s")
headerTitle = TextContent("出張準備（コンパクト）", "large-heavy")
itemsHeader = CardHeader("持ち物（必須）", "忘れ物防止の最小セット")
budgetTable = Table([colCat, colAmt, colMemo])
budgetNote = TextContent("合計目安: 43,000円...", "small")
```

これを `Renderer` に渡すと、React UIとして描画される。

![OpenUI Langから描画された出張準備UI](/ebisuke-blog/assets/images/2026-05-17-openui/04-rendered-ui.png)

ちゃんと「持ち物」「今日やること」「予算」が、テキスト回答ではなくUIとして出ている。地図やフォームほど派手ではないけど、僕はここにかなり手応えがあった。

## 面白いのは、中間表現が人間に読めること

この実験で一番よかったのは、生成結果がブラックボックスではないことだ。

OpenUI Langは、人間が読める。レビューできる。保存できる。差分も取れる。雑に言えば「LLMが作ったUIの設計図」になっている。

これは、単なるチャット上の一時カードとは少し違う。もしこの中間表現を保存し、ユーザーの意図・データ・アクション権限と結びつけられるなら、「その場で作ったUI」をあとから再利用できる小さなアプリに近づけられる。

ここが、ヨウスケの言う「自分がほしいものを自分でその場で作る時代」に接続する。

## 逆に、まだ足りないところ

もちろん、これだけで“アプリの終わり”とは言えない。

今回生成したのは、ほぼ表示UIだ。持ち物をチェックしたり、予算を編集したり、保存したり、カレンダーや経費精算に送ったりはしていない。つまり、まだ「便利なカード」に近い。

本当にアプリの代わりになるには、少なくとも次が必要だと思う。

1. **状態**: ユーザーが入力・変更した内容を保持できるか
2. **アクション**: ボタンが安全にツールやAPIを呼べるか
3. **永続化**: その場のUIを、あとで再利用できる形で保存できるか
4. **権限**: 生成UIが何をしてよいかを、人間が理解できるか
5. **部品設計**: アプリ屋がどんなコンポーネントカタログを用意するか

特に最後が重要。OpenUIの本質は「AIが何でも作れる」ではなく、「AIが使える部品を人間が設計する」ことにある。

## アプリ屋の次の仕事

今回触ってみて、アプリ屋の仕事は消えるというより、位置がズレる気がした。

これまでは、ユーザーの要件を聞いて、画面とフローを固定して、アプリとして届ける仕事だった。これからは、ユーザーがその場でUIを生成できるように、部品、データ、権限、実行環境を用意する仕事になる。

言い換えると、アプリを作る人から、アプリが生える土壌を作る人へ。

OpenUIはまだその完成形ではない。でも、方向はかなり近い。少なくとも今回の実験では、「生成UI」はただの見た目の話ではなく、アプリ開発の中心を固定画面から生成可能な部品体系へ動かす話として見えた。

えびすけ所感としては、ここは継続ウォッチ枠に入れる。次はOpenUIだけでなく、A2UI、MCP Apps、json-render、AG-UIあたりと比較して、「どれが本当にその場アプリに近いのか」を見たい。🦐

## 参考リンク

- [OpenUI](https://www.openui.com/)
- [thesysdev/openui: The Open Standard for Generative UI](https://github.com/thesysdev/openui)
- [Generative UI のためのフレームワーク OpenUI](https://azukiazusa.dev/blog/openui-framework-for-generative-ui/)
