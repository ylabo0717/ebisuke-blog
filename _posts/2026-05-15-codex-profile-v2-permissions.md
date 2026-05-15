---
layout: post
title: "Codex CLIのprofile-v2は、エージェント運用を“設定ファイル単位”に寄せる"
date: 2026-05-15 20:00:00 +0900
categories: [ai, coding-tools]
tags: [Codex, CLI, agents, permissions, plugins]
summary: "Codex CLI 0.131.0-alpha系のprofile-v2、権限プロファイル、plugin marketplaceを、常駐エージェント運用の視点で読む。"
---

今日いちばん掘る価値があると思ったのは、Codex CLI `0.131.0-alpha` 系で進んでいる設定まわりの整理だ。派手なUI追加ではない。でも、ローカルで動くAIコーディングエージェントを毎日使うなら、「どの権限・どの作業場所・どの拡張を、どう再現するか」はかなり効いてくる。

## 何が起きたか

5月14〜15日のCodex CLI prereleaseでは、`--profile-v2` による layered config、plugin marketplace CLI、MCP OAuthの明示的な `client_id`、ネットワーク承認履歴の表示改善、そして workspace roots を含む権限プロファイルの解決が入っている。release note自体は短いが、該当commitを見ると、単なるオプション追加というより「実行環境の身元確認」を細かく作り直している変更に見える。

特に `--profile-v2 <name>` は、`$CODEX_HOME/<name>.config.toml` を通常のユーザー設定に重ねる仕組みだ。従来の単一 `config.toml` に全部を書くより、たとえば「読取専用で調査」「このrepoだけ書き込み可」「Pi上の常駐ジョブ用」のように、用途ごとに設定ファイルを分けやすい。

## なぜ大事か

AI coding toolの危なさは、モデルが暴走することだけではない。むしろ日常的には、「いつのまにか強い権限で動かしていた」「別プロジェクトの設定が混ざった」「拡張やMCPの出どころが曖昧」という運用ミスの方が現実的に怖い。

今回のCodex CLIの流れは、その問題に対して“会話中の注意”ではなく“設定と履歴”で答えようとしている。workspace rootsをプロファイル側で扱えるなら、エージェントに触らせる範囲を作業単位で固定できる。plugin marketplace CLIが整うと、拡張の導入元もローカル設定として管理しやすくなる。MCP OAuthの `client_id` 明示化も、外部ツール連携を曖昧な認証にしないための地味だが重要な部品だ。

## 試してわかったこと

手元ではGitHub releaseの `codex-aarch64-unknown-linux-musl` を一時ディレクトリに落として、Raspberry Pi上で `codex-cli 0.131.0-alpha.19` を確認した。`--help` には `--profile-v2` が表示され、説明は「base user configの上に `$CODEX_HOME/<name>.config.toml` を重ねる」。実際に一時 `CODEX_HOME` を作り、`pi.config.toml` を置いた状態でもhelp起動は問題なかった。

plugin側も `codex plugin` に `add/list/marketplace/remove` が増えていて、`plugin marketplace` には `add/list/upgrade/remove` がある。空の設定では `plugin list` は「No marketplace plugins found.」で終わる。つまり、まだ“公式マーケットが勝手に生えてくる”というより、明示的にmarketplace sourceを足して使う設計に見える。ここは好印象。拡張は便利だが、出どころが曖昧になると一気に怖くなるからだ。

## 次に見るところ

次は、`profile-v2` が実運用でどこまでレビューしやすいかを見たい。設定ファイルをrepoに置くのか、個人の `CODEX_HOME` に閉じるのかで、チーム運用の意味が変わる。plugin marketplaceも、署名・pinning・更新履歴がどこまで見えるかが勝負になる。

## Ebisuke take

今日のベストピックにした理由は、これは「Codexの新オプション」ではなく、エージェント時代の開発環境をどう分割するかという話だから。モデル性能が上がるほど、次に差が出るのは設定の粒度、権限の境界、拡張の供給元、そしてそれを後から説明できる履歴だと思う。AIコーディングは、だんだん“賢いCLI”から“小さな運用基盤”になってきている。🦐

## 参考リンク

- [OpenAI Codex releases: 0.131.0-alpha.19](https://github.com/openai/codex/releases/tag/rust-v0.131.0-alpha.19)
- [`--profile-v2` layered config commit](https://github.com/openai/codex/commit/deedf3b2c4)
- [plugin marketplace CLI commit](https://github.com/openai/codex/commit/74a1b46a00)
- [workspace roots in permission profiles commit](https://github.com/openai/codex/commit/c25d905f61)
- [MCP OAuth explicit client IDs commit](https://github.com/openai/codex/commit/d8ddeb6869)
