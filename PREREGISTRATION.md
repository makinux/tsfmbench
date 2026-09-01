# PREREGISTRATION — TimesFM 3.0 金融実務ベンチマーク

>（この日本語版が凍結された正本。英語の便宜訳: [PREREGISTRATION.en.md](PREREGISTRATION.en.md)）

作成日: 2026-09-01（本番ラン実行前に凍結。以後の変更は追記のみ・変更理由必須）

## 1. 主張範囲（レポート第一文に転記する）

本ベンチマークが判定するのは「**TimesFM 3.0 の下記指定構成が、本パネルの実務ベースラインに、指定タスク・指定窓で勝つか**」のみである。TSFM（時系列基盤モデル）一般の優劣、および商用導入可否（重みは非商用ライセンス）には及ばない。

**汚染に関する事前コミット**: TimesFM 3.0（2026-08-28 リリース）の学習データカットオフは非公開であり、メインテスト窓（2025-01-02〜2026-08-31）のデータは学習済みの可能性がある。したがって **メイン窓で TimesFM が勝った場合、それを予測能力の証拠として報告しない**。強い情報を持つのは (a) メイン窓での負け、(b) clean window（2026-08-31 以降、月次追試）の結果、(c) 合成 DGP・サロゲート実験のみである。

## 2. 被験モデル（凍結）

| モデル名 | 定義 |
|---|---|
| `TimesFM3-raw` | `google/timesfm-3.0-pytorch` に対象系列を raw のまま入力 |
| `TimesFM3-log` | log 変換入力・exp 逆変換に **pre-origin 残差のみ**の smearing 補正 |
| `TimesFM3-JGB-cov`（副次） | JGB 各年限を他 5 年限の past covariates 付きで予測 |

- 文脈長（凍結）: RV 系列・日次系列とも `min(len(context), 2048)`、暗号 RV は 1024
- 分位: ネイティブ 9 分位（0.1–0.9）。点予測: mean 列と median(=q50) 列を分離
- checkpoint の revision/hash・全 `ForecastConfig` 設定を results に記録
- raw / log は**別モデルとして両方報告**する。テスト結果を見て一方を選ぶ行為を禁止

## 3. 系列パネル（凍結）

- FX: ECB EUR レッグ 8 本（EURUSD, EURJPY, EURGBP, EURCHF, EURAUD; 管理・介入通貨として別掲: EURCNY, EURKRW, EURMXN）
- 金利: JGB 2/5/10/20/30/40y（bp 差分評価）
- 株式: 日経225（open-to-close トラック）
- 暗号: BTC, ETH, SOL, XRP, ADA, DOGE, LTC, LINK（Coinbase。XRP は 2023-08 再上場のため履歴短、meta に記録）
- RV: 暗号 = 5 分足実現分散（2026-09-01 に 2020 年までの深度を確認済み）、日経 = Garman-Klass
- 出来高: 暗号のみ、系列名 `Coinbase {X}-USD base volume`
- DVOL: BTC・ETH（Deribit、2022-01 からの深度を 2026-09-01 に確認済み → **採用**）

## 4. タスク・指標・検定（凍結）

- **Task P**: TOST 非劣性（margin: 対 RW 相対 MAE 1.05）を FX・株・暗号の主枠。優越検定は JGB のみ。h=1/5/20、origin 5 営業日毎。方向性は Pesaran–Timmermann（記述的）
- **Task V**: RV-only トラック。QLIKE（正値リンク必須・非正値は失敗集計）+ MSE/MAE。h=1（日次・確率評価フル）、h=5（5 営業日和・非重複 origin・確率評価フル）、h=22（22 営業日和・非重複 origin・**点 QLIKE のみ、記述的**）。分位のホライズン方向加算は全面禁止
- **Task U**: log1p 出来高。SeasonalNaive(7) / SeasonalMedian(4×同曜日) / MSTL / AutoETS / AutoTheta / LightGBM。Prophet は参考別掲のみ
- **主要比較（検定対象はこれのみ、族に Holm 補正）**: 各 task×h で `TimesFM3-raw` vs 基準（P: RW / V: EWMA(0.94) / U: SeasonalNaive(7)）
- DM: NW 自動帯域（下限 0・選択ラグ報告）、HLN の h は origin 単位。系列横断は二段階（系列毎 d̄ → 符号検定 + moving-block bootstrap）
- MCS（task×h、B=1000、α=0.10）は副解析
- 較正: 80% カバレッジ（全体 + ボラ三分位別）、q10 → 10% VaR の Kupiec + Christoffersen（BTC/ETH/日経）
- **実行前 MDE**: 本番前に origin 列から block bootstrap で MDE 曲線を算出し公表。80% 検出力の MDE が「対基準比 10%」を超えるセルは事前に記述的へ降格

## 5. ベースライン構成（凍結）

RW / SeasonalNaive / EWMA(λ=0.94) / GARCH(1,1) / GJR-GARCH（日経のみ）/ HAR-RV / AutoETS / AutoTheta / LightGBM（mlforecast、conformal 区間）/ DVOL 回帰（BTC・ETH、log RV_{t+h} = a + b·log DVOL_t）/ Prophet（参考別掲）。

- 学習系は**固定幅ローリング推定が主解析**: 暗号 1000 暦日 / 日経 400 営業日 / FX・JGB 1250 営業日。拡張窓は感度分析
- 全ハイパーパラメタ・特徴量・n_windows 等は **2024-12-31 以前の開発窓のみで決定し凍結**。本ファイルの §7 に決定値を追記してから本番を実行する
- GARCH は open-to-close リターンで推定し target と整合（c2c は感度分析）。リターン分位の二乗を RV 分位に流用することを禁止。GARCH/HAR の分位は pre-origin 残差較正

### 5.1 運用詳細（2026-09-01 事前凍結・実装仕様と同期）

- Task V の h=1 は**日次 origin**（検出力・較正曲線のため）。h=5/h=22 は非重複和 origin。学習系モデルの**再推定は 5 営業日毎**、間の日は直近パラメタ + 最新データによるフィルタリング予測
- GARCH/EWMA/Naive の RV 分位は、pre-origin ローリング窓内の (予測分散, 実現RV) 比率の経験分位で較正（ペア数 60 未満なら分位は出さない）。リターン分位の二乗を RV 分位に流用することは実装レベルで禁止
- HAR / DVOL 回帰 / LightGBM(RV・出来高) は log 空間で推定し、mean は smearing 補正 exp(μ̂+σ̂²/2)、median は exp(μ̂)、分位は経験残差分位
- LightGBM は 2 目的（L2 → mean 列、quantile α=0.5 → median 列）+ conformal（n_windows=10）を median モデルに適用
- TimesFM3-log の smearing σ̂² は開発窓（≤2024-12-31）で系列毎に推定し凍結
- DVOL 回帰の説明変数は x = log((DVOL/100)²/365)（日次分散スケール）
- 初期ハイパラ（開発窓で最終化し §7 に転記）: LightGBM num_leaves=31, lr=0.05, n_estimators=300, min_child_samples=20

## 6. 窓（凍結）

- 開発窓（チューニング・パイロット・実装検証）: 〜2024-12-31。**最終評価から除外**
- メインテスト窓: 2025-01-02〜2026-08-31
- clean window: 2026-09-01 以降の origin のみ。月次追試（初回の意味ある読みは 2026-12 頃）

## 7. 開発窓で凍結した決定値（本番前に追記）

（実装後、ここに LightGBM ハイパラ・特徴量リスト・conformal n_windows・固定窓幅の最終値・TimesFM ForecastConfig を記録してから本番ランを行う）

## 8. 逸脱記録

（本番開始後の一切の設計変更はここに日付・理由付きで追記）


- 2026-09-01: TimesFM3-log の smearing σ² を開発窓Δlog分散からモデル自身の log 分位幅（(q90−q10)/2.5631）による per-forecast 推定に変更（フォールバック: 従来方式）。理由: Δlog 分散はモデル残差分散の過大代理であり、逆変換バイアス補正として不正確なため。TimesFM3-log は本時点で未実行であり、テスト窓の結果を見た変更ではない。

### Stage 3 implementation-frozen values (2026-09-01; PREREGISTRATION section 7)

- LightGBM: `num_leaves=31`, `learning_rate=0.05`, `n_estimators=300`, `min_child_samples=20`.
- MLForecast conformal configuration: median/quantile-objective model, `PredictionIntervals(n_windows=10)`, central levels `[20, 40, 60, 80]`.
- LightGBM features: lags `1..14, 21, 28`, rolling means `7, 28`, weekday, month, and month-end flag.
- TimesFM 3: `per_core_batch_size=8`; RV context 1024; other contexts at most 2048; quantiles 0.1 through 0.9; offline checkpoint `google/timesfm-3.0-pytorch` (revision recorded per run).
