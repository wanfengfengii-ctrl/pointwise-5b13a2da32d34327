# 热处理曲线等效事故核账

两片试样均从 20 °C 升到 21 °C，之后保温到第 4 秒。甲在第 1 秒到温，乙在第 3 秒到温。关源后，甲和乙的实收曲线在第 1 秒应分别读得 21 °C 和 61/3 °C。

| 申报温差容差 | 甲、乙按原顺序签发的正确裁决 |
| --- | --- |
| 0 °C | `retest` |
| 1/4 °C | `retest` |
| 1/3 °C | `equivalent` |

从项目根目录运行 `python3 -B incident.py`。核账打印实际值和预期值。`elapsed_1s_c` 来自实际发行并实收的两件，`issued_verdicts` 为其签发结果，`external_verdicts` 为根据同一组折点独立制备的合法 V1 件的签发结果。已计算的业务结果偏离预期时，核账以非零状态退出并打印 `THERMAL_ALIGNMENT_MISMATCH`。

日常接口、原回归和样例见 README.md。交付继续使用 `.pointwise-runtime.json` 中的 `version` 1 和 `kind` `cli`。`setup` 是准备命令的 argv 列表，`verify` 和 `demo` 各是一条 argv 命令，分别核验原业务回归并演示停源比测及勘误后的原号领取。
