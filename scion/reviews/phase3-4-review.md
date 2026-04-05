# Scion Phase 3-4 Review — Module Audit

*Reviewer: Cris (对照 scion-engineering-arch-v1.md)*
*Date: 2026-04-05*
*Status: 171/171 tests passed*

---

## 审核摘要

总体评分: **8/10**
可直接进入 Phase 5: **YES（1个 P0 需修复，其余 P1 可后续处理）**

---

## Phase 3 模块审核

### T09: Experiment Protocol (protocol/)

**接口一致性: 8/10**
- `run_canary(candidate_ws, champion_ws) -> CanaryResult` ✅
- `run_experiment(stage, candidate_ws, champion_ws, hypothesis_action, expand) -> ProtocolResult` ✅
- SplitManager / SeedLedger 与规范一致 ✅
- `lexicographic_compare` 正确实现字典序（subcategory_splits > total_cost）✅

**安全边界: 8/10**
- 暴露控制：screening 暴露 aggregate（win_rate + median_delta），validation/frozen 只暴露 outcome ✅
- raw_metrics_ref 正确指向 JSON 文件 ✅
- Canary 是 veto-only，不做改善证据 ✅

**统计实现: 7/10**
- bootstrap CI 使用固定 seed=42，确定性可复现 ✅
- 中位数计算正确（奇偶处理）✅
- **P1**: `compute_delta` 只用 `total_cost` 计算 delta，未考虑字典序第一目标 `subcategory_splits`。如果 splits 改善但 cost 增加，delta 会是负数，与 "win" 判定矛盾。建议改为组合 delta 或分别追踪。

**门控逻辑: 9/10**
- screening: win_rate + median_delta 双条件 ✅，expand 在 0.5-threshold 区间 ✅
- validation: CI + win_rate 组合判定 ✅
- frozen: 保守策略（ci_low >= 0 才 pass）✅

### T10: Pool Manager (runtime/pool_manager.py)

**接口一致性: 8/10**
- `build_candidate_pool(champion_pool, hypothesis, patch) -> dict` ✅
- `export_registry(pool, target_dir) -> str` ✅
- 权重归一化 ✅

**边界条件: 7/10**
- create_new 后权重归一化 ✅
- remove 后权重归一化 ✅
- **P1**: modify 操作通过文件名匹配 target，如果 target_file 和 pool 中的 file_path 格式不一致（相对/绝对路径），可能匹配失败。建议统一用 basename 比较。
- `_guess_class_name` 从文件名推断类名，简单但脆弱 **P1**

### T14: Failure Router (failure/router.py)

**接口一致性: 9/10** — 完全匹配规范
- 四层分类 ✅
- proposal/contract → retry_llm (不消耗预算) ✅
- verification_light → retry_llm，重试耗尽后 discard (消耗预算) ✅
- verification_heavy → discard (消耗预算 + 写 hypothesis memory) ✅
- infra → retry_infra (不消耗预算) ✅
- evaluation → discard ✅
- unknown category 兜底处理 ✅

---

## Phase 4 模块审核

### T11: Branch Controller (core/branch.py)

**接口一致性: 9/10**
- 状态机完整：12 states 全部覆盖 ✅
- `apply_decision` 使用 (Decision, current_state) 映射表，清晰 ✅
- `mark_all_stale` + `reconcile_stale` ✅
- `block_infra` / `unblock_infra`（保存/恢复前状态）✅
- `schedule_branch`（READY_* → running state）— 规范未明确列出但合理 ✅

**安全边界: 8/10**
- 非法状态转换抛 `StateTransitionError` ✅
- `_ACTIVE_STATES` 枚举正确 ✅
- **P1**: `get_code_base` 返回 `str`（"champion" 或 hash），规范定义返回 `CodeBase` 类型。当前 MVP 可接受，Phase 5 集成时需确保语义清晰。

### T12: Scheduler (core/scheduler.py)

**接口一致性: 9/10** — 简洁正确
- 词典序优先级完全匹配规范 ✅
- FIFO within tier (sorted by created_at) ✅
- 无活跃分支返回 `create_new` ✅

### T13: Decision Engine + Safe Feature Extractor (core/decision.py + features.py)

**安全边界: 9/10** ⭐ 关键模块，实现质量高
- `_validate_no_free_text` 运行时校验：UUID 正则 + Literal 枚举 + KNOWN_FAILURE_CODES ✅
- `DecisionInputGuardError` 专用异常 ✅
- DecisionEngine 是纯确定性函数，不读 LLM 文本 ✅
- 预检安全：contract/verification/canary 未通过直接 ABANDON ✅

**决策逻辑: 8/10**
- screening: win_rate >= threshold + delta → QUEUE_VALIDATE ✅
- validation: CI + win_rate → QUEUE_FROZEN 或 EXPAND 或 ABANDON ✅
- frozen: ci_low >= 0 → PROMOTE ✅
- **P0**: screening 失败（win_rate < 0.5）返回 `CONTINUE_EXPLORE` 而非规范中的行为。规范 §4.1 状态转换表中 `screen_fail/unclear → 回到 EXPLORE（iterate）` 是正确的，但 Decision 枚举里 `CONTINUE_EXPLORE` 的语义是"继续迭代"，而实际上 screening_fail 应该触发 LLM 重新 propose（不是用同一个 patch 继续）。这个语义在 Campaign Manager 主循环集成时需要明确：CONTINUE_EXPLORE 后是重走 Round 1 还是直接 re-screen。**建议在 Phase 5 明确此路径。**

### T15: Termination Conditions (core/termination.py)

**接口一致性: 9/10** — 四条件独立可测
- max_experiments ✅
- wall_clock ✅
- stagnation（连续 N 个 abandoned）✅
- no_active + cannot_create_new ✅

---

## 必须修复 (P0)

1. **Decision Engine: CONTINUE_EXPLORE 语义澄清**
   - screening_fail 返回 CONTINUE_EXPLORE，但主循环需要知道这意味着"丢弃当前 patch，回 Round 1 重新 propose"
   - 建议：在 CampaignManager 主循环中，CONTINUE_EXPLORE 后始终走完整的 Round 1 → Round 2 流程
   - 这不需要改 Decision 枚举，但需要在 Phase 5 的主循环实现中明确处理

## 建议改进 (P1)

1. **compute_delta 与字典序对齐** — 当前只取 total_cost delta，应考虑 subcategory_splits 的贡献
2. **Pool Manager 路径匹配** — modify 时用 basename 而非全路径匹配
3. **get_code_base 返回语义** — 当前返回 "champion" 字符串 magic value，考虑用 enum 或 Optional

## 测试覆盖

Phase 3-4 测试覆盖良好（96 个新测试），覆盖了：
- 分支状态机完整生命周期 ✅
- 调度器优先级 + FIFO ✅
- 决策引擎 screening/validation/frozen 全路径 ✅
- DecisionInputGuard 正反用例 ✅
- 终止条件四项独立测试 ✅
- 协议三级门控 ✅
- Failure Router 四层路由 ✅

---

*审核结论：Phase 3-4 代码质量高于 Phase 2，核心安全边界（DecisionInputGuard、三层控制）实现到位。P0 (CONTINUE_EXPLORE 语义) 不需要改代码，但 Phase 5 主循环集成时必须明确处理。可以进入 Phase 5。*
