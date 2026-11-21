# 衡川热处理曲线交班台账

衡川材料试验中心的白班试验员从参考探头校准和试验台采样登记试验。交班员按指定修订移交校准曲线。夜班质控员关源后判断两次试验能否等效，复核员以后按原报告核账，并依据补测结论安排人工复测。总时长相同的试验也可能有不同的升温速率和保温时长。

## 运行

使用 Python 3.11 标准库和本地 SQLite，从项目根目录运行。

```sh
python3 -B check_project.py
python3 -B demo.py
```

`check_project.py` 由控制台物化时提供。源码的完整测试也可直接用 `python3 -B -m unittest discover` 执行。演示将两份正常样例写入临时源库，经独立交换目录实收，然后在关闭源连接的情况下比测，并重开分析库核账。演示和测试各自使用临时目录。

## 一天的交班

1. 白班以 `trial.calibration.register_calibration(trials, probe_id, scale, offset)` 固化校准并取得校准修订号。
2. 试验员用 `trial.revisions.record_trial(trials, trial_id, calibration_id, samples, parent_revision_id=None)` 提交按实测顺序的采样对，取得试验修订号。固定校准和提交顺序随修订保存。
3. 交班员用 `issue.package.issue_curve(trials, issues, revision_id)` 发行该修订。返回 `PackageEnvelope`，以 `to_bytes()` 得到交换件。
4. 夜班用 `intake.receipts.accept_curve(catalog, exchange_bytes)` 得到实收整数编号，可以通过 `get_accepted_curve(catalog, received_id)` 取得已实收曲线与出处。随后关闭源连接。
5. 夜班用 `compare.request.compare_and_publish(catalog, reports, left_id, right_id, tolerance)` 比测两份完整试验，取得 `(ReportSnapshot, SuccessReceipt)`。报告的 `verdict` 为 `equivalent`（等效）或 `retest`（补测）。两种结论均签存。
6. 白班发现试验有勘误时，以原修订号作为父号提交全部更正采样和固定校准。新修订取得新号，可以另行发行与实收。父修订仍可发行。
7. 夜班用新件复核。本项目的样例中，甲第 1 秒到温，乙原记录第 3 秒到温，两者第 4 秒结束。零容差和 1/4 °C 均补测，1/3 °C 等效。乙更正为第 2 秒到温后，零容差等效。
8. 复核员重开分析库，使用 `report.readback.read_report(reports, report_id, mode='receive')` 取得已存报告与回执。`mode='export'` 返回对应的确定格式 JSON 字符串。按原报告号领取即可核对当时的甲乙顺序、容差、双件出处和回执。

## 连接与输入

由调用方提供并关闭 `sqlite3.Connection`。源连接上构造 `TrialRepository` 后调用 `initialize()`，再在同一连接初始化 `IssueRegistry`。分析连接上初始化 `IntakeCatalog` 和 `ReportRepository`。这些类型分别位于 `trial.repository`、`issue.registry`、`intake.catalog` 和 `report.repository`。各写入口以空闲连接为前提，自己提交其事务。重开后重复初始化会保留原数据和已提交的勘误。

探头、试验与各文本编号为合法 UTF-8、非空、首尾无空白及无 ASCII 控制字符的字符串。时间、原读值、比例、偏置与容差接受 `fractions.Fraction`、整数和形如 `-12` 或 `3/4` 的字符串。空值、布尔值、浮点值、非法文本及零分母受到拒绝。显式零值合法，容差还须非负。采样须提供至少两个 `(时间, 原读值)` 对，时间严格递增。勘误父修订必须存在且归于同一试验。编号为不透明引用，报告中的甲乙顺序严格按照请求。

温度为 `原读值 × 比例 + 偏置`，单位为摄氏度。第一个采样时刻定义实逝秒的零点，相邻点按秒线性插值，保温与回落保留真实时长。分析中的一条连续对齐从两试验的起点走到各自终点，全程温差须不超过申报容差。同一路径上任意先后两点之间，乙的经过时间须在甲的 1/2 至 2 倍之间。两种约束均包含边界。校准、求值和裁决使用有理运算，固定请求可确定地复现裁决。

## V1 交换和历史账

V1 外层为 UTF-8 JSON 对象，字段为 `version`、`issue_id`、`trial_id`、`revision_id`、`body` 和 `digest`。`version` 是整数 1。`body` 为嵌入的 UTF-8 JSON 文本，内容是 `{"knots": [[[时间分子, 时间分母], [温度分子, 温度分母]], ...]}`。折点严格按时间递增且从零起，分子和分母均为 JSON 整数，分母非零。原采样和校准留在源库。

`digest` 是其余五个字段按 Python `json.dumps` 的 `sort_keys=True, ensure_ascii=True, separators=(',', ':')` 编码后计算的 SHA-256 小写十六进制值。`body` 原文本参与计算。V1 的 SHA-256 提供内容绑定，交换渠道负责确认来件来源。同号同件重投返回相同实收号。同号异件或内容绑定失败不会改变已实收记录。

导出 JSON 的 `report` 和 `receipt` 各包含报告号、有序 `sources` 和 `request`。`request` 固定 `left_received_id`、`right_received_id` 与 `[分子, 分母]` 格式的 `tolerance`。报告另含裁决，回执另含回执号。源连接关闭、源修订勘误及分析库重开后，均从原报告号读取已存的快照和回执。

非法业务输入引发 `thermal_core.InvalidInput`，未知固定号引发 `thermal_core.MissingRecord`。损坏交换件引发 `intake.decoder.InvalidPackage`，已实收同号异件引发 `intake.catalog.IntakeConflict`，它也是一种 `InvalidPackage`。签存写失败引发 `report.publication.PublicationError`，其中的报告和回执编号是供核账的本次尝试编号，报告和成功回执均已回滚。只有提交成功才返回成功回执。
