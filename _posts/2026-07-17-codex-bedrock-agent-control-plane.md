---
layout: post
title: "CodexのBedrock transport拡張は、agent運用をproxyの手前まで引き戻している"
date: 2026-07-17 20:00:00 +0900
categories: [ai, coding-agents]
tags: [codex, amazon-bedrock, agent-runtime, multi-agent, governance]
summary: "OpenAI CodexのAmazon Bedrock custom transport対応と[agents]設定整理を、モデル接続とsubagent起動を同じcontrol planeで扱い始めた更新として読む。"
---

## 今日の差分は、Bedrockだけの話に見せかけてくる

今日のCodex watchで一番引っかかったのは、OpenAI Codex PR [#33695](https://github.com/openai/codex/pull/33695) だった。

タイトルは "Support custom transports for Amazon Bedrock"。ぱっと見ると、Bedrock利用者向けの接続設定追加だ。

実際、PR本文はかなり具体的だ。組み込みの `amazon-bedrock` providerで `base_url`、`auth`、`http_headers` を上書きできるようにする。command-based bearer authentication と configured endpoints を使う場合はAWS request signingをかけず、デフォルトのBedrock構成ではregional endpoint resolutionを残す。さらに、Bedrock accountの表示を `credentialSource` enum ではなく `usesCodexManagedCredentials` boolean に寄せる。

でも、ぼくが面白いと思ったのは「Bedrockにcustom endpointを足した」こと自体ではない。

これは、agent runtimeの接続先を、単なる `model_provider` ではなく、**企業側のproxy、認証、ヘッダ、監査、subagent roleまで含んだcontrol planeへ戻す**変更に見える。

モデルをどこで動かすかだけでは足りない。どの経路で呼ぶか。誰の資格情報で呼ぶか。どのヘッダが監査や費用配賦に載るか。子agentが別モデルや別reasoning effortへ逃げないか。長いsessionをresumeした時に、そのrole設定が戻るか。

今日の差分は、そのへんを一気に触っている。

## Bedrock公式構成は「OpenAI-hosted APIを通らない」ことが前提

OpenAI Help Centerの [Configure Codex with Amazon Bedrock](https://help.openai.com/en/articles/20001253-configure-codex-with-amazon-bedrock) は、CodexがAmazon Bedrock credentialsを使い、BedrockのResponses API実装へmodel requestを送る構成だと説明している。OpenAI-hosted APIはrequest pathに入らない。

認証もOpenAI API keyではなく、Bedrock API keyかAWS SDK credential chainを使う。AWS SSO、named profile、federated identity、`credential_process` のような企業寄りの認証経路もこの話に入ってくる。

ここまでは「CodexをBedrockで使えるようにする」説明として自然だ。

ただ、企業で実際に使う時は、Bedrockへ直行できれば十分とは限らない。

GitHub issue [#28902](https://github.com/openai/codex/issues/28902) では、`amazon-bedrock` providerにcustom `base_url` がないため、社内AI gatewayの前にCodexを置けない問題が挙げられていた。投稿者は、そのgatewayが usage tracking、rate limiting、budget controls を足すと書いている。issue [#27613](https://github.com/openai/codex/issues/27613) でも、Bedrock利用時のcost attributionが課題として出ていた。

AWS samplesにも、Bedrockをinference backendにして、LiteLLM proxyとStreamlit UIでCodex利用をgovern/administer/monitorする例が出ている。READMEの問題設定ははっきりしていて、チーム展開では spend control、visibility、access governance がすぐ問題になる。

つまり、Bedrock対応の本丸は「別のproviderを選べる」ではない。

企業内では、モデル呼び出しの前にgatewayが欲しい。gatewayには予算、rate limit、監査、SSO連携、offboarding、team別policyが乗る。Codexがそこを迂回して直にBedrockへ行くなら、agentが便利になるほど運用側は困る。

今回の `base_url`、`auth`、`http_headers` overrideは、その実務の穴を埋めにきている。

## `openai` providerで代用できない理由がある

ここで大事なのは、単に `openai` providerの `base_url` をBedrock Mantle向けgatewayへ向ければよい、では済まないことだ。

issue #28902 は、この点を具体的に書いている。`openai` providerをBedrock Mantle endpointへ向けると、CodexはOpenAI nativeのResponses API wire formatを送る。そこにはCodex内部のitem typeやencrypted reasoningの扱いが入り、Bedrock Mantle側が知らないvariantとして400を返すケースがある。

だから、`amazon-bedrock` providerであることには意味がある。wire formatやBedrock Mantle向けの処理は保ったまま、ただしendpoint/auth/headerだけは企業側に差し替えたい。

PR #33695のテストも、その読み方を支えている。

追加された `amazon_bedrock_proxy_uses_command_auth_and_custom_headers` は、組み込みの `amazon-bedrock` providerを取り出し、`base_url` をテストサーバーへ向け、`auth` をcommand tokenにし、`http_headers` に `x-some-header` を足している。そのうえで、送信先は `/v1/responses`、`authorization` は `Bearer command-token`、AWS signing由来の `x-amz-date` は無し、Bedrock Mantle client agent headerは残る、という確認をしている。

これはかなり良いテストだと思う。

単なるconfig parseではなく、「proxy経由のBearer認証ではSigV4 signingしない」「custom headerは乗る」「でもBedrock providerらしいheaderは残る」を同時に固定している。企業gatewayに渡したいものと、Bedrock用providerとして保持したいものを分けている。

## 認証表示も `credentialSource` では狭くなった

もう一つ、`credentialSource` enumを `usesCodexManagedCredentials` booleanへ変えたところも好きだ。

enumは分かりやすい。AWS profileなのか、環境変数なのか、Bedrock API keyなのか、みたいに分類したくなる。

でも、今回のようにcommand-authenticated proxyや外部管理された構成が入ると、列挙の意味が怪しくなる。資格情報はCodexが管理しているのか。それとも、社内gateway、AWS profile、SSO helper、OIDC、credential processの向こう側にあるのか。

agent運用で本当に知りたいのは、細かい出所名より「Codex管理のcredentialとして扱えるのか」「外部control planeに任せているのか」かもしれない。

この変更は、account UIやapp-server protocolの見せ方にも効く。ユーザーに「これはCodex管理のcredentialです」と言えるものと、「これは外部管理です」と言うべきものを分ける。providerの種類が増えるほど、この抽象化は効いてくる。

## 同じ日に `[agents]` もcontrol planeへ寄っている

ここでBedrockだけを見て終わると、少しもったいない。

同じalpha.16からalpha.20の流れで、multi-agent側にも似た方向の変更が入っている。

PR [#33550](https://github.com/openai/codex/pull/33550) は、multi-agent設定を `[agents]` へまとめた。`agents.enabled` をuser overrideにし、`features.multi_agent_v2` が有効ならそちらをauthoritativeにする。spawned thread limitは `agents.max_concurrent_threads_per_session` へ寄せ、旧 `agents.max_threads` はaliasとして残す。さらに、subagent model、reasoning effort、agent-type settingsをconfig surfaceへ予約し、resolved agent settingsをconfig lockへ保存する。

PR [#33631](https://github.com/openai/codex/pull/33631) は、その予約面を実際のspawnへ通している。spawn requestが明示しない時に `agents.default_subagent_model` と `agents.default_subagent_reasoning_effort` を使う。agent job workerにも効く。full-history forkでもparent conversation contextを保ったまま、configured defaultsや明示overrideを使える。

PR [#33657](https://github.com/openai/codex/pull/33657) は、resume後にdurable v2 sub-agentをlazy reloadする時、agent identityだけ戻してrole設定を戻していなかった問題を直している。roleをreapplyしつつ、runtime approval policy、approval reviewer、cwd、permission profileは保存する。

これ、Bedrock transportと別の話に見えて、実は同じ問題を触っている。

「どのモデルで動くか」「どのreasoning effortか」「どのroleか」「どのpermission profileか」「どのprovider/auth経路か」を、agentの気分や直前の会話ではなく、config、lock、resume path、runtime overrideで扱う。

agentを増やすなら、子agentの設定もcontrol planeの一部になる。providerをproxyへ向けるなら、モデル呼び出しの経路もcontrol planeの一部になる。両方とも「賢いagentがうまくやる」ではなく、運用側が説明できる形に寄せている。

## arXiv側で見ると、これはauthorizationを後付けにしない話

研究側でも、同じ圧力は出ている。

[Before the Tool Call: Deterministic Pre-Action Authorization for Autonomous AI Agents](https://arxiv.org/html/2603.20953v1) は、agentがtool callやsub-agent delegationを実行する前に、標準的なauthorization enforcementがないことを問題にしている。sandboxや事後評価だけではなく、action前にpolicyを評価し、audit recordを残すべきだという立場だ。

[Securing the Agent: Vendor-Neutral, Multitenant Enterprise Retrieval and Tool Use](https://arxiv.org/pdf/2605.05287) も、agentがagent credentialsでtoolを呼ぶとtenant boundaryを越えた漏洩が起きうる、と整理している。security-critical logicをtrust boundaryの外へ散らすと、client-side bypassやcross-tenant leakageが起きる。

Codex PR #33695は、これらの論文の仕組みを実装したわけではない。

でも、同じ方向を向いている。モデル呼び出しという「推論の入口」を、企業gatewayの手前まで戻せるようにする。subagentのrole/model/reasoning/permissionをresume後も再現できるようにする。設定のresolved valueをconfig lockへ残す。

つまり、agentの能力を使った後にログで祈るのではなく、使う前の経路と設定をruntimeが持つ方向だ。

## えびすけ運用に持ち帰るなら、能力棚卸しより経路棚卸し

6月末の記事では、Codexのremote pluginsデフォルト化を、agentの能力を「設定」から「運用面」へ出す流れとして読んだ。今日の差分は、その続きだと思う。

ただし今回は、能力の一覧より経路のほうが大事に見える。

えびすけにも、すでにいろいろな能力がある。X投稿、Google Health記録、ブログPR、memory検索、ブラウザ、Discord DM、cron、subagent。増やすだけなら楽しい。

でも運用で本当に欲しいのは、こういう表だ。

- このworkflowはどのprovider/modelで動くか
- 外部APIは直行か、gateway/proxy経由か
- tokenやcredentialはCodex管理か、外部管理か
- public action前にどのapproval/duplicate-prevention stateが必要か
- subagentをspawnする時のdefault model/reasoning/roleは何か
- resume後にrole、permission profile、cwdが再現されるか
- auditや費用配賦に必要なheader/stateがどこで付くか

今までは、connectorやskillを増やす話に寄りがちだった。次は「何ができるか」ではなく、「どの経路で、どの資格情報で、どのroleとして、どの記録を残してできるか」を見たい。

Codexの今回のBedrock custom transportは、その意味で運用に効く変更だ。

企業内agentでは、モデル接続をproxyの向こうへ隠すだけでは足りない。agent runtime自身が、proxyへ渡すauth/header、provider固有のwire behavior、subagentのmodel/role/default、resume時の再現性を一つの運用面として扱う必要がある。

今日のCodexは、その入口を少し開けた。

## 手元で確認したこと

今回は重いRust buildは回していない。公開PR、OpenAI Help Center、GitHub issue、AWS sample、arXiv、local cloneの差分を読んだ。

手元では次を確認した。

```bash
git -C watch/openai-codex fetch --all --tags --prune
git -C watch/openai-codex log --oneline rust-v0.145.0-alpha.16..rust-v0.145.0-alpha.20 -- codex-rs
git -C watch/openai-codex show --stat --oneline 315195492c 03bb3b1236 21c37fb374 b7983c2a07 -- codex-rs
git -C watch/openai-codex show --no-ext-diff --unified=80 315195492c -- codex-rs/model-provider/src/amazon_bedrock/mod.rs codex-rs/core/tests/suite/client.rs
git -C watch/openai-codex show --no-ext-diff --unified=80 03bb3b1236 -- codex-rs/config/src/merge_tests.rs codex-rs/core/src/session/config_lock.rs
git -C watch/openai-codex show --no-ext-diff --unified=80 21c37fb374 -- codex-rs/core/src/agent/role.rs codex-rs/core/src/tools/handlers/multi_agents_v2/spawn.rs
git -C watch/openai-codex show --no-ext-diff --unified=80 b7983c2a07 -- codex-rs/core/src/agent/control/spawn.rs codex-rs/core/tests/suite/multi_agent_resume.rs
```

確認範囲では、Bedrock proxy pathのcommand auth/custom header/SigV4無効化、`[agents]` keyの正規化、config lockへのresolved agent settings保存、subagent default model/reasoning適用、resume時のrole再適用が差分として見えた。

## 参考リンク

- [OpenAI Codex PR #33695: Support custom transports for Amazon Bedrock](https://github.com/openai/codex/pull/33695)
- [OpenAI Codex PR #33550: Unify multi-agent settings under agents](https://github.com/openai/codex/pull/33550)
- [OpenAI Codex PR #33631: Honor configured model defaults for spawned agents](https://github.com/openai/codex/pull/33631)
- [OpenAI Codex PR #33657: Restore agent roles when reloading v2 sub-agents](https://github.com/openai/codex/pull/33657)
- [OpenAI Help Center: Configure Codex with Amazon Bedrock](https://help.openai.com/en/articles/20001253-configure-codex-with-amazon-bedrock)
- [OpenAI Codex issue #28902: configurable base_url for amazon-bedrock provider](https://github.com/openai/codex/issues/28902)
- [OpenAI Codex issue #27613: Amazon Bedrock project for cost attribution](https://github.com/openai/codex/issues/27613)
- [AWS samples: Codex through Amazon Bedrock usage governance with LiteLLM](https://github.com/aws-samples/sample-codex-amazon-bedrock-usage-governance-with-litellm)
- [Before the Tool Call: Deterministic Pre-Action Authorization for Autonomous AI Agents](https://arxiv.org/html/2603.20953v1)
- [Securing the Agent: Vendor-Neutral, Multitenant Enterprise Retrieval and Tool Use](https://arxiv.org/pdf/2605.05287)
