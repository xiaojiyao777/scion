# Scion v0.5 持续算法研究设计

*2026-11-21 · 详细设计与逐模块实施；研究效果尚未验收*

用户已接受 v0.4 阶段收官及下一阶段主线：**让 agent 围绕一个持续的算法问题，
自主观察、实验、修正解释，再提交正式 H/C。** v0.4 原科学成功验收部分达成；
CVRP 独立保留收益仍未确认，继续跨版本跟踪。

Git 阶段交接已完成：`v0.4` tag 指向 `eb339d32`，已通过 `6befa390` 合入并推送
主分支 `master`。当前开发分支为从该合并点建立的 `codex/v0.5-dev`；v0.5 正式进入
设计研发阶段，P1/P2 后端、P3 的 O 接入与 P4 的 M 延续逐模块实施；O/M 均默认关闭。

从仓库入口和当前 TASK 进入本目录；本索引不另设任务队列。

- [详细机制设计](v0.5-continuous-algorithm-research-design.md)：研究工作单元、观察动作、材料延续、H/C 边界、失败与资源语义，以及实施切片。
- [验收与对照设计](v0.5-research-mechanism-acceptance.md)：四层验收、A/B/C 对照、科学目标继承及启动前必须冻结的内容。
- [V3 对齐与模块验证计划](v0.5-v3-alignment-and-module-plan.md)：设计缺口、逐项蓝图对照、P0–P7 依赖与每个模块的设计退出条件；执行进度只在 TASK 跟踪。
- [P0 接口与边界合同](v0.5-p0-interface-and-boundary-contract.md)：具体动作 schema、资源配置、数据权限、H→C 时序、失败路由、12 项边界用例与 V3 扩展文本。
- [P1 公开问题执行设计](v0.5-p1-public-problem-execution.md)：可选 provider、runner/checker 协议、CVRP/Warehouse 具体输入与真实源码绑定、14 项用例及 P1/P2 验证依赖。
- [P2 隔离执行设计](v0.5-p2-isolated-observation-execution.md)：精确挂载、单进程后端、真实配置绑定、资源计量、当前材料存取与 S01–S12 联合验收。
- [P3 会话权限与交接](v0.5-p3-session-permissions-and-handoff.md)：H/C 角色、真实正式输入排除、材料安全投影、H Contract 后交接、失败路由和 T01–T12 验收。
- [P4 材料延续与 fresh import](v0.5-p4-material-continuity.md)：跨 attempt 权限、完整源码与公开投影、清理前保留、导入格式、缺失/失败路由和 M01–M12 验收。
- [P5 研究过程诊断与开放研究](v0.5-p5-process-assessment.md)：六项双问题诊断、隔离参考答案、双人评审、两项开放研究、显式资源/停止规则及 D01–D12；工程工具与真实 E2 分开验收。
- [P5b 实际研究记录](../../docs/experiments/v0.5/README.md)：固定矩阵的冻结输入、完整失败/无收益记录和过程验收；运行完成不等于 E2 通过。
- [P5c 可复查实验与持续问题会话](v0.5-p5c-question-session-and-materials.md)：测试材料回读、实际源码保留、错误测试复核、无候选结束的接口与 Q01–Q15。A/B/C 已接入；C 显式 investigation 生命周期先由 V3 采纳再实施，旧正式模式不变；运行验证见 TASK/current-state。
- [P5d 前瞻 E2 能力研究](../../docs/experiments/v0.5/v05-p5d-e2-preregistration-20261121.md)：P5c 后的新诊断、两问题开放调查、跨 attempt 复用机会和独立双评。首槽触发整批认证停止，E2 仍待验证。[实际运行与评审](../../docs/experiments/v0.5/v05-p5d-e2-postrun-20261121.md)
- [v0.4 阶段收官依据](../../docs/planning/v0.4/v04-stage-review-and-v05-research-mechanism-proposal-20261114.md)：M1–M5 与既有证据；详细机制以本目录的新设计为准。

[V3](../scion-architecture-v3.md) 仍是唯一架构权威，
[direct-runtime addendum](../scion-architecture-v3-v0.4-direct-runtime-addendum.md)
仍描述 v0.4 实现。V3 已显式采纳本轮公开研究扩展；具体功能、验收证据及尚未
接入的边界以 TASK/current-state 为准，不能把架构采纳等同于 agent 能力已开放。

旧 [Evidence Uplift roadmap](../v0.5-evidence-uplift-roadmap.md) 已由本方向取代，
仅作历史材料。它不构成收官前置条件或新的实验授权。
