# Scion Phase 5 Review — Integration Audit

*Reviewer: Cris (对照 scion-engineering-arch-v1.md §1.2, §2.1-2.3, §5)*
*Date: 2026-04-05*
*Status: 222/222 tests passed*

---

## 审核摘要

总体评分: **8/10**
可直接进入 Phase 6 (CLI + E2E): **YES**

---

## 模块审核

### T16: LLM Client (proposal/llm_client.py + mock_client.py)

**接口一致性: 8/10**
- call(prompt, response_schema, model) -> dict ✅
- 指数退避重试 (5s, 15s) ✅
- 格式不合规重试（附加错误信息）✅
- MockLLMClient 可配置 success/format_error/timeout/exhausted ✅
- 序列模式支持（多次调用返回不同响应）✅

**P1**: 实际 LLM API 调用部分标记为 TODO（依赖外部 API key），但 Mock 模式完整可测。合理的 MVP 策略。

### T18: Creative Layer (proposal/engine.py)

**接口一致性: 9/10**
- generate_hypothesis(context) -> HypothesisProposal ✅
- generate_code(context) -> PatchProposal ✅
- fix_code(context) -> PatchProposal ✅
- JSON 解析 → dataclass 转换正确 ✅

### T19: Context Manager (proposal/context_manager.py)

**暴露控制: 9/10** ⭐ 关键安全边界
- hypothesis_context: 含 pool summary / branch history / blacklist / sibling summary ✅
- hypothesis_context: **不含** validation/frozen 数据 ✅
- code_context: 含 problem spec / hypothesis / target file / 接口规范 ✅
- code_context: **不含** 历史结果 ✅
- fix_context: 含 failed patch + failure details ✅
- `_summarise_champion_code` 读实际文件并截断到 3000 chars ✅

### T20: Campaign Manager (core/campaign.py) ⭐ 核心模块

**14 步流程覆盖: 8/10**
1. Scheduler 选择/创建分支 ✅
2. BranchController 确定代码基线 ✅
3. ContextManager 构建上下文 ✅
4. CreativeLayer Round 1 → HypothesisProposal ✅
5. ContractGate validate_hypothesis ✅
6. CreativeLayer Round 2 → PatchProposal ✅
7. ContractGate validate_patch ✅
8. WorkspaceMaterializer apply_patch ✅
9. VerificationGate run ✅（MVP stub，syntax-only）
10. Canary（通过 experiment_protocol.run_canary）✅
11. ExperimentProtocol run_experiment ✅
12. SafeFeatureExtractor → DecisionFeatures ✅
13. DecisionEngine → Decision ✅
14. BranchController apply_decision + cleanup ✅

**P0 修复验证: ✅**
- CONTINUE_EXPLORE 正确处理：清理 workspace + 清除 hypothesis/patch + 下轮重走 Round 1 → Round 2 ✅
- frozen_patterns 从 ProblemSpec 注入：`WorkspaceMaterializer(campaign_dir, frozen_patterns=frozenset(problem_spec.search_space.frozen))` ✅

**状态分派: 9/10**
- EXPLORE → 完整 14 步 ✅
- VALIDATING / FROZEN_TESTING → eval-only (复用 workspace) ✅
- STALE → reconcile ✅
- READY_* → schedule_branch 推进 ✅
- ABANDON → 清理 workspace + hypothesis + budget ✅
- PROMOTE → champion 快照 + mark_all_stale ✅

**失败路由: 8/10**
- contract fail → FailureRouter → retry_llm ✅
- verification_light → attempt fix → 再验证 → 若失败则 route ✅
- verification_heavy → route + blacklist ✅
- LLM 超时/格式错误 → FailureEvent(proposal) → route ✅
- experiment 失败 → FailureEvent(evaluation) → ABANDON ✅

**边界问题: 7/10**
- **P1**: `_setup_workspace` 中 `get_code_base` 返回 hash 而非路径时，fallback 到 champion。逻辑正确但有 code smell（用 `os.path.isdir` 判断是 hash 还是路径）
- **P1**: VerificationGate 是 MVP stub（只做 syntax check），Phase 6/E2E 需要完整实现
- **P1**: hypothesis 存储用 in-memory list（无 SQLite），MVP 可接受，生产需迁移

---

## 必须修复 (P0)

**无**。之前的两个 P0 都已在 Phase 5 实现中修复：
1. ✅ CONTINUE_EXPLORE 语义：清理 workspace 并重新 propose
2. ✅ frozen_patterns 注入：从 ProblemSpec 传入

## 建议改进 (P1)

1. VerificationGate 需要完整实现（8 项 P0 检查），当前 stub 只做 syntax
2. LLMClient 需要真实 API 调用实现（当前 TODO）
3. hypothesis 存储迁移到 SQLite（当前 in-memory list）
4. `_setup_workspace` 的 hash/path 判断改用 explicit flag

## 测试覆盖

- 26 tests: LLM Client (mock/retry/format_error/timeout/exhausted)
- 29 tests: Campaign Manager (full path/CONTINUE_EXPLORE/contract fail/canary fail/stale/promote/fix-on-light)

---

*审核结论：Phase 5 实现了完整的 14 步主循环，所有已知 P0 问题已修复。VerificationGate 是 MVP stub 但不阻塞 E2E 骨架测试。代码质量高，可进入 Phase 6 (CLI + Surrogate Integration + E2E Validation)。*
