# Scion Phase 2 Review — Module Audit

*Reviewer: Cris (对照 scion-engineering-arch-v1.md)*
*Date: 2026-04-05*
*Status: Phase 2 代码已落盘，75/75 tests passed*

---

## 审核摘要

总体评分: **7/10**
可直接进入 Phase 3: **YES（但有 2 个 P0 需在 Phase 3 开始前修复）**

---

## 逐模块审核

### Contract Gate (contract/gate.py)

**接口一致性: 8/10**
- `validate_hypothesis(hypothesis, active_hypotheses, blacklist) -> ContractResult` ✅ 与规范一致
- `validate_patch(patch) -> ContractResult` ✅ 与规范一致
- 返回类型 `ContractResult` 正确使用 `core/models.py` 定义 ✅

**安全边界: 7/10**
- C1-C10 全部实现 ✅
- C1 实现方式偏差：规范要求 `pydantic v2 model_validate`，实际实现是手动字段检查。当前 `HypothesisProposal` 是 dataclass 不是 Pydantic model，所以手动检查可以接受，但与规范字面描述不一致。**P1**
- C7 只检查第一个找到 `execute` 方法的类，如果文件中有多个类（辅助类+算子类），可能误判。**P1**
- C9 `open(..., 'w')` 检测良好，覆盖了位置参数和关键字参数两种形式 ✅
- C9 对 `subprocess.Popen`、`subprocess.call` 等 attribute 调用的检测通过 `obj_name in _SENSITIVE_APIS` 实现，正确 ✅

**边界条件: 8/10**
- `delete` action 在 C6/C7/C8/C9 中均正确跳过 ✅
- validate_patch 有 fail-fast 短路逻辑（C4/C5 失败后不做 AST 检查）✅
- C10 新颖性检查使用 `(change_locus, action, target_file)` 三元组比较 ✅

**测试覆盖: 9/10**
- 37 个测试，覆盖 C1-C10 每一项的正反用例 ✅
- ContractResult 结构测试 ✅
- 缺少：多类文件的 C7 测试 **P1**

---

### Runner (runtime/runner.py + subprocess_runner.py)

**接口一致性: 6/10** ⚠️
- `Runner` Protocol 签名与规范一致 ✅
- `ResourceLimits` dataclass 与规范一致 ✅
- **P0 偏差**：规范定义 `RunResult.output: Optional[SolverOutput]`（解析后的 JSON 对象），实际实现为 `RunResult.output_path: Optional[str]`（文件路径）。`SolverOutput` dataclass（vehicles/assignment/objective/feasible）完全缺失。
  - 影响：Verification Gate 和 Experiment Protocol 都期望拿到解析后的 `SolverOutput`，而不是自己去读文件。
  - **必须修复**：在 `core/models.py` 中添加 `SolverOutput`，Runner 负责解析 JSON 并填充。

**安全边界: 8/10**
- 环境变量净化：只传 PATH + PYTHONPATH ✅（规范要求不泄露 HOME，实现正确）
- `preexec_fn` 设置 RLIMIT_CPU / RLIMIT_AS / RLIMIT_NOFILE ✅
- 有 fallback 逻辑处理不支持 RLIMIT_AS 的平台 ✅

**边界条件: 8/10**
- Timeout: `proc.communicate(timeout=...)` + `_kill_proc` (SIGKILL to process group) ✅
- 僵尸进程：`proc.wait(timeout=5)` 有保护 ✅
- OOM 分类：exit_code -9 / SIGKILL + MemoryError 检测 ✅
- MemoryError 在 runner 自身的异常处理 ✅

**测试覆盖: 7/10**
- success/crash/env sanitization 测试 ✅
- timeout 测试因内存限制被 skip（环境约束，可接受）
- 缺少：SolverOutput 解析测试（因为该功能未实现）**P0**

---

### Workspace Materializer (runtime/workspace.py)

**接口一致性: 7/10**
- `create_branch_workspace(branch_id, code_base: str)` — 规范写 `code_base: CodeBase`，实际用 `str`。`CodeBase` 类型未在 models.py 中定义。当前用 str 路径是合理的 MVP 简化。**P1**
- `apply_patch(workspace, patch) -> str` ✅ 返回 code_hash
- `create_champion_snapshot(champion, target_dir) -> str` ✅
- `cleanup(workspace)` ✅
- `compute_code_hash` 作为公开方法暴露 ✅（规范未明确列出但合理）

**安全边界: 7/10**
- Frozen file 二次校验（Contract Gate 是第一层）✅ 双层保护达成
- ⚠️ Frozen patterns 硬编码在 workspace.py 的 `_DEFAULT_FROZEN_PATTERNS` 中，而非从 `ProblemSpec.search_space.frozen` 读取。这意味着如果 ProblemSpec 的 frozen 列表变了，Workspace 的保护不会同步。**P0**
  - 修复方案：构造函数接收 `ProblemSpec` 或 `frozen_patterns` 参数（实际已有 `frozen_patterns` 参数，但默认值是硬编码的，需要调用方传入 ProblemSpec 的值）
- Champion snapshot 只读保护 (chmod) ✅
- cleanup 前先恢复可写权限再删除 ✅

**边界条件: 9/10**
- `code_hash` 确定性：sorted by relative path + sha256 ✅
- 空 operators/ 目录返回空 hash ✅
- 无 operators/ 目录返回空 hash ✅
- workspace 已存在时先 rmtree 再 copytree ✅

**测试覆盖: 9/10**
- 18 个测试，覆盖全面 ✅
- frozen file 拒绝测试 ✅
- hash 一致性/确定性测试 ✅
- cleanup 幂等性测试 ✅

---

## 必须修复 (P0)

1. **Runner: 添加 SolverOutput 并解析 JSON**
   - 在 `core/models.py` 添加 `SolverOutput` dataclass（vehicles, assignment, objective, feasible）
   - `RunResult` 增加 `output: Optional[SolverOutput]` 字段（可与 `output_path` 共存）
   - `LocalSubprocessRunner.run_solver` 在 success 时读取 output JSON 并解析为 `SolverOutput`
   - 添加解析测试

2. **Workspace: frozen_patterns 必须从 ProblemSpec 注入**
   - `WorkspaceMaterializer.__init__` 的 `frozen_patterns` 参数已存在，但默认值硬编码
   - CampaignManager 构造 Materializer 时必须传入 `ProblemSpec.search_space.frozen`
   - 在 Phase 5（主循环）集成时确保此注入路径正确
   - 暂时可标注 TODO，Phase 3-4 不受影响

---

## 建议改进 (P1)

1. **C1 用 Pydantic model_validate** — 当前手动检查可行但不够 DRY。考虑为 HypothesisProposal/PatchProposal 创建 Pydantic 校验版本（或双重定义）
2. **C7 多类文件处理** — 应遍历所有类找到 Operator 子类（通过基类名判断），而非只取第一个
3. **CodeBase 类型** — 可以定义为 `NewType("CodeBase", str)` 增强语义
4. **Runner JSON 解析错误分类** — JSON 解析失败应归入 "crash" 而非 "infra"

---

## 测试缺口

1. Runner: SolverOutput JSON 解析（正常/畸形 JSON/缺字段）
2. Contract Gate: 多类文件中 C7 的行为
3. Workspace: `frozen_patterns` 从外部注入时的行为（非默认值）
4. Runner: `_kill_proc` 的 process group kill 路径（需 mock）

---

*审核结论：代码质量良好，架构对齐度高。P0-1 (SolverOutput) 影响后续 Verification Gate 和 Protocol 的开发，需优先修复。P0-2 (frozen注入) 可在 Phase 5 集成时修复。可以进入 Phase 3。*
