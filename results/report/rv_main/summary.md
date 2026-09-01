本ベンチマークが判定するのは「**TimesFM 3.0 の下記指定構成が、本パネルの実務ベースラインに、指定タスク・指定窓で勝つか**」のみである。TSFM（時系列基盤モデル）一般の優劣、および商用導入可否（重みは非商用ライセンス）には及ばない。

学習済みの可能性があるため、本窓での TimesFM の勝ちは能力の証拠として報告しない。

# rv / main report

Run ID: `rv-main-e4320d20e90c`. 主指標: per-series QLIKE ratio vs EWMA.

## リーダーボード

凡例: ratio < 1 が基準より良い。

### h=1

| model | median ratio | mean ratio | win rate | series | fail | fail rate | rows used | fail reasons | runtime total (s) | runtime/origin (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| DVOL | 0.984374 | 0.984374 | 0.5 | 2 | 0 | 0 | 1205 | — | 90.6722 | 0.150368 |
| EWMA | 1 | 1 | 0 | 8 | 0 | 0 | 4608 | — | 26.2618 | 0.0434079 |
| GARCH | 0.911062 | 0.920848 | 0.875 | 8 | 0 | 0 | 4608 | — | 73.7653 | 0.121926 |
| GJR-GARCH | 0.829344 | 0.829344 | 1 | 1 | 0 | 0 | 403 | — | 5.06574 | 0.0125701 |
| HAR-RV | 0.77464 | 0.734296 | 1 | 8 | 0 | 0 | 4608 | — | 77.2163 | 0.12763 |
| LightGBM | 0.710251 | 0.7118 | 1 | 8 | 141 | 0.030599 | 4467 | insufficient_history=141 | 692.487 | 1.14461 |
| NaivePrev | 1.09621 | 1.04818 | 0.25 | 8 | 0 | 0 | 4608 | — | 13.1482 | 0.0217325 |
| TimesFM3-log | 0.693672 | 0.681499 | 1 | 8 | 0 | 0 | 4608 | — | 220.634 | 0.364684 |
| TimesFM3-raw | 0.810915 | 0.817276 | 1 | 8 | 21 | 0.00455729 | 4587 | nonpositive_forecast=21 | 215.152 | 0.355624 |

MDE footnote: MDE=0.114085 SD; standardized effect=-2.06991; MDE 以上.
MCS: ok; origins=604; mcs_universe=EWMA, GARCH, HAR-RV, LightGBM, NaivePrev, TimesFM3-log, TimesFM3-raw; excluded_partial_coverage=model=DVOL, reason=successful coverage missing for: RV_ADA, RV_DOGE, RV_LINK, RV_LTC, RV_N225_GK, RV_SOL, model=GJR-GARCH, reason=successful coverage missing for: RV_ADA, RV_BTC, RV_DOGE, RV_ETH, RV_LINK, RV_LTC, RV_SOL; included=TimesFM3-log; pvalues=NaivePrev=0, GARCH=0, EWMA=0, TimesFM3-raw=0, HAR-RV=0, LightGBM=0.1, TimesFM3-log=1.

### h=5

| model | median ratio | mean ratio | win rate | series | fail | fail rate | rows used | fail reasons | runtime total (s) | runtime/origin (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| DVOL | 0.87639 | 0.87639 | 1 | 2 | 5 | 0.0208333 | 235 | missing_actual=5 | 79.7646 | 0.367579 |
| EWMA | 1 | 1 | 0 | 8 | 24 | 0.0261438 | 894 | missing_actual=24 | 12.8349 | 0.0441062 |
| GARCH | 0.828019 | 0.832832 | 1 | 8 | 24 | 0.0261438 | 894 | missing_actual=24 | 53.7308 | 0.184642 |
| GJR-GARCH | 0.683547 | 0.683547 | 1 | 1 | 0 | 0 | 80 | — | 2.6327 | 0.0329088 |
| HAR-RV | 0.717914 | 0.697354 | 1 | 8 | 24 | 0.0261438 | 894 | missing_actual=24 | 66.2217 | 0.227566 |
| LightGBM | 0.871331 | 0.893924 | 0.75 | 8 | 52 | 0.0566449 | 866 | insufficient_history=28, missing_actual=24 | 653.747 | 2.24655 |
| NaivePrev | 0.953397 | 0.938922 | 0.625 | 8 | 24 | 0.0261438 | 894 | missing_actual=24 | 6.69165 | 0.0229954 |
| TimesFM3-log | 0.726471 | 0.731337 | 1 | 8 | 24 | 0.0261438 | 894 | missing_actual=24 | 106.33 | 0.365396 |
| TimesFM3-raw | 0.927889 | 0.922895 | 0.875 | 8 | 24 | 0.0261438 | 894 | missing_actual=24 | 102.971 | 0.353853 |

MDE footnote: MDE=0.166524 SD; standardized effect=-1.08154; MDE 以上.
MCS: ok; origins=262; mcs_universe=EWMA, GARCH, HAR-RV, LightGBM, NaivePrev, TimesFM3-log, TimesFM3-raw; excluded_partial_coverage=model=DVOL, reason=successful coverage missing for: RV_ADA, RV_DOGE, RV_LINK, RV_LTC, RV_N225_GK, RV_SOL, model=GJR-GARCH, reason=successful coverage missing for: RV_ADA, RV_BTC, RV_DOGE, RV_ETH, RV_LINK, RV_LTC, RV_SOL; included=HAR-RV; pvalues=NaivePrev=0, TimesFM3-raw=0.001, EWMA=0.001, LightGBM=0.001, GARCH=0.001, TimesFM3-log=0.043, HAR-RV=1.

### h=22

| model | median ratio | mean ratio | win rate | series | fail | fail rate | rows used | fail reasons | runtime total (s) | runtime/origin (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| DVOL | 0.477737 | 0.477737 | 1 | 2 | 7 | 0.12963 | 47 | missing_actual=7 | 9.50437 | 0.198008 |
| EWMA | 1 | 1 | 0 | 8 | 29 | 0.140777 | 177 | missing_actual=29 | 3.58985 | 0.0527919 |
| GARCH | 0.666575 | 0.677451 | 1 | 8 | 29 | 0.140777 | 177 | missing_actual=29 | 11.0223 | 0.162093 |
| GJR-GARCH | 0.493997 | 0.493997 | 1 | 1 | 0 | 0 | 18 | — | 0.363088 | 0.0201715 |
| HAR-RV | 0.617068 | 0.611947 | 1 | 8 | 29 | 0.140777 | 177 | missing_actual=29 | 11.0146 | 0.16198 |
| LightGBM | 0.742944 | 0.824774 | 0.875 | 8 | 32 | 0.15534 | 174 | missing_actual=29, insufficient_history=3 | 95.3223 | 1.4018 |
| NaivePrev | 0.703076 | 0.756081 | 0.75 | 8 | 29 | 0.140777 | 177 | missing_actual=29 | 1.62016 | 0.0238259 |
| TimesFM3-log | 0.545068 | 0.591648 | 1 | 8 | 29 | 0.140777 | 177 | missing_actual=29 | 25.0841 | 0.368884 |
| TimesFM3-raw | 0.881686 | 0.893237 | 0.625 | 8 | 29 | 0.140777 | 177 | missing_actual=29 | 25.1637 | 0.370054 |

MDE footnote: MDE=0.361592 SD; standardized effect=-0.411432; MDE 以上.
MCS: ok; origins=60; mcs_universe=EWMA, GARCH, HAR-RV, LightGBM, NaivePrev, TimesFM3-log, TimesFM3-raw; excluded_partial_coverage=model=DVOL, reason=successful coverage missing for: RV_ADA, RV_DOGE, RV_LINK, RV_LTC, RV_N225_GK, RV_SOL, model=GJR-GARCH, reason=successful coverage missing for: RV_ADA, RV_BTC, RV_DOGE, RV_ETH, RV_LINK, RV_LTC, RV_SOL; included=GARCH, HAR-RV, TimesFM3-log; pvalues=EWMA=0.001, TimesFM3-raw=0.002, LightGBM=0.062, NaivePrev=0.067, GARCH=0.465, TimesFM3-log=0.624, HAR-RV=1.

## 主要比較の二段階検定

| h | model | benchmark | mean dbar | sign p | Holm p | bootstrap CI low | bootstrap CI high | bootstrap p | MDE context |
|---|---|---|---|---|---|---|---|---|---|
| 1 | TimesFM3-raw | EWMA | -0.0690781 | 0.0078125 | 0.0234375 | -0.0923641 | -0.0497854 | 0.0009995 | MDE 以上 |
| 5 | TimesFM3-raw | EWMA | -0.0267276 | 0.0703125 | 0.140625 | -0.0444812 | -0.0116852 | 0.0009995 | MDE 以上 |
| 22 | TimesFM3-raw | EWMA | -0.027821 | 0.726562 | 0.726562 | -0.0703466 | 0.0146514 | 0.207896 | MDE 以上 |

符号凡例: d = TimesFM の損失 − 基準モデルの損失。mean dbar < 0 は TimesFM の損失が基準より小さい（勝ち）方向、> 0 は負け方向。

## 較正

### h1: 80% coverage

| model | overall | low vol | middle vol | high vol | n |
|---|---|---|---|---|---|
| DVOL | 0.79751 | 0.833333 | 0.778055 | 0.781095 | 1205 |
| EWMA | 0.820964 | 0.839844 | 0.824219 | 0.798828 | 4608 |
| GARCH | 0.801215 | 0.777344 | 0.813802 | 0.8125 | 4608 |
| GJR-GARCH | 0.761787 | 0.822222 | 0.746269 | 0.716418 | 403 |
| HAR-RV | 0.816189 | 0.829427 | 0.822266 | 0.796875 | 4608 |
| LightGBM | 0.512201 | 0.51041 | 0.537273 | 0.488919 | 4467 |
| NaivePrev | 0.810981 | 0.823568 | 0.83138 | 0.777995 | 4608 |
| TimesFM3-log | 0.78928 | 0.804688 | 0.786458 | 0.776693 | 4608 |
| TimesFM3-raw | 0.805973 | 0.828646 | 0.810334 | 0.77894 | 4587 |

WQL:

| model | WQL | n |
|---|---|---|
| DVOL | 0.456798 | 1205 |
| EWMA | 0.491274 | 4608 |
| GARCH | 0.471639 | 4608 |
| GJR-GARCH | 0.539853 | 403 |
| HAR-RV | 0.422104 | 4608 |
| LightGBM | 0.425423 | 4467 |
| NaivePrev | 0.529348 | 4608 |
| TimesFM3-log | 0.407246 | 4608 |
| TimesFM3-raw | 0.414319 | 4587 |

q10 → 10% VaR:

| model | series | n | violations | Kupiec p | Christoffersen ind p | Christoffersen cc p |
|---|---|---|---|---|---|---|
| DVOL | RV_BTC | 603 | 39 | 0.00212864 | 0.000418845 | 1.77225e-05 |
| DVOL | RV_ETH | 602 | 54 | 0.392125 | 0.000446647 | 0.00146008 |
| EWMA | RV_BTC | 603 | 46 | 0.0436515 | 0.0224603 | 0.00965885 |
| EWMA | RV_ETH | 602 | 56 | 0.564155 | 0.000244339 | 0.00101402 |
| EWMA | RV_N225_GK | 403 | 29 | 0.0493553 | 4.9996e-06 | 4.32831e-06 |
| GARCH | RV_BTC | 603 | 63 | 0.715766 | 1.63695e-05 | 8.68112e-05 |
| GARCH | RV_ETH | 602 | 59 | 0.870114 | 6.05942e-09 | 4.47973e-08 |
| GARCH | RV_N225_GK | 403 | 37 | 0.579002 | 0.0532717 | 0.132442 |
| GJR-GARCH | RV_N225_GK | 403 | 38 | 0.700078 | 0.814763 | 0.903354 |
| HAR-RV | RV_BTC | 603 | 59 | 0.85948 | 0.0490762 | 0.141984 |
| HAR-RV | RV_ETH | 602 | 51 | 0.200466 | 0.0401586 | 0.0536607 |
| HAR-RV | RV_N225_GK | 403 | 39 | 0.828282 | 0.505027 | 0.782155 |
| LightGBM | RV_BTC | 603 | 183 | 1.90149e-43 | 0.00511859 | 6.5788e-44 |
| LightGBM | RV_ETH | 602 | 160 | 9.85188e-31 | 0.00314751 | 1.83202e-31 |
| LightGBM | RV_N225_GK | 268 | 96 | 8.03164e-30 | 0.235065 | 5.68511e-29 |
| NaivePrev | RV_BTC | 603 | 62 | 0.818238 | 0.0277869 | 0.0865506 |
| NaivePrev | RV_ETH | 602 | 56 | 0.564155 | 0.0155781 | 0.0454464 |
| NaivePrev | RV_N225_GK | 403 | 43 | 0.657045 | 0.378853 | 0.615219 |
| TimesFM3-log | RV_BTC | 603 | 56 | 0.555148 | 0.545477 | 0.699893 |
| TimesFM3-log | RV_ETH | 602 | 63 | 0.705558 | 0.228865 | 0.451433 |
| TimesFM3-log | RV_N225_GK | 403 | 37 | 0.579002 | 0.805611 | 0.831764 |
| TimesFM3-raw | RV_BTC | 596 | 50 | 0.178804 | 0.678195 | 0.371632 |
| TimesFM3-raw | RV_ETH | 597 | 67 | 0.327703 | 0.51774 | 0.502493 |
| TimesFM3-raw | RV_N225_GK | 403 | 32 | 0.154311 | 0.763321 | 0.346493 |

### h5: 80% coverage

| model | overall | low vol | middle vol | high vol | n |
|---|---|---|---|---|---|
| DVOL | 0.8 | 0.886076 | 0.833333 | 0.679487 | 235 |
| EWMA | 0.85123 | 0.909396 | 0.879195 | 0.765101 | 894 |
| GARCH | 0.788591 | 0.714765 | 0.852349 | 0.798658 | 894 |
| GJR-GARCH | 0.7875 | 0.703704 | 0.884615 | 0.777778 | 80 |
| HAR-RV | 0.805369 | 0.775168 | 0.845638 | 0.795302 | 894 |
| LightGBM | 0.448037 | 0.394464 | 0.458333 | 0.491349 | 866 |
| NaivePrev | 0.825503 | 0.88255 | 0.852349 | 0.741611 | 894 |
| TimesFM3-log | 0.892617 | 0.939597 | 0.90604 | 0.832215 | 894 |
| TimesFM3-raw | 0.89821 | 0.926174 | 0.919463 | 0.848993 | 894 |

WQL:

| model | WQL | n |
|---|---|---|
| DVOL | 0.373936 | 235 |
| EWMA | 0.45598 | 894 |
| GARCH | 0.455287 | 894 |
| GJR-GARCH | 0.460962 | 80 |
| HAR-RV | 0.373756 | 894 |
| LightGBM | 0.388255 | 866 |
| NaivePrev | 0.482388 | 894 |
| TimesFM3-log | 0.370459 | 894 |
| TimesFM3-raw | 0.36938 | 894 |

## 診断

### 前半・後半

| h | period | model | win rate | median ratio | series |
|---|---|---|---|---|---|
| 1 | first_half | DVOL | 0.5 | 0.981893 | 2 |
| 1 | first_half | EWMA | 0 | 1 | 8 |
| 1 | first_half | GARCH | 1 | 0.867539 | 8 |
| 1 | first_half | GJR-GARCH | 1 | 0.636139 | 1 |
| 1 | first_half | HAR-RV | 1 | 0.779153 | 8 |
| 1 | first_half | LightGBM | 1 | 0.686145 | 8 |
| 1 | first_half | NaivePrev | 0.25 | 1.07393 | 8 |
| 1 | first_half | TimesFM3-log | 1 | 0.690386 | 8 |
| 1 | first_half | TimesFM3-raw | 1 | 0.816872 | 8 |
| 1 | second_half | DVOL | 0.5 | 0.992884 | 2 |
| 1 | second_half | EWMA | 0 | 1 | 8 |
| 1 | second_half | GARCH | 0.5 | 1.03699 | 8 |
| 1 | second_half | GJR-GARCH | 0 | 1.09877 | 1 |
| 1 | second_half | HAR-RV | 1 | 0.756876 | 8 |
| 1 | second_half | LightGBM | 0.875 | 0.653667 | 8 |
| 1 | second_half | NaivePrev | 0.375 | 1.10804 | 8 |
| 1 | second_half | TimesFM3-log | 1 | 0.675328 | 8 |
| 1 | second_half | TimesFM3-raw | 0.875 | 0.778388 | 8 |
| 5 | first_half | DVOL | 0.5 | 0.90693 | 2 |
| 5 | first_half | EWMA | 0 | 1 | 8 |
| 5 | first_half | GARCH | 1 | 0.826046 | 8 |
| 5 | first_half | GJR-GARCH | 1 | 0.552839 | 1 |
| 5 | first_half | HAR-RV | 1 | 0.707721 | 8 |
| 5 | first_half | LightGBM | 0.875 | 0.821353 | 8 |
| 5 | first_half | NaivePrev | 0.625 | 0.906375 | 8 |
| 5 | first_half | TimesFM3-log | 1 | 0.765252 | 8 |
| 5 | first_half | TimesFM3-raw | 0.375 | 1.01372 | 8 |
| 5 | second_half | DVOL | 1 | 0.842281 | 2 |
| 5 | second_half | EWMA | 0 | 1 | 8 |
| 5 | second_half | GARCH | 0.75 | 0.839321 | 8 |
| 5 | second_half | GJR-GARCH | 0 | 1.00706 | 1 |
| 5 | second_half | HAR-RV | 1 | 0.72304 | 8 |
| 5 | second_half | LightGBM | 0.375 | 1.06754 | 8 |
| 5 | second_half | NaivePrev | 0.5 | 0.98871 | 8 |
| 5 | second_half | TimesFM3-log | 1 | 0.733532 | 8 |
| 5 | second_half | TimesFM3-raw | 0.875 | 0.826293 | 8 |
| 22 | first_half | DVOL | 1 | 0.469607 | 2 |
| 22 | first_half | EWMA | 0 | 1 | 8 |
| 22 | first_half | GARCH | 0.875 | 0.711913 | 8 |
| 22 | first_half | GJR-GARCH | 1 | 0.421343 | 1 |
| 22 | first_half | HAR-RV | 1 | 0.582341 | 8 |
| 22 | first_half | LightGBM | 0.875 | 0.702247 | 8 |
| 22 | first_half | NaivePrev | 0.875 | 0.609105 | 8 |
| 22 | first_half | TimesFM3-log | 1 | 0.607016 | 8 |
| 22 | first_half | TimesFM3-raw | 0.5 | 1.02567 | 8 |
| 22 | second_half | DVOL | 1 | 0.484687 | 2 |
| 22 | second_half | EWMA | 0 | 1 | 8 |
| 22 | second_half | GARCH | 1 | 0.603534 | 8 |
| 22 | second_half | GJR-GARCH | 1 | 0.922649 | 1 |
| 22 | second_half | HAR-RV | 0.75 | 0.636367 | 8 |
| 22 | second_half | LightGBM | 0.75 | 0.728548 | 8 |
| 22 | second_half | NaivePrev | 0.75 | 0.835259 | 8 |
| 22 | second_half | TimesFM3-log | 0.875 | 0.485986 | 8 |
| 22 | second_half | TimesFM3-raw | 0.875 | 0.50978 | 8 |

### 系列グループ別

| h | group | model | median ratio | mean ratio | win rate | series |
|---|---|---|---|---|---|---|
| 1 | fx | DVOL | NA | NA | NA | 0 |
| 1 | fx | EWMA | NA | NA | NA | 0 |
| 1 | fx | GARCH | NA | NA | NA | 0 |
| 1 | fx | GJR-GARCH | NA | NA | NA | 0 |
| 1 | fx | HAR-RV | NA | NA | NA | 0 |
| 1 | fx | LightGBM | NA | NA | NA | 0 |
| 1 | fx | NaivePrev | NA | NA | NA | 0 |
| 1 | fx | TimesFM3-log | NA | NA | NA | 0 |
| 1 | fx | TimesFM3-raw | NA | NA | NA | 0 |
| 1 | rates | DVOL | NA | NA | NA | 0 |
| 1 | rates | EWMA | NA | NA | NA | 0 |
| 1 | rates | GARCH | NA | NA | NA | 0 |
| 1 | rates | GJR-GARCH | NA | NA | NA | 0 |
| 1 | rates | HAR-RV | NA | NA | NA | 0 |
| 1 | rates | LightGBM | NA | NA | NA | 0 |
| 1 | rates | NaivePrev | NA | NA | NA | 0 |
| 1 | rates | TimesFM3-log | NA | NA | NA | 0 |
| 1 | rates | TimesFM3-raw | NA | NA | NA | 0 |
| 1 | equity | DVOL | NA | NA | NA | 0 |
| 1 | equity | EWMA | 1 | 1 | 0 | 1 |
| 1 | equity | GARCH | 0.850343 | 0.850343 | 1 | 1 |
| 1 | equity | GJR-GARCH | 0.829344 | 0.829344 | 1 | 1 |
| 1 | equity | HAR-RV | 0.707695 | 0.707695 | 1 | 1 |
| 1 | equity | LightGBM | 0.791397 | 0.791397 | 1 | 1 |
| 1 | equity | NaivePrev | 1.14593 | 1.14593 | 0 | 1 |
| 1 | equity | TimesFM3-log | 0.687824 | 0.687824 | 1 | 1 |
| 1 | equity | TimesFM3-raw | 0.910918 | 0.910918 | 1 | 1 |
| 1 | crypto | DVOL | 0.984374 | 0.984374 | 0.5 | 2 |
| 1 | crypto | EWMA | 1 | 1 | 0 | 7 |
| 1 | crypto | GARCH | 0.91957 | 0.93092 | 0.857143 | 7 |
| 1 | crypto | GJR-GARCH | NA | NA | NA | 0 |
| 1 | crypto | HAR-RV | 0.775228 | 0.738097 | 1 | 7 |
| 1 | crypto | LightGBM | 0.700826 | 0.700429 | 1 | 7 |
| 1 | crypto | NaivePrev | 1.07746 | 1.03422 | 0.285714 | 7 |
| 1 | crypto | TimesFM3-log | 0.69952 | 0.680595 | 1 | 7 |
| 1 | crypto | TimesFM3-raw | 0.793752 | 0.803899 | 1 | 7 |
| 5 | fx | DVOL | NA | NA | NA | 0 |
| 5 | fx | EWMA | NA | NA | NA | 0 |
| 5 | fx | GARCH | NA | NA | NA | 0 |
| 5 | fx | GJR-GARCH | NA | NA | NA | 0 |
| 5 | fx | HAR-RV | NA | NA | NA | 0 |
| 5 | fx | LightGBM | NA | NA | NA | 0 |
| 5 | fx | NaivePrev | NA | NA | NA | 0 |
| 5 | fx | TimesFM3-log | NA | NA | NA | 0 |
| 5 | fx | TimesFM3-raw | NA | NA | NA | 0 |
| 5 | rates | DVOL | NA | NA | NA | 0 |
| 5 | rates | EWMA | NA | NA | NA | 0 |
| 5 | rates | GARCH | NA | NA | NA | 0 |
| 5 | rates | GJR-GARCH | NA | NA | NA | 0 |
| 5 | rates | HAR-RV | NA | NA | NA | 0 |
| 5 | rates | LightGBM | NA | NA | NA | 0 |
| 5 | rates | NaivePrev | NA | NA | NA | 0 |
| 5 | rates | TimesFM3-log | NA | NA | NA | 0 |
| 5 | rates | TimesFM3-raw | NA | NA | NA | 0 |
| 5 | equity | DVOL | NA | NA | NA | 0 |
| 5 | equity | EWMA | 1 | 1 | 0 | 1 |
| 5 | equity | GARCH | 0.747859 | 0.747859 | 1 | 1 |
| 5 | equity | GJR-GARCH | 0.683547 | 0.683547 | 1 | 1 |
| 5 | equity | HAR-RV | 0.58403 | 0.58403 | 1 | 1 |
| 5 | equity | LightGBM | 0.658639 | 0.658639 | 1 | 1 |
| 5 | equity | NaivePrev | 0.756119 | 0.756119 | 1 | 1 |
| 5 | equity | TimesFM3-log | 0.58437 | 0.58437 | 1 | 1 |
| 5 | equity | TimesFM3-raw | 0.961117 | 0.961117 | 1 | 1 |
| 5 | crypto | DVOL | 0.87639 | 0.87639 | 1 | 2 |
| 5 | crypto | EWMA | 1 | 1 | 0 | 7 |
| 5 | crypto | GARCH | 0.860833 | 0.844971 | 1 | 7 |
| 5 | crypto | GJR-GARCH | NA | NA | NA | 0 |
| 5 | crypto | HAR-RV | 0.738784 | 0.713544 | 1 | 7 |
| 5 | crypto | LightGBM | 0.954503 | 0.927536 | 0.714286 | 7 |
| 5 | crypto | NaivePrev | 0.985544 | 0.965037 | 0.571429 | 7 |
| 5 | crypto | TimesFM3-log | 0.727292 | 0.752332 | 1 | 7 |
| 5 | crypto | TimesFM3-raw | 0.9107 | 0.917434 | 0.857143 | 7 |
| 22 | fx | DVOL | NA | NA | NA | 0 |
| 22 | fx | EWMA | NA | NA | NA | 0 |
| 22 | fx | GARCH | NA | NA | NA | 0 |
| 22 | fx | GJR-GARCH | NA | NA | NA | 0 |
| 22 | fx | HAR-RV | NA | NA | NA | 0 |
| 22 | fx | LightGBM | NA | NA | NA | 0 |
| 22 | fx | NaivePrev | NA | NA | NA | 0 |
| 22 | fx | TimesFM3-log | NA | NA | NA | 0 |
| 22 | fx | TimesFM3-raw | NA | NA | NA | 0 |
| 22 | rates | DVOL | NA | NA | NA | 0 |
| 22 | rates | EWMA | NA | NA | NA | 0 |
| 22 | rates | GARCH | NA | NA | NA | 0 |
| 22 | rates | GJR-GARCH | NA | NA | NA | 0 |
| 22 | rates | HAR-RV | NA | NA | NA | 0 |
| 22 | rates | LightGBM | NA | NA | NA | 0 |
| 22 | rates | NaivePrev | NA | NA | NA | 0 |
| 22 | rates | TimesFM3-log | NA | NA | NA | 0 |
| 22 | rates | TimesFM3-raw | NA | NA | NA | 0 |
| 22 | equity | DVOL | NA | NA | NA | 0 |
| 22 | equity | EWMA | 1 | 1 | 0 | 1 |
| 22 | equity | GARCH | 0.503964 | 0.503964 | 1 | 1 |
| 22 | equity | GJR-GARCH | 0.493997 | 0.493997 | 1 | 1 |
| 22 | equity | HAR-RV | 0.623296 | 0.623296 | 1 | 1 |
| 22 | equity | LightGBM | 1.5013 | 1.5013 | 0 | 1 |
| 22 | equity | NaivePrev | 0.629004 | 0.629004 | 1 | 1 |
| 22 | equity | TimesFM3-log | 0.51395 | 0.51395 | 1 | 1 |
| 22 | equity | TimesFM3-raw | 1.20147 | 1.20147 | 0 | 1 |
| 22 | crypto | DVOL | 0.477737 | 0.477737 | 1 | 2 |
| 22 | crypto | EWMA | 1 | 1 | 0 | 7 |
| 22 | crypto | GARCH | 0.684056 | 0.702235 | 1 | 7 |
| 22 | crypto | GJR-GARCH | NA | NA | NA | 0 |
| 22 | crypto | HAR-RV | 0.61084 | 0.610326 | 1 | 7 |
| 22 | crypto | LightGBM | 0.715627 | 0.728127 | 1 | 7 |
| 22 | crypto | NaivePrev | 0.744488 | 0.774235 | 0.714286 | 7 |
| 22 | crypto | TimesFM3-log | 0.576187 | 0.602748 | 1 | 7 |
| 22 | crypto | TimesFM3-raw | 0.880575 | 0.849204 | 0.714286 | 7 |

### 管理通貨・XRP（本表から分離）

| h | series | model | ratio |
|---|---|---|---|
| 1 | RV_XRP | DVOL | NA |
| 1 | RV_XRP | EWMA | 1 |
| 1 | RV_XRP | GARCH | 0.800621 |
| 1 | RV_XRP | GJR-GARCH | NA |
| 1 | RV_XRP | HAR-RV | 0.772372 |
| 1 | RV_XRP | LightGBM | 0.92471 |
| 1 | RV_XRP | NaivePrev | 1.10913 |
| 1 | RV_XRP | TimesFM3-log | 0.838356 |
| 1 | RV_XRP | TimesFM3-raw | 1.02576 |
| 5 | RV_XRP | DVOL | NA |
| 5 | RV_XRP | EWMA | 1 |
| 5 | RV_XRP | GARCH | 0.683082 |
| 5 | RV_XRP | GJR-GARCH | NA |
| 5 | RV_XRP | HAR-RV | 0.67831 |
| 5 | RV_XRP | LightGBM | 0.95401 |
| 5 | RV_XRP | NaivePrev | 1.25439 |
| 5 | RV_XRP | TimesFM3-log | 0.915543 |
| 5 | RV_XRP | TimesFM3-raw | 1.04584 |
| 22 | RV_XRP | DVOL | NA |
| 22 | RV_XRP | EWMA | 1 |
| 22 | RV_XRP | GARCH | 0.624576 |
| 22 | RV_XRP | GJR-GARCH | NA |
| 22 | RV_XRP | HAR-RV | 0.509303 |
| 22 | RV_XRP | LightGBM | 0.709778 |
| 22 | RV_XRP | NaivePrev | 0.917606 |
| 22 | RV_XRP | TimesFM3-log | 0.648458 |
| 22 | RV_XRP | TimesFM3-raw | 0.939154 |

## 参考別掲（reference=True、本表・勝率・MCS から除外）

| h | model | median ratio | mean ratio | fail | rows used |
|---|---|---|---|---|---|
| — | NA | NA | NA | NA | NA |

## Manifest 照合

Status: **ok**

| model | expected rows | actual rows | match |
|---|---|---|---|
| DVOL | 1499 | 1499 | yes |
| EWMA | 6482 | 6482 | yes |
| GARCH | 6482 | 6482 | yes |
| GJR-GARCH | 501 | 501 | yes |
| HAR-RV | 6482 | 6482 | yes |
| LightGBM | 6482 | 6482 | yes |
| NaivePrev | 6482 | 6482 | yes |
| TimesFM3-log | 6482 | 6482 | yes |
| TimesFM3-raw | 6482 | 6482 | yes |
