# P5d 冻结输入与评审材料

本包对应首槽收到认证错误后结案的八槽真实 provider 研究。研究设计、逐题参考解释、成本与停止规则、双评流程及整批判据以[预注册](../../../docs/experiments/v0.5/v05-p5d-e2-preregistration-20261121.md)为准。

|文件|使用者及用途|
|---|---|
|[plan.json](plan.json)|operator 按冻结顺序使用每行的 argv、environment 和共同 cwd。两个 03 已含各自的实际材料导入参数。|
|[public](public)|每个槽位只把对应 JSON 传给 `--research-input`。合成示例直接放在问题正文，`observations` 留空，避免触发问题包对历史观察的其他解释。|
|[config](config)|实际 H/C 限制以及 diagnostic/open 的 O+M 配置。|
|[诊断参考](evaluator/diagnostic-reference.json)|operator 与双评审对照六题实际样例输出、合法输入和独立 checker 结果。|
|[独立评审表](evaluator/independent-review-form.json)|每位评审用一份私有副本，保留自己的八行评分、原始引用和缺失原因。|
|[离线核验记录](offline-verification.json)|记录冻结时的实际检查范围和临时 scripted 演练结果。|

完整源码、正式输入、运行环境和参考计算记录保存在[本机冻结根](/home/clawd/research/scion-experiments/v05-p5d-e2-20261121)。问题包可见范围依照现有投影。评审目录不进入算法 workspace、材料导入或运行环境。

[逐槽处置、成本与双评汇总](postrun/batch-20261121.json)随仓库保留。原始调用 trace、初评文件和证据映射见[运行报告](../../../docs/experiments/v0.5/v05-p5d-e2-postrun-20261121.md)。
