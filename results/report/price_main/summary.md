本ベンチマークが判定するのは「**TimesFM 3.0 の下記指定構成が、本パネルの実務ベースラインに、指定タスク・指定窓で勝つか**」のみである。TSFM（時系列基盤モデル）一般の優劣、および商用導入可否（重みは非商用ライセンス）には及ばない。

学習済みの可能性があるため、本窓での TimesFM の勝ちは能力の証拠として報告しない。

# price / main report

Run ID: `price-main-330da8e61162`. 主指標: per-series MAE ratio vs RW.

## リーダーボード

凡例: ratio < 1 が基準より良い。

### h=1

| model | median ratio | mean ratio | win rate | series | fail | fail rate | rows used | fail reasons | runtime total (s) | runtime/origin (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| AutoETS | 1.0006 | 0.999564 | 0.421053 | 19 | 0 | 0 | 1846 | — | 2183.28 | 9.02184 |
| AutoTheta | 0.998178 | 1.00238 | 0.526316 | 19 | 0 | 0 | 1846 | — | 483.567 | 1.99821 |
| LightGBM† | 34.8728 | 206.998 | 0 | 19 | 790 | 0.427952 | 1056 | insufficient_history=790 | 716.84 | 2.96215 |
| RW | 1 | 1 | 0 | 19 | 0 | 0 | 1846 | — | 58.1505 | 0.240291 |
| TimesFM3-log | 1.01734 | 1.02341 | 0.1875 | 16 | 243 | 0.131636 | 1603 | invalid_context=243 | 91.4294 | 0.377808 |
| TimesFM3-raw | 1.014 | 1.01759 | 0.263158 | 19 | 0 | 0 | 1846 | — | 101.126 | 0.417876 |

† 自動注記（機械的判定閾値: median ratio > 5 または fail率 > 40%）: この構成のこのタスクへの適用は不適切であることが実行結果から判明した（例: グローバル LightGBM をスケールの異なる価格レベルに適用）。事前登録により本番後の再設定は行わない。このモデルのこのタスクでの数値は『誤設定ベースライン』として解釈し、モデル一般の能力の証拠としないこと。

MDE footnote: MDE=0.180825 SD; standardized effect=0.232712; MDE 以上.
MCS: ok; origins=122; mcs_universe=AutoETS, AutoTheta, LightGBM, RW, TimesFM3-raw; excluded_partial_coverage=model=TimesFM3-log, reason=successful coverage missing for: JGB_10Y, JGB_2Y, JGB_5Y; included=AutoETS, AutoTheta, RW, TimesFM3-raw; pvalues=LightGBM=0.085, TimesFM3-raw=0.558, AutoETS=0.779, RW=0.885, AutoTheta=1.

### h=5

| model | median ratio | mean ratio | win rate | series | fail | fail rate | rows used | fail reasons | runtime total (s) | runtime/origin (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| AutoETS | 1.00024 | 0.996348 | 0.473684 | 19 | 0 | 0 | 1827 | — | 2152.67 | 8.96945 |
| AutoTheta | 1.00746 | 1.00008 | 0.368421 | 19 | 0 | 0 | 1827 | — | 480.968 | 2.00403 |
| LightGBM† | 8.83845 | 134.544 | 0 | 19 | 778 | 0.425835 | 1049 | insufficient_history=778 | 715.905 | 2.98294 |
| RW | 1 | 1 | 0 | 19 | 0 | 0 | 1827 | — | 57.879 | 0.241163 |
| TimesFM3-log | 1.01873 | 1.01346 | 0.1875 | 16 | 240 | 0.131363 | 1587 | invalid_context=240 | 90.3648 | 0.37652 |
| TimesFM3-raw | 1.01461 | 1.00829 | 0.315789 | 19 | 0 | 0 | 1827 | — | 100.04 | 0.416835 |

† 自動注記（機械的判定閾値: median ratio > 5 または fail率 > 40%）: この構成のこのタスクへの適用は不適切であることが実行結果から判明した（例: グローバル LightGBM をスケールの異なる価格レベルに適用）。事前登録により本番後の再設定は行わない。このモデルのこのタスクでの数値は『誤設定ベースライン』として解釈し、モデル一般の能力の証拠としないこと。

MDE footnote: MDE=0.181583 SD; standardized effect=0.321205; MDE 以上.
MCS: ok; origins=121; mcs_universe=AutoETS, AutoTheta, LightGBM, RW, TimesFM3-raw; excluded_partial_coverage=model=TimesFM3-log, reason=successful coverage missing for: JGB_10Y, JGB_2Y, JGB_5Y; included=AutoETS, AutoTheta, LightGBM, RW, TimesFM3-raw; pvalues=LightGBM=0.11, TimesFM3-raw=0.253, AutoTheta=0.345, AutoETS=0.345, RW=1.

### h=20

| model | median ratio | mean ratio | win rate | series | fail | fail rate | rows used | fail reasons | runtime total (s) | runtime/origin (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| AutoETS | 0.999644 | 0.97893 | 0.526316 | 19 | 0 | 0 | 1770 | — | 2085.39 | 8.91193 |
| AutoTheta | 1.00402 | 0.978681 | 0.421053 | 19 | 0 | 0 | 1770 | — | 474.176 | 2.02639 |
| LightGBM† | 6.44966 | 69.6402 | 0 | 19 | 747 | 0.422034 | 1023 | insufficient_history=747 | 710.503 | 3.03634 |
| RW | 1 | 1 | 0 | 19 | 0 | 0 | 1770 | — | 56.6441 | 0.242069 |
| TimesFM3-log | 1.01094 | 1.00148 | 0.375 | 16 | 231 | 0.130508 | 1539 | invalid_context=231 | 87.8108 | 0.37526 |
| TimesFM3-raw | 0.990666 | 0.980363 | 0.684211 | 19 | 0 | 0 | 1770 | — | 97.2692 | 0.41568 |

† 自動注記（機械的判定閾値: median ratio > 5 または fail率 > 40%）: この構成のこのタスクへの適用は不適切であることが実行結果から判明した（例: グローバル LightGBM をスケールの異なる価格レベルに適用）。事前登録により本番後の再設定は行わない。このモデルのこのタスクでの数値は『誤設定ベースライン』として解釈し、モデル一般の能力の証拠としないこと。

MDE footnote: MDE=0.372678 SD; standardized effect=0.310881; 検出力不足 — 判別不能.
MCS: ok; origins=118; mcs_universe=AutoETS, AutoTheta, LightGBM, RW, TimesFM3-raw; excluded_partial_coverage=model=TimesFM3-log, reason=successful coverage missing for: JGB_10Y, JGB_2Y, JGB_5Y; included=AutoETS, AutoTheta, RW, TimesFM3-raw; pvalues=LightGBM=0.098, TimesFM3-raw=0.315, AutoTheta=0.431, AutoETS=0.431, RW=1.

## 主要比較の二段階検定

| h | model | benchmark | mean dbar | sign p | Holm p | bootstrap CI low | bootstrap CI high | bootstrap p | MDE context |
|---|---|---|---|---|---|---|---|---|---|
| 1 | TimesFM3-raw | RW | 1.12105 | 0.0635681 | 0.190704 | -0.109589 | 3.41113 | 0.261869 | MDE 以上 |
| 5 | TimesFM3-raw | RW | 6.35045 | 0.167068 | 0.334137 | 0.0352727 | 16.5034 | 0.001999 | MDE 以上 |
| 20 | TimesFM3-raw | RW | 14.2578 | 0.167068 | 0.334137 | -0.613338 | 36.7709 | 0.245877 | 検出力不足 — 判別不能 |

符号凡例: d = TimesFM の損失 − 基準モデルの損失。mean dbar < 0 は TimesFM の損失が基準より小さい（勝ち）方向、> 0 は負け方向。

## 較正

### h1: 80% coverage

| model | overall | low vol | middle vol | high vol | n |
|---|---|---|---|---|---|
| AutoETS | 0.859697 | 0.88961 | 0.855285 | 0.834146 | 1846 |
| AutoTheta | 0.82286 | 0.904221 | 0.77561 | 0.788618 | 1846 |
| LightGBM | 0.371212 | 0.934659 | 0.173295 | 0.00568182 | 1056 |
| RW | 0.742145 | 0.839286 | 0.673171 | 0.713821 | 1846 |
| TimesFM3-log | 0.798503 | 0.814953 | 0.790262 | 0.790262 | 1603 |
| TimesFM3-raw | 0.801733 | 0.826299 | 0.79187 | 0.786992 | 1846 |

WQL:

| model | WQL | n |
|---|---|---|
| AutoETS | 0.0132474 | 1846 |
| AutoTheta | 0.0131306 | 1846 |
| LightGBM | 0.0292372 | 1056 |
| RW | 0.013412 | 1846 |
| TimesFM3-log | 0.0130892 | 1603 |
| TimesFM3-raw | 0.0132144 | 1846 |

### h5: 80% coverage

| model | overall | low vol | middle vol | high vol | n |
|---|---|---|---|---|---|
| AutoETS | 0.85769 | 0.891626 | 0.837438 | 0.844007 | 1827 |
| AutoTheta | 0.824849 | 0.889984 | 0.761905 | 0.82266 | 1827 |
| LightGBM | 0.375596 | 0.94 | 0.174785 | 0.0114286 | 1049 |
| RW | 0.749863 | 0.83908 | 0.650246 | 0.760263 | 1827 |
| TimesFM3-log | 0.819786 | 0.835539 | 0.78828 | 0.835539 | 1587 |
| TimesFM3-raw | 0.818829 | 0.844007 | 0.784893 | 0.827586 | 1827 |

WQL:

| model | WQL | n |
|---|---|---|
| AutoETS | 0.026097 | 1827 |
| AutoTheta | 0.0256046 | 1827 |
| LightGBM | 0.0517846 | 1049 |
| RW | 0.025856 | 1827 |
| TimesFM3-log | 0.0262162 | 1587 |
| TimesFM3-raw | 0.0260555 | 1827 |

### h20: 80% coverage

| model | overall | low vol | middle vol | high vol | n |
|---|---|---|---|---|---|
| AutoETS | 0.838418 | 0.889831 | 0.794915 | 0.830508 | 1770 |
| AutoTheta | 0.762147 | 0.862712 | 0.681356 | 0.742373 | 1770 |
| LightGBM | 0.352884 | 0.912023 | 0.146628 | 0 | 1023 |
| RW | 0.716949 | 0.816949 | 0.635593 | 0.698305 | 1770 |
| TimesFM3-log | 0.818713 | 0.82846 | 0.808967 | 0.818713 | 1539 |
| TimesFM3-raw | 0.802825 | 0.840678 | 0.771186 | 0.79661 | 1770 |

WQL:

| model | WQL | n |
|---|---|---|
| AutoETS | 0.0566385 | 1770 |
| AutoTheta | 0.0559176 | 1770 |
| LightGBM | 0.112604 | 1023 |
| RW | 0.0569076 | 1770 |
| TimesFM3-log | 0.0573283 | 1539 |
| TimesFM3-raw | 0.0561641 | 1770 |

## Task P 専用

### TOST 非劣性（margin 1.05）

| h | group | relative MAE | CI low | CI high | p | noninferior | n |
|---|---|---|---|---|---|---|---|
| 1 | fx | 1.01434 | 0.983083 | 1.04779 | 0.0314843 | yes | 425 |
| 1 | equity | 0.998161 | 0.965546 | 1.03425 | 0.00649675 | yes | 81 |
| 1 | crypto | 1.01415 | 0.993 | 1.03571 | 0.00349825 | yes | 854 |
| 5 | fx | 0.95018 | 0.911285 | 0.988599 | 0.00049975 | yes | 420 |
| 5 | equity | 1.03138 | 0.994909 | 1.10174 | 0.185407 | no | 80 |
| 5 | crypto | 1.02576 | 1.0023 | 1.05032 | 0.0464768 | no | 847 |
| 20 | fx | 0.997761 | 0.94198 | 1.03904 | 0.0664668 | yes | 405 |
| 20 | equity | 1.06039 | 1.00484 | 1.10167 | 0.790605 | no | 77 |
| 20 | crypto | 1.0148 | 0.9912 | 1.04362 | 0.009995 | yes | 826 |

### JGB 優越 DM

| h | series | DM stat | p | n |
|---|---|---|---|---|
| 1 | JGB_10Y | 2.60496 | 0.0109524 | 81 |
| 1 | JGB_20Y | 3.27268 | 0.00157417 | 81 |
| 1 | JGB_2Y | 1.76147 | 0.0819803 | 81 |
| 1 | JGB_30Y | 0.119781 | 0.904957 | 81 |
| 1 | JGB_40Y | -0.288575 | 0.773653 | 81 |
| 1 | JGB_5Y | 1.39355 | 0.167313 | 81 |
| 5 | JGB_10Y | 0.918849 | 0.360971 | 80 |
| 5 | JGB_20Y | -0.282475 | 0.778318 | 80 |
| 5 | JGB_2Y | -0.49201 | 0.624077 | 80 |
| 5 | JGB_30Y | 0.434251 | 0.66529 | 80 |
| 5 | JGB_40Y | 1.13801 | 0.258558 | 80 |
| 5 | JGB_5Y | -0.128369 | 0.898183 | 80 |
| 20 | JGB_10Y | -2.60785 | 0.0109637 | 77 |
| 20 | JGB_20Y | -2.27576 | 0.0256777 | 77 |
| 20 | JGB_2Y | -1.39379 | 0.167444 | 77 |
| 20 | JGB_30Y | -2.43937 | 0.0170449 | 77 |
| 20 | JGB_40Y | -1.74588 | 0.0848737 | 77 |
| 20 | JGB_5Y | -2.1851 | 0.0319636 | 77 |

符号凡例: DM 検定の d = TimesFM の損失 − 基準モデルの損失。DM stat < 0 は TimesFM の損失が基準より小さい（勝ち）方向、> 0 は負け方向。

### Pesaran–Timmermann（記述的）

| h | model | group | stat | p | hit rate | n |
|---|---|---|---|---|---|---|
| 1 | AutoETS | crypto | 1.7428 | 0.0813679 | 0.519906 | 854 |
| 1 | AutoETS | equity | 0.320269 | 0.748764 | 0.518519 | 81 |
| 1 | AutoETS | fx | -0.379926 | 0.704 | 0.491765 | 425 |
| 1 | AutoETS | rates | -1.54876 | 0.12144 | 0.516461 | 486 |
| 1 | AutoTheta | crypto | 2.2181 | 0.0265481 | 0.530445 | 854 |
| 1 | AutoTheta | equity | 0.579614 | 0.562175 | 0.530864 | 81 |
| 1 | AutoTheta | fx | -0.0525745 | 0.958071 | 0.498824 | 425 |
| 1 | AutoTheta | rates | 0.58072 | 0.561429 | 0.524691 | 486 |
| 1 | LightGBM | crypto | 1.96143 | 0.0498288 | 0.523419 | 854 |
| 1 | LightGBM | equity | -0.671937 | 0.501624 | 0.4375 | 16 |
| 1 | LightGBM | fx | -0.179644 | 0.857432 | 0.466667 | 90 |
| 1 | LightGBM | rates | 0.120772 | 0.903871 | 0.510417 | 96 |
| 1 | RW | crypto | NA | NA | 0.537471 | 854 |
| 1 | RW | equity | NA | NA | 0.506173 | 81 |
| 1 | RW | fx | NA | NA | 0.491765 | 425 |
| 1 | RW | rates | NA | NA | 0.450617 | 486 |
| 1 | TimesFM3-log | crypto | -1.59307 | 0.111145 | 0.48829 | 854 |
| 1 | TimesFM3-log | equity | 1.52225 | 0.127946 | 0.580247 | 81 |
| 1 | TimesFM3-log | fx | 1.38959 | 0.164653 | 0.527059 | 425 |
| 1 | TimesFM3-log | rates | -1.32093 | 0.186525 | 0.452675 | 243 |
| 1 | TimesFM3-raw | crypto | -0.51558 | 0.606148 | 0.515222 | 854 |
| 1 | TimesFM3-raw | equity | 1.01979 | 0.30783 | 0.555556 | 81 |
| 1 | TimesFM3-raw | fx | 0.899132 | 0.368582 | 0.515294 | 425 |
| 1 | TimesFM3-raw | rates | -2.09886 | 0.0358296 | 0.432099 | 486 |
| 5 | AutoETS | crypto | 0.575712 | 0.56481 | 0.493506 | 847 |
| 5 | AutoETS | equity | -1.02795e-15 | 1 | 0.4875 | 80 |
| 5 | AutoETS | fx | 0.402161 | 0.687565 | 0.514286 | 420 |
| 5 | AutoETS | rates | -0.967062 | 0.333513 | 0.558333 | 480 |
| 5 | AutoTheta | crypto | -2.46811 | 0.0135827 | 0.439197 | 847 |
| 5 | AutoTheta | equity | -1.40314 | 0.160574 | 0.4875 | 80 |
| 5 | AutoTheta | fx | 1.33038 | 0.183394 | 0.530952 | 420 |
| 5 | AutoTheta | rates | -0.819341 | 0.412592 | 0.56875 | 480 |
| 5 | LightGBM | crypto | -0.00945925 | 0.992453 | 0.4817 | 847 |
| 5 | LightGBM | equity | 0.52048 | 0.602729 | 0.5625 | 16 |
| 5 | LightGBM | fx | -2.97093 | 0.002969 | 0.388889 | 90 |
| 5 | LightGBM | rates | 1.43474 | 0.151362 | 0.604167 | 96 |
| 5 | RW | crypto | NA | NA | 0.558442 | 847 |
| 5 | RW | equity | NA | NA | 0.4 | 80 |
| 5 | RW | fx | NA | NA | 0.464286 | 420 |
| 5 | RW | rates | NA | NA | 0.408333 | 480 |
| 5 | TimesFM3-log | crypto | -1.53457 | 0.124888 | 0.492326 | 847 |
| 5 | TimesFM3-log | equity | 0.0937573 | 0.925302 | 0.525 | 80 |
| 5 | TimesFM3-log | fx | 1.32151 | 0.186332 | 0.519048 | 420 |
| 5 | TimesFM3-log | rates | -1.21626 | 0.223885 | 0.466667 | 240 |
| 5 | TimesFM3-raw | crypto | -0.667359 | 0.504543 | 0.519481 | 847 |
| 5 | TimesFM3-raw | equity | -0.0919781 | 0.926715 | 0.5 | 80 |
| 5 | TimesFM3-raw | fx | 0.845497 | 0.397833 | 0.504762 | 420 |
| 5 | TimesFM3-raw | rates | -0.216686 | 0.828453 | 0.516667 | 480 |
| 20 | AutoETS | crypto | -0.458543 | 0.646562 | 0.470944 | 826 |
| 20 | AutoETS | equity | -1.28121 | 0.20012 | 0.415584 | 77 |
| 20 | AutoETS | fx | -0.847097 | 0.396941 | 0.48642 | 405 |
| 20 | AutoETS | rates | -0.449233 | 0.653264 | 0.714286 | 462 |
| 20 | AutoTheta | crypto | -3.35809 | 0.000784821 | 0.403148 | 826 |
| 20 | AutoTheta | equity | -1.1414 | 0.253704 | 0.623377 | 77 |
| 20 | AutoTheta | fx | 0.947382 | 0.343444 | 0.520988 | 405 |
| 20 | AutoTheta | rates | NA | NA | 0.78355 | 462 |
| 20 | LightGBM | crypto | -2.26994 | 0.0232111 | 0.427361 | 826 |
| 20 | LightGBM | equity | 0.143829 | 0.885635 | 0.5625 | 16 |
| 20 | LightGBM | fx | -1.42643 | 0.153743 | 0.470588 | 85 |
| 20 | LightGBM | rates | -1.85448 | 0.0636707 | 0.541667 | 96 |
| 20 | RW | crypto | 0 | 1 | 0.579903 | 826 |
| 20 | RW | equity | NA | NA | 0.298701 | 77 |
| 20 | RW | fx | NA | NA | 0.449383 | 405 |
| 20 | RW | rates | NA | NA | 0.21645 | 462 |
| 20 | TimesFM3-log | crypto | -0.656236 | 0.511672 | 0.495157 | 826 |
| 20 | TimesFM3-log | equity | -1.12827 | 0.259205 | 0.545455 | 77 |
| 20 | TimesFM3-log | fx | 0.686982 | 0.492094 | 0.496296 | 405 |
| 20 | TimesFM3-log | rates | -1.1033 | 0.269898 | 0.753247 | 231 |
| 20 | TimesFM3-raw | crypto | 2.53908 | 0.0111143 | 0.571429 | 826 |
| 20 | TimesFM3-raw | equity | -2.45987 | 0.0138989 | 0.402597 | 77 |
| 20 | TimesFM3-raw | fx | 0.816046 | 0.414474 | 0.496296 | 405 |
| 20 | TimesFM3-raw | rates | -1.6281 | 0.103504 | 0.74026 | 462 |

## 診断

### TimesFM3-log 系列数差異

| h | model | series | other-model max series | invalid_context failures | reason |
|---|---|---|---|---|---|
| 1 | TimesFM3-log | 16 | 19 | 243 | fail_reasons=invalid_context が 243 件。log 定義不能（非正値を含む金利系列等）のコンテキストは失敗会計となるため。 |
| 5 | TimesFM3-log | 16 | 19 | 240 | fail_reasons=invalid_context が 240 件。log 定義不能（非正値を含む金利系列等）のコンテキストは失敗会計となるため。 |
| 20 | TimesFM3-log | 16 | 19 | 231 | fail_reasons=invalid_context が 231 件。log 定義不能（非正値を含む金利系列等）のコンテキストは失敗会計となるため。 |

### 前半・後半

| h | period | model | win rate | median ratio | series |
|---|---|---|---|---|---|
| 1 | first_half | AutoETS | 0.421053 | 1.00101 | 19 |
| 1 | first_half | AutoTheta | 0.421053 | 1.00167 | 19 |
| 1 | first_half | LightGBM | 0 | 43.8657 | 19 |
| 1 | first_half | RW | 0 | 1 | 19 |
| 1 | first_half | TimesFM3-log | 0.1875 | 1.02505 | 16 |
| 1 | first_half | TimesFM3-raw | 0.210526 | 1.02555 | 19 |
| 1 | second_half | AutoETS | 0.473684 | 1.00013 | 19 |
| 1 | second_half | AutoTheta | 0.315789 | 1.01007 | 19 |
| 1 | second_half | LightGBM | 0 | 28.6366 | 19 |
| 1 | second_half | RW | 0 | 1 | 19 |
| 1 | second_half | TimesFM3-log | 0.4375 | 1.00769 | 16 |
| 1 | second_half | TimesFM3-raw | 0.315789 | 1.00695 | 19 |
| 5 | first_half | AutoETS | 0.421053 | 1.0002 | 19 |
| 5 | first_half | AutoTheta | 0.526316 | 0.999891 | 19 |
| 5 | first_half | LightGBM | 0 | 11.2955 | 19 |
| 5 | first_half | RW | 0 | 1 | 19 |
| 5 | first_half | TimesFM3-log | 0.1875 | 1.02594 | 16 |
| 5 | first_half | TimesFM3-raw | 0.157895 | 1.02694 | 19 |
| 5 | second_half | AutoETS | 0.526316 | 0.99993 | 19 |
| 5 | second_half | AutoTheta | 0.315789 | 1.01267 | 19 |
| 5 | second_half | LightGBM | 0 | 11.7337 | 19 |
| 5 | second_half | RW | 0 | 1 | 19 |
| 5 | second_half | TimesFM3-log | 0.375 | 1.00466 | 16 |
| 5 | second_half | TimesFM3-raw | 0.684211 | 0.992799 | 19 |
| 20 | first_half | AutoETS | 0.578947 | 0.999632 | 19 |
| 20 | first_half | AutoTheta | 0.473684 | 1.0012 | 19 |
| 20 | first_half | LightGBM | 0 | 6.22613 | 19 |
| 20 | first_half | RW | 0 | 1 | 19 |
| 20 | first_half | TimesFM3-log | 0.375 | 1.00553 | 16 |
| 20 | first_half | TimesFM3-raw | 0.631579 | 0.993298 | 19 |
| 20 | second_half | AutoETS | 0.526316 | 0.99966 | 19 |
| 20 | second_half | AutoTheta | 0.473684 | 1.00054 | 19 |
| 20 | second_half | LightGBM | 0 | 8.82048 | 19 |
| 20 | second_half | RW | 0 | 1 | 19 |
| 20 | second_half | TimesFM3-log | 0.4375 | 1.0067 | 16 |
| 20 | second_half | TimesFM3-raw | 0.736842 | 0.98214 | 19 |

### 系列グループ別

| h | group | model | median ratio | mean ratio | win rate | series |
|---|---|---|---|---|---|---|
| 1 | fx | AutoETS | 0.998639 | 0.99815 | 0.6 | 5 |
| 1 | fx | AutoTheta | 1.00482 | 1.00444 | 0.4 | 5 |
| 1 | fx | LightGBM | 372.509 | 562.781 | 0 | 5 |
| 1 | fx | RW | 1 | 1 | 0 | 5 |
| 1 | fx | TimesFM3-log | 1.01454 | 1.02074 | 0.2 | 5 |
| 1 | fx | TimesFM3-raw | 1.014 | 1.02166 | 0.2 | 5 |
| 1 | rates | AutoETS | 0.996109 | 0.997103 | 0.666667 | 6 |
| 1 | rates | AutoTheta | 1.00471 | 1.00737 | 0.5 | 6 |
| 1 | rates | LightGBM | 35.8702 | 38.8195 | 0 | 6 |
| 1 | rates | RW | 1 | 1 | 0 | 6 |
| 1 | rates | TimesFM3-log | 1.05428 | 1.05329 | 0 | 3 |
| 1 | rates | TimesFM3-raw | 1.0374 | 1.02855 | 0.166667 | 6 |
| 1 | equity | AutoETS | 1.00085 | 1.00085 | 0 | 1 |
| 1 | equity | AutoTheta | 0.989879 | 0.989879 | 1 | 1 |
| 1 | equity | LightGBM | 1.45424 | 1.45424 | 0 | 1 |
| 1 | equity | RW | 1 | 1 | 0 | 1 |
| 1 | equity | TimesFM3-log | 0.996414 | 0.996414 | 1 | 1 |
| 1 | equity | TimesFM3-raw | 0.998161 | 0.998161 | 1 | 1 |
| 1 | crypto | AutoETS | 1.00294 | 1.0025 | 0.142857 | 7 |
| 1 | crypto | AutoTheta | 0.997191 | 0.998427 | 0.571429 | 7 |
| 1 | crypto | LightGBM | 1.63669 | 126.384 | 0 | 7 |
| 1 | crypto | RW | 1 | 1 | 0 | 7 |
| 1 | crypto | TimesFM3-log | 1.01524 | 1.01638 | 0.142857 | 7 |
| 1 | crypto | TimesFM3-raw | 1.01045 | 1.00808 | 0.285714 | 7 |
| 5 | fx | AutoETS | 0.997855 | 0.995132 | 0.6 | 5 |
| 5 | fx | AutoTheta | 0.998931 | 0.995506 | 0.6 | 5 |
| 5 | fx | LightGBM | 407.845 | 393.543 | 0 | 5 |
| 5 | fx | RW | 1 | 1 | 0 | 5 |
| 5 | fx | TimesFM3-log | 1.01549 | 1.00659 | 0.2 | 5 |
| 5 | fx | TimesFM3-raw | 1.01725 | 1.00854 | 0.2 | 5 |
| 5 | rates | AutoETS | 0.991595 | 0.985628 | 0.833333 | 6 |
| 5 | rates | AutoTheta | 0.996609 | 0.993463 | 0.5 | 6 |
| 5 | rates | LightGBM | 11.0504 | 15.2832 | 0 | 6 |
| 5 | rates | RW | 1 | 1 | 0 | 6 |
| 5 | rates | TimesFM3-log | 1.01907 | 1.01635 | 0 | 3 |
| 5 | rates | TimesFM3-raw | 1.00203 | 1.00421 | 0.5 | 6 |
| 5 | equity | AutoETS | 1.00252 | 1.00252 | 0 | 1 |
| 5 | equity | AutoTheta | 0.984336 | 0.984336 | 1 | 1 |
| 5 | equity | LightGBM | 1.33925 | 1.33925 | 0 | 1 |
| 5 | equity | RW | 1 | 1 | 0 | 1 |
| 5 | equity | TimesFM3-log | 1.02877 | 1.02877 | 0 | 1 |
| 5 | equity | TimesFM3-raw | 1.03138 | 1.03138 | 0 | 1 |
| 5 | crypto | AutoETS | 1.00563 | 1.00552 | 0.142857 | 7 |
| 5 | crypto | AutoTheta | 1.01175 | 1.01126 | 0 | 7 |
| 5 | crypto | LightGBM | 1.53996 | 70.7981 | 0 | 7 |
| 5 | crypto | RW | 1 | 1 | 0 | 7 |
| 5 | crypto | TimesFM3-log | 1.01839 | 1.01495 | 0.285714 | 7 |
| 5 | crypto | TimesFM3-raw | 1.01652 | 1.00832 | 0.285714 | 7 |
| 20 | fx | AutoETS | 1.00016 | 1.00216 | 0.4 | 5 |
| 20 | fx | AutoTheta | 1.00702 | 0.993148 | 0.2 | 5 |
| 20 | fx | LightGBM | 147.742 | 199.999 | 0 | 5 |
| 20 | fx | RW | 1 | 1 | 0 | 5 |
| 20 | fx | TimesFM3-log | 1.00621 | 1.02233 | 0.4 | 5 |
| 20 | fx | TimesFM3-raw | 1.02345 | 1.02119 | 0.4 | 5 |
| 20 | rates | AutoETS | 0.912562 | 0.916826 | 1 | 6 |
| 20 | rates | AutoTheta | 0.917024 | 0.92105 | 1 | 6 |
| 20 | rates | LightGBM | 6.44212 | 8.64159 | 0 | 6 |
| 20 | rates | RW | 1 | 1 | 0 | 6 |
| 20 | rates | TimesFM3-log | 0.912012 | 0.91501 | 1 | 3 |
| 20 | rates | TimesFM3-raw | 0.922138 | 0.926858 | 1 | 6 |
| 20 | equity | AutoETS | 1.00597 | 1.00597 | 0 | 1 |
| 20 | equity | AutoTheta | 0.968093 | 0.968093 | 1 | 1 |
| 20 | equity | LightGBM | 2.18085 | 2.18085 | 0 | 1 |
| 20 | equity | RW | 1 | 1 | 0 | 1 |
| 20 | equity | TimesFM3-log | 1.03811 | 1.03811 | 0 | 1 |
| 20 | equity | TimesFM3-raw | 1.06039 | 1.06039 | 0 | 1 |
| 20 | crypto | AutoETS | 1.00398 | 1.01171 | 0.285714 | 7 |
| 20 | crypto | AutoTheta | 1.01997 | 1.01926 | 0 | 7 |
| 20 | crypto | LightGBM | 1.50952 | 38.4484 | 0 | 7 |
| 20 | crypto | RW | 1 | 1 | 0 | 7 |
| 20 | crypto | TimesFM3-log | 1.02276 | 1.01841 | 0.142857 | 7 |
| 20 | crypto | TimesFM3-raw | 0.996018 | 0.985631 | 0.714286 | 7 |

### 管理通貨・XRP（本表から分離）

| h | series | model | ratio |
|---|---|---|---|
| 1 | EURCNY | AutoETS | 0.99491 |
| 1 | EURCNY | AutoTheta | 1.00001 |
| 1 | EURCNY | LightGBM | 9.23616 |
| 1 | EURCNY | RW | 1 |
| 1 | EURCNY | TimesFM3-log | 1.0155 |
| 1 | EURCNY | TimesFM3-raw | 1.01869 |
| 1 | EURKRW | AutoETS | 1.00007 |
| 1 | EURKRW | AutoTheta | 1.01163 |
| 1 | EURKRW | LightGBM | 2.69895 |
| 1 | EURKRW | RW | 1 |
| 1 | EURKRW | TimesFM3-log | 1.01298 |
| 1 | EURKRW | TimesFM3-raw | 1.01999 |
| 1 | EURMXN | AutoETS | 1.00758 |
| 1 | EURMXN | AutoTheta | 1.01369 |
| 1 | EURMXN | LightGBM | 5.17446 |
| 1 | EURMXN | RW | 1 |
| 1 | EURMXN | TimesFM3-log | 1.0011 |
| 1 | EURMXN | TimesFM3-raw | 1.00084 |
| 1 | XRP-USD | AutoETS | 1.01079 |
| 1 | XRP-USD | AutoTheta | 1.00243 |
| 1 | XRP-USD | LightGBM | 40.7248 |
| 1 | XRP-USD | RW | 1 |
| 1 | XRP-USD | TimesFM3-log | 1.02076 |
| 1 | XRP-USD | TimesFM3-raw | 1.02479 |
| 5 | EURCNY | AutoETS | 1.00073 |
| 5 | EURCNY | AutoTheta | 1.00158 |
| 5 | EURCNY | LightGBM | 10.6598 |
| 5 | EURCNY | RW | 1 |
| 5 | EURCNY | TimesFM3-log | 1.02932 |
| 5 | EURCNY | TimesFM3-raw | 1.02982 |
| 5 | EURKRW | AutoETS | 1.00005 |
| 5 | EURKRW | AutoTheta | 1.00857 |
| 5 | EURKRW | LightGBM | 2.21019 |
| 5 | EURKRW | RW | 1 |
| 5 | EURKRW | TimesFM3-log | 1.03684 |
| 5 | EURKRW | TimesFM3-raw | 1.03403 |
| 5 | EURMXN | AutoETS | 0.991934 |
| 5 | EURMXN | AutoTheta | 1.0007 |
| 5 | EURMXN | LightGBM | 4.07229 |
| 5 | EURMXN | RW | 1 |
| 5 | EURMXN | TimesFM3-log | 1.01099 |
| 5 | EURMXN | TimesFM3-raw | 1.01119 |
| 5 | XRP-USD | AutoETS | 1.07093 |
| 5 | XRP-USD | AutoTheta | 1.01519 |
| 5 | XRP-USD | LightGBM | 24.0295 |
| 5 | XRP-USD | RW | 1 |
| 5 | XRP-USD | TimesFM3-log | 0.978547 |
| 5 | XRP-USD | TimesFM3-raw | 0.968501 |
| 20 | EURCNY | AutoETS | 1.00051 |
| 20 | EURCNY | AutoTheta | 1.00997 |
| 20 | EURCNY | LightGBM | 4.87349 |
| 20 | EURCNY | RW | 1 |
| 20 | EURCNY | TimesFM3-log | 1.01334 |
| 20 | EURCNY | TimesFM3-raw | 1.01275 |
| 20 | EURKRW | AutoETS | 1.00002 |
| 20 | EURKRW | AutoTheta | 0.979782 |
| 20 | EURKRW | LightGBM | 1.92615 |
| 20 | EURKRW | RW | 1 |
| 20 | EURKRW | TimesFM3-log | 1.09443 |
| 20 | EURKRW | TimesFM3-raw | 1.07573 |
| 20 | EURMXN | AutoETS | 0.996866 |
| 20 | EURMXN | AutoTheta | 0.995272 |
| 20 | EURMXN | LightGBM | 2.32362 |
| 20 | EURMXN | RW | 1 |
| 20 | EURMXN | TimesFM3-log | 0.999648 |
| 20 | EURMXN | TimesFM3-raw | 0.998223 |
| 20 | XRP-USD | AutoETS | 1.15901 |
| 20 | XRP-USD | AutoTheta | 1.06065 |
| 20 | XRP-USD | LightGBM | 14.2177 |
| 20 | XRP-USD | RW | 1 |
| 20 | XRP-USD | TimesFM3-log | 1.02857 |
| 20 | XRP-USD | TimesFM3-raw | 0.947573 |

## 参考別掲（reference=True、本表・勝率・MCS から除外）

| h | model | median ratio | mean ratio | fail | rows used |
|---|---|---|---|---|---|
| — | NA | NA | NA | NA | NA |

## Manifest 照合

Status: **ok**

| model | expected rows | actual rows | match |
|---|---|---|---|
| AutoETS | 6554 | 6554 | yes |
| AutoTheta | 6554 | 6554 | yes |
| LightGBM | 6554 | 6554 | yes |
| RW | 6554 | 6554 | yes |
| TimesFM3-log | 6554 | 6554 | yes |
| TimesFM3-raw | 6554 | 6554 | yes |
