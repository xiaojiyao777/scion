# Scion v0.5 持续算法研究设计

*2026-11-15 · 详细设计初稿，尚未实施或完成效果验收*

用户已接受 v0.4 阶段收官及下一阶段主线：**让 agent 围绕一个持续的算法问题，
自主观察、实验、修正解释，再提交正式 H/C。** v0.4 原科学成功验收部分达成；
CVRP 独立保留收益仍未确认，继续跨版本跟踪。

Git 阶段交接已完成：`v0.4` tag 指向 `eb339d32`，已通过 `6befa390` 合入并推送
主分支 `master`。当前开发分支为从该合并点建立的 `codex/v0.5-dev`；v0.5 正式进入
设计研发阶段，具体接口仍待评审，现有 runtime 尚未加入 O/M 能力。

从仓库入口和当前 TASK 进入本目录；本索引不另设任务队列。

- [详细机制设计](v0.5-continuous-algorithm-research-design.md)：研究工作单元、观察动作、材料延续、H/C 边界、失败与资源语义，以及实施切片。
- [验收与对照设计](v0.5-research-mechanism-acceptance.md)：四层验收、A/B/C 对照、科学目标继承及启动前必须冻结的内容。
- [v0.4 阶段收官依据](../../docs/planning/v0.4/v04-stage-review-and-v05-research-mechanism-proposal-20261114.md)：M1–M5 与既有证据；详细机制以本目录的新设计为准。

[V3](../scion-architecture-v3.md) 仍是唯一架构权威，
[direct-runtime addendum](../scion-architecture-v3-v0.4-direct-runtime-addendum.md)
仍描述实际运行实现。这里明确区分“已接受的方向”与“待评审的具体契约”；
实现前须将采纳的能力与暴露变更回写权威契约，不能直接依据草案绕过当前边界。

旧 [Evidence Uplift roadmap](../v0.5-evidence-uplift-roadmap.md) 已由本方向取代，
仅作历史材料。它不构成收官前置条件或新的实验授权。
