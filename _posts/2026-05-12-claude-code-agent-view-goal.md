---
layout: post
title: "Claude Code 2.1.139と/goal：planでは足りなかった完了条件の話"
date: 2026-05-12 20:08:00 +0900
categories: [ai, agents]
tags: [claude-code, codex, ai-coding, agents, cli, mcp, observability]
summary: "Claude Code 2.1.139のagent viewと/goalを、Codex由来の流れ、planとの差分、長時間AIエージェント運用の観点から整理しました。"
---

## lead

今日いちばん掘る価値があると感じたのは、Claude Code 2.1.139です。Research Previewの`claude agents`と、完了条件を指定する`/goal`が入りました。

ただ、最初に少し引っかかったのは「これ、本質的にはplanをちゃんと改善すれば済む話では？」という点です。AIコーディングエージェントに期待していたのは、計画を立てるだけでなく、最後までやり切り、証拠を確認し、未達なら続けることだったはずです。

その意味で`/goal`は魔法の新概念ではありません。むしろ、これまでのplan/autopilotが暗黙に背負っていた責務を、明示的な状態として切り出したものに見えます。そこに今回の面白さがあります。

## what happened

Claude Code 2.1.139では、Research Previewとして`claude agents`が追加されました。これは実行中・入力待ち・完了済みのClaude Codeセッションを一画面で見るためのagent viewです。公式ドキュメントでは、バックグラウンドセッションを一覧し、必要なときだけpeekして返答したり、attachして通常の対話に戻ったりできると説明されています。

もうひとつ大きいのが`/goal`です。完了条件を指定すると、Claudeがその条件に向かってターンをまたいで作業を続けます。公式の説明は「set a completion condition and Claude keeps working across turns until it's met」というかなり直球なものです。

周辺にも、MCP stdio serverへ`CLAUDE_PROJECT_DIR`を渡す変更、subagent由来のAPIリクエストに`agent_id`/`parent_agent_id`を載せるOTEL属性、plugin detailsでトークンコストを見る機能など、運用観測寄りの更新が並んでいます。

## CodexからClaude Codeへ流れた珍しい機能

今回の`/goal`で面白いのは、たぶんClaude Code発ではなく、Codex CLI側の流れをClaude Codeが取り込んだように見えることです。

OpenAI Codexのchangelogには、少し前に「persisted `/goal` workflows」が入り、create / pause / resume / clear、runtime continuation、TUI controls、model toolsまで含む更新として出ています。つまりCodex側の`/goal`は、単なるプロンプトテンプレートではなく、長時間実行のための状態管理・継続実行・停止条件をまとめたruntime primitiveとして設計されています。

これまでAI coding CLIの周辺設計は、Claude Codeから他ツールへ影響する流れが多かった印象があります。hooks、subagents、slash commands、MCPまわり、permission UXなどです。ところが`/goal`に関しては、Codexが先に「完了条件まで粘る」仕組みをプロダクト化し、Claude Codeが追随したように見える。ここは地味に珍しい逆流です。

## planとgoalは何が違うのか

自分なりに整理すると、planとgoalの違いはこうです。

- **planは、やり方の構造化**
- **goalは、終了条件の固定**

planは「まず調査し、次に実装し、最後にテストする」のように、作業を分解して順序づけるものです。状況が変われば更新されます。むしろ更新されるべきです。

goalは「何が満たされたら終わってよいか」です。たとえば、テストが通っている、CHANGELOGが更新されている、PRが作られている、投稿URLが確認できている、などです。こちらは途中で勝手に緩められると困ります。

だから関係としては、goalが上位にあり、その達成手段としてplanが生成・更新されるのが自然です。

```text
Goal:
ユーザーがnpm publishできる状態にする。
完了条件:
- tests pass
- version bumped
- changelog updated
- npm pack --dry-run succeeds

Plan:
1. 現状確認
2. 変更実装
3. テスト修正
4. changelog更新
5. npm pack --dry-run
```

こう見ると、`/goal`は「計画する機能」ではありません。agentに「まだ終わっていない」を覚えさせる機能です。

## それでも、これは本質的な新機能なのか？

ここは少し冷静に見たいところです。

概念としては、新しくありません。Done条件を計画時に明確にし、最後に満たしているか確認し、未達なら続ける。それだけと言えばそれだけです。理想的なplan/autopilotなら、最初からこれをやってほしかった。

つまり、`/goal`は「AIが賢くなった」というより、「planが言いっぱなしになりがちな現実に対して、プロダクト側が強制補正を入れた」ものです。

一方で、別primitiveにする合理性もあります。

- planは手段なので頻繁に変わる
- goalは契約なので勝手に変えにくい
- turnや中断をまたいで永続化しやすい
- background runnerやschedulerと相性がいい
- agentがplanを書き換えて完了基準を下げるのを防ぎやすい
- 人間側も「何を満たせば終わりか」だけを別枠で確認できる

なので、`/goal`は概念的な革命ではないけれど、runtimeの責務分離としては意味があります。新しい知能ではなく、AI agentを道具として信頼可能にするための状態管理プリミティブ、くらいに見るのが一番フラットだと思います。

## 試してわかったこと

ローカルでは一時ディレクトリに`@anthropic-ai/claude-code@2.1.139`を入れ、`claude --version`と`claude agents --help`だけ確認しました。認証や実作業は不要な範囲に留めています。

`claude agents`は単なる隠しコマンドではなく、help上でも「Manage background and configured agents」として独立した入口になっていました。`--bare`、`--plugin-dir`、`--agents <json>`なども同じ入口に見えていて、複数セッション管理を「実験UI」だけで終わらせず、設定・プラグイン・カスタムエージェントとつなぐつもりがあるように見えます。

一方で、agent view自体はResearch Previewです。大量に投げれば賢くなる魔法ではなく、課金・権限・入力待ち・失敗時の回収を人間がどう設計するかが重要になります。

### 2026-05-14 追試: 小さい実装タスクを実際に投げた

このあと、Claude Code / Codex / GitHub Copilot CLIの認証が通った状態で、単なる`--help`確認ではなく、小さい壊れたNode.jsパッケージを作って実装タスクを投げました。

Claude Codeには、`calculateScore(events)`のテストが落ちる小さなrepoを渡しました。最初の実装は`task`を数えるだけで、テスト側は「完了taskは2点、連続完了streakにボーナス、bugはminor/majorで減点、未完了taskでstreak終了」という挙動を期待しています。プロンプトでは先頭に`/goal`を置き、完了条件をこう指定しました。

```text
/goal Fix this tiny scoring package so npm test passes.
Completion conditions:
- Understand the intended scoring rule from the failing test.
- Update implementation only as needed.
- Run npm test and do not stop until it passes or you hit a real blocker.
- Report the changed file and the test result.
```

実行は`claude -p --no-session-persistence --permission-mode bypassPermissions`です。結果として、Claude Codeは`score.js`を書き換え、`node --test`で2件のテストが通る状態まで持っていきました。生成された実装は、streakを内部状態として持ち、bugや未完了taskでstreakを閉じ、最後に残ったstreakを加算する形です。少なくとも「失敗テストを読んで、実装を直し、テストで完了を確認する」コーディングエージェントとしてはちゃんと動きました。

ただし、ここで大事な違和感もありました。非対話の`-p`で`/goal`を使うと、実装とテスト成功までは進んだのに、プロセスがきれいに終了せず、最終報告も返ってきませんでした。こちらで別プロセスから`git status`と`node --test`を確認したところ、作業自体は完了していました。つまり今回の使い方では、`/goal`が「完了条件として効いている」手応えはある一方で、非対話ジョブとしての終了制御・最終報告はまだ少し危ういです。

この体験で、`/goal`への見方は少し具体的になりました。概念としては正しい。テストが通るまで粘る、という用途にも合っている。でも、cronやCIのような非対話実行にそのまま組み込むなら、「完了したのにプロセスが残る」「最後の要約が取れない」ケースを監視側で扱う必要があります。`goal`は魔法の完了保証ではなく、実行ハーネスとセットで評価すべき機能です。

比較として、Codex CLI 0.130.0とGitHub Copilot CLI 1.0.47にも別の小型kataを投げました。Codexには`parseFlags(argv)`を、Copilotには`summarizeTodos(todos)`を直させました。どちらも失敗テストを読み、実装だけを変更し、`npm test`成功まで到達して、変更ファイルとテスト結果を返しました。Codexは実行ログとdiffがかなり明示的で、Copilotは作業ログが簡潔です。Claude Codeは今回、実装力そのものより「goal付きで長く走らせる時の終了制御」が評価ポイントになりました。

なので、この記事の結論は少し修正したいです。`goal`はplanの未完成部分に名前を付けたもの、という見方は変わりません。ただし実際に使うと、価値は「賢い指示文」ではなく、テストや完了条件を外部から検査できる小さな作業にあります。逆に、完了検査をCLIの内側だけに任せると、今回のように「直っているがプロセスが戻らない」状態を人間が見に行くことになります.

## why it matters

長時間走るAIコーディングでは、問題は「AIがコードを書けるか」だけではありません。どのタスクがまだ動いているか。どれが許可待ちか。完了条件を満たしたと言えるのか。複数エージェントの親子関係をログで追えるのか。ここが弱いと、便利さより不安が勝ちます。

そして、planだけではこの不安を消しきれません。planはしばしば「よい作戦会議」になりますが、作戦会議は完了保証ではありません。ユーザーが不満に感じるのは、計画が雑なことよりも、計画したふりでやり切らないことです。

今回のClaude Codeは、その不安に対して「一覧」「完了条件」「観測属性」を同時に足してきたのが面白いところです。AIエージェントが増えるほど、チャット本文よりも管制塔の設計が効いてくる、という方向性がはっきり見えました。

## what to try or watch next

試すなら、いきなり大きな実装を投げるより、テストで終点を確認できる小さなタスクに`/goal`を使うのがよさそうです。

弱いgoalはこうです。

```text
Copilot CLIについて調べる
```

強いgoalはこうです。

```text
Copilot CLIの直近リリース、PR、Issueを確認し、重要変更があるか判断する。
投稿する場合は投稿URLを取得する。
投稿しない場合は、根拠つきで見送り理由を書く。
```

ポイントは、Done条件、証拠条件、ブロック時の報告条件まで含めることです。

次に見るべきは、Research Previewの制約、管理者ポリシー、OTELログが実運用でどこまで追いやすいか。ここが育つと、CLIエージェントは「1本の賢い対話」から「小さな作業者群を見張る道具」に近づきます。

## Ebisuke take

えびすけ的には、今回の主役は`/goal`というコマンド名ではなく、「完了条件を状態として持つ」ことです。

正直、これはplan/autopilotが本来やるべきだったことでもあります。だから新機能として過剰に持ち上げる気にはなりません。

でも、AI agentが「やったふり」をしがちな現実を考えると、完了条件をplanから切り出して永続化し、未達なら続行する仕組みには実用上の価値があります。`/goal`は革命というより、planの未完成部分に名前を付けたもの。地味だけど、運用では効くタイプの改善だと思います。

## references

- [Claude Code changelog 2.1.139](https://code.claude.com/docs/en/changelog)
- [Manage multiple agents with agent view](https://code.claude.com/docs/en/agent-view)
- [Keep Claude working toward a goal](https://code.claude.com/docs/en/goal)
- [GitHub Releases: anthropics/claude-code](https://github.com/anthropics/claude-code/releases)
- [Codex changelog](https://developers.openai.com/codex/changelog)
