# tsfmbench — TimesFM 3.0 金融実務ベンチマーク

TimesFM 3.0（zero-shot 時系列基盤モデル）を、公式評価（GIFT-Eval / fev-bench / TIME）と重複しない金融市場データ上で、実務ベースライン（RW / EWMA / GARCH系 / HAR-RV / DVOL回帰 / LightGBM / 統計モデル）と比較する。設計は多モデル敵対的レビュー（Codex gpt-5.6 × Claude Opus、2ラウンド）を経て確定し、[PREREGISTRATION.md](PREREGISTRATION.md) に凍結されている。

**主張範囲**: 本ベンチが判定するのは「TimesFM 3.0 の指定構成が本パネルのベースラインに勝つか」のみ。TSFM 一般や商用導入可否（重みは非商用ライセンス）には及ばない。メイン窓（2025-01〜2026-08）はモデルの学習データに含まれる可能性があり、**勝ちは能力の証拠として報告しない**（負けと clean window のみ強い情報）。

## タスク

| タスク | 対象 | 基準 | 主損失 |
|---|---|---|---|
| P 価格 | FX 8 EURレッグ・JGB 6年限・日経225・暗号8 | RandomWalk | 対RW相対MAE（TOST非劣性） |
| V 実現ボラ | 暗号8×5分足RV・日経GK | EWMA(0.94) | QLIKE（対基準比のみ集計） |
| U 出来高 | Coinbase base volume 8 | SeasonalNaive(7) | 対基準相対MAE |

## 実行

```powershell
uv sync --all-extras
uv run tsfmbench probe                     # データソース到達性
uv run tsfmbench download                  # 全ソース取得（--update で差分）
uv run tsfmbench build                     # 正規化 parquet
uv run tsfmbench audit                     # データ監査（違反で exit 1）
uv run tsfmbench mde                       # 実行前検出力レポート
uv run tsfmbench run --task rv --window main
uv run tsfmbench report --task rv --window main
```

## 月次 clean-window 追試（汚染フリー評価、初回の意味ある読みは 2026-12 頃）

```powershell
uv run tsfmbench download --update
uv run tsfmbench build
uv run tsfmbench audit
uv run tsfmbench run --task rv --window clean
uv run tsfmbench run --task price --window clean
uv run tsfmbench run --task volume --window clean
uv run tsfmbench report --task rv --window clean
```

## Windows + プロキシ環境での注意

- uv 標準の python-build-standalone は、TLS 検査型プロキシ配下の Windows で `OPENSSL_Uplink: no OPENSSL_Applink` クラッシュを起こすことがある → python.org ビルドの 3.12 を使用（pyproject の `python-preference = "only-system"`）
- TLS 検査プロキシ配下では `system-certs = true`（uv）+ 実行時 `truststore` で OS の証明書ストアを信頼させる
- HF チェックポイントは `HF_HUB_OFFLINE=1` でキャッシュからロード（DL は torch 非依存プロセスで）
- 日経 raw CSV とモデル重みは再配布不可（git 外）

## 実装

コード生成は Codex (gpt-5.6) に委譲し、Claude (Fable 5) が仕様策定・レビュー・実行・検証を担当。設計の凍結内容と逸脱記録は [PREREGISTRATION.md](PREREGISTRATION.md)、経緯の読み物は [blog/](blog/timesfm3-finance-bench.md) を参照。テスト: `uv run pytest -q`（79 + slow 1）。
