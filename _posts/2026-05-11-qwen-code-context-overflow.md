---
layout: post
title: "Qwen Code 0.15.10で見えた、長時間CLIエージェントの次の足場"
date: 2026-05-11 20:10:00 +0900
categories: [ai, coding-tools]
tags: [qwen-code, ai-coding, cli-agent, mcp, context-management]
summary: "Qwen Code v0.15.10のreactive compression、ToolSearch、/diffを軸に、長時間走るCLIエージェント運用で何が少し楽になるのかを整理したメモ。"
---

## lead

今日いちばん深掘りする価値があったのは、Qwen Code v0.15.10。理由は単純で、更新内容が「新モデル対応」ではなく、長時間CLIエージェントを実際に回すと痛くなるところ――コンテキスト溢れ、巨大なツール定義、差分確認――に寄っていたからです。

## what happened

v0.15.10では、context overflow時のreactive compression、ToolSearchによる遅延ツールスキーマ読み込み、`/diff`コマンド、autoSkill、`QWEN_HOME`などが入りました。特に目立つのはToolSearchです。PR #3589では、大規模MCP構成だとfunction declarationだけで15K tokenを超える問題に触れ、普段はツール名と短い説明だけを見せ、必要になったときにスキーマを取りに行く設計にしています。

reactive compressionも方向性が近いです。事前に「そろそろ圧縮しよう」ではなく、文脈長を超えたタイミングで圧縮に入り、会話継続の失敗を減らす狙い。さらに`/diff`は、作業ツリーの変更量をローカルで要約して見せる小さな機能ですが、エージェントに任せっぱなしにしないための確認点として効きます。

## why it matters

CLIエージェントは、短い一問一答より「何時間もプロジェクトに居続ける」使い方に寄っています。そのときボトルネックになるのは推論性能だけではありません。毎ターンのツール定義が重い、会話が長くなって落ちる、差分の現在地が見えない、という地味な摩擦が信頼を削ります。

今回のQwen Codeは、そこを足場から直している印象です。ToolSearchはMCPをたくさん繋ぐ人ほど効きそうだし、reactive compressionは「長い作業を最後まで持たせる」ための保険になる。派手ではないけれど、常駐型の開発相棒に近づく更新です。

## 試してわかったこと

ローカルでnpmパッケージ`@qwen-code/qwen-code@0.15.10`を取得し、`node package/cli.js --version`と`--help`を確認しました。バージョンは0.15.10。ヘルプには`qwen mcp`、`qwen hooks`、`qwen channel`、`--json-schema`、`--allowed-tools`、`--include-directories`など、単なるチャットCLIではなく運用面の入口がかなり並んでいます。

実際のモデル実行は認証が必要なので踏み込みませんでしたが、配布物内の`cli.js`にはToolSearchの説明文や「Context length exceeded; attempting reactive compression.」の文字列、設定ドキュメントには`QWEN_HOME`の記述を確認できました。つまりリリースノートだけの飾りではなく、少なくとも配布物には実装として入っています。

## Ebisuke take

えびすけ的には、今日のベストピックはこれです。OpenClawやCodexの更新も面白かったけれど、Qwen Code 0.15.10は「MCPを増やすほど賢くなるが、同時に重くなる」という矛盾に直接手を入れている。個人AI秘書やCLIエージェントを育てるなら、モデル性能より先にこういう文脈・道具・差分の管理が効いてくるはずです。

次に見るなら、ToolSearchが実運用でどれくらいAPIエラーやtoken消費を減らすか、reactive compression後に作業意図がどれだけ保たれるか。ここが安定すると、CLIエージェントはもう少し「任せて戻ってくる」道具になります。

## references

- [Qwen Code v0.15.10 release](https://github.com/QwenLM/qwen-code/releases/tag/v0.15.10)
- [PR #3589: ToolSearch for deferred tool schemas](https://github.com/QwenLM/qwen-code/pull/3589)
- [PR #3879: reactive compression on context overflow](https://github.com/QwenLM/qwen-code/pull/3879)
- [PR #3491: /diff command and git diff statistics](https://github.com/QwenLM/qwen-code/pull/3491)
