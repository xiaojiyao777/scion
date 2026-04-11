# Scion v0.2 — GPT-5.4-Pro 完整架构审查

*审查日期: 2026-04-11*
*审查范围: Scion v0.2 全量代码与设计（Sprint A-E）*
*审查模型: GPT-5.4-Pro (reasoning)*

---

## 1. 审查目标

你是 Scion 框架的架构审查员。Scion 是一个面向组合优化算法自动改进的研究执行框架。

v0.2 在 v0.1 基础上实现了以下核心能力：
- **Sprint A**: Foundation — deterministic 环境、V5 诊断增强、campaign artifact 完整性
- **Sprint B**: Parameter plumbing — 参数搜索配置、权重 IO、evaluator
- **Sprint C**: Parameter search close loop — 随机/局部优化器、promote hook、lineage
- **Sprint D**: First proof — 端到端验证（promote 后自动触发权重优化）
- **Sprint E**: Search-efficiency polish + Engineering robustness — 20 个 task（Pydantic 校验、降级恢复、AST 扫描、家族追踪、策略引导、停滞检测、熔断器、贝叶斯优化器等）

你需要审查整个 v0.2 代码是否：

1. **遵循架构 v3 的核心约束**（三层控制、Decision Input Guard、LLM 只能提案不能决策）
2. **与 v0.2 设计文档一致**（不偏离设计意图）
3. **没有引入安全/正确性风险**
4. **代码质量达到研究框架标准**
5. **各模块之间的接口一致、依赖合理**

---

## 2. 架构核心约束（必须严格检查）

### 2.1 三层控制模型

```
Layer A: Creative Layer (LLM, tainted)
  → 输出全部视为 tainted 数据
Gate 1: Contract Gate (结构边界)
Gate 2: Verification Gate (语义正确性)
Layer B: Decision Layer (确定性)
  → 只读 DecisionFeatures（数值+枚举，无自由文本）
```

**审查要点**：
- v0.2 的所有变更是否在任何地方让 LLM 的输出绕过 Contract/Verification 直接影响决策？
- 参数搜索层（optimizer）是否正确隔离在 Decision Layer 之外？
- 降级恢复（T20）复用 hypothesis 时是否重新经过 Contract Gate？

### 2.2 Decision Input Guard

```python
@dataclass(frozen=True)
class DecisionFeatures:
    # 只有数值和枚举字段，没有任何自由文本
    branch_id: str
    stage: Literal["screening", "validation", "frozen"]
    win_rate: Optional[float]
    median_delta: Optional[float]
    # ...
```

**审查要点**：
- StagnationDetector、CircuitBreaker、HypothesisFamily 等新模块是否向 DecisionFeatures 注入了自由文本？
- 参数优化结果（WeightOptimizationResult）是否绕过 DecisionFeatures 直接影响 champion 状态？

### 2.3 暴露控制

| 信息类型 | Screening | Validation | Frozen |
|---|---|---|---|
| per-case 原始结果 | 可见（LLM/人类）| 不可见 | 永不暴露 |
| aggregate | 可见 | 可见 | 仅 aggregate |

**审查要点**：
- ContextManager 改动（T09/T10/T26）是否泄露了 validation/frozen 的 per-case 数据给 LLM？
- Champion baseline hints 的数据来源是否只来自 screening？
- "What Worked" 记忆分类是否只包含 screening 阶段的数据？

### 2.4 参数搜索与结构搜索的隔离

架构 v3 §19 定义：参数搜索在 promote 后触发，不走 Branch/Verification/Protocol。

**审查要点**：
- 参数优化是否独立于分支状态机？
- 优化只在 champion snapshot 的 copy 上进行，不影响正在进行的分支实验？
- 优化结果是否正确写入 lineage？

---

## 3. 模块级审查清单

### 3.1 core/campaign.py — 主循环（重点审查）

这是整个框架的核心。v0.2 改动最大的文件。

审查项：
- [ ] 主循环 `run()` → `run_one_step()` 的完整流程是否符合架构 v3 §18 伪代码
- [ ] T20 降级恢复：pending hypothesis 的复用是否绕过 Contract Gate？
- [ ] T29 熔断器：连续 LLM 失败后的 campaign 终止是否正确写入 summary？误触发风险？
- [ ] T25/T23 停滞检测：诊断信息是否被回喂给 LLM？是否影响 Decision Engine？
- [ ] `_on_promote()` 的权重优化 hook：是否在独立 workspace 上操作？
- [ ] 权限 bug 修复：copytree 后的 chmod 是否正确？
- [ ] 分支状态机转换是否与架构 v3 §11.3 一致
- [ ] Budget 管理是否正确（哪些操作消耗预算，哪些不消耗）

### 3.2 proposal/context_manager.py — 上下文构造（重点审查）

控制 LLM 看到什么信息，直接关系到暴露控制。

审查项：
- [ ] `build_hypothesis_context()` 是否只暴露 screening 阶段的数据？
- [ ] T07 HypothesisFamily：family_id 的规则提取是否鲁棒？
- [ ] T08 Strategy guidance："AVOID this approach" 是否构成对 LLM 的决策指令？（架构 v3 §1.3 LLM 只能提案）
- [ ] T09 Richer feedback：反馈是否包含 validation/frozen per-case 数据？
- [ ] T10 Champion baseline hints：数据来源是否只从 screening 实验？
- [ ] T26 Memory classification："What Worked" 是否泄露 validation/frozen 细节？
- [ ] Prompt caching 策略是否合理（system blocks 分层、cache_control 设置）

### 3.3 proposal/engine.py + schemas.py — Proposal 引擎

审查项：
- [ ] T19 Pydantic 校验：validators 是否与 HypothesisProposal/PatchProposal dataclass 一致？
- [ ] ProposalValidationError 是否被路由为 category A 失败（retryable，不消耗分支预算）？
- [ ] 两轮 Proposal（hypothesis → code）的上下文隔离是否正确（Round 2 不看历史结果）

### 3.4 proposal/llm_client.py — LLM 通信层

审查项：
- [ ] T22 分级重试：foreground/background 分级是否正确传播？
- [ ] T27 截断恢复：retry 是否可能无限循环？部分内容返回后下游能否处理？
- [ ] Prompt caching（cache_control）是否正确实现？
- [ ] API 错误处理是否完善（429/529/refusal/timeout）

### 3.5 contract/gate.py — Contract Gate

审查项：
- [ ] C1-C10 检查清单是否与架构 v3 §9 一致
- [ ] T21 C9b_non_rng_random：检测模式是否完整？`rng.*` 跳过逻辑能否被绕过？
- [ ] import 白名单是否与 problem.yaml 定义一致

### 3.6 verification/gate.py — Verification Gate

审查项：
- [ ] V1-V9 检查顺序是否正确（V1-V4 light → V5 state_mutation → V6 feasibility → V7 objective → V8 nondeterminism → V9 perf_guard）
- [ ] 失败路由是否与架构 v3 §10.4 一致（轻度可重试，重度不可重试）
- [ ] V5/V8 拆分后的检查逻辑是否正确

### 3.7 core/stagnation.py — 停滞检测（全新模块）

审查项：
- [ ] 四种检测（collapse/oscillation/plateau/timeout_cascade）的阈值是否合理
- [ ] CampaignDiagnosis 的 recommendation 是否只用于日志/报告，不回喂 Decision？
- [ ] 与 campaign 主循环的集成点是否正确

### 3.8 parameter/ — 参数搜索层

审查项：
- [ ] ParameterSearchSpace、evaluator、optimizer 接口是否一致
- [ ] RandomLocalWeightOptimizer 是否 seed-deterministic
- [ ] BayesianWeightOptimizer fallback chain（skopt → scipy → RandomLocal）是否可靠
- [ ] 权重优化结果是否只写入 champion snapshot，不影响 Decision？
- [ ] WeightOptimizationResult 的 lineage 记录是否完整

### 3.9 runtime/ — 运行时隔离

审查项：
- [ ] subprocess runner 环境是否 clean（PYTHONHASHSEED=0 等）
- [ ] T28 输出外包：`__offloaded__:` 前缀是否有注入风险？
- [ ] workspace 隔离是否充分（champion snapshot 只读、分支独立 workspace）

### 3.10 failure/router.py — 失败路由

审查项：
- [ ] 四层分类（Proposal/Contract → Verification → Runtime/Infra → Evaluation）是否与架构 v3 §13 一致
- [ ] 哪些失败消耗预算，哪些不消耗，是否正确

### 3.11 lineage/ — 追溯性

审查项：
- [ ] SQLite schema 是否覆盖架构 v3 §14.2 的最低记录字段
- [ ] 权重优化 lineage（weight_optimizations 表）是否完整
- [ ] hypothesis → code → evaluation → decision 全链路是否可追溯

### 3.12 cli/main.py — CLI

审查项：
- [ ] `scion postmortem` 命令输出是否完整
- [ ] `scion report` / `scion inspect` 是否反映 Sprint E 新功能
- [ ] 错误处理是否合理

### 3.13 config/ — 配置层

审查项：
- [ ] ProblemSpec / ProtocolConfig / SplitManifest / SeedLedger 定义是否完整
- [ ] 新增配置项（optimizer_type 等）是否有合理默认值
- [ ] 向后兼容性：v0.1 的 problem.yaml 是否仍能加载

---

## 4. 跨模块一致性检查

- [ ] 新增模块的依赖关系是否合理（无循环依赖）
- [ ] 数据模型（models.py）是否是所有模块的 single source of truth
- [ ] 错误类型的传播路径是否一致
- [ ] 所有模块是否使用统一的 logging 风格
- [ ] 测试是否有 mock 过度掩盖集成问题的风险

---

## 5. 输入文档

### 5.1 架构与设计参考（只读）

**[A1] 基石架构文档 — scion-architecture-v3.md**
```
<在此粘贴 ~/research/or-autoresearch-agent/design/scion-architecture-v3.md 全文>
```

**[A2] v0.2 设计文档 — scion-v0.2-design.md**
```
<在此粘贴 ~/research/or-autoresearch-agent/scion/design/scion-v0.2-design.md 全文>
```

**[A3] v0.2 开发计划 — scion-v0.2-development-plan.md**
```
<在此粘贴 ~/research/or-autoresearch-agent/scion/design/scion-v0.2-development-plan.md 全文>
```

**[A4] CC 源码综合参考 — cc-design-reference-v2.md**
```
<在此粘贴 ~/research/or-autoresearch-agent/scion/design/cc-design-reference-v2.md 全文>
```

**[A5] UUID Postmortem — 001-v5-uuid-nondeterminism.md**
```
<在此粘贴 ~/research/or-autoresearch-agent/scion/postmortem/001-v5-uuid-nondeterminism.md 全文>
```

### 5.2 完整源码（审查对象）

以下是 v0.2 的全部核心源码文件。每个文件粘贴完整内容。

**核心模块：**

**[C1] scion/core/campaign.py**（主循环 — 最重要）
```python
<在此粘贴完整文件>
```

**[C2] scion/core/models.py**（数据模型）
```python
<在此粘贴完整文件>
```

**[C3] scion/core/scheduler.py**（调度器）
```python
<在此粘贴完整文件>
```

**[C4] scion/core/decision.py**（决策引擎）
```python
<在此粘贴完整文件>
```

**[C5] scion/core/stagnation.py**（停滞检测）
```python
<在此粘贴完整文件>
```

**[C6] scion/core/termination.py**（终止条件）
```python
<在此粘贴完整文件>
```

**Proposal 层：**

**[C7] scion/proposal/engine.py**（Proposal 引擎）
```python
<在此粘贴完整文件>
```

**[C8] scion/proposal/schemas.py**（Schema + Pydantic 校验）
```python
<在此粘贴完整文件>
```

**[C9] scion/proposal/context_manager.py**（上下文构造 — 重要）
```python
<在此粘贴完整文件>
```

**[C10] scion/proposal/llm_client.py**（LLM 通信层）
```python
<在此粘贴完整文件>
```

**Contract / Verification：**

**[C11] scion/contract/gate.py**（Contract Gate）
```python
<在此粘贴完整文件>
```

**[C12] scion/verification/gate.py**（Verification Gate）
```python
<在此粘贴完整文件>
```

**[C13] scion/verification/state_mutation.py**（V5）
```python
<在此粘贴完整文件>
```

**[C14] scion/verification/nondeterminism.py**（V8）
```python
<在此粘贴完整文件>
```

**Runtime / Execution：**

**[C15] scion/runtime/subprocess_runner.py**（子进程运行器）
```python
<在此粘贴完整文件>
```

**[C16] scion/runtime/workspace.py**（workspace 管理）
```python
<在此粘贴完整文件>
```

**[C17] scion/runtime/pool_manager.py**（算子池管理）
```python
<在此粘贴完整文件>
```

**Protocol / Experiment：**

**[C18] scion/protocol/experiment.py**（实验协议）
```python
<在此粘贴完整文件>
```

**[C19] scion/protocol/evaluation.py**（评估逻辑）
```python
<在此粘贴完整文件>
```

**[C20] scion/protocol/stats.py**（统计）
```python
<在此粘贴完整文件>
```

**Parameter Search：**

**[C21] scion/parameter/optimizer.py**（优化器）
```python
<在此粘贴完整文件>
```

**[C22] scion/parameter/evaluator.py**（评估器）
```python
<在此粘贴完整文件>
```

**[C23] scion/parameter/search_space.py**（搜索空间）
```python
<在此粘贴完整文件>
```

**Failure / Lineage：**

**[C24] scion/failure/router.py**（失败路由）
```python
<在此粘贴完整文件>
```

**[C25] scion/lineage/registry.py**（追溯注册）
```python
<在此粘贴完整文件>
```

**[C26] scion/lineage/branch_store.py**（分支/假设存储）
```python
<在此粘贴完整文件>
```

**Config：**

**[C27] scion/config/problem.py**（问题配置）
```python
<在此粘贴完整文件>
```

**CLI：**

**[C28] scion/cli/main.py**（CLI 入口）
```python
<在此粘贴完整文件>
```

**Problem Definition：**

**[C29] problems/warehouse_delivery/problem.yaml**
```yaml
<在此粘贴完整文件>
```

**[C30] problems/warehouse_delivery/protocol.yaml**
```yaml
<在此粘贴完整文件>
```

**[C31] problems/warehouse_delivery/split_manifest.yaml**
```yaml
<在此粘贴完整文件>
```

---

## 6. 输出要求

请按以下结构输出审查结果：

### 6.1 架构合规性（Pass/Fail + 详细说明）

| 约束 | 结果 | 说明 |
|------|------|------|
| 三层控制模型完整性 | ? | |
| Decision Input Guard 无自由文本 | ? | |
| 暴露控制（validation/frozen 不泄露给 LLM） | ? | |
| LLM 只能提案不能决策 | ? | |
| 参数搜索与结构搜索隔离 | ? | |

### 6.2 模块级审查结果

每个 §3 中的审查项，逐项给出：
- **状态**：✅ 通过 / ⚠️ 需注意 / ❌ 违规
- **发现**：具体问题描述（引用代码行号或函数名）
- **建议**：修复方案（如果有问题）

### 6.3 跨模块一致性

### 6.4 代码质量问题

包括但不限于：
- 重复代码
- 错误处理不完善
- 命名不一致
- 注释不足或过多
- 类型标注缺失

### 6.5 与设计文档的偏差

对照 v0.2 设计文档和架构 v3，列出实现与设计的偏差：
- 设计中有但未实现的
- 实现了但与设计不符的
- 实现超出设计范围的

### 6.6 总结

- **总体评价**（1-5 分）
- **必须修复的问题**（blocking — 不修就不能做 Sprint F 实验）
- **建议修复的问题**（non-blocking — 可以在 Sprint F 后修）
- **Sprint F 实验前的准备事项**
- **v0.3 需要关注的架构债务**
