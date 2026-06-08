# Scion CVRP 4R GPT-5.5 Tooling Verify 实验报告

Run root: `/home/clawd/research/scion-experiments/v04-p1-tooling-verify-4r-gpt55-20260607T135248Z-claw`

分析日期: 2026-06-07

## 1. 摘要结论

本次 run 是完整且有效的 4R screening run，但没有进入 validation/frozen，也没有 promotion。`run_status.json` 和 `campaign/run_status.json` 均记录 `run_complete=true`、`run_validity_status=valid`、`completed_requested_rounds=true`、`last_stop_reason=max_rounds_exhausted`。`campaign/status.json` 的 accounting reconciliation 显示 4 次 proposal attempts、4 次 formal screened candidates、4 个 effective rounds，quality blocks 为 0，model repair 为 0，validation/frozen/promotion 均为 0。

所有 LLM traces 共 30 次调用，模型字段全部为 `gpt-5.5`：4 次 `hypothesis_target_intent`、4 次 `hypothesis`、18 次 `tool_selection`、4 次 `code`。这满足本次实验的模型一致性目标。

研究结果是负面但有诊断价值：前两轮机制都成功通过 Contract/Verification/Canary 并完成 formal screening，但实际 objective 全部 tie，只有 runtime/activation 诊断；第三轮出现一个 pair-level loss，被 lifecycle 标成 `quality_regression` 且 current head discarded；第四轮出现一个 pair-level win，被标成 `weak_positive`，但 case-level 仍全 tie，且 runtime aggregate 因 cached champion 低置信被排除。最终不适合直接进入 8R；更合理的下一步是先优化 Scion 机制层的证据保真、弱信号跟进和 runtime fresh champion 策略，而不是硬编码 CVRP algorithm。

## 2. 设计基准与审计边界

本报告按 `scion/design/scion-architecture-v3.md` 与 `scion/docs/AGENT_ONBOARDING.md` 审计：

- LLM/proposal/tool observations 均视为 tainted，只能作为 proposal 层反馈，不可直接驱动 promotion。
- Decision 只应读取 Contract、Verification、Protocol、Safe Feature Extractor 之后形成的结构化 `DecisionFeatures`。
- CVRP 语义应来自 problem/adapters/providers/specs/solver artifacts；generic core 不应吸收 CVRP route/capacity/demand/ALNS/VNS 语义。
- 分支治理遵循 one branch = one research direction；弱正或 no-effect 分支可保留或引导 clean fork，但清晰回归应被隔离。

本次分析只读取 artifacts：`campaign/status.json`、`run_status.json`、`campaign_summary.json`、`scion.db`、`agentic_sessions/*/output.json`、scratch prompt manifests/self-check/smoke artifacts、`llm_traces`、`metrics` 和 retained workspaces。没有修改源码。

## 3. Run-Level 事实

| 项目 | 结论 |
|---|---|
| Wrapper/campaign 状态 | complete、valid、wrapper exit 0 |
| 请求轮数 | 4 |
| effective rounds | 4 |
| proposal attempts | 4 total / 4 consumed |
| formal screened candidates | 4 |
| protocol evaluated candidates | 4 |
| protocol stage counts | screening=4, validation=0, frozen=0 |
| quality blocks | 0 |
| model repair | 0 |
| telemetry failed/repairable attempts | 0 |
| promoted/accepted experiments | 0 |
| active slots at end | used=3/max=3: branch 1fe9, 9b6a, 97ac |

Final branch state:

- `1fe9bd8e-bb82-4040-a1ac-c6def73040c5`: `active_no_effect` retained checkpoint `b15c156c...`, mechanism `route_merge_vns`。
- `9b6a35aa-4a89-4913-91f2-a0fe939032cb`: `active_no_effect` retained checkpoint `6d947e29...`, mechanism `route_compaction_repair`。
- `a5eedcf2-5595-4bc2-a8ab-76f302c05e60`: `discarded` / `diagnostic_repair` / inactive, mechanism `slack_penalized_regret_repair`。
- `97aca1d2-0c29-474e-8eba-160bc3f09f31`: `discarded` / `diagnostic_repair` but active slot retained, mechanism `objective_aware_reheating`，`weak_positive_followup=true`。

## 4. 逐轮分析

### Round 1: `route_merge_vns`

Branch: `1fe9bd8e-bb82-4040-a1ac-c6def73040c5`

Hypothesis: 当前 VNS 已有 2-opt、relocate、Or-opt、swap、tail exchange，但缺少一次性吸收 sparse route 的 whole-route absorption move。假设是在 `policies/baseline_modules/local_search.py` 增加 `route_merge_vns`，在不增加 route count、保持容量可行的前提下，把 donor route 的所有 customers 插入其他 routes，若 route count 降低或 total_distance 改善才应用。

目标与机制:

- `change_locus=solver_design`
- `action=modify`
- `target_file=policies/baseline_modules/local_search.py`
- `mechanism_ids=["route_merge_vns"]`
- 目标 objectives: `fleet_violation`, `total_distance`
- protected objective: `fleet_violation`

LLM 调用与作用:

- Hypothesis session `4b3b6b28...`: `hypothesis_target_intent` 选择研究目标；`hypothesis` 产出结构化假设。工具主要是 `memory.query`，以及 deterministic context/prompt preface 中的 surface/problem/active solver facts。
- Code session `d38029f4...`: 8 次 `tool_selection` + 1 次 `code`。工具包括 `context.read_branch_state`、`context.read_surface`、`context.read_algorithm_file`、`feedback.query_screening`、`feedback.query_runtime`。第一轮无历史 screening/runtime feedback，工具返回 0 rows 或无 runtime feedback。

Patch 做了什么:

- 在 `_default_vns_operators()` 注册 `_route_merge_vns`。
- 新增 `_route_merge_vns(solution, context, reserve)`，选择最多 8 个短/低 load donor routes，检查全局 slack，逐 customer 寻找 capacity-feasible cheapest insertion，完整吸收后才替换 routes。
- 使用 `context.record_iteration`、`context.record_move`、`context.record_phase` 记录机制 telemetry。

Gate/Protocol/Decision:

- self-check: schema valid，contract preview passed。
- algorithm smoke: passed，5 selected cases，provider hook used，`solver_algorithm_errors=0`。
- Contract: passed。
- Verification: passed。
- Canary: passed。
- Screening: 8 cases x 2 seeds = 16 pairs，case wins/losses/ties = 0/0/8，pair wins/losses/ties = 0/0/16，median_delta=0，CI=[0,0]。
- Runtime: high/sufficient，median runtime ratio 0.9987，median delta -10.5 ms，但 runtime 只是 tie-break/supporting signal。
- Telemetry: activation observed；`route_merge_vns` phase positive runtime in 12/16 runs，但 effect fields 0/16 positive，diagnostic 为 executed no improvement。
- Decision: `continue_explore`，reason codes 包括 `SCREENING_FAIL_WIN_RATE`、`SCREENING_NEUTRAL_SIGNAL_CONTINUE`、`SCREENING_RUNTIME_SATURATION_DIAGNOSTIC`、`SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`、`SCREENING_RUNTIME_BUDGET_SATURATION`。

研究质量评价:

假设合理且与机制匹配：它针对“局部 moves 缺少整 route absorption”的明确弱点，代码也确实实现了完整 donor absorption，不是无关 helper。失败经验可用：机制激活但 objective effect 为零，说明“再增加 VNS-side whole-route merge”不是高价值方向，后续应换 stage 或降低同质 runtime 消耗。

### Round 2: `route_compaction_repair`

Branch: `9b6a35aa-4a89-4913-91f2-a0fe939032cb`

Hypothesis: Round 1 的 route merge VNS 已激活但无 objective effect 且 runtime saturated；因此把 whole-route absorption 从 VNS registry 移到 ALNS repair 后、embedded VNS 前，作为 deterministic post-repair route compaction。目标是 compact fragmented/light routes，减少 VNS 负担并改善 total_distance。

目标与机制:

- `change_locus=solver_design`
- `action=create_new`
- `target_file=policies/baseline_modules/route_compaction.py`
- `additional_changes`: `policies/baseline_modules/scheduler.py`
- `mechanism_ids=["route_compaction_repair"]`
- target objective: `total_distance`
- protected objective: `fleet_violation`

LLM 调用与作用:

- Hypothesis session `4b04ec1d...`: `hypothesis_target_intent` + `hypothesis`。工具读到了 1 条 screening feedback 和 runtime feedback，即 Round 1 的 no-effect/runtime saturation。
- Code session `70201afa...`: 3 次 `tool_selection` + 1 次 `code`。工具包括 `memory.query`、`feedback.query_screening`、`feedback.query_runtime`、`context.read_algorithm_file`、`context.read_branch_state`。

Patch 做了什么:

- 新增 `route_compaction.py`，实现 `_route_compaction_repair(solution, max_routes, context, reserve)`。
- 选择 top-3 light donor routes，复制 candidate，尝试把 donor customers 按 demand 排序插入其他可行 route。
- 接受条件：feasible、route count 不增加、max_routes 不违反，并且 total_cost 改善，或 route count 降低且 distance 不变坏。
- 在 scheduler 中 import `_route_compaction_repair`，并在 `repair_op(candidate, removed, rng)` 和 `candidate.remove_empty_routes()` 之后、embedded VNS 前调用。

Gate/Protocol/Decision:

- self-check: schema valid，contract preview passed；有 C11 expected telemetry advisory，但不是 hard block。
- algorithm smoke: passed，5 selected cases，provider hook used，`solver_algorithm_errors=0`。
- Contract: passed。
- Verification: passed。
- Canary: passed。
- Screening: 12 cases x 2 seeds = 24 pairs，case wins/losses/ties = 0/0/12，pair wins/losses/ties = 0/0/24，median_delta=0，CI=[0,0]。
- Runtime: `low_cached_champion` 但 status sufficient；median runtime ratio 0.999879，median delta -1.0 ms，runtime aggregate 仍非 standalone optimization signal。
- Telemetry: activation observed；`route_compaction_repair` runtime positive 19/24，iterations positive 24/24，但 effect fields 0/24 positive。
- Decision: `continue_explore`，reason codes 增加 `SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE`，仍是 no-effect + runtime/telemetry diagnostic。

研究质量评价:

这是一个基于 Round 1 失败经验的合理跨分支改造：保留“route absorption”思想，但改变 activation stage 和 ownership。代码对应假设，且 telemetry 证明机制运行了。失败经验也清楚：post-repair compaction 仍无法产生 objective effect，说明 route-level compaction 家族在当前 screening 分布上低价值，后续需要更换机制 family，而不是继续同质 compaction。

### Round 3: `slack_penalized_regret_repair`

Branch: `a5eedcf2-5595-4bc2-a8ab-76f302c05e60`

Hypothesis: 前两轮 local-search/compaction 机制激活但无 wins，问题可能不在缺少 merge/compaction move，而在 ALNS repair 生成的候选过于按 immediate insertion delta 贪心，造成后续 relocate/Or-opt/two-opt-star 难以改善。因此修改 `destroy_repair.py` 的 regret insertion scoring，引入 residual capacity slack 和 route-load imbalance penalty。

目标与机制:

- `change_locus=solver_design`
- `action=modify`
- `target_file=policies/baseline_modules/destroy_repair.py`
- `additional_changes`: `policies/baseline_modules/scheduler.py`
- `mechanism_ids=["slack_penalized_regret_repair"]`
- target objective: `total_distance`
- protected objective: `fleet_violation`

LLM 调用与作用:

- Hypothesis session `db23b3fb...`: `hypothesis_target_intent` + `hypothesis`。工具读到 2 条 screening feedback 和 runtime feedback，即前两轮 zero-effect evidence。
- Code session `86d19388...`: 3 次 `tool_selection` + 1 次 `code`。工具包括 `memory.query`、`feedback.query_screening`、`feedback.query_runtime`、`context.read_algorithm_file`、`context.read_branch_state`。

Patch 做了什么:

- 完整 workspace 未保留，因为 current head 后续被 discarded；可从 output 的 typed-edit summary 验证 patch intent。
- `destroy_repair.py` 增加约 71 行，改变 repair scoring，目标是以 O(1) slack/load penalty 调整已有 insertion candidates。
- `scheduler.py` 有 5 个 composed edits：import/调用/telemetry wiring，约增加 20 行净变化。
- algorithm smoke status 为 diagnostic 但 `passed=true`，failure_class=`telemetry_static_diagnostic`，`solver_algorithm_errors=0`。

Gate/Protocol/Decision:

- self-check: schema valid，contract preview passed。
- Contract: passed。
- Verification: passed。
- Canary: passed。
- Screening: 8 cases x 2 seeds = 16 pairs，case wins/losses/ties = 0/0/8，但 pair wins/losses/ties = 0/1/15。
- 非 tie pair: `cvrplib/B/B-n52-k7.vrp`, seed 11，candidate total_distance 748 vs champion 747，delta=-1，fleet_violation 均为 0。
- Runtime: aggregate excluded，`runtime_evidence_status=fresh_champion_required`，`runtime_confidence=low_cached_champion`，runtime_pairs=0；per-pair candidate/champion audit evidence 仍在 metrics 中。
- Telemetry: activation observed；`slack_penalized_regret_repair` phase runtime positive 16/16，effect fields positive 11/16，说明机制局部有活动与局部改善，但 final protocol objective 有一个 pair-level loss。
- Decision: `continue_explore`，原因主要是 `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`；branch state 后处理为 `quality_regression`，current head `discarded`，active slot inactive，release reason=`quality_regression_without_actionable_diagnostic_slot_release`。

研究质量评价:

这个假设比前两轮更有研究价值，因为它主动吸收了“增加 route absorption move 无效”的跨分支经验，改换到 candidate formation stage。代码方向与假设一致，telemetry 的 phase-level positive effect 表明机制不是 inert。但 protocol loss 说明 slack penalty 有真实质量风险：局部 slack-aware improvement 不等于 final total_distance improvement。下一步经验应是“如果继续 repair scoring，应以 branch-local diagnostic 限制 penalty 强度/触发条件，并优先分析 loss case”，而不是直接推广。

### Round 4: `objective_aware_reheating`

Branch: `97aca1d2-0c29-474e-8eba-160bc3f09f31`

Hypothesis: 前三轮显示新增 neighborhood/repair-side机制多为 tie 或回归，但 ALNS 仍有 accepted/neutral accepted moves。瓶颈可能是 simulated annealing schedule 过静态，无法根据 stagnation 或 best-improving scarcity 调节接受行为。因此在 `acceptance.py` 修改 `_SimulatedAnnealing`，引入 objective-aware reheating，并在 scheduler 中记录 outcome。

目标与机制:

- `change_locus=solver_design`
- `action=modify`
- `target_file=policies/baseline_modules/acceptance.py`
- `additional_changes`: `policies/baseline_modules/scheduler.py`
- `mechanism_ids=["objective_aware_reheating"]`
- target objective: `total_distance`
- protected objective: `fleet_violation`

LLM 调用与作用:

- Hypothesis session `b55a9609...`: `hypothesis_target_intent` + `hypothesis`。工具读到 3 条 screening feedback 和 runtime feedback，明确避开 route_merge、route_compaction、slack repair，转向 acceptance family。
- Code session `83cab56e...`: 4 次 `tool_selection` + 1 次 `code`。工具包括 `memory.query`、`feedback.query_screening`、`feedback.query_runtime`、多个 `context.read_algorithm_file` 和 `context.read_branch_state`。

Patch 做了什么:

- 完整 workspace 未保留，因为 current head 被 discarded；可从 output 的 typed-edit summary 验证 patch intent。
- `acceptance.py` 净增约 26 行、删 2 行，修改 SA cooling/reheat 行为。
- `scheduler.py` 增约 12 行、删 1 行，用于给 acceptance policy 传递/记录 outcome。
- algorithm smoke status 为 diagnostic 但 `passed=true`，failure_class=`activation_not_observed_diagnostic`，`solver_algorithm_errors=0`。

Gate/Protocol/Decision:

- self-check: schema valid，contract preview passed；有 C11 expected telemetry advisory，但不是 hard block。
- Contract: passed。
- Verification: passed。
- Canary: passed。
- Screening: 8 cases x 2 seeds = 16 pairs，case wins/losses/ties = 0/0/8，pair wins/losses/ties = 1/0/15，median_delta=0，CI=[0,0]。
- 非 tie pair: `cvrplib/B/B-n31-k5.vrp`, seed 29，candidate total_distance 673 vs champion 675，delta=+2，fleet_violation 均为 0。
- Runtime: aggregate excluded，`runtime_evidence_status=fresh_champion_required`，`runtime_confidence=low_cached_champion`，runtime_pairs=0。
- Telemetry: screening 中 activation observed；`objective_aware_reheating` runtime positive 11/16，effect fields positive 14/16，phase best deltas 有正值。但 smoke 阶段曾给 activation_not_observed diagnostic，说明 small smoke 未稳定覆盖触发条件。
- Decision: `continue_explore`，reason codes 为 `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED` 与 `SCREENING_RUNTIME_BUDGET_SATURATION`；branch state 为 `weak_positive`，`weak_positive_followup=true`，但 current head 仍是 `discarded`。

研究质量评价:

这是四轮中最好的研究动作：它明确吸收了三轮历史失败，转向不同 mechanism family，并且产生了一个 pair-level positive signal，没有 pair-level loss。弱点是证据还不够 promotion：case-level 仍全 tie，runtime aggregate 被排除，smoke activation 诊断与 formal screening activation observed 之间存在触发覆盖差异。它适合作为下一轮 branch-local follow-up 的线索，不适合作为 champion promotion。

## 5. 分支研究质量总评

整体研究质量高于“随机试算子”，因为每轮都基于前序 evidence 改变机制 family 或 activation stage：

- Round 1 是合理 baseline extension：补全 VNS whole-route absorption。
- Round 2 明确吸收 Round 1 的 zero-effect/runtime saturation，把机制迁到 post-repair。
- Round 3 吸收前两轮 compaction/merge 低效，转到 repair candidate formation。
- Round 4 吸收前三轮新增 move/repair 低效，转到 acceptance dynamics，并产生 pair-level weak positive。

代码与假设基本对应，没有看到“只加 helper 不接入”的 inert patch。前两轮 retained workspace 的 diff 验证了实际接入；后两轮虽未保留 workspace，但 code session output 的 typed-edit summary、smoke artifact 和 formal metrics 均证明 patch 被执行并进入 protocol。

主要问题不在 agent 无法提出有效研究，而在证据转化层：

- 前两轮没有 objective effect，但保留 active_no_effect checkpoint，占用 active slots，并触发 diversity/reroute guidance。
- 第三轮有局部 telemetry positive，却 final objective loss，Scion 正确将其隔离。
- 第四轮有 pair-level weak positive，但 current head 仍 discarded；这可能是 lifecycle 对 weak-positive/fresh-runtime 情况过保守，或者是 artifact 表达不够清晰，需要 Scion 机制层改进。

## 6. Scion 框架设计符合性检查

### 符合项

- Proposal/LLM/tool observations 被标为 tainted，输出进入 proposal feedback/memory，而不是 Decision 直接输入。
- `campaign_summary.json` 的 `cross_branch_research_observability` 明确 `policy=proposal_observability_only`，`decision_input_policy=excluded_from_decision_features`。
- prompt manifest 包含 visibility ledger、active-facts/source visibility、material-difference visibility；跨分支材料作为 proposal 可见信息，而非 promotion 决策字段。
- Decision events 的 `decision_features_json` 只包含结构化 gate/protocol/runtime/lifecycle fields，没有读取 hypothesis 自由文本。
- CVRP algorithm changes 均发生在 problem-owned solver artifacts/workspaces 的 `policies/baseline_modules/*` 与 scheduler wiring 中；本次没有发现 generic core 被写入 CVRP route/capacity/demand 语义。
- Contract/Verification/Canary/Protocol 顺序完整，4 个 formal candidates 均通过 hard gates 后才进入 screening。

### 风险与改进点

1. Evidence scope 表达不一致：`campaign_summary.json` 的 cross-branch observability 有 full step history/screening step counts，而 `status.json` 的对应 payload 标成 `step_history_scope=none`、`protocol_screening_steps=0`、`status_scope=loop_accounting_inferred`。这不一定是 bug，但给 post-run 审计造成歧义。建议报告层优先使用 `campaign_summary.json` 做完整回放，`status.json` 只作 final snapshot。

2. Discarded candidate 的完整 diff 没有 retained workspace。Round 3/4 只能从 output patch summary、typed-edit derived diff summary、metrics 与 smoke artifacts 重建。建议 Scion 对 every formally screened candidate 保留 canonical patch artifact，即使 current head discarded，便于实验报告逐行审计。

3. Weak-positive lifecycle 表达不够直观。Round 4 有 pair-level win 且 no losses，被标成 `weak_positive_followup=true`，但 current head 仍 `discarded`。如果这是 intentional，报告需要明确“discarded means not retained as candidate head, not evidence discarded”；如果不是 intentional，应调整 branch card 文案和 checkpoint policy，避免 operator 误读为弱正证据丢失。

4. Fresh champion runtime policy 是当前推进瓶颈之一。Round 3/4 的 runtime aggregate 被 `low_cached_champion` 和 `fresh_champion_required` 排除是合理保守，但这会让 weak positive 无法升级为更强 evidence。建议 Scion 在出现 pair-level win/no-loss 或 loss diagnostic 时自动 queue fresh champion replay，而不是进入更长 rounds 后再发现 runtime evidence 不可用。

5. Smoke diagnostic 与 formal screening activation 有差异。Round 4 smoke 是 `activation_not_observed_diagnostic`，但 screening 中 activation observed 且 effect positive 14/16。这说明 smoke 用例覆盖触发条件不足，适合优化 provider smoke case selection 或将 diagnostic 表达为“smoke coverage weak”而非机制风险。

## 7. Promotion/Validation/Frozen 结论

没有 promotion。没有 validation。没有 frozen holdout。没有 accepted experiments。

四轮都停在 screening 后的 `continue_explore`：

- Round 1/2: no-effect, no objective wins, activation observed but zero objective effect。
- Round 3: quality regression，one pair-level loss。
- Round 4: weak positive，one pair-level win but no case-level win，runtime aggregate excluded。

因此不能把任何候选提升为 champion，也不应声称 solver quality improved。最多可以说：Round 4 的 acceptance-family 方向产生了一个值得 branch-local follow-up 的弱正信号。

## 8. 是否进入 8R

不建议现在直接进入 8R。理由：

- 前两轮已经证明同质 route absorption/compaction 会消耗 runtime 且 objective effect 为零。
- 后两轮的关键 runtime evidence 被 fresh-champion policy 排除，直接 8R 会放大低置信 runtime 状态。
- Round 4 的 weak positive 值得跟进，但需要更清晰的 branch-local continuation 和 fresh runtime replay，而不是盲目增加轮数。
- 当前问题更像 Scion evidence/lifecycle/feedback plumbing 的机制优化点，而不是 CVRP algorithm 需要人工 hard-code。

建议下一步是机制层优化后再跑 4R/6R 验证：

1. 对 formally screened discarded candidates 保留 canonical patch/diff artifact。
2. 当出现 pair-level win/no-loss 或 loss diagnostic 时，自动触发 fresh champion replay 或标记 queue_validate_with_fresh_runtime，而不是让 runtime aggregate 长期 excluded。
3. 对 weak-positive current head 的 branch card 明确区分 code retention、evidence retention 和 follow-up policy。
4. 加强 proposal feedback 中的 phase-level causal summary：例如 Round 3 “local repair phase positive but final B-n52 loss”，Round 4 “acceptance phase positive and B-n31 pair win but case-level tie”。
5. 调整 smoke case selection 或 diagnostic wording，使 smoke activation coverage 与 formal screening 触发条件更一致。

## 9. 无法完全验证点

- Round 3/4 的完整最终 source diff 未在 `campaign/workspaces` 中保留；本报告依据 `agentic_sessions/*/output.json` 的 patch summary/repair attribution、self-check/smoke artifacts、DB event、metrics 进行还原。
- transcript 文件存在但逐轮分析主要依赖 `output.json`、tool ledgers、llm trace index 与 metrics；如 transcript 内有额外自由文本推理，本报告没有把它作为决策证据使用。
- `status.json` 与 `campaign_summary.json` 对 cross-branch/evidence scope 的 source counts 表达不同；本报告把它作为审计限制，而非判定 run invalid。

