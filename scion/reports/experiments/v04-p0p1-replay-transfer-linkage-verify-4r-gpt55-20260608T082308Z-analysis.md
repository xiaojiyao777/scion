# Scion 4R linkage 修复后完整实验后验分析

实验：`v04-p0p1-replay-transfer-linkage-verify-4r-gpt55-4r-gpt55-20260608T082308Z-claw`  
Run root：`/home/clawd/research/scion-experiments/v04-p0p1-replay-transfer-linkage-verify-4r-gpt55-4r-gpt55-20260608T082308Z-claw`  
Campaign：`/home/clawd/research/scion-experiments/v04-p0p1-replay-transfer-linkage-verify-4r-gpt55-4r-gpt55-20260608T082308Z-claw/campaign`  
报告时间：2026-06-08

## 结论先行

这次 4R 是一次**有效完成的 post-fix smoke**。wrapper 正常结束：`run_status.status=finished`、`wrapper_exit_status=0`、`ended_at=2026-06-08T08:53:52Z`。campaign validity 也完整：`valid=true`、`complete=true`、`requested_rounds=4`、`effective_rounds_completed=4`、`stopped_reason=max_rounds_exhausted`。

核心判断：

- semantic linkage 修复有效解决了上一组 partial 4R 的 proposal quality gate loop：本次 `proposal_attempts_total=4`，`formal_screened_candidates=4`，`protocol_evaluated_candidates=4`，`quality_blocks=0`；上一组 partial 是 `proposal_attempts_total=12`、只完成 2 个 formal candidates、后 10 次全部卡在 `branch_lesson_usage_required_missing`。
- 本次 4 个 formal candidates 都通过 Contract 与 Verification，并进入 screening；没有 scheduler active slot block，也没有 branch lifecycle policy block。
- `branch_lesson_usage_present=4`、`usage_satisfied=4`、`present_not_semantic=0`、`linkage_unrecognized=0`、`semantic_mismatch=0`，说明 gate 已能识别结构化 lesson usage，不再把存在的 semantic linkage 误报为 missing。
- 研究质量仍弱：4 个候选均未达到 promotion/validation/frozen。R1 是 regression 并 abandon；R2 是 tie-dominated quality regression；R3/R4 是 runtime/fresh-champion 相关的 unclear/weak signal，但没有 case-level improvement。
- 跨分支经验利用有真实语义影响，主要表现为 avoid/contrast 促使 target/mechanism 从 `destroy_repair.py` -> `route_merge.py` -> `local_search.py` -> `scheduler.py` 迁移；但这仍是“避开失败面/对比失败面”，不是借用弱正机制。`borrowed=0`、`weak_positive_transfer=0` 合理，因为本次 4R 内没有已经被 fresh replay 验证的正向 lesson。
- fresh replay 修复**未被闭环验证**。`fresh_champion_required_count=2` 且最终 branch card 中 `4411a29a...` 与 `09a13f03...` 都保持 `fresh_runtime_pending=true/fresh_runtime_required=true`，说明系统能标记 replay 需求，但在 max-round 终止前没有调度并执行 fresh replay。4R 不足以证明 replay scheduling 正确；需要 targeted replay test/experiment。
- 不建议直接升 8R。应先修或验证 fresh replay scheduling / replay-before-max-round termination；同时增加 weak-positive transfer trigger 的 targeted coverage。semantic linkage loop 可以视为通过 4R smoke，但 replay 与 weak-positive transfer 仍未通过验收。
- v3 边界守住：cross-branch lesson、candidate intent、observability/runtime guidance 都标为 `proposal_visibility_only` 或 `decision_features_excluded`；Decision 仍由 Contract/Verification/Protocol 后的 deterministic features 与 reason codes 驱动，没有把 LLM free text 或 lesson text 放进 DecisionFeatures。

## 运行有效性与全局计数

| 项 | 结果 | 判断 |
|---|---:|---|
| wrapper 状态 | `finished`, exit 0 | 进程正常结束 |
| ended_at | `2026-06-08T08:53:52Z` | 已落盘 |
| run validity | `valid=true`, `complete=true` | 完整有效 |
| requested / effective rounds | 4 / 4 | 满足 4R |
| stopped_reason | `max_rounds_exhausted` | 正常轮次耗尽 |
| total_rounds / screened_rounds | 4 / 4 | 口径一致 |
| formal_screened_candidates | 4 | 与 effective rounds 一致 |
| protocol_evaluated_candidates | 4 | 全部进入 screening |
| proposal_attempts_total | 4 | 无额外 quality loop |
| quality_blocks | 0 | linkage gate 不再误杀 |
| scheduler_active_slot_blocked_attempts | 0 | 无 active slot 阻塞 |
| branch_lifecycle_policy_blocks | 0 | 无 lifecycle policy 阻塞 |
| fresh_champion_required_count | 2 | replay 需求出现 |
| LLM traces | 32，全 ok | trace 完整 |
| model set | `['gpt-5.5']` | 模型符合要求 |

LLM request kind 分布：

| request kind | count |
|---|---:|
| `hypothesis_target_intent` | 4 |
| `hypothesis` | 5 |
| `tool_selection` | 18 |
| `code` | 5 |

`code=5` 是因为 Round 2 的 code session 有一次 contract preview retry：初版 route merge patch 被 `C9c_complexity_bound` 拦截，原因是 uncapped while loop；第二次 code 修复后才进入 formal candidate。这是 code preview 的正常修复路径，不是 quality block。

## 逐 LLM 调用核对

| Session | Branch | 阶段 | Call sequence | 结果 |
|---|---|---|---|---|
| S01 `ab7010e5` | `bb37bb2e` | hypothesis | target_intent -> hypothesis | 产出 `slack_biased_regret_repair`，目标 `destroy_repair.py` |
| S02 `4633698c` | `bb37bb2e` | code | tool_selection x6 -> code | code 完成，进入 formal screening |
| S03 `5410b616` | `43b508d6` | hypothesis | target_intent -> hypothesis | 产出 `route_merge_postrepair`，目标新文件 `route_merge.py` |
| S04 `a3b610ad` | `43b508d6` | code | tool_selection x6 -> code x2 | 第一次 code preview 因复杂度界限失败，第二次完成 |
| S05 `41a85c0c` | `4411a29a` | hypothesis | target_intent -> hypothesis | 产出 `route_compaction_2opt_star`，目标 `local_search.py` |
| S06 `0040380a` | `4411a29a` | code | tool_selection x2 -> code | code 完成，进入 formal screening |
| S07 `ef71ae0d` | `09a13f03` | hypothesis | target_intent -> hypothesis x2 | 初版 schema/telemetry preview 有问题，retry 后产出 `operator_observability_bandit` |
| S08 `1f10c787` | `09a13f03` | code | tool_selection x4 -> code | code 完成，进入 formal screening |

所有 trace 的 `ok=true`，模型均为 `gpt-5.5`。没有 LLM API failure、auth failure、process crash 或 protocol in-flight interrupt。

## 逐轮 formal candidate 分析

### Round 1：`bb37bb2e`，`slack_biased_regret_repair`

- Hypothesis：修改 `policies/baseline_modules/destroy_repair.py`，在 regret-2/3 repair 的近似同分 insertions 中加入 residual slack 与 insertion cost tie-break，避免松散装载造成 route-limit/rejection 或距离劣化。
- 上下文充分性：首轮已经有 problem summary、active solver facts、active solver map、`destroy_repair.py`/`local_search.py`/`scheduler.py` 源码、operator registry 与 boundary control。对首轮机制选择足够；cross-branch lesson 尚无实质历史。
- branch_lesson_usage：存在 1 个 avoided lesson，但它指向同一机制/同一 branch 的预占位 lesson，语义价值有限，更像 clean-fork diversity schema 的启动占位，不应过度解释为真实跨分支学习。
- Code：修改 `_regret2_insertion`、`_regret3_insertion`、`_regret_insertion`，加入 `context` telemetry、slack-biased insertion 与 phase recording。
- Contract/Verification：`contract_passed=true`，`verification_passed=true`。
- Protocol：screening 8 cases / 16 pairs，`gate_outcome=fail`。case 0 win / 1 loss / 7 tie；pair 1 win / 4 loss / 11 tie；`median_delta=0.0`，CI `[-5.5, 0.0]`。
- Telemetry/runtime：activation observed，effect positive，但 objective gate 失败；runtime confidence high，runtime pairs 16，同时有 `SCREENING_RUNTIME_BUDGET_SATURATION` 与 `BOTH_RUNTIME_BUDGET_SATURATION`。
- Decision：`abandon`，source 是 `lifecycle_policy`，reason 包含 `SCREENING_FAIL_WIN_RATE`、`BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`、`SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN`、`SCREENING_SOFT_ABANDON_NON_POSITIVE_CI`。
- 研究评价：机制可解释、实现边界正确，但结果是明确 regression；abandon 合理。

### Round 2：`43b508d6`，`route_merge_postrepair`

- Hypothesis：新增 `policies/baseline_modules/route_merge.py`，在 construction/repair 后做 bounded capacity-feasible route merge/compression，目标是在不破坏 fleet_violation 的前提下降低 distance。
- 上下文充分性：看到 R1 screening feedback 和 runtime feedback，prompt 中有 1 条 screening row、runtime feedback、cross-branch map、branch_lesson_usage_context、active solver source。足够支撑“避开 destroy_repair slack bias，转向 post-repair route merge”的选择。
- branch_lesson_usage：真实语义满足。它 avoided `lesson:f73900de210b4840`，明确从 closed/failed slack-biased destroy_repair 转向 route-count-preserving route merge；contrasted lesson 使用 `new_observable_postrepair_phase`，并给出 target_file/action/effect_path/activation_path/runtime strategy。输出不是只填 lesson_id。
- Code：新增 route merge helper，并集成到 solver path。第一次 code preview 因 `_nearest_sequence` 内 uncapped while loop 被 `C9c_complexity_bound` 拦截；retry 后加入 bounded/capped 实现才进入 formal candidate。
- Contract/Verification：`contract_passed=true`，`verification_passed=true`。
- Protocol：screening 12 cases / 24 pairs，`gate_outcome=fail`。case 0 win / 0 loss / 12 tie；pair 0 win / 2 loss / 22 tie；`median_delta=0.0`，CI `[0.0, 0.0]`。
- Telemetry/runtime：activation observed，但 effect missing / activated_no_positive_effect；runtime confidence `low_cached_champion`，runtime pairs 16，champion cached runtime pairs 8；candidate runtime saturation。
- Decision：`continue_explore`，但不是因为质量好，而是 stage decision 把它作为 tie-dominated diagnostic / observability candidate 继续收集，reason 包含 `SCREENING_FAIL_WIN_RATE`、`SCREENING_NEUTRAL_SIGNAL_CONTINUE`、`SCREENING_RUNTIME_SATURATION_DIAGNOSTIC`、`SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE`。
- 研究评价：跨分支 avoid/contrast 真实影响了 target 与 mechanism，但算法效果没有成立；后续 branch card 标记为 active_quality_regression，candidate code discarded。

### Round 3：`4411a29a`，`route_compaction_2opt_star`

- Hypothesis：修改 `policies/baseline_modules/local_search.py`，在 VNS registry 中加入 bounded route compaction / 2-opt-star-like neighborhood，尝试把低载 route 的 prefix/suffix/block 搬到兼容 route，优先 route compaction 而不是另一个 route merge module。
- 上下文充分性：看到前 2 轮 screening/runtime feedback，cross-branch map 更大，branch_lesson_usage_context 可见，并有 `local_search.py` grounded target context。足够支撑“避开 R2 route_merge.py zero/no-effect，转回 local_search VNS 内部邻域”的决策。
- branch_lesson_usage：真实语义满足。它 avoided `route_merge_postrepair` 的 zero/no-effect 与 slack-biased destroy_repair closed lesson；contrasted `lesson:a6a324357b38eab9`，将 action/target_file/effect_path/activation_path/runtime_budget_strategy 都改成 local_search route compaction。实际 code 也确实改 `local_search.py` 并注册 `_route_compaction_2opt_star`。
- Code：新增 `_route_compaction_2opt_star` 并加入 neighborhood list，带 `context.record_iteration`、`record_move`、`record_phase`。
- Contract/Verification：`contract_passed=true`，`verification_passed=true`。
- Protocol：screening 8 cases / 16 pairs，`gate_outcome=unclear`。case 0 win / 0 loss / 8 tie；pair 0 win / 1 loss / 15 tie；`median_delta=0.0`，CI `[0.0, 0.0]`。
- Telemetry/runtime：activation observed，effect zero / evaluated_no_effect；runtime confidence `low_cached_champion`，runtime pairs 0，champion cached runtime pairs 16；runtime aggregate excluded，fresh champion required。
- Decision：`continue_explore`，reason 包含 `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`、`TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`、runtime saturation。不是 promotion，也不是 validation。
- 研究评价：avoid/contrast 真实改变了机制面，但候选本身没有带来 objective gain，还产生 one-pair loss 和 effect-zero diagnostic。最终 branch card：`fresh_runtime_pending=true`、`fresh_runtime_required=true`，trigger 是 `actionable_loss_diagnostic`。

### Round 4：`09a13f03`，`operator_observability_bandit`

- Hypothesis：修改 `policies/baseline_modules/scheduler.py`，增加 destroy-repair pair-level observability/bandit selection，跟踪 pair activation、accepted/improving yield、zero-yield streak，并用轻量 penalty 减少低产组合的尝试。
- 上下文充分性：看到前 3 轮 screening/runtime feedback、cross-branch map、branch lessons、scheduler source 与 target-intent grounded context。初版 expected telemetry 与 no-objective-changing path 有矛盾，schema preview 给出反馈后重试通过。上下文足够，且 retry 起到了边界修复作用。
- branch_lesson_usage：真实语义满足。它 avoided slack-biased destroy_repair，contrasted route neighborhood/route merge/local_search compaction lessons，并明确转到 scheduler pair selection/observability，而不是再加邻域。实际 code 也改 `scheduler.py`，引入 pair score/attempt/zero streak table 与 `_choose_operator_pair`。
- Code：在 ALNS loop 中记录 `operator_observability_bandit` iteration/phase，维护 pair scores 与 zero streaks，成熟后用 epsilon floor 的 pair score sampling 代替独立 destroy/repair choice。
- Contract/Verification：`contract_passed=true`，`verification_passed=true`。
- Protocol：screening 8 cases / 16 pairs，`gate_outcome=unclear`。case 0 win / 0 loss / 8 tie；pair 1 win / 0 loss / 15 tie；`median_delta=0.0`，CI `[0.0, 0.0]`。
- Telemetry/runtime：activation observed，effect attribution missing / activated_no_positive_effect；runtime confidence `low_cached_champion`，runtime pairs 0，champion cached runtime pairs 16；runtime aggregate excluded，fresh champion required。
- Decision：`continue_explore`，reason 包含 `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`、runtime saturation。最终 branch card 保持 active slot。
- 研究评价：这是 4R 中唯一有 pair-level win/no-loss 的 weak signal，但 case-level 仍全 tie，runtime 证据依赖 cached champion，不能推广为机制成功。最终 branch card：`fresh_runtime_pending=true`、`fresh_runtime_required=true`，trigger 是 `pair_level_win_no_loss`。

## 跨分支经验利用分析

本次 cross-branch summary：

| 项 | count |
|---|---:|
| branch_lesson_record_count | 11 |
| branch_lesson_usage_requirement_count | 4 |
| branch_lesson_usage_present_count | 4 |
| branch_lesson_usage_satisfied_count | 4 |
| branch_lesson_usage_present_not_semantic_count | 0 |
| linkage_unrecognized / semantic_mismatch | 0 / 0 |
| borrowed_lesson_count | 0 |
| avoided_lesson_count | 5 |
| contrasted_lesson_count | 5 |
| preserved_same_branch_lesson_count | 0 |
| weak_positive_transfer_count | 0 |
| weak_positive_transfer_reject_count | 0 |
| decision_input_policy | `excluded_from_decision_features` |

avoid/contrast 是否真实影响了机制：

- R2 避开 R1 的 destroy_repair slack-bias，转向 create_new `route_merge.py`。这是 target_file/action/mechanism_family 的真实变化。
- R3 避开 R2 的 postrepair route_merge no-effect，转入 `local_search.py` 的 VNS registry，强调 bounded route compaction 而非 standalone route merge。实际 code 与 hypothesis 一致。
- R4 避开 route_compaction/route_merge 的 no-effect，转入 `scheduler.py` 的 operator pair selection/observability。实际 code 与 hypothesis 一致。

因此本次 `branch_lesson_usage_satisfied=4` 不是单纯 schema 字段满足；至少 R2-R4 的 usage 真实改变了 mechanism/target/code。不过研究利用质量仍偏“负迁移规避”：agent 会避开失败方向、对比失败方向，但还没有将弱正机制抽象成可复用组件。

为什么 `borrowed=0` 与 `weak_positive_transfer=0` 仍合理：

- 本次没有 promotion、validation、frozen，也没有 fresh champion replay 后的 positive evidence。
- R3/R4 产生的是 `unclear` 或 pair-level weak signal，且 runtime evidence 为 `low_cached_champion`，系统要求 fresh champion 后才能把 runtime/tie signal 用于升级。
- 借用弱正机制需要一个可借用、可信的 source lesson；本次之前的 lesson 大多是 regression/no-effect/abandoned，最适合 avoid/contrast，而不是 borrow。
- 4R 太短，刚出现 weak-positive marker 就达到 max_rounds，没留出 fresh replay 或后续 transfer turn。

## 与上一组 partial 4R 对比

上一组 partial 报告的关键事实：

- `run_validity.valid=true` 但 `complete=false`，`effective_rounds_completed=2`。
- `formal_screened_candidates=2`，`protocol_evaluated_candidates=2`。
- `proposal_attempts_total=12`，`quality_blocks=10`。
- 后 10 次集中卡在同一 branch 的 `branch_lesson_usage_required_missing`，停止原因是 `proposal_attempt_limit_exhausted`。
- artifacts 中实际存在 `branch_lesson_usage`，但 gate/ledger 仍误判 missing，根因是 semantic linkage 识别断裂。

本次 evidence：

- `run_validity.complete=true`，`effective_rounds_completed=4`，停止原因转为 `max_rounds_exhausted`。
- `proposal_attempts_total=4`，`quality_blocks=0`，没有 `branch_lesson_usage_required_missing`。
- cross-branch observability 中 `usage_present=4`、`usage_satisfied=4`，且 `present_not_semantic=0`、`linkage_unrecognized=0`、`semantic_mismatch=0`。
- 逐 artifact 检查显示 R2-R4 的 usage 不只是字段存在，而是包含 lesson_id、avoid/contrast reason、target_file、action、mechanism family、activation/effect path、runtime strategy，并且最终 code 真的改到了相应 target。

所以可以确认：semantic linkage 修复解决了上一组 partial 4R 的 quality gate loop。剩余问题已经从“proposal gate 无法前进”转移到“研究候选质量弱、fresh replay 未闭环、weak-positive transfer 未触发”。

## Fresh replay 修复验证状态

本次 `fresh_champion_required_count=2` 是重要进展：系统不再完全漏掉 fresh runtime pressure。两个最终 branch card 均有 replay 标记：

- `4411a29a... route_compaction_2opt_star`：`fresh_runtime_pending=true`、`fresh_runtime_required=true`，trigger=`actionable_loss_diagnostic`，reason 包含 `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED` 与 `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`。
- `09a13f03... operator_observability_bandit`：`fresh_runtime_pending=true`、`fresh_runtime_required=true`，trigger=`pair_level_win_no_loss`，reason 包含 `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`。

但这**不等于 replay scheduling 已被验证**。它证明了：

1. screening finalizer 能识别 low_cached_champion / runtime aggregate excluded。
2. branch card 能持久化 `fresh_champion_runtime_replay_pending`。
3. fresh replay requirement 没有污染 promotion boundary，仍是 proposal/guidance/follow-up 语义。

它没有证明：

1. scheduler 会在 max-round termination 前优先执行 fresh replay。
2. pending replay 会消耗何种 budget counter，是否应该计入 effective rounds。
3. fresh replay 执行后是否清除 pending、刷新 runtime confidence、生成可用于后续 transfer 的 lesson。
4. pair-level weak signal 是否能在 replay 后转成 borrowable weak-positive lesson。

因此更准确的解释是：4R 已覆盖 fresh replay marker，但没有覆盖 fresh replay execution。由于 max-round budget 以 `effective_rounds_completed` 为 counter，系统在第 4 个 formal screening 后立即停在 `max_rounds_exhausted`，没有给 pending replay 留出独立调度机会。这里既可能是 4R 不足，也可能是 replay-before-max-round termination 的调度语义仍未实现；需要 targeted test/experiment 区分。

建议针对 replay 做一个短程 targeted 验收，而不是用 8R 顺带观察：

- 构造或选择能稳定触发 `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED` 的 screening candidate。
- 设置 `requested_rounds` 刚好等于触发轮次，验证 max-round termination 前是否仍执行 pending fresh replay，或明确设计为 replay 不计入 requested rounds。
- 验收 branch card 从 pending -> executed/cleared 的状态转换。
- 验收 replay 后 runtime confidence 从 `low_cached_champion` 改为 fresh/sufficient，且 `runtime_aggregate_excluded` 状态正确更新。

## 分支内研究质量

本次分支内研究深度有限：

- 没有同一 branch 的 multi-round refine。4 个 formal candidates 都是 clean fork / new branch 方向。
- R1 regression 后 abandon 合理。
- R2 tie-dominated/no-effect 后仍保留 diagnostic follow-up，但 candidate code discarded。
- R3/R4 是 runtime/fresh-required 的 weak/unclear follow-up 候选，却在触发 pending 后到达 max rounds。
- `same_branch_refinement_not_selected_count=4`，说明 scheduler 一直选择 clean fork，而不是深挖已有 weak branch。

这对 smoke 不是失败，因为本轮主要验证 linkage gate 修复；但它不能证明 Scion 已具备分支内研究深度。若升阶，至少要看到一个 branch 在 weak-positive/fresh replay 后做 branch-local refine，而不是每轮都开新面。

## 是否可以升 8R

不建议直接升 8R。

理由：

1. semantic linkage gate 已过 smoke，但 fresh replay execution 没有过验收。
2. 两个需要 fresh replay 的 branch 在结束时仍 pending，说明 4R 没覆盖 replay scheduling。
3. weak-positive transfer 仍为 0；本轮只有 pair-level weak signal，没有 fresh-confirmed positive source。
4. 研究质量偏 observability/diagnostic，`candidate_intent_counts.observability_candidate=4`，没有 quality_candidate。
5. 若直接升 8R，可能只是继续积累 tie/diagnostic candidates，不能回答 replay-before-max-round 与 weak-positive borrow 的机制问题。

建议主会话下一步：

1. 先保留 semantic linkage 修复为通过项：它解决了 partial 4R 的 quality gate loop。
2. 立刻做 fresh replay targeted test/experiment，明确 pending replay 在 max-round 边界前后的调度语义。
3. 修或验证 replay-before-max-round termination：如果 replay 是 required follow-up，不能只在 branch card 留 pending 后直接停。
4. 增加 weak-positive transfer trigger 验收：让 fresh-confirmed weak-positive lesson 至少触发 borrow 或 machine-readable reject，而不是长期 `borrowed=0/weak_positive_transfer=0`。
5. 只有当 fresh replay targeted 验收通过，才升 8R；8R 的验收重点应是至少一次 branch-local refine 或 explicit bridge，而不是只看 completed rounds。

## v3 边界判断

按 `scion/design/scion-architecture-v3.md`，LLM output 是 tainted proposal；必须经过 Contract -> Verification -> Protocol -> Safe Feature Extractor 才能成为 DecisionFeatures；Decision Layer 只允许读取无自由文本的 deterministic features。

本次边界没有被破坏：

- 4 个 formal candidates 都先通过 Contract 与 Verification，再进入 Protocol。
- Decision reason codes 来自 screening/lifecycle/runtime deterministic outputs，例如 `SCREENING_FAIL_WIN_RATE`、`RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`、`SCREENING_RUNTIME_BUDGET_SATURATION`。
- `candidate_intent_visibility` 均标注 `formal_decision_unchanged=true`、`proposal_visibility_only=true`、`decision_features_excluded=true`。
- `observability_value_visibility` 与 `runtime_evidence_policy` 均标注 `decision_features_excluded=true`。
- `fresh_runtime_followup` 标注 `promotion_boundary=not_a_promotion_or_validation_decision`、`proposal_visibility_only=true`、`decision_features_excluded=true`。
- cross-branch research observability 的 policy 是 `proposal_observability_only`，`decision_input_policy=excluded_from_decision_features`。

因此，lesson/free text 没有污染 DecisionFeatures。当前风险不是 v3 决策边界失守，而是 proposal guidance 质量、fresh replay scheduling 和 weak-positive transfer coverage 还不足。

## 最终结论

这次 4R 完整实验通过了 semantic linkage 修复的关键 smoke：上一组 partial 的 `branch_lesson_usage_required_missing` quality gate loop 已消失，4 个 proposal 都成为 formal candidates 并完成 screening。v3 决策边界保持干净。

但它不能作为直接升 8R 的充分依据。当前应把状态拆开看：linkage gate 已通过；fresh replay 只验证了 pending marker，未验证执行；weak-positive transfer 未触发；研究质量仍停留在 avoid/contrast 与 observability diagnostics。主会话下一步应先做 targeted fresh replay / max-round boundary 验收，并补 weak-positive transfer trigger，再决定是否升 8R。
