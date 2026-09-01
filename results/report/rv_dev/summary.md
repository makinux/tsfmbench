本ベンチマークが判定するのは「**TimesFM 3.0 の下記指定構成が、本パネルの実務ベースラインに、指定タスク・指定窓で勝つか**」のみである。TSFM（時系列基盤モデル）一般の優劣、および商用導入可否（重みは非商用ライセンス）には及ばない。

開発窓 — 最終評価から除外、技術検証のみ。

# rv / dev report

Run ID: `rv-dev-7e5310b099c2`. 主指標: per-series QLIKE ratio vs EWMA.

## リーダーボード

### h=1

| model | median ratio | mean ratio | win rate | series | fail | rows used | fail reasons | runtime total (s) | runtime/origin (s) |
|---|---|---|---|---|---|---|---|---|---|
| EWMA | 1 | 1 | 0 | 8 | 1 | 11567 | insufficient_return_history=1 | 123.064 | 0.0679913 |
| NaivePrev | 0.946384 | 0.981353 | 0.625 | 8 | 0 | 11568 | — | 67.5283 | 0.0373085 |
| TimesFM3-raw | 0.83394 | 0.841339 | 1 | 8 | 60 | 11508 | nonpositive_forecast=60 | 406.281 | 0.224465 |

MDE footnote: MDE=0.0658868 SD; standardized effect=-2.1253; MDE 以上.
MCS: ok; origins=1810; included=TimesFM3-raw; pvalues=EWMA=0, NaivePrev=0, TimesFM3-raw=1.

### h=5

| model | median ratio | mean ratio | win rate | series | fail | rows used | fail reasons | runtime total (s) | runtime/origin (s) |
|---|---|---|---|---|---|---|---|---|---|
| EWMA | 1 | 1 | 0 | 8 | 103 | 2208 | missing_actual=102, insufficient_return_history=1 | 83.7557 | 0.0717086 |
| NaivePrev | 0.959703 | 1.00093 | 0.625 | 8 | 109 | 2202 | missing_actual=101, insufficient_history=8 | 46.8817 | 0.0401384 |
| TimesFM3-raw | 0.940066 | 0.987523 | 0.75 | 8 | 112 | 2199 | missing_actual=101, nonpositive_forecast=11 | 282.701 | 0.242039 |

MDE footnote: MDE=0.0841257 SD; standardized effect=-0.150592; MDE 以上.
MCS: ok; origins=1114; included=EWMA, NaivePrev, TimesFM3-raw; pvalues=NaivePrev=0.857, TimesFM3-raw=0.943, EWMA=1.

### h=22

| model | median ratio | mean ratio | win rate | series | fail | rows used | fail reasons | runtime total (s) | runtime/origin (s) |
|---|---|---|---|---|---|---|---|---|---|
| EWMA | 1 | 1 | 0 | 8 | 105 | 418 | missing_actual=104, insufficient_return_history=1 | 31.392 | 0.0754615 |
| NaivePrev | 0.896647 | 0.85633 | 0.625 | 8 | 109 | 414 | missing_actual=101, insufficient_history=8 | 17.2975 | 0.0415805 |
| TimesFM3-raw | 0.9792 | 1.01856 | 0.5 | 8 | 106 | 417 | missing_actual=102, nonpositive_forecast=4 | 102.634 | 0.246717 |

MDE footnote: MDE=0.153746 SD; standardized effect=-0.0479889; 検出力不足 — 判別不能.
MCS: ok; origins=336; included=NaivePrev; pvalues=EWMA=0.002, TimesFM3-raw=0.017, NaivePrev=1.

## 主要比較の二段階検定

| h | model | benchmark | mean dbar | sign p | Holm p | bootstrap CI low | bootstrap CI high | bootstrap p | MDE context |
|---|---|---|---|---|---|---|---|---|---|
| 1 | TimesFM3-raw | EWMA | -0.064656 | 0.0078125 | 0.0234375 | -0.0830093 | -0.0437914 | 0.0009995 | MDE 以上 |
| 5 | TimesFM3-raw | EWMA | -0.00568292 | 0.289062 | 0.578125 | -0.0264035 | 0.0210457 | 0.629685 | MDE 以上 |
| 22 | TimesFM3-raw | EWMA | -0.00544775 | 1 | 1 | -0.0776795 | 0.0752956 | 0.890555 | 検出力不足 — 判別不能 |

## 較正

### h1: 80% coverage

| model | overall | low vol | middle vol | high vol | n |
|---|---|---|---|---|---|
| EWMA | 0.799838 | 0.816437 | 0.816658 | 0.766423 | 11096 |
| NaivePrev | 0.786436 | 0.794372 | 0.788149 | 0.776786 | 11088 |
| TimesFM3-raw | 0.799096 | 0.81048 | 0.804484 | 0.782325 | 11508 |

WQL:

| model | WQL | n |
|---|---|---|
| EWMA | 0.536739 | 11096 |
| NaivePrev | 0.530588 | 11088 |
| TimesFM3-raw | 0.445635 | 11508 |

q10 → 10% VaR:

| model | series | n | violations | Kupiec p | Christoffersen ind p | Christoffersen cc p |
|---|---|---|---|---|---|---|
| EWMA | RV_BTC | 1749 | 191 | 0.205367 | 6.47622e-29 | 4.09417e-28 |
| EWMA | RV_ETH | 1748 | 179 | 0.738624 | 1.19641e-35 | 1.77877e-34 |
| EWMA | RV_N225_GK | 431 | 71 | 3.47795e-05 | 2.80163e-12 | 4.75364e-15 |
| NaivePrev | RV_BTC | 1748 | 200 | 0.0489871 | 2.03217e-05 | 1.64145e-05 |
| NaivePrev | RV_ETH | 1747 | 205 | 0.0183439 | 0.000105111 | 3.35388e-05 |
| NaivePrev | RV_N225_GK | 430 | 48 | 0.429208 | 0.000574219 | 0.00194721 |
| TimesFM3-raw | RV_BTC | 1791 | 163 | 0.198551 | 0.592207 | 0.3791 |
| TimesFM3-raw | RV_ETH | 1803 | 178 | 0.856448 | 0.501468 | 0.784839 |
| TimesFM3-raw | RV_N225_GK | 488 | 51 | 0.741559 | 0.225162 | 0.453861 |

### h5: 80% coverage

| model | overall | low vol | middle vol | high vol | n |
|---|---|---|---|---|---|
| EWMA | 0.830135 | 0.869712 | 0.876271 | 0.744501 | 1772 |
| NaivePrev | 0.79932 | 0.87585 | 0.85034 | 0.671769 | 1764 |
| TimesFM3-raw | 0.866758 | 0.942701 | 0.889495 | 0.768076 | 2199 |

WQL:

| model | WQL | n |
|---|---|---|
| EWMA | 0.472522 | 1772 |
| NaivePrev | 0.487516 | 1764 |
| TimesFM3-raw | 0.421359 | 2199 |

## 診断

### 前半・後半

| h | period | model | win rate | median ratio | series |
|---|---|---|---|---|---|
| 1 | first_half | EWMA | 0 | 1 | 7 |
| 1 | first_half | NaivePrev | 0.857143 | 0.906659 | 7 |
| 1 | first_half | TimesFM3-raw | 0.857143 | 0.821499 | 7 |
| 1 | second_half | EWMA | 0 | 1 | 8 |
| 1 | second_half | NaivePrev | 0.5 | 0.98334 | 8 |
| 1 | second_half | TimesFM3-raw | 1 | 0.852367 | 8 |
| 5 | first_half | EWMA | 0 | 1 | 7 |
| 5 | first_half | NaivePrev | 0.571429 | 0.918738 | 7 |
| 5 | first_half | TimesFM3-raw | 0.571429 | 0.978798 | 7 |
| 5 | second_half | EWMA | 0 | 1 | 8 |
| 5 | second_half | NaivePrev | 0.5 | 1.00436 | 8 |
| 5 | second_half | TimesFM3-raw | 0.625 | 0.938958 | 8 |
| 22 | first_half | EWMA | 0 | 1 | 7 |
| 22 | first_half | NaivePrev | 0.714286 | 0.792523 | 7 |
| 22 | first_half | TimesFM3-raw | 0.714286 | 0.912747 | 7 |
| 22 | second_half | EWMA | 0 | 1 | 8 |
| 22 | second_half | NaivePrev | 0.625 | 0.974097 | 8 |
| 22 | second_half | TimesFM3-raw | 0.375 | 1.12734 | 8 |

### 系列グループ別

| h | group | model | median ratio | mean ratio | win rate | series |
|---|---|---|---|---|---|---|
| 1 | fx | EWMA | NA | NA | NA | 0 |
| 1 | fx | NaivePrev | NA | NA | NA | 0 |
| 1 | fx | TimesFM3-raw | NA | NA | NA | 0 |
| 1 | rates | EWMA | NA | NA | NA | 0 |
| 1 | rates | NaivePrev | NA | NA | NA | 0 |
| 1 | rates | TimesFM3-raw | NA | NA | NA | 0 |
| 1 | equity | EWMA | 1 | 1 | 0 | 1 |
| 1 | equity | NaivePrev | 1.29312 | 1.29312 | 0 | 1 |
| 1 | equity | TimesFM3-raw | 0.868987 | 0.868987 | 1 | 1 |
| 1 | crypto | EWMA | 1 | 1 | 0 | 7 |
| 1 | crypto | NaivePrev | 0.933275 | 0.936815 | 0.714286 | 7 |
| 1 | crypto | TimesFM3-raw | 0.827701 | 0.837389 | 1 | 7 |
| 5 | fx | EWMA | NA | NA | NA | 0 |
| 5 | fx | NaivePrev | NA | NA | NA | 0 |
| 5 | fx | TimesFM3-raw | NA | NA | NA | 0 |
| 5 | rates | EWMA | NA | NA | NA | 0 |
| 5 | rates | NaivePrev | NA | NA | NA | 0 |
| 5 | rates | TimesFM3-raw | NA | NA | NA | 0 |
| 5 | equity | EWMA | 1 | 1 | 0 | 1 |
| 5 | equity | NaivePrev | 0.88448 | 0.88448 | 1 | 1 |
| 5 | equity | TimesFM3-raw | 0.933368 | 0.933368 | 1 | 1 |
| 5 | crypto | EWMA | 1 | 1 | 0 | 7 |
| 5 | crypto | NaivePrev | 0.989388 | 1.01756 | 0.571429 | 7 |
| 5 | crypto | TimesFM3-raw | 0.94196 | 0.99526 | 0.714286 | 7 |
| 22 | fx | EWMA | NA | NA | NA | 0 |
| 22 | fx | NaivePrev | NA | NA | NA | 0 |
| 22 | fx | TimesFM3-raw | NA | NA | NA | 0 |
| 22 | rates | EWMA | NA | NA | NA | 0 |
| 22 | rates | NaivePrev | NA | NA | NA | 0 |
| 22 | rates | TimesFM3-raw | NA | NA | NA | 0 |
| 22 | equity | EWMA | 1 | 1 | 0 | 1 |
| 22 | equity | NaivePrev | 1.00331 | 1.00331 | 0 | 1 |
| 22 | equity | TimesFM3-raw | 1.16813 | 1.16813 | 0 | 1 |
| 22 | crypto | EWMA | 1 | 1 | 0 | 7 |
| 22 | crypto | NaivePrev | 0.822515 | 0.835333 | 0.714286 | 7 |
| 22 | crypto | TimesFM3-raw | 0.909384 | 0.997194 | 0.571429 | 7 |

### 管理通貨・XRP（本表から分離）

| h | series | model | ratio |
|---|---|---|---|
| 1 | RV_XRP | EWMA | 1 |
| 1 | RV_XRP | NaivePrev | 0.846775 |
| 1 | RV_XRP | TimesFM3-raw | 0.794547 |
| 5 | RV_XRP | EWMA | 1 |
| 5 | RV_XRP | NaivePrev | 0.699215 |
| 5 | RV_XRP | TimesFM3-raw | 0.753347 |
| 22 | RV_XRP | EWMA | 1 |
| 22 | RV_XRP | NaivePrev | 0.742149 |
| 22 | RV_XRP | TimesFM3-raw | 0.786618 |

## 参考別掲（reference=True、本表・勝率・MCS から除外）

| h | model | median ratio | mean ratio | fail | rows used |
|---|---|---|---|---|---|
| — | NA | NA | NA | NA | NA |

## Manifest 照合

Status: **ok**

| model | expected rows | actual rows | match |
|---|---|---|---|
| EWMA | 15038 | 15038 | yes |
| NaivePrev | 15038 | 15038 | yes |
| TimesFM3-raw | 15038 | 15038 | yes |
