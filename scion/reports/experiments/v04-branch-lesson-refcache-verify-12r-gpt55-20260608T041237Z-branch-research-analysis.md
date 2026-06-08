# v04 branch lesson refcache verify 12R GPT-5.5 branch research analysis

实验目录：`/home/clawd/research/scion-experiments/v04-branch-lesson-refcache-verify-12r-gpt55-20260608T041237Z-claw/campaign`

主要证据：`campaign_summary.json`、`status.json`、`run_status.json`、`llm_traces/*.json`、`agentic_sessions/agentic_session_index.json`、`agentic_sessions/agentic_session_trace_index.json`、各 session 的 `output.json` / `transcript.json`、`scion.db`。

## 结论

不建议直接进入更长质量实验。当前 12R 证明了 branch lesson refcache/visibility 机制可以稳定产出审计字段，也证明了 proposal/Decision 边界基本守住了；但它还没有证明跨分支经验会稳定产生有效研究增益。12 个有效 screening 全部停在 screening，validation=0、frozen=0、promoted=0；其中 8 个结果被 `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED` 限制，11/12 个 runtime aggregate 因 low/cached champion 被排除。唯一 weak-positive 分支 `b80205c9` 形成了后续 refine，但后续 refinement 没有推进到 validation，最后还被 plateau clean-fork 策略抑制。

建议先优化机制，再放大轮数。优化重点不是降 token/calls，而是减少“字段合规但研究影响弱”的情况：修复 proposal action retry、让 fresh champion replay 真正执行并解除低可信 runtime tie、把 weak-positive lesson 纳入后续 proposal visibility、对 `branch_lesson_usage` 做语义一致性校验，并给 weak-positive 分支单独的 validation 或 replay 预算。

## 总体运行事实

| 项 | 值 | 解释 |
|---|---:|---|
| requested_rounds | 12 | requested_rounds 约束的是 effective screening rounds |
| total_rounds / proposal_attempts | 13 / 13 | 包含 1 次 proposal 阶段 quality block |
| screened_rounds / effective_rounds_completed | 12 / 12 | 12 个 formal screening candidate |
| protocol_stage_counts | screening=12, validation=0, frozen=0 | 没有任何候选进入验证/冻结 |
| promoted_experiments | 0 | 没有 promotion |
| quality_blocks | 1 | `existing_file_create_new_rejected` |
| llm traces / agentic sessions | 91 / 25 | 13 个 hypothesis phase session + 12 个 code phase session |
| runtime policy | fresh_champion_required_count=8, runtime_aggregate_excluded_count=11 | runtime 信号大多被作为 audit/proposal guidance，而非独立优化证据 |
| cross-branch lesson | requirements=12, present=12, satisfied=12 | 字段层面全部满足 |
| weak-positive transfer | 0 | 没有把 weak-positive 经验作为跨分支 transferable lesson |

## 逐轮表

| Loop | Branch | LLM 调用和上下文 | Hypothesis / code 意图 | Screening / Decision / lifecycle | Lesson 影响判断 |
|---:|---|---|---|---|---|
| 1 | `2ac12b1d` | S01: `hypothesis_target_intent` + `hypothesis`，algorithm profile；可见 problem summary、research surfaces、solver semantics、champion code、branch lesson context。S02: 7 次 `tool_selection` + 1 次 `code`；调用 `context.read_branch_state`、`context.read_surface`、`context.read_algorithm_file`。 | 在 `local_search.py` 加 `vns_2opt_star_route_merge`，whole-route merge / 2-opt* route merge。code 只改 `_default_vns_operators` 注册入口。 | screening 0/0/8，median=0，CI=[0,0]；Decision `continue_explore`，但 reason 包含 win-rate fail、runtime saturation、telemetry effect zero；branch parked_lineage，checkpoint retained，active slot 释放。 | lesson requirement 只有本 branch bridge no-effect。该轮更多是建立首个 no-effect lesson，而非使用跨分支经验。 |
| 2 | `4a1aafe0` | S03: target intent + hypothesis，两次 hypothesis retry；S04: 3 次 tool selection + code；读 `local_search.py`、branch state。 | 避免继续 VNS，转向 `destroy_repair.py` 的 `route_limit_regret_repair`，把 route limit pressure 提前到 regret repair。code exact_replace `_regret2_insertion` / `_regret3_insertion` / `_regret_insertion`。 | screening 0/0/8，median=0；Decision `continue_explore`；runtime tie 要 fresh champion，scheduler clean fork。 | 明确 avoided `2ac12b1d` 的 VNS route-merge lesson，并 contrasted repair telemetry。这里 lesson 影响真实：target_file 和 mechanism family 从 local_search/VNS 转到 destroy_repair/repair。 |
| 3 | `4a1aafe0` | S05: target intent + hypothesis，repair profile；S06: tool selection + 3 个 code exact_replace；读 `local_search.py`、branch state。 | 同 branch follow-up，改 `scheduler.py` 的 `timeboxed_vns_activation_bridge`，给 ALNS/VNS 一个 bounded observable VNS window。 | screening 0/1/7，median=-1，CI=[-6.25,0]；Decision `abandon`；reason 包含 soft abandon、negative delta、runtime saturation；lineage archived/abandoned。 | lesson usage 字段丰富，但研究路径从 route-limit repair 跳到 scheduler timebox，属于“同 branch low signal observation sample”。有效探索了 sibling，但结果回归，合理 abandon。 |
| 4 | `2b3dbde6` | S07: target intent + 2 次 hypothesis，algorithm profile；预取 list surfaces/problem/algorithm files/active solver design/call graph/map、operator registry、algorithm slice、screening/runtime feedback；self-check 调 `proposal.schema_preview` 和 `proposal.target_permission_preview`。 | 想在已存在的 `destroy_repair.py` 上 `create_new` `slack_seeded_repair` + `repair_portfolio_integration`。两次 formal hypothesis 都保持 `action=create_new`。 | pre-protocol proposal block；不计入 effective rounds。失败：`existing_file_create_new_rejected`。scheduler 后续创建 clean branch。 | lesson usage 字段存在，并避免 VNS/timebox/route-limit repair；但 action 错误让研究没有进入 code/protocol。 |
| 5 | `2b3dbde6` | S08: target intent + 2 次 hypothesis，repair profile；S09: 5 次 tool selection + code；读 local_search/destroy_repair/scheduler/branch state。 | 改 `construction.py` 的 `route_seed_lookahead`，在 initial construction 加轻量 route seed insertion lookahead。code exact_replace 小片段。 | screening 0/0/8，median=0；Decision `continue_explore`；fresh champion runtime required；scheduler `pending_retry_diagnostic_followup`。 | 从 failed destroy_repair create_new 转到 construction modify，说明 quality block 后的 reroute 生效。研究合理，但效果为 no-effect。 |
| 6 | `2b3dbde6` | S10: target intent + 2 次 hypothesis；S11: 1 次 tool_selection stop + 2 次 code exact_replace。 | 改 `acceptance.py` 的 `distance_plateau_reheat_acceptance`，给 SA acceptance plateau reheating / slower cooling。 | screening 0/0/8，median=0；Decision `continue_explore`；fresh champion runtime required；继续 diagnostic followup。 | 使用了 route-seed/no-effect 和 abandoned/timebox 等 lessons，换到 acceptance family。合理扩展，但仍没有质量信号。 |
| 7 | `886e3850` | S12: target intent + hypothesis；S13: 6 次 tool selection + code；读 branch state、surface、baseline algorithm、scheduler/state。 | 改 `destroy_repair.py` 的 `route_compression_repair`，偏向 existing routes、减少 singleton route。 | screening 0/1/7，median=0，CI=[-6,1]；Decision `abandon`，reason 含 soft abandon loss without win；branch abandoned/discarded。 | 在 destroy_repair family 上再次探索，但与已失败 route-limit repair 相近。lesson contrast 存在，实际差异不够强，abandon 合理。 |
| 8 | `b80205c9` | S14: target intent + hypothesis；S15: 6 次 tool selection + code；读 branch state、surface、baseline algorithm、scheduler/state。 | 改 `local_search.py` 注册 `split_route_segment_exchange`，尝试非 suffix contiguous segment exchange。 | screening 1/0/7，median=0，CI=[0,1]；tier `weak_positive`，Decision `continue_explore`；weak-positive not promotable；runtime saturation。 | 这是本次最有效的 lesson 影响：前面多个 repair/scheduler/construction no-effect 后，回到 local_search 但换成 segment exchange family。产生唯一 case-level positive signal。 |
| 9 | `b80205c9` | S16: target intent + hypothesis，repair profile；S17: tool_selection stop + code。 | refine 同机制 `split_route_segment_exchange`，调整 activation/budget/candidate pair filtering；code 改 `_split_route_segment_exchange` 和 `_bounded_segment_positions`。 | screening 0/0/8，median=0，CI=[0,0.5]；Decision `continue_explore`，scheduler `weak_positive_signal_followup`。 | 这是 same-branch weak-positive refinement，研究方向合理；但没有保持 case win，说明 refinement 可能削弱或信号不稳。 |
| 10 | `b80205c9` | S18: target intent + hypothesis；S19: tool_selection stop + code。 | 改 `local_search.py` 的 `_vns` / `_default_vns_operators`，引入 `split_route_segment_exchange_schedule`，调整调度/组合而非新增 family。 | screening 0/0/8，median=0；Decision `continue_explore`；scheduler `fresh_champion_runtime_replay_followup`。 | same-branch refinement 继续，但 runtime/fresh champion requirement 开始主导，质量研究没有进入 validation。 |
| 11 | `b80205c9` | S20: target intent + hypothesis；S21: branch state + stop + 2 次 code。 | 继续 `split_route_segment_exchange_schedule`，改 schedule 函数并加 cleanup / cut-bound helpers。 | screening 0/0/8，median=0；Decision `continue_explore`；fresh champion runtime replay followup。最终 branch card 保持 weak_positive，但 current head discarded，fresh_runtime_pending=true。 | 分支内研究从“weak-positive mechanism”逐渐变成修 runtime/activation 可信度。有效性有限，且没有触发 validation。 |
| 12 | `6a471676` | S22: target intent + hypothesis；S23: 4 次 tool selection + code。 | 新 clean fork，`local_search.py` 注册 `route_tail_reinsertion`，测试 cross-route tail/segment reinsertion。 | screening 0/0/8，median=0；branch card tier `quality_regression`，fresh runtime followup required；scheduler `plateau_reroute_clean_fork`。 | plateau 策略抑制了继续 weak-positive branch，转向 clean fork。避免局部过拟合合理，但也过早切断了 `b80205c9` 的弱正向线索。 |
| 13 | `44e902fd` | S24: target intent + 2 次 hypothesis；S25: 5 次 tool selection + code。 | 改 `scheduler.py` 的 `slack_seed_pool_selection`，在 scheduler-owned initial-solution path 比较多个 feasible seed。 | screening 0/0/8，median=0；Decision `continue_explore`；scheduler `plateau_reroute_clean_fork`；run 因 max_rounds_exhausted 完成。 | 使用 cross-branch no-effect/abandoned lessons，选择 construction scheduler family。字段满足，但效果仍 no-effect。 |

## 逐 LLM 调用摘要

下表按 agentic session 归并 91 个 LLM trace；每个 `tool_selection` 都是一次 LLM 调用，箭头后是该调用选择的工具或 `stop`。hypothesis 调用的可见上下文主要包括 `problem_summary`、problem semantics、`research_surfaces`、objective policy、champion research code、solver execution model、branch lesson context、cross-branch research map、screening/runtime feedback；code 调用的可见上下文主要包括 code quality rules、solver design implementation scope、feasibility rules、problem summary、full/bounded source and tool observations。

| Session | Branch | Trace calls | 产出 |
|---|---|---|---|
| S01 `a3f91cc9` | `2ac12b1d` | `hypothesis_target_intent` -> modify local_search route merge; `hypothesis#1` | 生成 `vns_2opt_star_route_merge` hypothesis，partial_hypothesis_only 等待 ContractGate approval。 |
| S02 `119f4f69` | `2ac12b1d` | `tool_selection`: branch_state -> surface -> baseline_algorithm -> scheduler -> state -> surface full -> stop; `code#1` | code exact_replace `_default_vns_operators`，把 route merge 注册进 VNS operators。 |
| S03 `58bbd8af` | `4a1aafe0` | `hypothesis_target_intent`; `hypothesis#1`; `hypothesis#2` | 两次 hypothesis 收敛到 `route_limit_regret_repair`，带 avoided/contrasted lessons。 |
| S04 `337ba981` | `4a1aafe0` | `tool_selection`: read local_search -> branch_state -> stop; `code#1` | code exact_replace regret insertion functions，加入 route-limit-aware repair bias。 |
| S05 `ead2ebc0` | `4a1aafe0` | `hypothesis_target_intent`; `hypothesis#1` | 生成 `timeboxed_vns_activation_bridge`，把焦点转到 scheduler budget/activation。 |
| S06 `2f246eae` | `4a1aafe0` | `tool_selection`: read local_search -> branch_state -> stop; `code#1` x3 | 三段 exact_replace 改 scheduler 的 timeboxed VNS activation path。 |
| S07 `b44a4072` | `2b3dbde6` | `hypothesis_target_intent`; `hypothesis#1`; retry `hypothesis#2`; self-check tools | 生成 `create_new destroy_repair.py`，两次被 preview 拒绝，session failed。 |
| S08 `3826197d` | `2b3dbde6` | `hypothesis_target_intent`; `hypothesis#1`; `hypothesis#2` | 改为 `modify construction.py route_seed_lookahead`，避开 create_new failure。 |
| S09 `bd961869` | `2b3dbde6` | `tool_selection`: read local_search -> destroy_repair -> scheduler -> branch_state -> stop; `code#1` | code exact_replace construction seed choice片段。 |
| S10 `2d32643e` | `2b3dbde6` | `hypothesis_target_intent`; `hypothesis#1`; `hypothesis#2` | 生成 `distance_plateau_reheat_acceptance`，转到 acceptance family。 |
| S11 `2e2944c2` | `2b3dbde6` | `tool_selection`: stop; `code#1` x2 | 两段 exact_replace 改 SA acceptance cooling/reheat 行为。 |
| S12 `666fd97b` | `886e3850` | `hypothesis_target_intent`; `hypothesis#1` | 生成 `route_compression_repair`，repair-side route compression bias。 |
| S13 `1607ed3f` | `886e3850` | `tool_selection`: branch_state -> surface -> baseline_algorithm -> scheduler -> state -> stop; `code#1` | exact_replace `_regret3_insertion` / `_route_compression_repair` / `_regret_insertion`。 |
| S14 `9e43f25f` | `b80205c9` | `hypothesis_target_intent`; `hypothesis#1` | 生成 `split_route_segment_exchange`，避免重复 repair/scheduler no-effect。 |
| S15 `9b05fef1` | `b80205c9` | `tool_selection`: branch_state -> surface -> baseline_algorithm -> scheduler -> state -> stop; `code#1` | 注册 split segment exchange 到 `_default_vns_operators`。 |
| S16 `19acdc6c` | `b80205c9` | `hypothesis_target_intent`; `hypothesis#1` | same-branch refine：减少广泛触发，优化 pair filtering。 |
| S17 `344b7b16` | `b80205c9` | `tool_selection`: stop; `code#1` | exact_replace `_split_route_segment_exchange` 和 helper。 |
| S18 `b6c4629a` | `b80205c9` | `hypothesis_target_intent`; `hypothesis#1` | same-branch schedule：把 segment exchange 改成 scheduled VNS path。 |
| S19 `9bd7d37a` | `b80205c9` | `tool_selection`: stop; `code#1` | exact_replace `_vns` / `_default_vns_operators` 调度。 |
| S20 `a2ce43cb` | `b80205c9` | `hypothesis_target_intent`; `hypothesis#1` | 继续 schedule refinement，目标是更少 post-activation no-effect。 |
| S21 `0aed80ea` | `b80205c9` | `tool_selection`: branch_state -> stop; `code#1` x2 | 改 schedule 函数，加 cut-bound / cleanup helpers。 |
| S22 `5abbe580` | `6a471676` | `hypothesis_target_intent`; `hypothesis#1` | clean fork：`route_tail_reinsertion`。 |
| S23 `68b7996f` | `6a471676` | `tool_selection`: branch_state -> surface -> baseline_algorithm -> stop; `code#1` | 注册 tail reinsertion 到 local_search operators。 |
| S24 `91e58f54` | `44e902fd` | `hypothesis_target_intent`; `hypothesis#1`; `hypothesis#2` | clean fork：`slack_seed_pool_selection`，scheduler-owned seed pool。 |
| S25 `0c2cda72` | `44e902fd` | `tool_selection`: branch_state -> surface -> baseline_algorithm -> state -> scheduler; `code#1` | exact_replace scheduler initial-solution selection。 |

## 分支表

| Branch | 假设脉络 | Code 实现范围 | Screening 结果 | Decision / lifecycle | 判断 |
|---|---|---|---|---|---|
| `2ac12b1d` | VNS route merge / route-count collapse | `local_search.py` operator registration; mechanism `vns_2opt_star_route_merge` | 0/0/8，median=0，telemetry activation observed but zero objective effect | `continue_explore` -> parked_lineage；checkpoint retained，active slot released，forbid consume_active_slot | 首轮探索合理，但证据表明 no-effect；parking/clean-fork policy 合理保护 active slots。 |
| `4a1aafe0` | 先 route-limit regret repair，后 timeboxed VNS activation bridge | `destroy_repair.py` regret insertion；`scheduler.py` bounded VNS window | 第一次 0/0/8；第二次 0/1/7、median=-1 | 第二次 `abandon`；branch discarded，lineage archived | 分支内研究从 repair 到 scheduler 是有差异的 sibling sample，但第二步质量回归，abandon 合理。 |
| `2b3dbde6` | failed slack-seeded repair -> construction route seed lookahead -> acceptance plateau reheat | proposal block 后转 `construction.py`、`acceptance.py` exact_replace | 两个 formal screening 都 0/0/8；另有 1 个 proposal block | 状态 explore，current head discarded，failure_codes 含 `PROPOSAL`；fresh champion runtime required | reroute 后机制多样性较好，但全部 no-effect。quality block 暴露 action/schema retry 缺陷。 |
| `886e3850` | route compression repair | `destroy_repair.py` route-compression helper + regret integration | 0/1/7，CI=[-6,1] | `abandon`，branch discarded | 与早前 route-limit repair 相近；lesson contrast 不足以避免 repair-family 重复失败。 |
| `b80205c9` | split route segment exchange -> same branch refinement -> scheduled exchange | 多次改 `local_search.py` VNS operator、segment exchange implementation、schedule/cleanup helpers | 首次 1/0/7 weak_positive；后 3 次 0/0/8 | 状态 explore，tier weak_positive retained；current heads discarded；fresh_runtime_pending=true，fresh_runtime_required=true | 这是唯一有效研究线索。问题是后续没有 validation 或 fresh replay 闭环，只在 screening 内多次 refine，最后被 clean-fork policy 压过。 |
| `6a471676` | route tail reinsertion clean fork | `local_search.py` operator registration | 0/0/8，但 branch card 标 quality_regression，case-level negative diagnostic | `continue_explore` + plateau reroute clean fork；head discarded | clean fork 有多样性，但并未利用 weak-positive sibling 的具体经验，且质量信号差。 |
| `44e902fd` | slack seed pool selection | `scheduler.py` initial solution seed pool selection | 0/0/8 | `continue_explore`，run 到 max rounds | 末轮转 construction scheduler family，字段合规，但未产生效果；适合作为 no-effect lesson，不适合作为继续放大依据。 |

## 跨分支 lesson 影响分析

机制层面是合规的：`cross_branch_research_observability` 显示 `branch_lesson_usage_requirement_count=12`、`present=12`、`satisfied=12`、`missing_block=0`，并且 policy 明确是 `proposal_observability_only`、`decision_input_policy=excluded_from_decision_features`。这符合 v3：cross-branch lesson 只进入 proposal visibility / audit，不进入 DecisionFeatures。

真实影响有，但不均衡：

- 真实避免：第 2 轮从 `2ac12b1d` 的 VNS route-merge no-effect 转到 `destroy_repair.py` route-limit repair；第 5/6 轮从 failed destroy_repair 转向 construction/acceptance；第 8 轮在多个 repair/scheduler/construction no-effect 后，选择了新的 local_search segment-exchange family。
- 字段合规偏强：许多 hypothesis 都填了 avoided/contrasted lessons，但常见表达只是 `not_vns_2opt`、`not_timeboxed_vns`、`not_route_limit_destroy` 这类粗粒度 contrast。它能证明 agent 看见了 lesson，但不足以证明它理解“为什么失败”并把失败机制转化为可检验的新实验设计。
- sibling/abandoned 传递存在：`candidate_lesson_types` 包含 `abandoned` 和 `no_effect`，source_branch_ids 覆盖 `4a1aafe0`、`2b3dbde6`、`886e3850` 等；后续 clean-fork 多次要求 action/activation/effect/runtime_budget_strategy contrast。
- weak-positive 传递不足：虽然 `b80205c9` 首次 screening 是 weak_positive，且 branch card 记录 `weak_positive_followup=true`，但 `weak_positive_transfer_count=0`。也就是说 weak-positive 主要留在同分支 refinement，未成为后续 clean fork 的明确 borrowed/preserved lesson。
- preserved lesson 很少：cross-branch observability 中 `preserved_same_branch_lesson_count=3`，而 avoided=20、contrasted=22。当前机制偏向“避开失败”，不擅长“保留弱正向机制并验证其可重复性”。

因此，本轮 lesson 机制的最强证据是：它能降低近重复，能要求 proposal 显示 contrast；最弱证据是：它还不能保证后续研究从经验中获得更高质量，尤其不能保护 weak-positive 线索进入 validation/replay。

## Quality block: `existing_file_create_new_rejected`

该 block 发生在 loop 4 / session `b44a4072` / branch `2b3dbde6`。LLM 先读到了足够上下文：surface/problem、allowlisted algorithm files、active solver design、call graph、active solver map、`destroy_repair.py`、`local_search.py`、`scheduler.py`、operator registry、algorithm slice、screening feedback、runtime feedback。它的 target intent 和两次 hypothesis 都选择：

- `action=create_new`
- `target_file=policies/baseline_modules/destroy_repair.py`
- mechanisms: `slack_seeded_repair`, `repair_portfolio_integration`

preview 结果分两层：

1. 第一次 schema preview 有过 `C11_expected_telemetry` 修正反馈，要求 effect telemetry 必须对应真实 objective-changing path，不能为 unchanged incumbent 声称 positive best_delta。
2. target permission preview 明确失败：`existing_file_create_new_rejected: existing file requires modify exact_replace with source_digest; create_new is only for new files. Minimal patch shape: action=modify, edit_intent=exact_replace, source_digest, non-empty old_string, new_string, replace_all=false.`

重试后 telemetry category 被修正，但 `action=create_new` 没有被修正，所以第二次 preview 仍因同一个 target/action 边界失败，最终 `Hypothesis self-check failed closed before approval`。

判断：这是合理 contract boundary + agent/schema retry 缺陷的组合，不是 Decision 问题，也不是 runtime 问题。contract boundary 正确，因为已存在文件必须走 `modify exact_replace`，否则 materializer 无法可靠做 source_digest 绑定。agent 行为有问题，因为它把“新增机制/函数”的算法语义错误映射成了文件级 `create_new`。tooling/schema preview 也有改进空间：C11 telemetry 反馈先占据了 retry 注意力，而 target/action 错误没有被提升成“必须修 action”的更强约束；retry constraint 还要求 preserve action/target/mechanism identity，可能间接固化了错误 action。

建议：把 action 分成 `file_action` 与 `mechanism_change_type`，或在 preview retry 中为 `existing_file_create_new_rejected` 提供自动修复模板：`file_action=modify`、`mechanism_changes[].change_type=add/integrate`。该类错误应优先于 telemetry schema retry。

## Promotion / validation / frozen / weak-positive / runtime / abandon

没有 promotion、validation、frozen。`status.json` 和 `campaign_summary.json` 都显示 protocol stage counts：screening=12、validation=0、frozen=0，promoted=0，frozen_budget used=0/limit=2。所有 candidate 都停在 screening gate 或 proposal gate。

weak-positive 有但没有被转成验证：`b80205c9` 首次 segment exchange 是 1/0/7，tier weak_positive，branch retained best checkpoint；后续三次 same-branch refine 都回到 0/0/8。screening feedback 明确写着 weak_positive is not promotable, screening gate remains authoritative。这个边界合理，但缺少下一步：没有自动触发 validation，也没有完成 fresh champion replay。

runtime/fresh champion 逻辑总体有帮助，但目前更像阻塞器。它防止 low/cached champion runtime tie 被误当成优化；这是好事。问题是 `fresh_champion_required_count=8`、`runtime_aggregate_excluded_count=11` 后，系统没有在 12R 内完成 replay 解除阻塞，导致大量 round 只生成 `fresh_champion_runtime_replay_followup` 或 `plateau_reroute_clean_fork`。

branch lifecycle abandon 基本合理。`4a1aafe0` 和 `886e3850` 都有 loss without win / negative or low CI / runtime saturation，abandon 避免继续消耗 active slots。`2ac12b1d` parked_lineage 保留 checkpoint 但释放 slot，也合理。可疑点是 plateau clean-fork 在后期压过了 weak-positive follow-up：第 12/13 步都有 `weak_positive_followup_suppressed=true`，原因是 `plateau_reroute_clean_fork`，这可能让唯一弱正向线索过早降级。

## v3 设计合规性

整体符合 Scion v3 边界：

- LLM 输出仍是 tainted proposal；Contract/preview/verification/protocol/Decision 分层存在，quality block 证明 pre-protocol boundary 能挡住非法 target/action。
- Decision 事件读取的是 deterministic features：contract_passed、verification_passed、canary_passed、win_rate、median_delta、branch_code_status、failure_codes、runtime guard 等；没有看到 Decision 直接读取自由文本 hypothesis 或 `branch_lesson_usage`。
- Cross-branch lessons 明确 `proposal_visibility_only=true`、`proposal_guidance_only=true`、`decision_features_excluded=true`，符合“lesson 只做 visibility/audit，不进入 promotion/scheduling 决策输入”的约束。
- CVRP/solver semantics 保留在 problem/surface/proposal 层；本报告也不把 route-limit、fleet_violation、VNS/ALNS 语义写成 generic core 需求。需要改的是 proposal/tooling 机制，而不是让 generic core 理解 CVRP 业务语义。

一个需要继续盯住的点：runtime/fresh champion、weak-positive suppression、plateau clean-fork 这些 scheduler/lifecycle policy 应继续只读安全枚举和数值 feature。不要为了提高 lesson 影响，把 `branch_lesson_usage` 自由文本接入 Decision。

## 框架缺陷和优化建议

1. 修正 action/schema preview 的优先级。`existing_file_create_new_rejected` 应是强 action repair，而不是普通 preview issue；retry 应允许把 file-level `create_new` 改成 `modify`，同时保留 mechanism-level `add`。
2. 给 weak-positive 建立明确闭环。第一次 weak-positive 后，不应只继续同分支 code refine；应优先 fresh champion replay，若仍正向则 queue validation，若不稳定再 clean fork。
3. 让 weak-positive lesson 可传递。当前 `weak_positive_transfer_count=0`，后续 clean fork 只看 no-effect/abandoned 压力。应该把 weak-positive 作为 `preserve` 或 `borrow` lesson 暴露给 sibling，要求说明保留哪些 activation/effect path、避免哪些过宽 schedule。
4. 对 `branch_lesson_usage` 做语义审计。仅统计 present/satisfied 会鼓励字段合规。建议增加机器可检验的 contrast：target_file 是否真的变化、mechanism_family 是否真的变化、runtime_budget_strategy 是否具体且与 code intent 对应。
5. 分离 runtime evidence 阻塞和研究调度。fresh champion required 是正确边界，但如果 replay 不执行，它会反复占用解释空间。建议在 scheduler 中把 fresh replay 作为独立 non-proposal action，避免反复生成新 code 来绕开 runtime 低可信。
6. 改善 same-branch refinement 限额。`b80205c9` 4 次 screening 内只有第一次 weak-positive，后续三次没有提升。可以设置：weak-positive 分支最多 1 次 code refinement，之后必须 replay/validation 或 park，不继续堆同类 modifications。
7. 保留 proposal visibility，不扩展 Decision 输入。lesson 机制的优化应发生在 Context/Proposal self-check/audit，不应把 LLM lesson 文本作为 DecisionFeatures。

## 下一步建议

先做一轮机制修复验证，而不是直接长跑：

1. 专门复现 `existing_file_create_new_rejected`，验收标准是 retry 后输出 `action=modify` + `edit_intent=exact_replace` + `source_digest`，mechanism_changes 仍可表达 `add/integrate`。
2. 做 4-6R weak-positive replay 实验，强制包含 fresh champion runtime replay；验收标准是 weak-positive 能进入 validation 或被明确证伪，而不是继续 screening-only refine。
3. 做 branch_lesson_usage 语义验收，抽样比对 hypothesis 的 avoided/contrasted/preserved lessons 与实际 target/mechanism/code intent；验收标准不是 present=100%，而是每条 lesson 至少有一个可验证 material difference 或 preserve claim。
4. 通过后再进入更长实验。长实验目标应是验证“lesson 机制提高有效研究密度和验证闭环率”，不是减少 token，也不是单纯增加 calls。
