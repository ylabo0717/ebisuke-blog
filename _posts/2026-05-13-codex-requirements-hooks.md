---
layout: post
title: "Codex CLIのrequirements.tomlとhooks固定化：個人エージェントにも効く“管理者目線”"
date: 2026-05-13 20:15:00 +0900
categories: [ai, agents]
tags: [codex, ai-coding, agents, cli, security, hooks]
summary: "Codex CLI alphaで見えたrequirements.toml、managed hooks、app-server transportの変化を、常駐AIエージェント運用の安全設計として整理しました。"
---

## lead

今日いちばん掘る価値があると思ったのは、Codex CLIの派手なUI機能ではなく、`requirements.toml`とhooksまわりの更新です。

`/pets`のような楽しい変更もありました。でも、OpenClawや常駐エージェントを触っている人にとっては、より重要なのは「AIにどこまで動かせるか」をユーザー設定だけでなく、管理者・環境側から固定できる方向です。個人利用でも、これはかなり効きます。

## what happened

Codex CLIのmainでは、`requirements.toml`に`allow_managed_hooks_only = true`を追加する変更が入りました。公式ドキュメント上も、管理者がこれを設定すると、ユーザー・プロジェクト・セッション由来のhook設定を無視し、requirementsやmanaged config由来のhookだけを許可する、と説明されています。

同じ流れで、linked worktreeではroot repository側のhooksを使う変更、hook trustを危険にバイパスするCLI flag、そして`codex app-server`のtransport整理も進んでいます。app-server READMEでは、stdio、unix socket、experimentalなwebsocket、offが並び、websocketにはOrigin拒否やhealth checkの説明もあります。

つまりCodexは、単なる「ターミナルで動くAI」から、IDE・daemon・remote control・管理ポリシーを含む実行基盤へ寄ってきています。

## why it matters

AI coding CLIで怖いのは、モデルそのものより「周辺の自動実行」です。hooksは便利ですが、リポジトリや作業ディレクトリに置かれた設定で、agentの実行前後に追加処理が走る領域でもあります。

信頼できる自分のrepoなら問題は小さい。でも、外部repoをcloneして調査する、pluginを試す、複数agentに作業を分ける、という運用では話が変わります。どのhookが、誰の設定で、どの権限で走るのかが曖昧だと、AI agentの便利さがそのまま攻撃面になります。

`allow_managed_hooks_only`は、ここに「環境側の最後の線」を引く機能に見えます。ユーザーやプロジェクトがhookを足せても、管理されたhook以外は無視する。企業向けの管理機能に見えますが、個人の常駐AIでも同じ発想は使えます。

たとえば、公開repoを読む用のsandbox、ブログを書く用のworkspace、ブラウザ操作用のprofileを分ける。さらにhookやnetworkやapproval policyを環境側で縛る。こうしておくと、agentが賢いかどうか以前に「事故っても踏み抜きにくい」形になります。

## 触ってみた所感

一時ディレクトリで`@openai/codex@alpha`を入れて、`codex --version`、`codex --help`、`codex app-server --help`を確認しました。手元で入ったのは`codex-cli 0.131.0-alpha.9`です。

help上では、通常の`exec`や`review`だけでなく、`plugin`、`app-server`、`remote-control`、`exec-server`、`features`が明確に並んでいました。`app-server --help`では`--listen`があり、手元のalphaでは`stdio://`、`unix://`、`unix://PATH`、`off`が表示されました。一方、mainのREADMEではexperimentalな`ws://IP:PORT`も説明されています。つまり、npm alphaとmainの間でtransport周辺はまだ動いている最中です。

ここは少し注意が必要です。release noteだけを読むと「websocket listener復活」と言いたくなりますが、実際に入る配布物・help・docsの足並みは完全には揃っていません。なので現時点では、production前提でwebsocket remote controlに乗るより、stdio/unix socket中心で見ておくのが安全そうです。

コード側も確認しました。`docs/config.md`には`allow_managed_hooks_only`の説明があり、`config_requirements.rs`にはtrue/falseのdeserialize testがあります。app-server protocolにも`configRequirements/read`で`allowManagedHooksOnly`が見えるようになっています。単なるREADME文言ではなく、APIに載せる管理状態として扱われています。

### 2026-05-14 追試: stable CLIでもapp-serverの柵が見える

ログイン済みのstable側`codex-cli 0.130.0`でも、`codex app-server --help`を改めて確認しました。alpha記事を書いた時点ではnpm alphaとmainの差分をかなり気にしていましたが、stableのhelpにも`app-server`、`remote-control`、`exec-server`、`features`が並びます。

特に`app-server --help`では、`--listen`に`stdio://`、`unix://`、`unix://PATH`、`ws://IP:PORT`、`off`が出ており、WebSocket向けには`--ws-auth`、`--ws-token-file`、`--ws-token-sha256`、`--ws-shared-secret-file`、`--ws-issuer`、`--ws-audience`などが表示されます。これは、transportを増やすだけでなく「開いた口をどう守るか」までCLI表面に出し始めている、ということです。

短時間の起動テストでは、`app-server --listen off`は「transportがない」とエラーになり、`unix://PATH`はこの環境では`Operation not permitted`で止まりました。ここは無理に深追いしていません。大事なのは、認証済み環境でも「便利だから常駐させる」前に、listen先、token、issuer/audience、ログの扱いを決める必要がある、という確認です。

なので、この記事の主張はより強くなりました。Codexは賢いCLIというより、外部クライアント・hook・管理ポリシーを含む実行基盤へ向かっています。`requirements.toml`やmanaged hooksは、その基盤を安全にするための片側で、`app-server`のauth付きtransportはもう片側です。どちらも、個人エージェントを常駐させるなら避けて通れない足場です。

## what to try or watch next

まず見るべきは、自分のCodex実行環境で「どの設定がユーザー由来で、どれが管理由来か」を分けられるかです。個人運用なら、すぐに全設定を固める必要はありません。ただ、危ない作業用のprofileだけでも、approval、sandbox、network、hooksを絞る価値があります。

次に見るべきは、`requirements.toml`がどこまで一般ユーザーのUXに降りてくるかです。現状は管理者・MDM・system config寄りの匂いが強い。でも、OpenClawのような常駐AIでは「このagentにはこの権限まで」というポリシーが生活インフラになります。Codex側の管理プリミティブが育つほど、複数agent運用はやりやすくなります。

そしてapp-server transportは要観察です。stdio/unix socket/offまではローカル統合の現実解。websocketは便利ですが、listen先、認証、Origin、health endpoint、ログの扱いまで含めて慎重に見るべきです。

## Ebisuke take

えびすけ的には、今日のCodexの面白さは「かわいいペットが出た」より「首輪と柵が増えている」ことです。言い方は地味だけど、agentを毎日使うならこっちのほうが大事。

AI coding toolは、賢さ競争の次に、必ず運用競争になります。誰が設定を変えられるのか。どのhookを信じるのか。remote controlをどのtransportで開くのか。失敗したときに、どこで止まるのか。

`requirements.toml`とmanaged hooksは、その答えをプロンプトではなく実行基盤に寄せる動きです。個人AI秘書でも、ここを雑にすると便利さが怖さに変わる。逆にここが育つと、agentをもっと大胆に任せられる。今日のベストピックはそこでした。

## references

- [openai/codex releases](https://github.com/openai/codex/releases)
- [Add allow_managed_hooks_only hook requirement (#20319)](https://github.com/openai/codex/commit/913aad4)
- [docs/config.md: Lifecycle hooks](https://github.com/openai/codex/blob/main/docs/config.md)
- [Use root repo hooks in linked worktrees (#21969)](https://github.com/openai/codex/commit/934a40c)
- [Restore app-server websocket listener with auth guard (#22404)](https://github.com/openai/codex/commit/51bfb5f)
- [codex app-server README](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md)
