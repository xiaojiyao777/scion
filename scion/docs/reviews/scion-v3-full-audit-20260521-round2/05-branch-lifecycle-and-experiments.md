# Branch Lifecycle 与 Experiment Flow 审核

审计重点：branch lifecycle、soft abandon、continue_explore、telemetry activation missing；schema/contract/smoke/screening/decision 是否符合 v3；是否能继续研究而不是过早抛弃。

## 总体判断

branch lifecycle 已从早期“低胜率直接抛弃”改为更接近 v3 的 soft abandon / continue explore 模式。activation missing 被建模为 repairable telemetry validation failure，screening/validation 可进入修复路径，不再简单计作 solver-quality loss。code repair retry 也避免了同一 hypothesis 被 duplicate gate 重复阻断。

主要偏离点是 screening gate：当前 decision 仍允许 `win_rate` 达标但 `median_delta` 为负的 candidate 进入 validation。这与 v3 蓝图中 screening gate 需要胜率和效果阈值同时达标的描述不一致。

## 发现 L-01

Severity：P1

模块：decision / screening gate

证据：

- `scion/scion/core/decision.py:102`
- `scion/scion/core/decision.py:108`
- `scion/scion/core/decision.py:117`
- `scion/design/scion-architecture-v3.md`

问题：

screening 阶段如果 `win_rate >= threshold` 但 `median_delta < 0`，当前 decision path 会返回 `QUEUE_VALIDATION`，reason 为 `SCREENING_PASS_NEGATIVE_DELTA`。v3 蓝图对 screening gate 的表述是胜率达到阈值且 median delta 达到 `δ_screen` 才进入 validation；negative median delta 更像弱信号或不确定信号，而不是 holdout validation 候选。

风险：

- validation budget 可能被总体效果为负的 branch 消耗。
- decision artifact 中的 `SCREENING_PASS_NEGATIVE_DELTA` 与 v3 gate 定义形成语义冲突。
- agent 可能将“负效果但胜率达标”误读为 protocol 认可方向。

建议修复：

把 negative median delta 的 high-win screening 归入 `CONTINUE_EXPLORE`、`EXPAND_SCREENING` 或 problem-declared special case，而不是默认 `QUEUE_VALIDATION`。如果保留该路径，必须在 protocol config 中显式声明 rationale，并把 reason 改成 non-pass 语义，例如 `SCREENING_INCONCLUSIVE_HIGH_WIN_NEGATIVE_EFFECT`。

## 发现 L-02

Severity：P2

模块：branch lifecycle / soft abandon policy

证据：

- `scion/scion/core/branch_lifecycle_policy.py:42`
- `scion/scion/core/branch_lifecycle_policy.py:108`
- `scion/scion/core/evaluation_orchestrator.py:168`
- `scion/scion/core/decision_finalizer.py:427`

问题：

soft abandon policy 已避免低信号 branch 被过早抛弃，这是 v3 正向变化。但策略主要看 case-level win/loss、candidate failed pairs、median delta 和 runtime ratio。若 case-level 被聚合成 neutral，但 pair-level 或 seed-level 呈现明显退化，branch 仍可能以 weak/neutral signal 继续探索。

风险：

- “继续研究”策略可能过宽，消耗 proposal/screening budget。
- branch-level audit 需要回看 pair-level stats 才能解释为什么一个低质量方向没有被 deprioritize。

建议修复：

不建议回到 hard abandon。建议增加 typed soft-risk signal：pair-level loss ratio、repeat zero-win streak、candidate failure density。该 signal 只用于 deprioritize / require sharper hypothesis，不直接 abandon，保持 v3 的探索弹性。

## 发现 L-03

Severity：P2

模块：scheduler / blocked infra lifecycle

证据：

- `scion/scion/core/scheduler.py:34`
- `scion/scion/core/scheduler.py:62`
- `scion/scion/core/scheduler.py:88`

问题：

`BLOCKED_INFRA` branch 被排除出 schedulable candidates，但仍可能计入 active branch cap。对于长 campaign，如果 infra-blocked branch 没有及时恢复或关闭，会占用 active capacity，影响可继续探索。

风险：

- branch 并非科学上失败，却阻塞 scheduler 资源。
- 主会话需要手动清理 infra-blocked branch，自动化程度不足。

建议修复：

将 `BLOCKED_INFRA` 从 active research capacity 中拆出，或设置单独 infra retry lane / expiry policy。status 中展示 blocked reason、last retry、next retry，不把它与 active scientific branch 混算。

## 发现 L-04

Severity：P2

模块：proposal quality budget / campaign loop

证据：

- `scion/scion/core/campaign_loop.py:34`
- `scion/scion/core/campaign_loop.py:188`
- `scion/scion/proposal/context/feedback.py:188`

问题：

proposal-quality loop limit 已从上一轮的偏紧预算调整为 `rounds + max(3, rounds)` 并支持配置覆盖，这是改进。但它仍是 campaign-level pre-screen global budget，多个 branch 连续遇到 novelty/contract/telemetry feedback 时，可能在形成足够 screening evidence 前用尽。

风险：

- 对高探索度问题，agent-quality blocks 可能压过 protocol evidence。
- 主会话难以区分“模型反复低质量提案”与“问题空间需要更多 allowed variant 引导”。

建议修复：

将 budget 报告拆成 total、per-branch、per-failure-category，并允许 problem adapter 为 novelty-heavy domain 声明更细的 retry envelope。保持 deterministic cap，但让 status 显示哪个 category 消耗了 budget。

## 正向对齐点

- `scion/scion/core/telemetry_validation.py:70` 将 activation missing 设为 screening/validation repairable，frozen fail closed，符合 v3 stage boundary。
- `scion/scion/core/telemetry_validation.py:121` 避免 repairable telemetry validation failure 计入 effective screening round。
- `scion/scion/core/decision_finalizer.py` 对 continue explore 的 workspace preservation 已加入低信号条件，不再简单按 win_rate 保留。
- `scion/scion/proposal/context_manager/manager.py:520` 的 `pending_code_retry_policy` 支持 approved hypothesis code repair，并避免 duplicate gate 重复阻断同一 hypothesis。

