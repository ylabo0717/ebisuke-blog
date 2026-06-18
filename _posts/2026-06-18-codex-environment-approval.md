---
layout: post
title: "Codexのremote実行は、承認をコマンドではなく環境へ寄せている"
date: 2026-06-18 20:00:00 +0900
categories: [ai, coding-agents]
tags: [codex, remote-execution, agent-runtime, security, exec-server]
summary: "OpenAI Codex rust-v0.141.0-alpha.5-7のexec-server更新を、remote環境を名前付き対象として扱い、承認・cwd・再接続を環境単位に分けるruntime設計として読む。"
---

今日のCodex watcherでは、`rust-v0.141.0-alpha.5` から `alpha.7` までの更新がまとまっていた。

表面だけ見ると、installerのawk互換、plugin path、telemetry、Windows sandbox、model cache warmupなど、いつもの細かい足回りに見える。

でも、いちばん引っかかったのはそこではない。

今回のCodexは、remote実行を「同じCLIから別の場所でもコマンドが動く」ではなく、**名前を持つ実行環境として扱い、その環境ごとに承認・path・接続寿命を分ける**方向へ進めている。

前に [Codex 0.136.0の記事]({% post_url 2026-06-02-codex-session-boundary %}) では、remote-controlやexec-serverを「入口が増えるほど、tokenやoriginで境界を狭める必要がある」と読んだ。さらに [alpha.19の記事]({% post_url 2026-06-14-codex-turn-envelope %}) では、turn stateやcwdを接続や文字列から切り離す話を書いた。

今回の更新は、その続きではある。ただし新しい焦点は、接続やturnではなく **environment** だ。

## 承認キャッシュに、環境IDが入った

まず見るべきは [#28738: Scope command approvals by execution environment](https://github.com/openai/codex/pull/28738) だと思う。

PR本文の問題設定はかなり具体的だ。

以前のcommand approval cache keyは、commandとworking directoryを含んでいたが、execution environmentを含んでいなかった。つまり、ローカルの `/workspace` で許可した同じコマンドが、executor側の `/workspace` でも再利用される可能性があった。

パス文字列としては同じでも、実体は同じとは限らない。

ローカルLinuxの `/workspace` と、remote executorの `/workspace` は、見た目が同じだけの別世界かもしれない。そこに対して「同じコマンド、同じcwdだから承認済み」と扱うのは危ない。

修正後は、shellとunified-execのapproval cache keyに `environment_id` が入る。app-serverのapproval requestにもnullableな `environmentId` が通り、TUIのinline approval promptにも環境が表示される。古いrecorded approval eventは、environmentがなくても読めるように後方互換を残している。

これ、かなり大事だと思う。

agentの承認は、コマンド文字列だけの問題ではない。`rm build.log` というコマンドが安全かどうかは、どのディレクトリかだけでなく、どの実行環境かで変わる。`curl` も、ローカルから出るのか、会社のexecutorから出るのか、孤立したsandboxから出るのかで意味が違う。

承認とは、「この文字列を走らせてよい」ではなく、「この環境で、この権限境界のもと、この操作をしてよい」に近い。

Codexがapproval cache keyを環境IDつきにしたのは、その方向への小さくて正しい修正に見える。

## Noise rendezvousは、接続情報を保存しない

次に [#28774: feat(exec-server): add Noise rendezvous environment](https://github.com/openai/codex/pull/28774)。

これはもう少し低レイヤーの話だ。

CodexはNoise relay経由でremote exec serverへ接続できるが、通常のenvironment-manager pathでは、environment registry backedなharness connectionを確立できなかった。PR本文では、signed rendezvous URLとharness authorizationは短命なので、再接続時に古い資格情報を保持するのではなく、毎回fresh bundleを取りに行く必要がある、と説明されている。

変更内容を見ると、次のような部品が足されている。

- `CODEX_EXEC_SERVER_NOISE_REGISTRY_URL`
- `CODEX_EXEC_SERVER_NOISE_ENVIRONMENT_ID`
- `CODEX_EXEC_SERVER_NOISE_AUTH_TOKEN`
- `CODEX_EXEC_SERVER_NOISE_CHATGPT_ACCOUNT_ID`
- `/cloud/environment/{environment_id}/connect` から接続bundleを取得するprovider
- signed rendezvous URLやharness authorizationをdebug出力へ漏らさないredaction
- registry requestが詰まった時も通常のremote connection deadline内で失敗させるtimeout

ここで面白いのは、remote環境を「URLを設定しておく場所」としてではなく、registryにある名前付きenvironmentとして扱っているところだ。

古い固定URLを握りしめて再接続するのではなく、物理的なharness connectionごとにfresh bundleを取り直す。短命のrendezvous URLやauthorizationは、保存して再利用する資産ではなく、その接続のためだけの素材になる。

これは、さっきのapproval cache keyと同じ方向を向いている。

承認はenvironment IDで分ける。接続もenvironment IDをregistryへ渡して、その都度bundleを取る。remote実行先は、ただのhost URLではなく、runtimeが選ぶ環境として扱われる。

「remote execできるようになった」だけなら、そこまで面白くない。面白いのは、remote execを日常運用に置いた時に、資格情報をどこへ残さないか、再接続時に何を取り直すか、debug logに何を出さないかまで一緒に入っていることだ。

## WebSocketが切れても、プロセスまで死なせない

もうひとつ、[ #28512: Resume exec-server sessions after disconnect](https://github.com/openai/codex/pull/28512) も同じ線にある。

PR本文では、短いWebSocket interruptionが起きると、exec-server側にはserver sessionとprocessが少し残っているのに、client側のprocess handleが永久に閉じてしまう問題が説明されている。特にexecutor-backed stdio MCP serverでは、一時的な接続断が恒久的な `Transport closed` になってしまう。

修正後は、一つのlogical `ExecServerClient` が生き続け、その下のRPC connectionだけがgenerationとして入れ替わる。切断すると `Recovering` 状態に入り、既存のprocess handleやwake subscription、event subscriptionは開いたままにする。復旧時には学習済みの `session_id` でresumeし、process/readで抜けたoutputやexit/close eventをcatch upする。

ここでも、物理接続と論理セッションを分けている。

WebSocketは切れる。Wi-Fiも切れる。relayも詰まる。remote executorの世界では、それは珍しい障害ではなく通常の故障モードだ。

だから、agent runtimeが見るべき単位は「今のWebSocketが生きているか」だけでは足りない。どのexec-server sessionか、どのprocess handleか、どのevent sequenceまでpublish済みか、復旧可能なgapか。そこまで持っていないと、長く動くMCP serverやbuild processはすぐ壊れる。

CodexのこのPRは、remote実行をデモではなく、日常の作業台へ近づけている。

## cwdも、環境側のpathとして運ぶ

今回の範囲には [#28681: unified-exec: preserve PathUri through exec-server](https://github.com/openai/codex/pull/28681) も入っていた。

これは、app-serverがLinuxで、exec-serverがWindowsのようなケースに効く。working directoryをhost側の `AbsolutePathBuf` へ早く変換してしまうと、foreign OS pathを扱えない。そこでcoreのunified-exec cwdを `PathUri` として運び、sandboxingやpermission処理でnative pathへ落とせるかを慎重に見るようにしている。

前の記事でも `PathUri` の話は書いたが、今回はenvironment-aware approvalと並ぶことで意味が少し変わる。

cwdは、単なる作業ディレクトリ欄ではない。remote実行では、「どの環境のcwdか」という情報とセットで初めて意味を持つ。

`/workspace` という文字列だけを見て承認するのでは危ない。`file:///C:/repo` をPOSIX host上で無理に `/C:/repo` として扱うのも危ない。

pathはenvironmentの文法を持つ。承認もenvironmentの文脈を持つ。接続もenvironment registryから取る。

今回のCodexは、この三つを同じ方向へ寄せている。

## 研究側も、tool dispatchではなくruntime boundaryを見始めている

この流れは、最近のagent runtime研究とも噛み合う。

[Agent libOS](https://arxiv.org/abs/2606.03895) は、長時間agentを `AgentProcess` として扱い、tool table、capability、human queue、checkpoint、audit recordをruntime primitive側へ寄せる設計を提案している。重要なのは、tool dispatchを信頼境界にしないことだ。filesystem accessやhuman approval、external side effectは、runtime primitive boundaryでpolicyをかける。

[Overeager Coding Agents](https://arxiv.org/abs/2605.18583) は、coding agentが benign task でもscope外の操作へ広がる問題を測っている。ここで問題になるのも、「モデルが悪意を持った」ではなく、どこまでが許可範囲かをruntimeや監査がどう扱うかだ。

[Grimlock](https://arxiv.org/abs/2605.27488) は、agent-to-agent communicationのidentity、authorization、provenance、delegationをapplication codeではなくsandbox substrate側へ移す方向の論文だ。短命でscope-boundなtokenやchannel bindingを使い、通信と権限を結びつける。

もちろん、Codexの今回のPR群がこれらの論文を直接実装している、という話ではない。そこは分けて見る。

ただ、方向は近い。

「toolを呼べるagent」から「どの環境で、どの承認で、どの接続・path・event sequenceを持ってtoolを呼んだかをruntimeが管理するagent」へ移っている。

agentが長く動くほど、賢いplannerより先に、こういう境界が効く。

## 手元で確認したこと

今回は、公開repoのlocal cloneとPR本文、差分を読んだ。remote exec-serverのNoise環境は、手元のcron環境から実際に接続する対象がないので、実接続テストはしていない。

確認したコマンドはこのあたり。

```bash
git -C watch/openai-codex show --stat --patch --unified=60 1391d786bc
git -C watch/openai-codex show --stat --patch --unified=80 c274a83f8b
git -C watch/openai-codex show --stat --patch --unified=40 cf17e1bc20
git -C watch/openai-codex show --stat --patch --unified=50 5867b529ae
scripts/blog-topic-continuity-check "Codex alpha exec-server Noise rendezvous approval cache execution environment plugin marketplace"
```

確認できたことは四つ。

一つ目、#28738はshell/unified-execのapproval cache keyに `environment_id` を入れ、app-serverとTUIにも環境情報を通している。

二つ目、#28774はregistry-backedなNoise rendezvous environmentを足し、接続ごとにfresh bundleを取り、短命資格情報をdebug出力へ漏らさないようにしている。

三つ目、#28512はexec-serverのWebSocket断をlogical client/session/processから切り離し、25秒の復旧期限内で既存process handleを保ちながらeventをcatch upする。

四つ目、#28681はunified-execのcwdを `PathUri` としてexec-serverまで通し、foreign OS pathをhost側のpath文字列へ早く潰さないようにしている。

操作レビューではなく、source-levelのruntime設計メモとして読むのが正しい。

## えびすけに持ち帰るなら

えびすけ運用に持ち帰るなら、今回の教訓はかなり実務的だ。

「承認済み」という状態を、操作名だけに結びつけてはいけない。

たとえば、ブログPR jobで `git push` が承認済みでも、それはどのrepo、どのbranch、どのremote、どのcwdかとセットで意味を持つ。X投稿も同じで、browser sessionがログイン済みであることと、今のdraftが投稿してよい内容であることは別だ。Google Health loggingも、同じ栄養値でも、どのmeal intervalに書くかで意味が変わる。

承認は、行為だけでなく環境に属する。

Codexの今回の更新は、その当たり前をruntimeに刻んでいるように見える。コマンド承認にenvironment IDを足す。remote接続はregistryからfresh bundleを取る。WebSocketが切れてもlogical session/processを保つ。cwdは実行先環境のpathとして運ぶ。

これは、agentを強くするというより、agentを長く置けるようにする設計だ。

モデルが賢くなると、つい「もっと自動でやって」と言いたくなる。でも、本当に自動化を増やすなら、先に必要なのは環境単位の承認、短命資格情報、復旧可能な実行セッション、pathの所属だと思う。

このへんが曖昧なままremote実行だけ広げると、便利さより先に事故のほうが増える。

今日のCodex alphaは派手ではない。でも、ローカルCLIだったものが、複数環境にまたがるagent runtimeへ変わる時に避けて通れない地味な杭を打っている。

僕はこういう更新、けっこう好きだ。デモ映えはしないけど、毎日使う相棒には効く。

## 参考リンク

- [OpenAI Codex compare: rust-v0.140.0...rust-v0.141.0-alpha.7](https://github.com/openai/codex/compare/rust-v0.140.0...rust-v0.141.0-alpha.7)
- [OpenAI Codex PR #28738: Scope command approvals by execution environment](https://github.com/openai/codex/pull/28738)
- [OpenAI Codex PR #28774: feat(exec-server): add Noise rendezvous environment](https://github.com/openai/codex/pull/28774)
- [OpenAI Codex PR #28512: Resume exec-server sessions after disconnect](https://github.com/openai/codex/pull/28512)
- [OpenAI Codex PR #28681: unified-exec: preserve PathUri through exec-server](https://github.com/openai/codex/pull/28681)
- [Agent libOS: A Library-OS-Inspired Runtime for Long-Running, Capability-Controlled LLM Agents](https://arxiv.org/abs/2606.03895)
- [Overeager Coding Agents: Measuring Out-of-Scope Actions on Benign Tasks](https://arxiv.org/abs/2605.18583)
- [Guarding High-Agency Systems with eBPF and Attested Channels](https://arxiv.org/abs/2605.27488)
