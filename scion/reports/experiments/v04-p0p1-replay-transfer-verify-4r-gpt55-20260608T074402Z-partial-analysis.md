# Scion 4R partial smoke 修复后实验分析

实验：`v04-p0p1-replay-transfer-verify-4r-gpt55-4r-gpt55-20260608T074402Z-claw`  
Run root：`/home/clawd/research/scion-experiments/v04-p0p1-replay-transfer-verify-4r-gpt55-4r-gpt55-20260608T074402Z-claw`  
Campaign：`/home/clawd/research/scion-experiments/v04-p0p1-replay-transfer-verify-4r-gpt55-4r-gpt55-20260608T074402Z-claw/campaign`  
报告时间：2026-06-08  

## 结论先行

这次 4R partial smoke 是一次**有效但未完成**的 partial run。wrapper 正常返回：`run_status.status=finished`、`wrapper_exit_status=0`、`ended_at=2026-06-08T08:05:13Z`。但 campaign 没有完成请求的 4 个有效轮次：`run_validity.valid=true`、`complete=false`、`completed_requested_rounds=false`，停止原因是 `proposal_attempt_limit_exhausted`。

核心判断：

- 这不是算法研究失败导致的 4R 失败，而是 proposal quality gate 的 framework regression。
- 已完成的 2 个 formal candidates 都通过了 Contract 与 Verification，并进入 screening；二者算法结果都没过 screening gate，abandon 合理。
- 后续 10 次 attempt 全部卡在同一个新分支 `3ed61c7d-7243-49c0-a051-000128cd17ac`，全部是 pre-protocol proposal block，失败类型均为 `proposal`。
- prompt 已投放 `branch_lesson_usage_requirement` 和 lesson ids；LLM 输出也包含结构化 `branch_lesson_usage` 与 `mechanism_id`/target/action linkage，但 gate/ledger 仍把它们记成 `branch_lesson_usage_required_missing`。这说明 gate 过严或 semantic linkage 识别断裂，而不是 LLM 完全没有使用 branch lessons。
- 不能升 8R/12R/20R。必须先修复 branch_lesson_usage semantic linkage，再重跑 4R partial smoke。

## 运行有效性与全局计数

| 项 | 结果 | 判断 |
|---|---:|---|
| wrapper 状态 | `finished`, exit 0 | 进程正常结束 |
| ended_at | `2026-06-08T08:05:13Z` | 已落盘 |
| run validity | `valid=true`, `complete=false` | 有效 partial evidence |
| completed requested rounds | `false` | 未完成 4R |
| stopped_reason | `proposal_attempt_limit_exhausted` | proposal gate 耗尽 attempt |
| requested_rounds | 4 | 请求 4 个有效轮次 |
| effective_rounds_completed | 2 | 只完成 2 个有效轮次 |
| formal_screened_candidates | 2 | 只产生 2 个 formal candidate |
| protocol_evaluated_candidates | 2 | 只进入 screening 2 次 |
| proposal_attempts_total | 12 | 2 formal + 10 blocked |
| quality_blocks | 10 | 全部 pre-protocol |
| failure_categories.proposal | 10 | 失败集中在 proposal quality gate |
| all LLM traces observed | 38 | trace index 完整 |
| model set | `['gpt-5.5']` | 模型符合要求 |

LLM request kind 分布：

| request kind | count |
|---|---:|
| `hypothesis_target_intent` | 12 |
| `hypothesis` | 15 |
| `tool_selection` | 9 |
| `code` | 2 |

这组计数解释了 partial 形态：前 2 轮各有 hypothesis + code，后 10 次都停在 hypothesis 阶段，没有 code generation，也没有 Contract/Verification/Protocol。

## 逐 LLM 调用核对

| Session | Branch | 类型 | Call sequence | 结果 |
|---|---|---|---|---|
| S01 `ebfcfb4b` | `b3d764e8` | hypothesis | target_intent -> hypothesis | 产出 `cross_route_2opt_reconnect`，目标 `local_search.py` |
| S02 `a8b889cc` | `b3d764e8` | code | tool_selection x6 -> code | code session 完成，进入 formal screening |
| S03 `dd37f495` | `cb178cf5` | hypothesis | target_intent -> hypothesis x2 | 产出 `route_limit_aware_repair`，目标 `destroy_repair.py`，经历一次 hypothesis retry |
| S04 `9f13d4ee` | `cb178cf5` | code | tool_selection x3 -> code | code session 完成，进入 formal screening |
| S05 `ac57e0d4` | `3ed61c7d` | blocked hypothesis | target_intent -> hypothesis x2 | `budget_adaptive_alns_vns_gating`，blocked as required_missing |
| S06 `b53950f8` | `3ed61c7d` | blocked hypothesis | target_intent -> hypothesis | `savings_route_merge_bridge`，blocked |
| S07 `0466ae9f` | `3ed61c7d` | blocked hypothesis | target_intent -> hypothesis | `delta_scaled_acceptance`，blocked |
| S08 `819d298d` | `3ed61c7d` | blocked hypothesis | target_intent -> hypothesis x2 | `route_packing_seed`，blocked |
| S09 `7b695c7d` | `3ed61c7d` | blocked hypothesis | target_intent -> hypothesis | `relative_delta_acceptance`，blocked |
| S10 `a062418b` | `3ed61c7d` | blocked hypothesis | target_intent -> hypothesis | `alns_operator_phase_telemetry`，blocked |
| S11 `8ee65898` | `3ed61c7d` | blocked hypothesis | target_intent -> hypothesis | `relative_delta_sa_filter`，blocked |
| S12 `7aa1f54a` | `3ed61c7d` | blocked hypothesis | target_intent -> hypothesis | `relative_delta_sa_filter`，blocked |
| S13 `038fd280` | `3ed61c7d` | blocked hypothesis | target_intent -> hypothesis | `route_packing_seed`，blocked |
| S14 `dcc33f7d` | `3ed61c7d` | blocked hypothesis | target_intent -> hypothesis | `route_packing_seed`，blocked |

所有 trace 的 `ok=true`，模型均为 `gpt-5.5`。没有证据显示 LLM API failure、tooling auth failure、进程 crash 或 protocol in-flight interrupt。

## 逐轮分析

### Round 1：branch `b3d764e8`，`cross_route_2opt_reconnect`

- Hypothesis：修改 `policies/baseline_modules/local_search.py`，新增 bounded capacity-feasible cross-route 2-opt reconnect neighborhood。
- LLM 调用：S01 生成 target intent + hypothesis；S02 通过 6 次 tool selection 后生成 code。
- Contract/Verification：`contract_passed=true`，`verification_passed=true`。
- Protocol：screening 8 cases / 16 pairs，`gate_outcome=fail`。
- 结果：case 0 win / 1 loss / 7 tie；pair 1 win / 3 loss / 12 tie；`median_delta=0.0`，CI `[-1.5, 0.0]`。
- Runtime：`runtime_evidence_confidence=high`，但 both-side runtime budget saturation，`saturation_ratio=1.0176`。
- Decision：`abandon`，原因包括 `SCREENING_FAIL_WIN_RATE`、`SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN`、`SCREENING_SOFT_ABANDON_NON_POSITIVE_CI`、runtime saturation。
- 判断：这是一个有效 formal candidate，但算法上没有通过 screening。abandon 合理，不能算 framework failure。

### Round 2：branch `cb178cf5`，`route_limit_aware_repair`

- Hypothesis：修改 `policies/baseline_modules/destroy_repair.py`，将 repair insertion 改成 route-limit aware。
- LLM 调用：S03 生成 target intent + hypothesis，经历一次 hypothesis retry；S04 通过 3 次 tool selection 后生成 code。
- Contract/Verification：`contract_passed=true`，`verification_passed=true`。
- Protocol：screening 8 cases / 16 pairs，`gate_outcome=fail`。
- 结果：case 1 win / 0 loss / 7 tie；pair 3 win / 3 loss / 10 tie；`median_delta=0.0`，CI `[-0.5, 0.0]`。
- Runtime：`runtime_evidence_confidence=low_cached_champion`，runtime aggregate 被排除；candidate-side runtime saturation，`saturation_ratio=1.0144`。
- Telemetry：activation observed，但 effect attribution missing；无 telemetry guard failure。
- Decision：`abandon`，原因包括 `SCREENING_FAIL_WIN_RATE`、`SCREENING_SOFT_ABANDON_NON_POSITIVE_CI`、candidate runtime saturation。
- 判断：这是第二个有效 formal candidate。它有一点 case-level/pair-level weak signal，但没有达到 screening gate，也没有 fresh replay 或 validation。abandon 合理，不能作为 P0/P1 完整验收。

### Round 3-12：branch `3ed61c7d`，proposal quality loop

10 次 attempt 全部发生在同一个 branch `3ed61c7d-7243-49c0-a051-000128cd17ac`，全部是 `proposal_block`，全部 `counts_toward_max_rounds=false`，全部停止在 `failure_stage=proposal`。

质量门记录的共同失败：

```text
agent_quality_blocked:branch_lesson_usage_required_missing
structured branch_lesson_usage is required before code generation
```

这些 attempt 覆盖了多个 target/mechanism：

| Attempt | Target | Mechanism | LLM usage 形态 |
|---|---|---|---|
| R3 | `scheduler.py` | `budget_adaptive_alns_vns_gating` | avoided + contrasted lessons |
| R4 | `route_merge.py` | `savings_route_merge_bridge` | avoided + contrasted + rejected weak-positive |
| R5 | `acceptance.py` | `delta_scaled_acceptance` | avoided + contrasted + rejected weak-positive |
| R6 | `construction.py` | `route_packing_seed` | avoided + contrasted |
| R7 | `acceptance.py` | `relative_delta_acceptance` | avoided + contrasted + rejected weak-positive |
| R8 | `scheduler.py` | `alns_operator_phase_telemetry` | borrowed + avoided + contrasted |
| R9 | `acceptance.py` | `relative_delta_sa_filter` | avoided + contrasted |
| R10 | `acceptance.py` | `relative_delta_sa_filter` | avoided + contrasted + rejected weak-positive |
| R11 | `construction.py` | `route_packing_seed` | avoided + contrasted |
| R12 | `construction.py` | `route_packing_seed` | avoided + contrasted |

这不是“LLM 没有填字段”的简单问题。`agentic_sessions/*/output.json` 中这些 blocked hypotheses 均有 `branch_lesson_usage` 对象，且多次包含 `lesson_id`、`mechanism_id`、`target_file`、`action`、`activation_path`、`effect_path` 或 `changed_dimensions`。但 quality block ledger 仍统一归因为 `required_missing`。

因此更准确的根因是：quality gate 没有正确识别 LLM 输出中的 semantic linkage，尤其是 `mechanism_id` 与 lesson usage entry、target/action、activation/effect path 之间的链接。gate 把“存在但未被语义识别”的 usage 当成“缺失”。这就是本报告称为 Confucius root cause 的问题。

## 为什么这是 framework quality gate regression

这次 partial run 的失败点不是算法候选在 protocol 中连续失败，而是 framework 在 proposal 阶段形成了不可恢复的 quality loop：

- `proposal_attempts_total=12`，但只有 2 个进入 protocol。
- `quality_blocks=10`，且 10 次全部属于 `failure_categories.proposal`。
- `stopped_reason=proposal_attempt_limit_exhausted`，不是 `max_rounds_exhausted`。
- blocked attempts 没有进入 code generation，所以没有 Contract、Verification、screening、validation 或 frozen 证据。
- blocked attempts 的 target/mechanism 并不完全重复，LLM 也并非只输出空壳；它尝试了 scheduler、route_merge、acceptance、construction 等多个 surface。
- framework 自己的 stagnation signal 也将其归类为 `proposal_quality_loop`，建议 `inspect_agent_trace`，并说明是 proposal/code-generation quality 或 prompt/gate feedback mismatch。

算法层面，前两个 formal candidates 的 screening failure 是正常研究信号：它们没有过 objective gate，生命周期 abandon 合理。但 4R 没完成的直接原因是后续 10 次 pre-protocol block，而不是算法候选被 protocol 判差。

## 与 Scion v3 架构的一致性

按照 `scion/design/scion-architecture-v3.md`，Scion v3 的硬边界是：LLM 只能 proposal，输出视为 tainted；Contract -> Verification -> Protocol -> Safe Feature Extractor 之后才能形成 `DecisionFeatures`；Decision Layer 只允许读取 `DecisionFeatures`，不能读 LLM 自由文本。

本次 partial run 中，这个边界总体仍守住：

- 已完成的 2 个 candidate 都先通过 Contract 与 Verification，再进入 Protocol。
- Decision 使用 screening gate/lifecycle reason codes，例如 `SCREENING_FAIL_WIN_RATE`、`SCREENING_SOFT_ABANDON_NON_POSITIVE_CI`，没有用 LLM rationale 直接晋升或调度。
- `candidate_intent_visibility`、`observability_value_visibility`、`runtime_evidence_policy`、`cross_branch_research_observability` 均标注 proposal-only / excluded from DecisionFeatures。
- Cross-branch lesson 与 branch_lesson_usage 是 proposal observability/guidance，不是 deterministic decision input。
- 10 次失败发生在 proposal quality gate，位于 code generation、Contract、Verification、Protocol 之前；没有污染 DecisionFeatures。

因此这不是 v3 边界失守，而是 v3 边界内的 proposal quality gate 语义识别回归：gate 正确地没有放行不满足要求的 proposal，但错误地把已填结构化 usage 判断为 missing，导致无法前进。

## P0/P1 修复验证状态

| 项 | 本次观察 | 验证结论 |
|---|---|---|
| run wrapper finalization | `finished` + exit 0 + ended_at 落盘 | 已验证 |
| partial run validity | `valid=true` 且 `complete=false` | 已验证 partial 语义 |
| effective/formal accounting | requested 4，effective 2，formal 2，protocol 2 | 已验证计数口径 |
| Contract/Verification 基本链路 | 2 个 formal candidate 均通过 | 已验证基本链路仍可工作 |
| DecisionFeatures 边界 | proposal/observability/runtime guidance 均 excluded | 已验证边界未破 |
| branch_lesson_usage prompt 投放 | prompt/context 有 requirement 与 lesson ids | 已验证投放存在 |
| branch_lesson_usage gate | 10 次 blocked as `required_missing` | 未通过，且是当前 P0 blocker |
| semantic linkage 识别 | LLM 输出有 usage 与 mechanism linkage，但 gate 不认 | 未通过 |
| fresh replay | 未触发 fresh replay/validation/frozen | 未验证，不能证明有效 |
| weak-positive transfer | `weak_positive_transfer_count=0`，`weak_positive_transfer_reject_count=0` | 未验证 |
| target-intent block | 本次没有 target-intent mismatch block | 未验证，只能说明未出现 |
| telemetry block | `telemetry_failed_experiments=0`，但只有 2 个 protocol candidates | 未验证完整覆盖 |
| telemetry effect attribution | Round 2 有 effect attribution missing advisory | 只验证可见性，不是 block 链路验收 |

特别注意：`fresh_champion_required_count=0` 与没有 fresh replay 不能解释为 fresh replay 修复有效。它只是说明本次 run 没走到需要 fresh replay 的状态。同理，weak-positive transfer 未出现，不能作为 transfer 修复通过证据。

## Cross-branch observability 读数

本次 `cross_branch_research_observability` 关键计数：

| 项 | count |
|---|---:|
| `branch_lesson_record_count` | 8 |
| `branch_lesson_usage_requirement_count` | 4 |
| `branch_lesson_usage_present_count` | 2 |
| `branch_lesson_usage_satisfied_count` | 2 |
| `branch_lesson_usage_present_not_semantic_count` | 0 |
| `branch_lesson_usage_missing_block_count` | 10 |
| `borrowed_lesson_count` | 0 |
| `avoided_lesson_count` | 3 |
| `contrasted_lesson_count` | 0 |
| `weak_positive_transfer_count` | 0 |
| `weak_positive_transfer_reject_count` | 0 |

这里有一个关键不一致：summary 只把 2 次 usage 记为 present/satisfied，但 blocked branch 的 output artifacts 实际包含多个 `branch_lesson_usage` 对象。也就是说，observability 聚合层只认可了前两个已通过/已进入 formal 的 proposal usage，而 proposal quality block ledger 对后续 10 次全部记为 missing。这个不一致支持“semantic linkage 解析/认可逻辑过严或断裂”的判断。

## 是否可以升 8R/12R/20R

不能升。

原因很直接：

1. 请求 4R 只完成 2 个 effective rounds，没有完成 partial smoke 的最小请求。
2. 当前停止原因是 `proposal_attempt_limit_exhausted`，继续升轮次只会扩大同一 gate loop 的成本。
3. fresh replay、weak-positive transfer、target-intent block 修复、telemetry block 修复都没有被充分触发或覆盖。
4. branch_lesson_usage gate 是 P0/P1 当前阻塞点：它把有结构化 usage 的 proposal 仍判为 missing。
5. 12R 参考报告中的健康形态是“12 个 formal screened candidates + 少量合理 block/repairable”；本次形态是“2 formal + 10 proposal block”，质量级别完全不同。

## 下一步验收标准

修复后应先重跑同等 4R partial smoke，不应直接升 8R/12R/20R。建议验收标准如下：

1. `run_status.status=finished`、`wrapper_exit_status=0`，且 campaign `run_validity.valid=true`。
2. `completed_requested_rounds=true`，`effective_rounds_completed=4`，`formal_screened_candidates=4`，`protocol_evaluated_candidates>=4`。
3. `quality_blocks` 可以存在，但不得再次出现连续同因 `branch_lesson_usage_required_missing`；同一 branch 同因连续 block 应小于 2，并给出可执行 repair feedback。
4. 对包含 `branch_lesson_usage`、`lesson_id`、`mechanism_id`、`target_file`、`action`、`activation_path/effect_path` 的 proposal，gate 必须能识别 semantic linkage，不能误报 required_missing。
5. 质量门 ledger 要区分三类状态：字段缺失、字段存在但 schema 不合格、字段存在但 semantic linkage 不满足。不能统一压成 missing。
6. `branch_lesson_usage_present_count` 与 blocked proposal artifacts 的实际存在性要能对账；如果 block 是 semantic failure，应进入 present-not-semantic 或 equivalent reason，而不是 missing。
7. Cross-branch observability 仍必须保持 `decision_input_policy=excluded_from_decision_features`，不能为了修 gate 把 lesson usage 推入 DecisionFeatures。
8. 至少出现一个 clean-fork/sibling-aware proposal 被 quality gate 接受并进入 code generation，证明 branch_lesson_usage gate 不再阻断所有后续探索。
9. 若出现 weak-positive evidence，必须触发 borrow/preserve 或 machine-readable reject 的验收路径；否则仍不能宣称 weak-positive transfer 已验证。
10. 若仍未触发 fresh replay、target-intent block 或 telemetry block，只能记录为“未覆盖”，不得写成“已验证通过”。

## 最终结论

本次 run 是有效 partial evidence，但不能作为升阶依据。它验证了 wrapper finalization、partial validity accounting、前两轮 Contract/Verification/Protocol 基本链路和 DecisionFeatures 边界；同时暴露了一个阻断性的 branch_lesson_usage quality gate regression。

必须先修 semantic linkage 识别，尤其是 `mechanism_id` 与 lesson usage entry、target/action、activation/effect path 的关联判断；然后重跑 4R。只有当 4 个 requested rounds 完成，并且 branch_lesson_usage gate 不再误杀结构化 proposal，才可以讨论升到 8R/12R/20R。
