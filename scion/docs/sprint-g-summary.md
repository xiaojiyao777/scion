# Sprint G — GPT-5.4-Pro 审查整改总结

*日期: 2026-04-11 23:00 → 2026-04-12 12:20*
*分支: v0.2-dev*
*起始 commit: d1053b3 → 终止 commit: 0dbe24f*

---

## 0. 背景

Sprint E 完成后，对 v0.2 全量代码（31 个源码文件 + 5 份设计文档）进行了 GPT-5.4-Pro 架构审查。审查产出：

- `scion/reviews/scion-v02-review_result.md`（779 行审查意见）
- `scion/reviews/SprintF前整改任务单.md`（1169 行整改 spec）

审查发现 4 类核心问题：控制边界违反、协议统计粒度错误、参数搜索基线偏差、CLI/Prompt 未接入。拆为 G1-G4 四个 Sprint 逐一修复。

---

## 1. Sprint G1 — Control Boundary Hardening + Hypothesis Lifecycle

**Commit**: `78c7a4c` | **改动**: 6 files, +872/-35

| Task | 内容 |
|---|---|
| T1 | Gate bypass 修复：fix patch / pending hypothesis 全部经完整 Contract+Verification |
| T2 | verification 前不污染 `last_clean_code_hash`（仅 verification 通过后更新） |
| T3 | screening→validation→frozen→promote 全链路保持同一 `hypothesis_id` |
| T4 | stale reconcile 重走 Contract→Verification→re-screening |
| T5 | eval-only 步骤（validation/frozen）写入 `step_history` |
| T6 | hypothesis 状态机完整：pending→screening→validated→promoted/abandoned |
| T7 | `create_branch` 动作增加 `max_active_branches` 上限检查 |

**新增测试**: 12 tests in `unit/core/test_campaign_control_boundaries.py`

---

## 2. Sprint G2 — Protocol Correctness

**Commit**: `3a33dec` | **改动**: 11 files, +784/-117

| Task | 内容 |
|---|---|
| T1 | 统一 config schema：移除 `config/problem.py` 中的简化版，全部 re-export 权威类 |
| T2 | Case-level 统计：`CaseLevelResult` + majority vote 聚合 + case-level bootstrap CI |
| T3 | Canary 使用独立 split（不复用 screening cases） |
| T4 | Expand 增加 cases 而非 seeds（修正：扩展样本量 = 增加 case 覆盖） |
| T5 | Action-specific case 选择（modify/remove vs create_new 区分 N） |
| T6 | `protocol.yaml` 更新为嵌套格式 |

**新增测试**: 14 tests in `unit/protocol/test_protocol_correctness.py`

---

## 3. Sprint G3 — Parameter Search Correctness

**Commit**: `40b8a19` | **改动**: 11 files, +2654/-343（含审查文档）

| Task | 内容 |
|---|---|
| T1 | True baseline：optimizer 先评估 `current_weights`，不依赖随机采样 |
| T2 | Observations to disk：`weight_opt_<ts>.json` 持久化全部评估记录 |
| T3 | Mutable staging：`create_mutable_staging()` + `freeze_snapshot()` 解决权限问题 |
| T4 | Snapshot hash 包含 `registry.yaml`（权重变化纳入 champion 指纹） |
| T5 | `_run_weight_optimization` 接收并传递 `current_weights` |

**新增测试**: 11 tests in `unit/parameter/test_weight_optimizer_correctness.py`

---

## 4. Sprint G4 — CLI Real Runtime + Prompt Plumbing + Cleanup

**Commits**: `3292b99` + `0dbe24f` (Cris 修复) | **改动**: 7 files, +772/-343

| Task | 内容 |
|---|---|
| T1 | `scion run` 接入真实 Runner/ExperimentProtocol/VerificationGate |
| T2 | hypothesis prompt 注入 branch code / coverage / strategy / baseline hints |
| T3 | code prompt 注入 `## Previous Attempt Failed` 上下文 |
| T4 | `_sync_pool_registry()` — apply_patch 后重建 registry（remove/modify 正确性） |
| T5 | lineage 写入真实 `hypothesis_id` + `decision_reason_codes` |
| T6 | `hypothesis_store.py` 瘦身为 re-export；V-code 注释补全 |
| T7 | `scion inspect weights` + `scion optimize-weights` CLI 命令 |

**新增测试**: 12 tests in `unit/test_g4_plumbing.py`

**Cris 修复**: T4 `_sync_pool_registry` 在 champion pool 为空时覆盖 registry 的回归 bug（`0dbe24f`）

---

## 5. 总体统计

| 指标 | 数值 |
|---|---|
| **Commits** | 5（G1-G4 + Cris hotfix） |
| **文件变更** | 33 files |
| **代码增减** | +5,081 / -837 行 |
| **新增测试** | 49 tests（12+14+11+12） |
| **测试总数** | 573 (全部 PASSED ✅) |
| **开发耗时** | CC ~3.5h + Cris 验收 ~1.5h |
| **审查文档** | 2 份（审查意见 779L + 整改任务单 1169L） |

---

## 6. 修复的架构偏差

Sprint G 修复了 Pro 审查发现的全部 P0 问题：

1. ✅ **Gate bypass** — fix patch / pending hypothesis 全部过 Contract+Verification
2. ✅ **Clean-base 污染** — verification 前不更新 `last_clean_code_hash`
3. ✅ **Hypothesis ID 断裂** — 全链路保持同一 ID
4. ✅ **统计粒度错误** — case-level 聚合（majority vote + case-level CI）
5. ✅ **Canary 复用 screening** — 独立 split
6. ✅ **Expand 语义** — 增加 cases 而非 seeds
7. ✅ **Optimizer 无 baseline** — true baseline 评估 + mutable staging
8. ✅ **CLI 空壳** — `scion run` 接入完整 runtime
9. ✅ **Prompt 信息缺失** — branch code / failure history / strategy 注入

---

## 7. 下一步

Sprint G 完成标志着 v0.2 架构整改全部到位。下一步：

1. **Sprint F（端到端验证 campaign）** — 跑完整 15+ round campaign，验证整改后的行为
2. **分析 Sprint F 结果** — 对比 v0.1 验证实验，确认改善
3. **文档固化** — 更新 architecture v3 文档，标记 Sprint G 变更
