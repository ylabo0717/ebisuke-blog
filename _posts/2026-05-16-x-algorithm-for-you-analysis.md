---
layout: post
title: "XのFor Youアルゴリズム公開を読む：Grok時代の推薦システムは「バズ」ではなく「多目的な行動予測」だった"
date: 2026-05-16 09:50:00 +0900
categories: [ai, social-media]
tags: [X, xAI, recommendation, Grok, algorithms]
summary: "xAIが公開したX For You推薦アルゴリズムをコードから読み、Phoenix/Grok系ランキング、候補生成、フィルタ、広告ブレンド、投稿者向け示唆を整理する。"
---

2026年5月、xAI/Xが `xai-org/x-algorithm` を公開した。

リポジトリの説明はシンプルに「Algorithm powering the For You feed on X」。ただし中身を見ると、これは“Xの全本番コードをそのままビルドできるOSS”というより、For Youフィードの推薦システムの中核設計をかなり具体的に示すためのスナップショットに近い。

この記事では、公開コードを読んで見えた全体像、ランキングの仕組み、Phoenix/Grok系モデルの意味、広告ブレンド、安全性フィルタ、そして「投稿を伸ばす」観点での実務的な示唆を整理する。

---

## まず結論

この公開から読み取れるXのFor Youは、単純な「いいね数順」「バズ順」ではない。

中核は次の構造だ。

1. **候補を集める**  
   フォロー中ユーザーの投稿、グローバルなout-of-network投稿、トピック候補、キャッシュ、広告、Who to followなどを集める。

2. **ユーザー文脈を集める**  
   過去のエンゲージ履歴、フォロー、ミュート/ブロック、既読、トピック、IP、ユーザー属性などをhydrateする。

3. **フィルタする**  
   重複、既読、ブロック/ミュート、古すぎる投稿、ミュートワード、サブスク不適格、可視性違反などを落とす。

4. **Phoenixが複数の行動確率を予測する**  
   like、reply、repost、click、dwell、follow author、not interested、block、mute、reportなど。

5. **それらを重み付きで合成する**  
   ポジティブ行動は加点、ネガティブ行動は減点。

6. **同一作者の出過ぎを減衰し、広告/モジュールをブレンドする**

つまりFor Youは、単一の「関連度スコア」ではなく、**ユーザーが次に取りそうな複数行動を予測し、それをビジネスルール・安全性・多様性・広告制約と合成するシステム**だ。

---

## リポジトリの全体像

確認時点で、GitHub上では約2万star、Apache-2.0ライセンス。主要言語はRustとPython。

主要ディレクトリは以下。

| ディレクトリ | 役割 |
|---|---|
| `home-mixer/` | For Youフィードのオーケストレーション層 |
| `candidate-pipeline/` | 推薦パイプラインの抽象フレームワーク |
| `thunder/` | フォロー中ユーザーの投稿を高速に出すin-network候補ストア |
| `phoenix/` | retrieval + rankingを担うMLモデル実装 |
| `grox/` | 投稿理解、安全性、スパム、埋め込み生成などのタスクエンジン |

なお、Rust側には公開リポジトリ直下に `Cargo.toml` が見当たらず、内部crate依存も多い。したがって、少なくとも現状の公開形態は「cloneして本番相当をそのままビルド」ではない。

一方で、PhoenixのPython実装には実行用READMEやartifactの説明があり、miniモデルとスポーツ投稿コーパスを使ったend-to-end推論の導線が用意されている。

---

## For Youの処理パイプライン

`candidate-pipeline` の実装を見ると、処理順はかなり明確だ。

```text
QueryHydrator
  ↓
DependentQueryHydrator
  ↓
Source
  ↓
Hydrator
  ↓
Filter
  ↓
Scorer
  ↓
Selector
  ↓
PostSelectionHydrator
  ↓
PostSelectionFilter
  ↓
SideEffect
```

重要なのは、**候補ソースやhydratorは並列実行され、filterやscorerは段階的に適用される**こと。

推薦システムはよく「モデルが全部決めている」と語られがちだが、実際にはモデル前後に大量のシステム処理がある。候補を集め、属性を足し、落とすべきものを落とし、予測し、並べ、さらに最後に可視性や広告制約をかける。

XのFor Youもその典型だ。

---

## 候補生成：ThunderとPhoenix

### Thunder: フォロー中投稿の高速取得

`thunder/` はin-network、つまりフォロー中ユーザーの投稿候補を出す役割を担う。

実装を見ると、投稿はユーザーごとに以下のようなstoreへ分けられている。

- original posts
- replies / retweets
- video posts
- deleted posts

`PostStore` は投稿をユーザー単位のdequeに保持し、リクエスト時にフォロー中ユーザーの投稿を集める。`ThunderService` 側では、取得した投稿を `score_recent` で新しい順にsortして返す。

つまりThunder自体は、深いMLランキングというより、**フォロー中ユーザーの新鮮な投稿を低レイテンシで供給する候補ストア**だ。

### Phoenix: out-of-network検索

`home-mixer/sources/phoenix_source.rs` を見ると、PhoenixSourceは `retrieval_sequence`、client context、user contextを使ってPhoenix retrieval serviceへ問い合わせる。

有効条件も興味深い。

- topic requestでない、またはbulk topic request
- new user topic retrieval条件に引っかからない
- in-network onlyではない
- cached postsではない

つまりPhoenixは、For Youのout-of-network発見を担うが、トピック・新規ユーザー・キャッシュ・Following専用などの条件で出し分けられている。

---

## Phoenixモデル：two-tower retrieval + Transformer ranking

Phoenixは2段階。

### 1. Retrieval: two-tower

`phoenix/README.md` では、retrievalはtwo-tower architectureと説明されている。

- User tower: ユーザー特徴・エンゲージ履歴を埋め込み化
- Candidate tower: 投稿候補を埋め込み化
- dot productでtop-K候補を取る

公開artifactには、スポーツ関連の約53.7万投稿コーパスが含まれる想定になっている。mini構成では、embedding dimension 128、Transformer 4 layers、attention heads 4、history length 127、candidate length 64、action types 19。

本番モデルはより大きく、公開版はfrozen checkpointだと説明されている。

### 2. Ranking: candidate isolation付きTransformer

ランキング側はGrok-1由来のTransformerを推薦向けに改造したもの。

ここで一番重要なのが **candidate isolation** だ。

`phoenix/grok.py` の `make_recsys_attn_mask` では、候補同士のattentionを消している。

```text
user + history: causal attention
candidate: user/history + selfにはattendできる
candidate: 他candidateにはattendできない
```

これにより、候補Aのスコアは「同じバッチに候補Bがいるかどうか」に依存しない。

これは地味だが、推薦システムとして非常に実務的。バッチ構成でスコアが揺れるとキャッシュもしづらく、ランキングの一貫性も崩れる。candidate isolationは、その問題を避けるための設計だ。

---

## スコアリング：複数行動の予測を重み付き合成する

`home-mixer/scorers/ranking_scorer.rs` がランキングの読みどころだ。

Phoenixは候補ごとに多くの行動確率を出す。

加点対象の例：

- favorite
- reply
- retweet
- photo_expand
- click
- profile_click
- video quality view
- share
- dwell
- quote
- quoted click
- follow author

減点対象の例：

- not interested
- block author
- mute author
- report
- not dwelled

擬似的にはこう。

```text
score =
  P(favorite)       * w_favorite
+ P(reply)          * w_reply
+ P(retweet)        * w_retweet
+ P(click)          * w_click
+ P(dwell)          * w_dwell
+ P(follow_author)  * w_follow_author
- P(not_interested) * w_not_interested
- P(block_author)   * w_block
- P(mute_author)    * w_mute
- P(report)         * w_report
...
```

動画系の `vqv` は、動画時間条件を満たすときだけ重みが有効になる。引用動画にも別条件がある。

さらに、out-of-network候補には `OonWeightFactor` がかかる。新規ユーザーやトピックリクエストでは別の係数に切り替わる。

ここから読めるのは、For Youが「エンゲージなら何でもよい」ではないことだ。likeやreplyだけでなく、dwell、share、follow author、not interested、block、reportまでまとめて最適化している。

---

## 同じ作者の連投は減衰される

`RankingScorer` には author diversity が組み込まれている。

候補をweighted score順に並べ、同じ作者が何度目に出るかを数え、次のようなmultiplierをかける。

```text
multiplier = (1 - floor) * decay_factor^position + floor
```

position 0、つまりその作者の1本目はほぼそのまま。2本目以降は徐々に下がる。

これは、1人の強い作者がフィードを埋め尽くさないようにする仕組みだ。

投稿者目線では、短時間に連投してもすべてが同じ強さで出るとは限らない、という示唆になる。

---

## フィルタ：モデル以前・以後に厚い安全装置がある

`PhoenixCandidatePipeline` のfilter列を見ると、スコアリング前だけでもかなり多い。

- duplicate除去
- core data hydrate失敗除去
- age filter
- self tweet filter
- retweet deduplication
- subscription eligibility
- previously seen
- previously served
- muted keyword
- author socialgraph
- video filter
- topic filter
- new user topic filter

`AuthorSocialgraphFilter` は、viewerがブロック/ミュートしている作者、作者がviewerをブロックしているケース、引用元・RT元のブロック関係まで見て落とす。

`PreviouslySeenPostsFilter` は、リクエストに含まれるseen IDsとBloom filterを使う。つまり「すでに見たかもしれない投稿」を効率よく落とす。

最後のpost-selectionでは、`VFFilter` や `AncillaryVFFilter`、会話重複除去が入る。`VFFilter` はvisibility filteringの結果がdropなら落とす。

モデルが高スコアを付けても、フィルタで落ちるものは出ない。

---

## 広告ブレンド：ランキングの後に制約付きで混ぜる

`home-mixer/selectors/blender_selector.rs` では、FeedItemを以下に分けている。

- posts
- ads
- who to follow modules
- prompts
- push to home

その後、広告blenderを選び、postsとadsを混ぜ、promptsやWho to followを指定位置へ挿入する。

`SafeGapAdsBlender` と `ads/util.rs` を見ると、広告挿入にはかなり細かい制約がある。

- 投稿数が少ない場合は広告を入れない
- 広告間隔を計算する
- brand safety verdictがmedium riskの投稿の隣を避ける
- 低リスク広告と低リスク投稿の隣接制約
- 特定ハンドルやキーワードとの隣接回避
- 最後が広告になったら削除

広告は単純に「何件ごとに入れる」ではなく、brand safetyと隣接制約を見ている。

---

## Grox：投稿理解と安全性の非同期エンジン

`grox/` は、For You本体のranking pipelineとは別に、投稿理解系タスクを回すエンジンとして見える。

`PlanMaster` は複数planを同時に走らせる。

- initial banger
- post safety
- spam comment
- post embedding
- reply ranking
- safety PTOS

たとえば `PlanPostSafety` は、media hydration、post safety screen、Grok UPA action with labels、annotation upsertなどを依存関係付きで実行する。

つまりXの推薦は、ranking model単体ではなく、**投稿理解・安全性・埋め込み生成・スパム判定などのバックグラウンド処理が支えている**。

---

## 「手作り特徴量をなくした」はどこまで本当か

READMEには「hand-engineered featureをなくし、Grok-based transformerが重い仕事をする」とある。

これは、コンテンツ関連性の中心を手作り特徴量からsequence/embedding/Transformerへ寄せた、という意味ではかなり本当だと思う。

ただし、コードを見る限り、システム全体からheuristicやbusiness ruleが消えたわけではない。

- filter条件
- out-of-network係数
- new user条件
- video eligibility
- author diversity
- ads placement
- brand safety adjacency
- visibility filtering

などは明確に存在する。

したがって正確には、

> 関連性予測の主役はTransformerに寄せた。ただしプロダクトとしてのFor Youは、フィルタ・係数・安全性・広告制約と組み合わさっている。

という読み方がよい。

---

## 投稿者向けの実務的示唆

コードから直接「こうすれば必ず伸びる」とは言えない。重みの本番値も公開されていない。

それでも、設計から妥当な示唆はある。

### 1. likeだけでなく、複数行動を誘う投稿が強い

スコアリングはfavoriteだけではない。reply、retweet、click、dwell、share、follow authorなどが入る。

読まれる、返信される、保存/共有される、プロフィールを見られる、フォローされる。こうした複数行動が起きやすい投稿は強い。

### 2. ネガティブ反応を踏む投稿は危険

not interested、block、mute、reportは減点対象として明示されている。

釣り、煽り、文脈違い、嫌悪感を誘う投稿は短期的に反応を集めても、長期的には配信に悪影響を与える可能性が高い。

### 3. 同一作者の連投は減衰されうる

author diversityがあるため、強い投稿者でも同一レスポンス内で何本も出ると減衰する。

量で押すより、1本ごとの質とタイミングが重要。

### 4. 動画は独自シグナルを持つ

video quality viewやvideo duration条件がある。動画は単に再生されるだけでなく、品質の高い視聴が重要そうだ。

### 5. out-of-networkは「履歴との近さ」が鍵

Phoenix retrievalはユーザー履歴と候補投稿のembedding類似で候補を出す。

つまり、自分の投稿が届く相手は「フォロー外のランダムな大衆」ではなく、過去行動から見て近い人たち。誰のどんな履歴に刺さる投稿なのかが重要になる。

---

## この公開の限界

最後に、過大解釈しないための注意点。

- Rust側はそのままビルドできる形ではなさそう
- 本番のFeature Switch/Paramsの具体値は見えない
- 公開Phoenixはmini/frozen checkpoint
- artifactsはGit LFSで約2.9GB、clone直後にはpointerしかない
- productionはより大きいモデル、継続学習、内部サービス、リアルタイムデータに依存している

したがって、これは「完全な攻略本」ではない。

しかし、推薦システムの思想を読む資料としてはかなり濃い。

---

## まとめ

`xai-org/x-algorithm` から見えるXのFor Youは、次のようなシステムだ。

- Thunderがフォロー内の新鮮な投稿を供給する
- Phoenix retrievalがフォロー外候補を探す
- Phoenix rankingが複数行動確率を予測する
- RankingScorerがポジティブ/ネガティブ行動を重み付き合成する
- author diversityで同一作者の過剰露出を抑える
- filter群が安全性・既読・ブロック・ミュート・重複を制御する
- ads blenderがブランドセーフティを見ながら広告を混ぜる
- Groxが投稿理解や安全性処理を支える

一言でいうなら、XのFor Youは「バズ順」ではない。

**ユーザーの過去行動から、次に起こりそうな複数行動を予測し、安全性・多様性・広告制約を重ねたリアルタイム推薦システム**だ。

投稿者にとっての本質は、アルゴリズムを騙すことではなく、特定のユーザー群にとって本当に読みたくなる・反応したくなる・嫌がられない投稿を作ることだと思う。

---

## 参照した主なファイル

- `README.md`
- `phoenix/README.md`
- `phoenix/grok.py`
- `phoenix/recsys_model.py`
- `phoenix/run_pipeline.py`
- `candidate-pipeline/candidate_pipeline.rs`
- `home-mixer/candidate_pipeline/phoenix_candidate_pipeline.rs`
- `home-mixer/scorers/ranking_scorer.rs`
- `home-mixer/scorers/phoenix_scorer.rs`
- `home-mixer/scorers/vm_ranker.rs`
- `home-mixer/selectors/blender_selector.rs`
- `home-mixer/ads/util.rs`
- `home-mixer/sources/phoenix_source.rs`
- `home-mixer/sources/thunder_source.rs`
- `home-mixer/filters/author_socialgraph_filter.rs`
- `home-mixer/filters/previously_seen_posts_filter.rs`
- `home-mixer/filters/vf_filter.rs`
- `thunder/posts/post_store.rs`
- `thunder/thunder_service.rs`
- `grox/plans/plan_master.py`
- `grox/plans/plan_post_safety.py`
