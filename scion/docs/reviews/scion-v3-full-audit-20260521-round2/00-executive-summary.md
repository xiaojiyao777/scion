# Scion v3 全量架构审核 Round 2 总结

审计日期：2026-05-21

审计对象：`scion/scion`

审计基线：当前工作区 HEAD 为 `e1df1f6`（`Count formal telemetry failures in screening summaries`）

审计限制：本轮只写审计文档；未修改实现代码或测试代码；未运行测试；未读取 raw experiment traces。参考了 v3 蓝图、`AGENT_ONBOARDING.md`、已提交实验总结、既有审计文档和源码。

## 总体结论

本轮未发现需要立即停止 v0.4 开发的 P0。`e1df1f6` 后，formal telemetry failure 的统计链路已经明显收敛：screening summary、campaign status、lineage summary 都能把正式 protocol telemetry guard failure 纳入统计。`e04b1de` 后，CVRP novelty 对 cluster removal 的已知 false-positive 风险也被显著降低，provider 开始要求 exact span / matched span，并能区分 allowed variant。

但 v3 架构仍有 P1 级债务，主要集中在四类：

1. generic evidence 包仍直接承载 CVRP final-quality / case manifest / route gap 字段，违反 core/evidence 与 problem adapter 的边界。
2. telemetry failure 已经能被统计，但 decision reason taxonomy 仍过粗，且 telemetry veto 在 decision 中先于 runtime/quality 分支，容易把真实失败形态压扁成 `*_TELEMETRY_FAILED`。
3. screening 阶段存在 `win_rate` 达标但 `median_delta` 为负时直接进入 validation 的路径，偏离 v3 对 screening gate 的“胜率和效果同时达标”要求。
4. core/proposal/evidence 中仍有多个超过 1000 行的大文件，导致 v3 的 deterministic kernel、agentic flow、evidence recorder 等职责边界难以审计。

## P1 发现索引

| ID | 模块 | 摘要 | 详情文档 |
| --- | --- | --- | --- |
| B-01 | boundary / evidence | `scion/scion/evidence` 直接导出 CVRP final evaluation、route gap、BKS routes 等问题域字段 | `01-v3-boundary-and-core.md`, `03-evidence-lineage-telemetry.md` |
| T-01 | telemetry / decision | formal telemetry failure 统计已修复，但 top-level decision reason 仍过粗并遮蔽 runtime/quality 证据 | `03-evidence-lineage-telemetry.md` |
| L-01 | protocol / lifecycle | negative `median_delta` screening 仍可能 queue validation，偏离 v3 screening gate | `05-branch-lifecycle-and-experiments.md` |
| M-01 | modularity | `evidence_recorder.py`、`explore_step_pipeline.py`、`llm_client.py` 等生产文件超过 1000 行 | `06-modularity-and-test-debt.md` |

## 关键正向进展

agent 两阶段 hypothesis/code 的上下文构造比上一轮更接近 v3：`active_algorithm_facts` 已在 hypothesis、code、repair、planner tool-selection 中注入，并且 prompt 会在 raw tool observations 之前渲染 active facts。novelty provider 和 agent quality feedback 能携带 `fact_packet_digest`、`snapshot_digest`、`fact_ids`、provenance 和 span 证据，满足“agent 与 gate 同源、gate 不比 agent 看得更多”的主线要求。

telemetry boundary 也有实质改善：runtime telemetry guard 现在通过 problem surface declaration 和 role map 识别字段，而不是在 generic runtime 中硬编码 CVRP solver fields。`solver_algorithm_*` 字段主要留在 CVRP problem surface 和 CVRP runtime adapter 中。

branch lifecycle 从“低胜率一律抛弃”转向 soft abandon / continue explore；activation missing 被建模成 repairable telemetry validation failure，不再计入有效 screening round。这符合 v3 “可继续研究而不是过早抛弃”的方向。

## 仍需主会话关注

v0.4 当前的主要风险不是单点 bug，而是边界债与审计粒度债：有些路径功能上已经可跑，但 generic 包仍保留 problem-domain fallback 或大型聚合模块，后续再接入第二个问题域时会放大维护成本。建议主会话按 `07-prioritized-fix-plan.md` 分发 P1 任务，先清理 evidence boundary、decision reason taxonomy、screening gate 和大文件拆分，再处理 P2 的 legacy fallback、scheduler capacity、novelty regex 模块化和 boundary sentinel 扩展。

