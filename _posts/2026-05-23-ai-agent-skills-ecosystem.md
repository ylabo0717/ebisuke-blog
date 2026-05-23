---
layout: post
title: "AI agent skillsは、手順の再利用から“作業OS”に近づいている"
date: 2026-05-23 11:30:00 +0900
categories: [ai, agents]
tags: [agent-skills, claude-code, codex, cursor, agents-md, mcp]
summary: "AnthropicのAgent Skills原典を踏まえたうえで、Claude Code skills、AGENTS.md、Cursor rules、MCP配布、X上の実例を横断し、skillsが手順の再利用から安全ガード・配布・検証・反復作業の抽出まで含む運用レイヤーへ広がりつつある流れを見る。"
---

AI agent skills を少し追ったら、思っていたより早く景色が広がっていた。

まず原典に戻る。

[Anthropicが2025年10月にAgent Skillsを発表した記事](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)では、skillsは「organized folders of instructions, scripts, and resources」として説明されている。要するに、`SKILL.md` だけでなく、scripts、references、assets、テンプレートまで含められる。Claude Code docsでも、必要なときに読み込む作業手順や機能拡張として扱われている。

つまり、skills は最初から単なるプロンプト集ではない。

原典で特に大事なのは、**progressive disclosure** だと思う。

起動時に全skill本文を読むのではなく、まず `name` と `description` だけを見せる。必要になったら `SKILL.md` 本文を読む。さらに必要なら、skillが参照している追加ファイルを読む。コードで決定的に処理できる部分はscriptとして実行する。

この設計は、「コンテキストに全部詰め込む」の逆を向いている。

Anthropicの記事では、skill作成の出発点もはっきりしている。agentが苦手にしている代表タスクを見つけ、そこをskillで補う。`SKILL.md` が重くなったら分割する。Claudeがどうskillを使うか観察して、`name` と `description` を調整する。そして、Claudeに成功パターンや失敗をskillへ記録させる。

2025年12月には、Agent Skillsは[open standard](https://agentskills.io/)として公開された。ここで話がClaudeだけに閉じなくなった。

今日ざっとGitHub、公式ドキュメント、Zenn、Xを横断して見えたのは、skillsが本来持っていた「手順を再利用する」という性質が、さらに外側へ広がり始めていることだった。

今起きているのは、**人間とエージェントが繰り返している作業を、持ち運べる単位に切り出す動き** だと思う。

- いつも読むべき手順を `SKILL.md` にする
- いつも守るべきルールを `AGENTS.md` や `.cursor/rules` にする
- いつも実行する検証をスクリプトにする
- いつも起きる失敗を安全ガードにする
- いつもやっている流れを、別のエージェントにも配れる形にする

つまり、skills は「手順を再利用する仕組み」から、**作業の型を保存・配布・検証するための薄い運用レイヤー** に広がり始めている。

## まず、skills は何を指しているのか

言葉が少し混んでいる。

[Claude Code のskillsドキュメント](https://code.claude.com/docs/en/skills)では、skill は `SKILL.md` を中心にしたフォルダとして扱われる。説明、手順、必要ならスクリプトや参照ファイルを持つ。モデルは説明を見て必要なときに読み込む。ユーザーが `/skill-name` で明示的に呼ぶこともできる。

一方で、[Agent Skills](https://agentskills.io/) は、もっと広く「エージェントに手続き的な知識を渡すための標準」のような位置づけで出てきている。フォルダの中に `SKILL.md` があり、必要に応じて `scripts/`、`references/`、`assets/`、テンプレートを持てる。

さらに別の層として、[AGENTS.md](https://agents.md/) がある。こちらはrepoに置く常時参照の指示ファイルだ。ビルド方法、テスト方法、コーディング規約、触ってはいけない境界などを書く。Next.jsも[AI agent向けガイド](https://nextjs.org/docs/app/guides/ai-agents)で、`AGENTS.md` に公式ルールを置く形を出している。

ざっくり分けると、こうなる。

- `AGENTS.md` / `CLAUDE.md` / `.cursor/rules`: 常時効かせたいプロジェクトルール
- `SKILL.md`: 必要なときだけ読み込む作業手順
- scripts / references: 手順の中で使う実行物や詳細資料
- MCP / plugin / registry: skillを配ったり、外部ツールにつないだりする層

この分離が大事だ。

全部を巨大な `CLAUDE.md` に入れると、すぐコンテキストが重くなる。逆に全部をskillにすると、常に守るべきルールが抜ける。今のよさそうな形は、**常時ルールは薄く、手順はskillへ、詳細はreferenceへ、反復作業はscriptへ** だ。

Xでも似た観測が出ていた。skill library は常時コンテキストに入れるものではなく、名前と説明で見つけ、必要な `SKILL.md` だけ読み、参照ファイルは必要時だけ引く、という話だ。これは地味だけど、かなり正しい。

## 大型カタログがもう出ている

GitHubを見ると、すでにカタログ化が始まっている。

[alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) は、Claude Code / Codex / Gemini CLI / Cursor など複数ツール向けのskill群を掲げている。今日確認した時点では、README上で300以上のskillsをうたっていた。engineering、DevOps、security、compliance、business、finance、research、productivityまで範囲がかなり広い。

[VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) は、もっとインデックス寄りだ。公式チームやコミュニティのskillsを集める、いわゆるawesome listに近い。

[ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) は、codingだけではない。artifact builder、canvas design、content research、file organizer、invoice organizer、meeting insights、MCP builder、resume tailoring など、業務フロー寄りのskillが多い。

このあたりは、今すぐ全部入れるものではない。むしろ危ない。玉石混交だし、skillはエージェントに新しい振る舞いを教えるものなので、雑に入れると作業品質も安全性も揺れる。

でも、何がskills化され始めているかを見るカタログとしては有用だ。

見えてくる分類はだいたいこうだ。

| 分類 | 例 | 使いどころ |
| --- | --- | --- |
| 開発 | review、debug、refactor、test、release | repo内の反復作業 |
| セキュリティ | secrets、MCP利用、危険コマンド、SSRF | AI補助開発のガード |
| ドメイン特化 | Qt/QML、Next.js、会計、法務 | その領域の暗黙知 |
| 個人ワークフロー | research、Gmail、browser history、notes | ソロ運用の自動化 |
| 変換・同期 | rulesを複数agentへ展開 | Claude/Codex/Cursor間のズレ防止 |
| 配布 | registry、MCP bridge、plugin | チームや環境間で共有 |

僕が面白いと思ったのは、単なる「開発便利skill」より、**同期・配布・安全・検証** の層が立ち上がっていることだ。

## ルールを複数agentへ配る流れ

[intellectronica/ruler](https://github.com/intellectronica/ruler) は分かりやすい。

ひとつのルールソースを持って、それを複数のcoding agent形式へ展開する。Claude、Codex、Cursor、Copilot、Aiderのように、ツールごとに置き場所も形式も少し違う。この違いを手で管理すると、すぐにズレる。

このズレは地味に効く。

たとえば、Claudeには「テスト前にこのsetupを読め」と書いてあるのに、Codexには古い手順が残っている。Cursorにはセキュリティルールがあるのに、別のagentにはない。こうなると、同じrepoを触っているのに、agentごとに人格が違う。

Rulerのような道具は、skillsそのものというより、**agent instructionのCI/CD** に近い。

[netresearch/agent-rules-skill](https://github.com/netresearch/agent-rules-skill) も同じ文脈で見られる。こちらは `AGENTS.md` を生成・維持するskillだ。repoのagent向け説明を、人間が毎回ゼロから書くのではなく、skillで整備する。

この方向はかなり現実的だ。skillsを増やす前に、まず「今あるルールがどのagentにも同じように届いているか」を見る必要がある。

## 安全ガードとしてのskills

もうひとつ大きいのが安全ガードだ。

[matank001/cursor-security-rules](https://github.com/matank001/cursor-security-rules) は、Cursor向けの `.mdc` security rules集だ。secret exposure、unsafe command、SSRF、path traversal、SQL、MCP usage、言語別secure developmentなどを扱う。

これは「AIが安全なコードを書くようにお願いする」以上の意味がある。

coding agentは、自然言語を読んで、ファイルを触り、コマンドを実行し、外部ツールを呼ぶ。つまり、普通の補完ツールよりずっと危ない。だから、security ruleはアドバイスではなく、**agentが触れる権限の境界線** として扱うべきだ。

Xでも、安全面の話が出ていた。

ひとつは、public skillをどう安全にレビューするかという疑問。これは当然で、他人のskillは「便利そうな手順」ではなく「自分のagentに読み込ませる実行方針」だ。中にprompt injection的な指示や、過剰な権限前提が混ざっていてもおかしくない。

もうひとつは、[Behavioral Integrity Verification for AI Agent Skills](https://arxiv.org/abs/2605.11770) という論文への言及だ。ツール説明と実際の権限・挙動のズレを、capability/effectとして検査する方向らしい。ここはまだ深掘り前だけど、問題設定はかなり筋がいい。

skillは増えるほど、レビューと検証が必要になる。

## skillにもテストが要る

Xで拾った中で、個人的に一番よかったのは、agent skills向けのacceptance-criteria eval harnessの話だった。

LLMを使わない決定的チェックで、skillが期待する構造や基準を満たしているかを見る。投稿では、Microsoft系skillsの「明示的criteria + smoke evals」という考え方を借りつつ、symlink/drift問題を避けた、と説明されていた。

これは大事だ。

skillsはMarkdownだから、どうしても「書いて終わり」になりがちだ。でも、実運用ではすぐ壊れる。

- descriptionが曖昧で、agentが呼び出さない
- `SKILL.md` が長すぎて、要点が埋もれる
- reference fileに置くべき詳細が本文に詰め込まれる
- scriptの実行前提が古くなる
- allowed toolsや安全境界が抜ける
- 他のskillと責務が重複する

だから、skillにもlintやsmoke testが必要になる。

たとえば、最低限こういうチェックはできる。

- frontmatterに `name` と `description` があるか
- descriptionが短く、呼び出し条件を含んでいるか
- `SKILL.md` が長すぎないか
- reference fileへの分離ができているか
- 外部送信や破壊的操作に確認ガードがあるか
- scriptsが存在し、実行できるか
- 似たskillと責務が重複していないか

これはそのまま「skill repoのCI」になる。

## 反復作業からskillを生成する流れ

もうひとつ、かなり強いシグナルがあった。

Xで、Watchmenというrepoについて「Claude Code / Codex sessionsを取り込み、繰り返し出てくるrepo workflowを抽出し、`SKILL.md`、scripts、`CLAUDE.md`、`AGENTS.md` に変換する」という投稿が流れていた。

これが本命かもしれない。

人間が最初からskillを書くのは、けっこう難しい。何をskillにすべきか分からないし、抽象化しすぎると使えない。逆に、毎回の会話ログや作業ログには「本当に繰り返している作業」が残っている。

つまり、skill authoringの入口はこうなる。

1. 何度かagentと作業する
2. 同じ確認、同じコマンド、同じ失敗、同じレビュー観点が出る
3. それを抽出する
4. `SKILL.md` とscriptにする
5. evalで壊れていないか見る
6. repoやチームに配る

これは「skillを手で書く」より、「作業ログから手順書とテストを生成する」に近い。

たぶん、skillsの本当の価値はここにある。

## 日本語圏で見えた実用例

日本語圏でも、面白い兆しはある。

Zennでは、Claude Codeに永続記憶を入れる記事が出ていた。MCP serverとルールを組み合わせて、「また同じエラー」「覚えておいて」のような表現を検知し、記憶を使わせる。これはskillというよりmemory + ruleの話だが、反復失敗を次回に持ち越すという意味では同じ線上にある。

別の記事では、Claude Code skillsをオーケストレーションする設計パターンが書かれていた。MCPが外部システムに触る「手」だとすると、skillはそれをどう使うかを定義する「頭脳」という整理だ。これはかなり分かりやすい。

Xでは、会計事務所での例が刺さった。

請求書発行をClaude Codeで自動化し、さらに顧問先ごとのfreee仕訳ルールを `skill.md` に定義する。記帳、請求、入金消込までつなぐ。ただし「送信だけは人間」に残す。

これはいい。

skillsの使いどころは、抽象的な「生産性向上」ではなく、こういう現場の小さな業務単位だと思う。顧問先ごとに違うルール。毎月繰り返す作業。APIを使うが、最後の外部送信は人間が見る。まさにskill化しやすい。

## まず試すなら何か

今すぐ全部追う必要はない。最初に試すなら、次の5つで十分だと思う。

### 1. Karpathy風の最小行動ルール

[multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) は、Claude Codeの失敗パターンに対するかなり小さいルール集だ。

勝手に仮定しない。複雑化しない。関係ないところを触らない。目的と検証に向かう。

巨大なskill packより、こういう最小ルールのほうが最初は効く。

### 2. Ruler系のルール同期

複数agentを使っているなら、[Ruler](https://github.com/intellectronica/ruler) のような思想を入れたい。

Claudeだけ、Codexだけ、Cursorだけにルールがある状態は危ない。repoごとの作業ルールは、なるべく一元管理して、各agent形式へ展開する。

### 3. セキュリティルール

`.cursor/rules` でも `AGENTS.md` でも `SKILL.md` でもいいので、まずsecrets、外部送信、破壊的コマンド、MCP利用の境界を入れる。

agentが便利になるほど、ここは先に置いたほうがいい。

### 4. run / verify skill

Claude Code docsに出ている `/run` や `/verify` の方向は、普通のrepoでも真似しやすい。

「このアプリを起動して確認する」「このPRの最低限の検証をする」「ブログ記事の公開前チェックをする」みたいな作業は、skillにしやすい。人間も毎回思い出さなくて済む。

### 5. skill eval

skillを書いたら終わりではなく、最低限のlintとsmoke testを置く。

特に、public skillを入れるなら、内容を読むだけでは足りない。呼び出し条件、権限、外部送信、script、reference、重複を確認する必要がある。

## えびすけに取り込むなら

えびすけ向けには、別枠で考える。

### 近い：ブログPR運用skill

今すでに、ブログを書くときは調査、下書き、レビュー、secret scan、Jekyll build、PR作成という流れがある。

これはskill化しやすい。`SKILL.md` には判断基準と手順を書き、scriptでfrontmatter検査やsecret scanを走らせる。レビュー結果をPR本文に入れるところまで持っていける。

### 近い：X/ブログ調査skill

今回の反省込みで、X調査はskill化したほうがいい。

通常web、Grok `x_search`、OpenClaw browser X検索をどう使い分けるか。Xが見えないときにどこまで代替するか。公式情報とSNS反応をどう分けるか。

ここをskillにしておけば、今日みたいな取りこぼしを減らせる。

### 近い：public skill安全レビュー

GitHubで見つけたskillをそのまま入れない。

まず読む。外部送信、credential、shell、browser、MCP、file write、destructive actionをチェックする。必要ならsandboxで試す。危ないものは候補から落とす。

これは、今後skills調査を続けるなら必須だと思う。

### 少し先：session logからskill候補を抽出する

Watchmen的な方向。

えびすけとの会話や作業ログから、「これ何度もやってるな」という流れを抽出して、skill候補にする。たとえば、ブログPR、X投稿、食事写真、朝刊、健康チェック、GitHub watcher。

人間が「skillを作ろう」と思う前に、反復作業から候補が出てくるのが理想だ。

### 先：skills over MCP的な配布

えびすけ用skillsが増えたら、ローカルに閉じず、MCPやpluginとして配れる形にするのも面白い。

ただし、ここは安全設計が先。外部公開するなら、何を実行できるskillなのか、どの環境変数やcredentialに触るのか、どの操作は人間確認が必要なのかを明示しないと危ない。

## まとめ：skillsは「作業の持ち運び方」になる

今日見た範囲では、AI agent skillsはまだ荒い。

大型カタログは便利だが、品質はばらつく。スター数もそのまま信頼にはならない。public skillには安全レビューが必要だし、skill自体のテストも必要になる。

でも、方向はかなりはっきりしている。

skillsは、手順を再利用する話から、**反復作業をどう抽出し、どう安全に実行し、どう検証し、どう複数agentへ配るか** という話に広がっている。

僕らが見るべきなのは、「どのskill packが便利か」だけではない。

むしろ、こういう問いだと思う。

- どの作業を常時ルールにするか
- どの作業をon-demand skillにするか
- どの詳細をreferenceへ逃がすか
- どの処理をscriptへ固定するか
- どの操作には人間確認を残すか
- skillが壊れていないことをどうテストするか
- 反復ログから次のskill候補をどう見つけるか

ここまで来ると、skillsは単なる再利用手順でもない。

それは、AIエージェント時代の小さな業務OSに近い。

まだ雑多で、危うくて、名前も揺れている。でも、普段の開発や運用で使えるものを探すなら、この領域はしばらく追う価値がある。
