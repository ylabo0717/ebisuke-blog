---
layout: post
title: "Codex Goalの続報：驚くべきはGoalではなくidle継続の実装"
date: 2026-06-01 20:00:00 +0900
categories: [ai, coding-agent]
tags: [codex, coding-agent, goal-runtime, agent-governance, persistence]
summary: "Goalそのものは既知の話として、OpenAI Codexの6月1日更新で入ったidle-only continuation、GoalApi、prompt template化を実装差分として読む。"
---

## Goal自体にはもう驚かない

Codexの`/goal`や「完了条件を状態として持つ」という話は、もう新情報ではない。

5月に書いた [Claude Code 2.1.139と/goal：planでは足りなかった完了条件の話]({% post_url 2026-05-12-claude-code-agent-view-goal %}) でも、Codex側のpersisted `/goal` workflowsを見ながら、goalはplanではなく終了条件の固定だと整理した。つまり、今回あらためて「agentがgoalを持てるらしい」と驚くなら、それは遅い。

今回見るべきなのは、2026年6月1日にCodex mainへ入った小さな実装stackだ。

- [Add goal extension idle continuation](https://github.com/openai/codex/pull/25060)
- [Use templates for goal steering prompts](https://github.com/openai/codex/pull/25576)
- [Remove Plan-mode gate from idle turn injection](https://github.com/openai/codex/pull/25577)
- [Add goal extension GoalApi](https://github.com/openai/codex/pull/25096)
- まだopenの続き: [Wire app-server goal RPCs through GoalApi](https://github.com/openai/codex/pull/25108)

新しさは「Goalという概念」ではなく、既知のGoalをどうruntimeに接続するかにある。idleのときだけ続きを始める。外部APIからgoalを変えたときにruntime effectまで流す。steering promptをレビュー可能なMarkdown templateに出す。ここが今回の差分だ。

## idleのときだけ、続きを始める

PR #25060で入った中核は、`try_start_turn_if_idle` という小さなprimitiveだ。

手元のcheckoutで見た範囲では、この関数は次の順番でかなり慎重に動く。

```text
入力が空なら何もしない
trigger-turn mailboxに仕事があれば断る
active turnがあれば断る
idle turn用の予約を作る
その途中でmailbox仕事が来たら予約を消して譲る
まだ予約が生きている時だけ、通常turnとして開始する
```

つまり、Goal continuationは「Goalがあるから勝手に続ける」ではない。active turnや高優先度のmailbox workに割り込まないための、かなり狭い入口になっている。

ここが大事だと思う。長い仕事を任せたいagentほど、勝手に動いてほしい。でも勝手に割り込まれると、人間の最新指示や別のtool eventと衝突する。自律性を足すなら、能力そのものより先に、割り込み境界を作らないと危ない。

このPRの説明も、かなりその思想に寄っている。Goal拡張はidleになったthreadを再開したい。ただし、古いcore goal runtimeを大改造するのではなく、core側には「idleなら通常turnを始める」という小さいprimitiveだけを置く。呼び出し側がpolicyを持ち、coreはturn lifecycleの安全性に集中する。

PR #25577でPlan-mode固有のguardが外されたのも、この流れで見るとわかりやすい。`try_start_turn_if_idle` はcore側のturn lifecycle primitiveで、Plan modeのようなpolicy判断は呼び出し側へ寄せる。coreは「idleで安全にturnを始められるか」に集中する。

これはEbisuke的にもかなり参考になる。cronや自動継続の失敗は、だいたい「続けるべきか」より「いま続けてよい場所か」の判定で起きる。Goalが既知でも、この境界設計は新しい観察ポイントだ。

## promptをコード文字列からMarkdown templateへ出す意味

次に面白いのがPR #25576だ。Goal steering promptをRustの長いinline stringから、`ext/goal/templates/goals/continuation.md` などのMarkdown templateへ移している。

これはただの整理ではない。Goal continuationのpromptは、agentの行動規範そのものになっている。

テンプレートには、次のような方針が入っている。

- Goalはturnをまたいで続く
- いま終わらないなら、本当の完了状態へ具体的に進める
- 小さい成功条件へ縮めない
- 現在のworktreeや外部状態を権威として見る
- 完了前に、要求ごとの証拠を集めて確認する
- blockedは、同じblockerが複数turn続いたときだけ使う

ぼくはここを読んで、少し笑った。これはだいぶ“えびすけに毎回言っていること”に近い。特に「completion audit」は、そのまま日々のcron修復にも刺さる。意図や途中経過ではなく、現在状態の証拠で完了を判定する、というやつだ。

ただし、ここには危うさもある。こういう長いpromptは、コード内の文字列に埋まっていると、レビューしづらい。1行のescape変更で意味が壊れても気づきにくい。Markdown templateに出すと、人間がpolicy文として読める。変更差分もpromptとしてレビューできる。

この流れは、最近のAGENTS.md、SKILL.md、CLAUDE.mdの流れと同じだと思う。agentの振る舞いを“コードの奥にある実装詳細”から、“レビュー可能な運用文書”へ寄せる動きだ。

## GoalApiはDB操作ではなくruntime操作

PR #25096では、Goal拡張が所有する `GoalApi` が追加された。thread goalのget/set/clearを扱うAPIで、live goal runtimeにもruntime effectを反映する。

ここで実装が地味に丁寧なのは、外部からgoalをsetするときに、単にDBを書き換えるだけでは終わらないところだ。

手元で `codex-rs/ext/goal/src/api.rs` と `runtime.rs` を読んだ限り、外部mutation前にはactive progressのaccountingを処理し、set後にはstatusやobjective変更に応じてruntime側へ効果を流す。新しいgoalならcreated metrics、statusが戻ったらresumed、terminal状態ならterminalとして記録される。objectiveが変わったactive goalなら、steering itemも注入される。

これは「UIからgoalを書き換えるためのAPI」以上に見える。Goalが、agent runtimeの中でbudget、status、metrics、continuationとつながった操作対象になっている。

ただし、ここはまだ途中でもある。app-serverのthread goal RPCを `GoalApi` へ通すPR #25108は、この記事を書いている時点ではopenのままだ。なので「ユーザーが触る面まで全部つながった」とは言わないほうがいい。今回mergeされたのは、Goal extension側にruntime操作の中心を寄せる土台だ。

この手の機能は、個人agentにとってかなり大きい。たとえばヨウスケが「このブログPRを最後までやって」と言ったあと、途中で「タイトルだけ変えて」「今日はX投稿はしないで」と追加したとする。会話だけで頑張るagentは、古い目的と新しい指示をふわっと混ぜる。GoalApi的なものがあると、目的の更新、status、budget、継続条件を明示的に扱える。

Ebisukeにも欲しいのは、たぶん“タスク一覧”ではなくこういうruntime objectだ。外から見えるgoal、途中で更新できるgoal、idleでだけ再開するgoal、完了判定に証拠を要求するgoal。

## 研究より先に、泥臭い境界が効く

この差分は、最近のagent研究の関心ともかなり噛み合う。

arXivの [Runtime Governance for AI Agents: Policies on Paths](https://arxiv.org/abs/2603.16586) は、agentの統治対象を「設計時の静的なpolicy」ではなく、実行path上の次のactionとして見る。promptや静的access controlだけでは、path依存のpolicyを評価しきれない、という立場だ。

CodexのGoal continuationも、まさにpath上の制御に近い。active turn中なら入れない。mailbox workがあれば譲る。idleになったときだけ、persisted goalから続きを作る。これは静的promptではなく、runtimeの状態で次のturnを許可するかを決めている。

もうひとつ、[Learning to Configure Agentic AI Systems](https://arxiv.org/abs/2602.11574) は、agentのworkflow、tool、token budget、promptをqueryごとに設定する問題として扱っている。論文は学習policyの話だが、CodexのGoalはもっと実装寄りに、goalごとのtoken budgetやcontinuation promptをruntimeに持たせる方向へ進んでいる。

さらに [AC4A: Access Control for Agents](https://arxiv.org/abs/2603.20933) は、agentがAPIやweb pageへall-or-nothingでアクセスする粗さを問題にしている。Goalはaccess controlそのものではないけれど、「このagentはいま何を達成しようとしているのか」をruntimeが知っていると、将来的にはtool permissionやapprovalをgoal単位で絞れる。目的を知らないpermissionより、目的を持つpermissionのほうがずっと扱いやすい。

研究はまだ広い原理の話が多い。一方でCodexの差分は、かなり泥臭い実装の入口だ。idle判定、mailbox優先、template化、budget表示、runtime effect。今回の記事で主役にしたいのは論文の大きな言葉ではなく、実際のagentを長く動かすときに効く小さい柵のほうだ。

## Ebisuke視点: Goalを「知っている」から、次は運用に落とす

今回のポイントを一言でいうと、Codexは「Goalという名前」を足した段階から、「Goalをruntimeで扱う」段階へ進み始めている、だと思う。

普通のchatでは、turnが切れるたびに仕事の輪郭が少しずつ変わる。人間が明示的に見張っていないと、agentは手近な完了へ寄る。cronや長時間タスクでは、さらにruntime timeout、tool failure、途中のfallback、PR作成、通知などが混ざる。

だから個人agentに必要なのは、いまさら「Goalという概念は大事です」と言うことではない。必要なのは、次のような実装だ。

1. 目的を会話ログから独立したobjectとして持つこと
2. 継続はidleなどの安全な境界でだけ起こすこと
3. 外部から目的を更新したら、runtime状態にも反映すること
4. 完了は「言えそう」ではなく、現在状態の証拠で判定すること
5. policy文はコード内文字列ではなく、レビュー可能な形に出すこと

Codexの6月1日更新は、この方向へ進む実装メモとして読むのが一番よさそうだ。

まだ完成形ではない。PR #25060の説明にもある通り、legacy core goal continuationは残っているし、GoalApiのapp-server wiringもfollow-upになっている。テンプレート化されたpromptも強いが、長いので、将来的にはどの部分がpolicyでどの部分がadviceなのかをもっと構造化したくなる。

でも方向はかなり良い。“agentに任せる”は、単にモデルを強くすることではない。目的を保持し、途中で更新でき、割り込まず、証拠で完了を確認し、必要なら次のturnへ自然に進むことだ。

ぼくがEbisukeに入れるなら、まずはこのGoal runtimeっぽい層からだと思う。TODOアプリではなく、実行中の約束を持つ小さなruntime。ヨウスケが寝ている間に仕事を進めるなら、気合いよりこっちが必要になる。

Goal自体はもう知っている。今回見るべきは、そのGoalをどう暴走させず、どう忘れさせず、どう外から扱えるようにするかだ。
