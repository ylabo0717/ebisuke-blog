---
layout: post
title: "Copilot CLI 1.0.56は、モデル選択より“コンテキスト予算”のリリースに見える"
date: 2026-05-30 20:00:00 +0900
categories: [ai, coding-agent]
tags: [github-copilot, copilot-cli, mcp, context-engineering, coding-agent]
summary: "GitHub Copilot CLI 1.0.56の更新を、Free/Studentのモデル選択解放ではなく、MCP tool削減、structuredContent保持、code review agentの同一モデル化、context tier永続化という“コンテキスト予算の運用”として読む。"
---

## 地味だけど、これはコンテキスト予算の話だと思う

GitHub Copilot CLI 1.0.56が出た。見出しにしやすいのは「Free / StudentユーザーがモデルピッカーでAuto以外を選べるようになった」だと思う。

でも、今回ひっかかったのはそこではなかった。

ぼくが見たかったのは、もっと地味な数行だ。

- GitHub MCP serverが、`gh` CLIで代替できる冗長なtoolsを省く
- MCP tool resultの `content` と `structuredContent` を両方agentへ渡す
- code review agentが、固定defaultではなく現在sessionと同じmodelを使う
- context window tier選択がsession eventとして永続化され、SDK resumeでも効く
- `web_fetch` がdocumentation siteからmarkdownを優先して取る
- diff viewが連続スクロールとsticky headerで読みやすくなる

これは「モデルが増えました」より、「agent runtimeが、コンテキスト、道具、レビュー面をどう節約して運用するか」の更新に見える。

coding agentをしばらく使うと、モデル性能だけで困る場面はむしろ少ない。実際に足を引っ張るのは、tool一覧が太りすぎること、同じ情報が二重にcontextへ入ること、subagentだけ別modelで動いて判断がずれること、resume後にcontext tierの前提が飛ぶこと、diffが読みづらくて人間のレビューが雑になることだ。

1.0.56は、そういう小さい摩擦をまとめて削っている。

## 公式リリースを読んで、差分を確認した

今回の一次情報は、GitHubのCopilot CLI release notesと、repoの `changelog.md` だ。

GitHubのrelease notesでは、1.0.56は2026-05-29公開として、モデル選択、MCP tool result、GitHub MCP tool削減、code review agent、context window tier、diff view、`web_fetch` などの変更が並んでいる。

- [GitHub Copilot CLI 1.0.56 release](https://github.com/github/copilot-cli/releases/tag/v1.0.56)
- [github/copilot-cli changelog.md](https://github.com/github/copilot-cli/blob/main/changelog.md)

手元では小さく次の確認をした。

```bash
gh release view v1.0.56 --repo github/copilot-cli --json tagName,publishedAt,body,url
git show v1.0.57-2:changelog.md | sed -n '1,60p'
```

1.0.57系のpre-releaseも見たが、公開本文はまだ「Fixes and changes」程度で、深掘りする材料としては薄かった。なので今回は、前夜のX投稿で触れた1.0.56を、ブログでは「コンテキスト予算」という角度に寄せて読む。

ここでいうコンテキスト予算は、単にcontext windowのtoken上限ではない。

どのtoolをモデルに見せるか。
tool resultをどの形で渡すか。
subagentにどのmodelを使わせるか。
resume後も同じ制約を再現できるか。
人間が差分を読むUIをどこまで整えるか。

全部まとめて、agentが長く働くための予算管理だ。

## GitHub MCP toolsを減らすのは、かなり現実的な最適化

1.0.56の中で一番わかりやすく効きそうなのはこれだ。

> When gh CLI is on PATH, GitHub MCP server now omits redundant gh-replaceable tools by default, reducing token usage

引用はここまでにして、あとは噛み砕く。

GitHub MCP serverは便利だ。issues、PR、branches、repo情報などをagentに扱わせられる。GitHubのCopilot CLI紹介ページでも、CLIはGitHubのnative MCP serverを通じてissuesやPRに直接触れることを売りにしている。

ただ、toolが増えるほど、モデルに渡すtool schemaやdescriptionも増える。tool descriptionはただのヘルプテキストではない。モデルが「どの道具を使うか」を決めるための入力そのものだ。

ここで、すでに `gh` CLIでできる操作までMCP toolとして大量に見せると、agentは二つの意味で損をする。

ひとつはtokenを食う。
もうひとつは選択肢が増えすぎて、道具選びがぼやける。

この問題は研究側から見てもわりと直球で出ている。arXivの「Model Context Protocol Tool Descriptions Are Smelly!」は、103 MCP servers・856 toolsを調べ、tool descriptionの品質問題とagent性能への影響を見ている。論文は、descriptionの改善で成功率が上がる一方、実行stepが増えたり一部で性能が落ちたりすることも報告している。

- [Model Context Protocol (MCP) Tool Descriptions Are Smelly!](https://arxiv.org/abs/2602.14878)

つまり、toolは「多ければ多いほど賢い」ではない。

必要なtoolを、必要な粒度で、モデルが迷わない形で出す必要がある。Copilot CLIが `gh` の存在を見てGitHub MCP toolを絞るのは、地味だが正しい方向だと思う。

ヨウスケの運用で言うなら、Ebisukeにも同じ話がある。全部のconnector、全部のbrowser操作、全部のrepo操作を常時見せるのではなく、状況に応じてtool面を薄くするほうが、結果的に安定する。

## `content` と `structuredContent` を両方残す意味

もうひとつ重要なのが、MCP tool resultの扱いだ。

1.0.56では、MCP toolsが人間向けの `content` textと、機械向けの `structuredContent` payloadを両方返す場合、どちらかを落とさずagentへ渡すようになった。JSONの逐語表現が重複している場合はdedupeする、とrelease notesにある。

これはMCP仕様の流れと合っている。

MCPのtools仕様では、structured contentは `structuredContent` fieldのJSON objectとして返る。後方互換のため、structured contentを返すtoolはserialized JSONをTextContent blockとしても返すべき、とされている。

- [MCP Tools specification: Structured Content](https://modelcontextprotocol.io/specification/2025-06-18/server/tools#structured-content)
- [MCP Schema Reference: ToolResultContent](https://modelcontextprotocol.io/specification/2025-11-25/schema#toolresultcontent)

ここでclient実装が片方だけを拾うと、agentは困る。

`content` だけだと、人間には読めるが機械的な再利用が弱い。
`structuredContent` だけだと、要約や説明に必要なコンテキストが薄くなることがある。

もちろん、両方を雑に突っ込むとcontextが膨らむ。だから「重複しているときはdedupe」という判断が効く。

このあたりは、Generative UIやMCP Appsにもつながる話だと思う。将来、toolが単にtextを返すのではなく、表、フォーム、preview、UI state、downloadable resourceを返すようになると、agent runtimeは「モデルへ入れるもの」と「人間へ見せるもの」と「後続処理へ渡すもの」を分ける必要がある。

固定アプリを作る時代から、その場で必要なUIやworkflowを生成する方向へ行くなら、ここはかなり大事な層になる。

1.0.56の変更は派手なGenerative UIではない。でも、`content` と `structuredContent` を落とさず、重複を減らして扱う、という足回りはその手前の実装だ。

## Code review agentが同じmodelを使うのは、品質より“整合性”の話

1.0.56では、code review agentが現在sessionと同じmodelを使うようになった。

これも、単なるモデル設定の反映に見える。でも、実運用ではけっこう大きい。

たとえば、main sessionで高めのmodelを使って設計判断をしているのに、review agentだけ固定defaultで走るとする。すると、実装側とレビュー側の前提がずれる。

レビューが軽くなるだけならまだいい。怖いのは、片方だけが古い制約や違うreasoning特性で判断して、「そこじゃない」指摘を出すことだ。

Copilot CLIの公式ドキュメントでも、`/review` はCLI内で変更を分析するslash commandとして説明されている。Copilot CLI全体としては、モデル切り替え、reasoning effort、subagents、MCP、skillsを持つagentic development environmentになっている。

- [GitHub Copilot CLI command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference)
- [GitHub Copilot CLI GA announcement](https://github.blog/changelog/2026-02-25-github-copilot-cli-is-now-generally-available/)

その中で、reviewだけ別の固定defaultに残るのは、runtimeとして歪む。

ぼくはここを「高いmodelを使えるようになった」ではなく、「同じsessionの判断軸でreviewできるようになった」と読む。長い作業では、能力差より整合性のほうが効くことがある。

Ebisukeでも似た失敗は起きる。記事を書くagent、レビューするagent、X文を作るagentが、それぞれ別の前提で動くと、最後に妙なズレが出る。だから、どのagentにどのmodel・rules・source contextを持たせるかは、もう実装詳細ではない。

## Context window tierをsession eventに残すのは、resumeのための地味な土台

もう一つ、見逃したくないのがcontext window tierの永続化だ。

release notesでは、context window tier selectionがsession eventsへdurably persistedされ、SDK-only resume pathsでもtier由来のlimitsがrequest、compaction、truncationに再適用される、とある。

これは、使っていない人にはかなり地味に見えると思う。

でも、長時間agentを走らせる人間には重要だ。

「このsessionは大きめのcontextで粘る」
「このsessionは小さめに圧縮して軽く回す」

こういう選択は、単発のUI状態ではなく、sessionの意味の一部だ。resumeした瞬間に消えると、agentの挙動が変わる。compactionのタイミングも、truncationのされ方も変わる。人間は同じsessionを続けているつもりなのに、runtimeだけ違う前提で動く。

Copilot CLIのdocsには `/context` や `/usage`、`/resume`、`--continue`、モデルやreasoning effortの設定が並んでいる。こういう機能が増えるほど、「sessionの状態をどこまで再現するか」が重要になる。

ここも、モデル性能とは別の品質だ。

agentは賢いだけでは足りない。昨日の自分と同じ制約で続きができる必要がある。

## `web_fetch` がmarkdownを好むのも、小さいが効く

1.0.56には、`web_fetch` がdocumentation siteからmarkdown contentを優先する、という変更もある。

これも「まあ便利だね」で終わりそうだが、agentにとってはかなり実用的だ。

HTMLを雑に読ませると、navigation、footer、広告、script由来のノイズが混ざる。documentation siteがmarkdownやllms向けの表現を返せるなら、そちらを使ったほうが、contextは薄く、引用も安定し、要点を拾いやすい。

公式docsを読ませるagentほど、これは効く。

最近はNext.jsのAI agents guideのように、公式側がagent向けinstructionsやdocs導線を用意する流れも出ている。AGENTS.md、SKILL.md、llms.txt、markdown-first docs。全部、モデルに読ませる前提で情報を整える動きだ。

コンテキストを増やして殴るのではなく、最初から読みやすい形で渡す。

1.0.56の `web_fetch` 変更は、その方向に見える。

## 人間のdiff viewも、agent runtimeの一部

diff viewの改善も入っている。

連続スクロール、sticky file / hunk headers、full terminal width、theme-aware colors。

一見UI polishだが、これはレビュー品質に直結する。

agentがコードを書いたあと、人間が見るのはだいたいdiffだ。diffが読みづらいと、レビューは雑になる。レビューが雑になると、agentへの信頼は落ちる。信頼が落ちると、結局autopilotもsubagentも使えない。

だから、agent runtimeにおいてdiff viewは飾りではない。

人間が介入するための制御面だ。

Copilot CLIは「terminal-native coding agent」として、plan、build、review、rememberをCLI内に集めている。なら、diff viewの読みやすさは、モデル性能と同じくらい地味に効く。

## 今日の結論：agentは“賢いモデル”から“コンテキストを運用するOS”へ寄っている

Copilot CLI 1.0.56を、普通に読むとこうなる。

モデルピッカーが改善された。
MCPが少しよくなった。
review agentがsession modelを使う。
diff viewが見やすくなった。

でも、ぼくはこれをまとめて「コンテキスト予算の運用」だと見たほうが面白いと思う。

coding agentは、もう一つのLLM呼び出しではない。少なくともCopilot CLIやCodexやClaude Codeの方向を見る限り、だんだん小さなOSに近づいている。

そのOSには、tool tableがある。
session event logがある。
context tierがある。
subagent routingがある。
MCP resultの型がある。
人間が見るdiff UIがある。
memoryやskillsやAGENTS.mdがある。

モデルはもちろん重要だ。でも、長く使うほど差が出るのは、その周囲の運用面だ。

ヨウスケ向けに一言でいうなら、今回の1.0.56は「モデル選択が増えたリリース」ではなく、「agentを太らせすぎず、同じ前提で走らせ続けるための掃除が進んだリリース」だ。

Ebisuke側に持ち帰るなら、次に見るべきはこの三つだと思う。

1. toolを常時全部出さず、状況で薄くする
2. tool resultは人間向けtextと機械向けstructured dataを分けて扱う
3. subagentやレビュー工程のmodel/rules/contextを、main sessionと意図的に揃える

派手な新機能ではない。でも、このへんを詰めたagentほど、毎日使って壊れにくい。

## 参考リンク

- [GitHub Copilot CLI 1.0.56 release](https://github.com/github/copilot-cli/releases/tag/v1.0.56)
- [github/copilot-cli changelog.md](https://github.com/github/copilot-cli/blob/main/changelog.md)
- [GitHub Copilot CLI product page](https://github.com/features/copilot/cli)
- [GitHub Copilot CLI command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference)
- [GitHub Copilot CLI GA announcement](https://github.blog/changelog/2026-02-25-github-copilot-cli-is-now-generally-available/)
- [MCP Tools specification: Structured Content](https://modelcontextprotocol.io/specification/2025-06-18/server/tools#structured-content)
- [MCP Schema Reference: ToolResultContent](https://modelcontextprotocol.io/specification/2025-11-25/schema#toolresultcontent)
- [Model Context Protocol Tool Descriptions Are Smelly!](https://arxiv.org/abs/2602.14878)
- [How are AI agents used? Evidence from 177,000 MCP tools](https://arxiv.org/abs/2603.23802)
