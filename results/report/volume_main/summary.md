本ベンチマークが判定するのは「**TimesFM 3.0 の下記指定構成が、本パネルの実務ベースラインに、指定タスク・指定窓で勝つか**」のみである。TSFM（時系列基盤モデル）一般の優劣、および商用導入可否（重みは非商用ライセンス）には及ばない。

学習済みの可能性があるため、本窓での TimesFM の勝ちは能力の証拠として報告しない。

# volume / main report

Run ID: `volume-main-44c6d78ac972`. 主指標: per-series MAE ratio vs SeasonalNaive7.

## リーダーボード

凡例: ratio < 1 が基準より良い。

### h=1

| model | median ratio | mean ratio | win rate | series | fail | fail rate | rows used | fail reasons | runtime total (s) | runtime/origin (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| AutoETS | 0.647193 | 0.635234 | 1 | 7 | 0 | 0 | 854 | — | 592.656 | 4.85784 |
| AutoTheta | 0.648759 | 0.635766 | 1 | 7 | 0 | 0 | 854 | — | 337.267 | 2.76448 |
| LightGBM | 0.63877 | 0.642561 | 1 | 7 | 0 | 0 | 854 | — | 595.494 | 4.8811 |
| SeasonalMedian4 | 0.889192 | 0.895661 | 1 | 7 | 0 | 0 | 854 | — | 5.04719 | 0.0413704 |
| SeasonalNaive7 | 1 | 1 | 0 | 7 | 0 | 0 | 854 | — | 5.2232 | 0.0428131 |
| TimesFM3-log | 0.609469 | 0.608578 | 1 | 7 | 0 | 0 | 854 | — | 69.5446 | 0.570038 |
| TimesFM3-raw | 0.607311 | 0.607153 | 1 | 7 | 0 | 0 | 854 | — | 72.5311 | 0.594517 |

MDE footnote: MDE=0.255706 SD; standardized effect=-7.79871; MDE 以上.
MCS: ok; origins=122; mcs_universe=AutoETS, AutoTheta, LightGBM, SeasonalMedian4, SeasonalNaive7, TimesFM3-log, TimesFM3-raw; excluded_partial_coverage=—; included=TimesFM3-raw; pvalues=SeasonalNaive7=0, SeasonalMedian4=0, LightGBM=0, AutoETS=0.001, AutoTheta=0.001, TimesFM3-log=0.042, TimesFM3-raw=1.

### h=5

| model | median ratio | mean ratio | win rate | series | fail | fail rate | rows used | fail reasons | runtime total (s) | runtime/origin (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| AutoETS | 0.859428 | 0.859973 | 1 | 7 | 0 | 0 | 847 | — | 584.477 | 4.83039 |
| AutoTheta | 0.870652 | 0.864783 | 1 | 7 | 0 | 0 | 847 | — | 333.963 | 2.76003 |
| LightGBM | 0.794756 | 0.818076 | 1 | 7 | 0 | 0 | 847 | — | 592.46 | 4.89637 |
| SeasonalMedian4 | 0.903546 | 0.910841 | 1 | 7 | 0 | 0 | 847 | — | 5.02592 | 0.0415365 |
| SeasonalNaive7 | 1 | 1 | 0 | 7 | 0 | 0 | 847 | — | 5.19819 | 0.0429603 |
| TimesFM3-log | 0.784943 | 0.78815 | 1 | 7 | 0 | 0 | 847 | — | 68.9858 | 0.570131 |
| TimesFM3-raw | 0.786838 | 0.786947 | 1 | 7 | 0 | 0 | 847 | — | 71.8973 | 0.594193 |

MDE footnote: MDE=0.256778 SD; standardized effect=-4.52942; MDE 以上.
MCS: ok; origins=121; mcs_universe=AutoETS, AutoTheta, LightGBM, SeasonalMedian4, SeasonalNaive7, TimesFM3-log, TimesFM3-raw; excluded_partial_coverage=—; included=TimesFM3-log, TimesFM3-raw; pvalues=SeasonalNaive7=0, SeasonalMedian4=0, AutoTheta=0, AutoETS=0, LightGBM=0.014, TimesFM3-log=0.229, TimesFM3-raw=1.

## 主要比較の二段階検定

| h | model | benchmark | mean dbar | sign p | Holm p | bootstrap CI low | bootstrap CI high | bootstrap p | MDE context |
|---|---|---|---|---|---|---|---|---|---|
| 1 | TimesFM3-raw | SeasonalNaive7 | -0.194177 | 0.015625 | 0.03125 | -0.211548 | -0.177036 | 0.0009995 | MDE 以上 |
| 5 | TimesFM3-raw | SeasonalNaive7 | -0.101055 | 0.015625 | 0.03125 | -0.11582 | -0.0856846 | 0.0009995 | MDE 以上 |

符号凡例: d = TimesFM の損失 − 基準モデルの損失。mean dbar < 0 は TimesFM の損失が基準より小さい（勝ち）方向、> 0 は負け方向。

## 較正

### h1: 80% coverage

| model | overall | low vol | middle vol | high vol | n |
|---|---|---|---|---|---|
| AutoETS | 0.813817 | 0.859649 | 0.830986 | 0.750877 | 854 |
| AutoTheta | 0.816159 | 0.866667 | 0.823944 | 0.757895 | 854 |
| LightGBM | 0.566745 | 0.603509 | 0.570423 | 0.526316 | 854 |
| SeasonalMedian4 | 0.825527 | 0.814035 | 0.862676 | 0.8 | 854 |
| SeasonalNaive7 | 0.825527 | 0.814035 | 0.862676 | 0.8 | 854 |
| TimesFM3-log | 0.791569 | 0.810526 | 0.827465 | 0.736842 | 854 |
| TimesFM3-raw | 0.79274 | 0.810526 | 0.827465 | 0.740351 | 854 |

WQL:

| model | WQL | n |
|---|---|---|
| AutoETS | 0.0178195 | 854 |
| AutoTheta | 0.0178518 | 854 |
| LightGBM | 0.0189133 | 854 |
| SeasonalMedian4 | 0.0255795 | 854 |
| SeasonalNaive7 | 0.0255795 | 854 |
| TimesFM3-log | 0.0170513 | 854 |
| TimesFM3-raw | 0.0170291 | 854 |

### h5: 80% coverage

| model | overall | low vol | middle vol | high vol | n |
|---|---|---|---|---|---|
| AutoETS | 0.855962 | 0.897527 | 0.85461 | 0.815603 | 847 |
| AutoTheta | 0.838253 | 0.886926 | 0.833333 | 0.794326 | 847 |
| LightGBM | 0.596222 | 0.621908 | 0.553191 | 0.613475 | 847 |
| SeasonalMedian4 | 0.831169 | 0.823322 | 0.882979 | 0.787234 | 847 |
| SeasonalNaive7 | 0.831169 | 0.823322 | 0.882979 | 0.787234 | 847 |
| TimesFM3-log | 0.818182 | 0.830389 | 0.833333 | 0.79078 | 847 |
| TimesFM3-raw | 0.815821 | 0.830389 | 0.833333 | 0.783688 | 847 |

WQL:

| model | WQL | n |
|---|---|---|
| AutoETS | 0.022991 | 847 |
| AutoTheta | 0.0231647 | 847 |
| LightGBM | 0.0227339 | 847 |
| SeasonalMedian4 | 0.0248859 | 847 |
| SeasonalNaive7 | 0.0248859 | 847 |
| TimesFM3-log | 0.0205779 | 847 |
| TimesFM3-raw | 0.020581 | 847 |

## 診断

### 前半・後半

| h | period | model | win rate | median ratio | series |
|---|---|---|---|---|---|
| 1 | first_half | AutoETS | 1 | 0.68392 | 7 |
| 1 | first_half | AutoTheta | 1 | 0.656255 | 7 |
| 1 | first_half | LightGBM | 1 | 0.66701 | 7 |
| 1 | first_half | SeasonalMedian4 | 0.857143 | 0.861122 | 7 |
| 1 | first_half | SeasonalNaive7 | 0 | 1 | 7 |
| 1 | first_half | TimesFM3-log | 1 | 0.643137 | 7 |
| 1 | first_half | TimesFM3-raw | 1 | 0.639445 | 7 |
| 1 | second_half | AutoETS | 1 | 0.598663 | 7 |
| 1 | second_half | AutoTheta | 1 | 0.593376 | 7 |
| 1 | second_half | LightGBM | 1 | 0.624111 | 7 |
| 1 | second_half | SeasonalMedian4 | 1 | 0.899645 | 7 |
| 1 | second_half | SeasonalNaive7 | 0 | 1 | 7 |
| 1 | second_half | TimesFM3-log | 1 | 0.589946 | 7 |
| 1 | second_half | TimesFM3-raw | 1 | 0.589159 | 7 |
| 5 | first_half | AutoETS | 1 | 0.847736 | 7 |
| 5 | first_half | AutoTheta | 1 | 0.847735 | 7 |
| 5 | first_half | LightGBM | 1 | 0.773958 | 7 |
| 5 | first_half | SeasonalMedian4 | 1 | 0.936611 | 7 |
| 5 | first_half | SeasonalNaive7 | 0 | 1 | 7 |
| 5 | first_half | TimesFM3-log | 1 | 0.767498 | 7 |
| 5 | first_half | TimesFM3-raw | 1 | 0.767557 | 7 |
| 5 | second_half | AutoETS | 1 | 0.858664 | 7 |
| 5 | second_half | AutoTheta | 1 | 0.854601 | 7 |
| 5 | second_half | LightGBM | 1 | 0.83799 | 7 |
| 5 | second_half | SeasonalMedian4 | 1 | 0.929171 | 7 |
| 5 | second_half | SeasonalNaive7 | 0 | 1 | 7 |
| 5 | second_half | TimesFM3-log | 1 | 0.805903 | 7 |
| 5 | second_half | TimesFM3-raw | 1 | 0.803438 | 7 |

### 系列グループ別

| h | group | model | median ratio | mean ratio | win rate | series |
|---|---|---|---|---|---|---|
| 1 | fx | AutoETS | NA | NA | NA | 0 |
| 1 | fx | AutoTheta | NA | NA | NA | 0 |
| 1 | fx | LightGBM | NA | NA | NA | 0 |
| 1 | fx | SeasonalMedian4 | NA | NA | NA | 0 |
| 1 | fx | SeasonalNaive7 | NA | NA | NA | 0 |
| 1 | fx | TimesFM3-log | NA | NA | NA | 0 |
| 1 | fx | TimesFM3-raw | NA | NA | NA | 0 |
| 1 | rates | AutoETS | NA | NA | NA | 0 |
| 1 | rates | AutoTheta | NA | NA | NA | 0 |
| 1 | rates | LightGBM | NA | NA | NA | 0 |
| 1 | rates | SeasonalMedian4 | NA | NA | NA | 0 |
| 1 | rates | SeasonalNaive7 | NA | NA | NA | 0 |
| 1 | rates | TimesFM3-log | NA | NA | NA | 0 |
| 1 | rates | TimesFM3-raw | NA | NA | NA | 0 |
| 1 | equity | AutoETS | NA | NA | NA | 0 |
| 1 | equity | AutoTheta | NA | NA | NA | 0 |
| 1 | equity | LightGBM | NA | NA | NA | 0 |
| 1 | equity | SeasonalMedian4 | NA | NA | NA | 0 |
| 1 | equity | SeasonalNaive7 | NA | NA | NA | 0 |
| 1 | equity | TimesFM3-log | NA | NA | NA | 0 |
| 1 | equity | TimesFM3-raw | NA | NA | NA | 0 |
| 1 | crypto | AutoETS | 0.647193 | 0.635234 | 1 | 7 |
| 1 | crypto | AutoTheta | 0.648759 | 0.635766 | 1 | 7 |
| 1 | crypto | LightGBM | 0.63877 | 0.642561 | 1 | 7 |
| 1 | crypto | SeasonalMedian4 | 0.889192 | 0.895661 | 1 | 7 |
| 1 | crypto | SeasonalNaive7 | 1 | 1 | 0 | 7 |
| 1 | crypto | TimesFM3-log | 0.609469 | 0.608578 | 1 | 7 |
| 1 | crypto | TimesFM3-raw | 0.607311 | 0.607153 | 1 | 7 |
| 5 | fx | AutoETS | NA | NA | NA | 0 |
| 5 | fx | AutoTheta | NA | NA | NA | 0 |
| 5 | fx | LightGBM | NA | NA | NA | 0 |
| 5 | fx | SeasonalMedian4 | NA | NA | NA | 0 |
| 5 | fx | SeasonalNaive7 | NA | NA | NA | 0 |
| 5 | fx | TimesFM3-log | NA | NA | NA | 0 |
| 5 | fx | TimesFM3-raw | NA | NA | NA | 0 |
| 5 | rates | AutoETS | NA | NA | NA | 0 |
| 5 | rates | AutoTheta | NA | NA | NA | 0 |
| 5 | rates | LightGBM | NA | NA | NA | 0 |
| 5 | rates | SeasonalMedian4 | NA | NA | NA | 0 |
| 5 | rates | SeasonalNaive7 | NA | NA | NA | 0 |
| 5 | rates | TimesFM3-log | NA | NA | NA | 0 |
| 5 | rates | TimesFM3-raw | NA | NA | NA | 0 |
| 5 | equity | AutoETS | NA | NA | NA | 0 |
| 5 | equity | AutoTheta | NA | NA | NA | 0 |
| 5 | equity | LightGBM | NA | NA | NA | 0 |
| 5 | equity | SeasonalMedian4 | NA | NA | NA | 0 |
| 5 | equity | SeasonalNaive7 | NA | NA | NA | 0 |
| 5 | equity | TimesFM3-log | NA | NA | NA | 0 |
| 5 | equity | TimesFM3-raw | NA | NA | NA | 0 |
| 5 | crypto | AutoETS | 0.859428 | 0.859973 | 1 | 7 |
| 5 | crypto | AutoTheta | 0.870652 | 0.864783 | 1 | 7 |
| 5 | crypto | LightGBM | 0.794756 | 0.818076 | 1 | 7 |
| 5 | crypto | SeasonalMedian4 | 0.903546 | 0.910841 | 1 | 7 |
| 5 | crypto | SeasonalNaive7 | 1 | 1 | 0 | 7 |
| 5 | crypto | TimesFM3-log | 0.784943 | 0.78815 | 1 | 7 |
| 5 | crypto | TimesFM3-raw | 0.786838 | 0.786947 | 1 | 7 |

### 管理通貨・XRP（本表から分離）

| h | series | model | ratio |
|---|---|---|---|
| 1 | VOL_Coinbase_XRP-USD_base | AutoETS | 0.587969 |
| 1 | VOL_Coinbase_XRP-USD_base | AutoTheta | 0.591561 |
| 1 | VOL_Coinbase_XRP-USD_base | LightGBM | 0.603772 |
| 1 | VOL_Coinbase_XRP-USD_base | SeasonalMedian4 | 0.933871 |
| 1 | VOL_Coinbase_XRP-USD_base | SeasonalNaive7 | 1 |
| 1 | VOL_Coinbase_XRP-USD_base | TimesFM3-log | 0.57731 |
| 1 | VOL_Coinbase_XRP-USD_base | TimesFM3-raw | 0.574459 |
| 5 | VOL_Coinbase_XRP-USD_base | AutoETS | 0.81976 |
| 5 | VOL_Coinbase_XRP-USD_base | AutoTheta | 0.819993 |
| 5 | VOL_Coinbase_XRP-USD_base | LightGBM | 0.792627 |
| 5 | VOL_Coinbase_XRP-USD_base | SeasonalMedian4 | 0.875391 |
| 5 | VOL_Coinbase_XRP-USD_base | SeasonalNaive7 | 1 |
| 5 | VOL_Coinbase_XRP-USD_base | TimesFM3-log | 0.746002 |
| 5 | VOL_Coinbase_XRP-USD_base | TimesFM3-raw | 0.743257 |

## 参考別掲（reference=True、本表・勝率・MCS から除外）

| h | model | median ratio | mean ratio | fail | rows used |
|---|---|---|---|---|---|
| 1 | Prophet | 0.854225 | 0.854714 | 0 | 854 |
| 5 | Prophet | 0.942188 | 0.959884 | 0 | 847 |

## Manifest 照合

Status: **ok**

| model | expected rows | actual rows | match |
|---|---|---|---|
| AutoETS | 1944 | 1944 | yes |
| AutoTheta | 1944 | 1944 | yes |
| LightGBM | 1944 | 1944 | yes |
| Prophet | 1944 | 1944 | yes |
| SeasonalMedian4 | 1944 | 1944 | yes |
| SeasonalNaive7 | 1944 | 1944 | yes |
| TimesFM3-log | 1944 | 1944 | yes |
| TimesFM3-raw | 1944 | 1944 | yes |
