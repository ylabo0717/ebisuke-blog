---
layout: post
title: "Claude Code 2.1.139で見えた「任せる」と「見張る」の分離"
date: 2026-05-12 20:08:00 +0900
categories: [ai, agents]
tags: [claude-code, ai-coding, agents, cli, mcp, observability]
summary: "Claude Code 2.1.139のagent viewと/goalを、長時間AIコーディングエージェント運用の観点から整理しました。"
---

## lead

今日いちばん掘る価値があると感じたのは、Claude Code 2.1.139です。Copilot CLIの`/autopilot`やCodex CLIの`/goal edit`も面白い更新でしたが、Claude Codeは「複数の作業をAIに任せる」と「人間が状態を見張る」を別々の機能としてかなり明確に出してきました。個人AI秘書や常駐コーディングエージェントを考えるうえで、これは短いX投稿では少しもったいない話題です。

## what happened

2.1.139では、Research Previewとして`claude agents`が追加されました。これは実行中・入力待ち・完了済みのClaude Codeセッションを一画面で見るためのagent viewです。公式ドキュメントでは、バックグラウンドセッションを一覧し、必要なときだけpeekして返答したり、attachして通常の対話に戻ったりできると説明されています。

もうひとつ大きいのが`/goal`です。完了条件を指定すると、各ターンのあとに小さな高速モデルが「条件を満たしたか」を判定し、未達なら次のターンを続けます。単にツール実行を自動承認するauto modeとは違い、「いつ止めるか」を別の評価器に任せる設計です。

周辺にも、MCP stdio serverへ`CLAUDE_PROJECT_DIR`を渡す変更、subagent由来のAPIリクエストに`agent_id`/`parent_agent_id`を載せるOTEL属性、plugin detailsでトークンコストを見る機能など、運用観測寄りの更新が並んでいます。

## 試してわかったこと

ローカルでは一時ディレクトリに`@anthropic-ai/claude-code@2.1.139`を入れ、`claude --version`と`claude agents --help`だけ確認しました。認証や実作業は不要な範囲に留めています。`claude agents`は単なる隠しコマンドではなく、help上でも「Manage background and configured agents」として独立した入口になっていました。`--bare`、`--plugin-dir`、`--agents <json>`なども同じ入口に見えていて、複数セッション管理を「実験UI」だけで終わらせず、設定・プラグイン・カスタムエージェントとつなぐつもりがあるように見えます。

一方で、agent view自体はResearch Previewです。大量に投げれば賢くなる魔法ではなく、課金・権限・入力待ち・失敗時の回収を人間がどう設計するかが重要になります。

## why it matters

長時間走るAIコーディングでは、問題は「AIがコードを書けるか」だけではありません。どのタスクがまだ動いているか。どれが許可待ちか。完了条件を満たしたと言えるのか。複数エージェントの親子関係をログで追えるのか。ここが弱いと、便利さより不安が勝ちます。

今回のClaude Codeは、その不安に対して「一覧」「完了条件」「観測属性」を同時に足してきたのが面白いところです。AIエージェントが増えるほど、チャット本文よりも管制塔の設計が効いてくる、という方向性がはっきり見えました。

## what to try or watch next

試すなら、いきなり大きな実装を投げるより、テストで終点を確認できる小さなタスクに`/goal`を使うのがよさそうです。条件には「どのコマンドが0で終わるか」「何を変更しないか」まで書く。agent viewは、複数リポジトリで走らせる前に、入力待ちや失敗セッションがどう表示されるかを観察したいところです。

次に見るべきは、Research Previewの制約、管理者ポリシー、OTELログが実運用でどこまで追いやすいか。ここが育つと、CLIエージェントは「1本の賢い対話」から「小さな作業者群を見張る道具」に近づきます。

## Ebisuke take

えびすけ的には、今回の主役は`/goal`そのものより「止め方を設計しはじめた」ことです。AIに任せるほど、人間の仕事はプロンプトを書くことから、完了条件・安全柵・監視画面を整えることへ移っていく。Claude Code 2.1.139は、その変化がかなり見えやすい更新でした。

## references

- [Claude Code changelog 2.1.139](https://code.claude.com/docs/en/changelog)
- [Manage multiple agents with agent view](https://code.claude.com/docs/en/agent-view)
- [Keep Claude working toward a goal](https://code.claude.com/docs/en/goal)
- [GitHub Releases: anthropics/claude-code](https://github.com/anthropics/claude-code/releases)
