# Scion v0.2 Sprint E — GPT-5.4-Pro Architecture Review

*审查日期: 2026-04-11*
*审查范围: Sprint E1-E5 全部变更 (commits c982d9d..996d684)*
*审查模型: GPT-5.4-Pro (reasoning)*

---

## 1. 审查目标

你是 Scion 框架的架构审查员。Scion 是一个面向组合优化算法自动改进的研究执行框架，核心架构定义在 `scion-architecture-v3.md` 中。

Sprint E 是 v0.2 的"Search-efficiency polish + Engineering robustness"阶段，共 20 个 task（E1-E5 五个 phase），由 Claude Code 自动开发。你需要审查这些变更是否：

1. **遵循架构 v3 的核心约束**（三层控制、Decision Input Guard、LLM 只能提案不能决策）
2. **与 v0.2 设计文档一致**（不偏离设计意图）
3. **没有引入新的安全/正确性风险**
4. **代码质量达到研究框架标准**

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

**审查要点**：Sprint E 的变更是否在任何地方让 LLM 的输出绕过 Contract/Verification 直接影响决策？

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

**审查要点**：新增的 StagnationDetector、CircuitBreaker、HypothesisFamily 等模块是否向 DecisionFeatures 注入了自由文本？

### 2.3 暴露控制

| 信息类型 | Screening | Validation | Frozen |
|---|---|---|---|
| per-case 原始结果 | 可见（LLM/人类）| 不可见 | 永不暴露 |
| aggregate | 可见 | 可见 | 仅 aggregate |

**审查要点**：T09/T10 的 feedback 改动是否泄露了 validation/frozen 的 per-case 数据给 LLM？

---

## 3. 重点审查项（主干变更）

### 3.1 campaign.py — 主循环变更（+274 行）

Sprint E 在 campaign 主循环中加了三个新逻辑路径：

**T20: 降级恢复**
- Code gen 失败时保留 hypothesis，下一轮复用
- 审查：pending hypothesis 的复用是否绕过了 Contract Gate？
- 审查：retry 逻辑是否正确计入/不计入分支预算？

**T25/T23: 停滞检测 + 诊断**
- 每轮结束后调用 StagnationDetector
- 审查：诊断信息是否被回喂给 LLM？如果是，是否违反了暴露控制？
- 审查：停滞信号是否影响 Decision Engine 的晋升/淘汰决策？

**T29: 熔断器**
- 连续 3 次 LLM 失败触发 circuit breaker
- 审查：熔断后的 campaign 终止是否正确写入 summary？
- 审查：是否有可能误触发（比如网络抖动导致的连续失败）？

### 3.2 context_manager.py — 上下文构造变更（+333 行）

这是 LLM 看到什么信息的关键模块。

**T07: HypothesisFamily tracking**
- 审查：family_id 的规则提取是否足够鲁棒？是否会错误归类？
- 审查：exploration coverage report 是否泄露了不该暴露的信息？

**T08: Strategy-shift guidance**
- 审查：guidance 是否构成了对 LLM 的"决策指令"？（按架构 v3，LLM 只能提案，guidance 是否越界？）
- 注意：guidance 说"AVOID this approach"是否等于决策层在指示 LLM？

**T09: Richer case feedback**
- 审查：反馈中是否包含了 validation/frozen 阶段的 per-case 数据？
- 审查：champion baseline hints 的数据来源是 screening 还是 validation？

**T10: Champion baseline hints**
- 审查：baseline 数据来自哪里？只能来自 screening 阶段

**T26: Memory classification**
- 审查："What Worked" 部分是否暴露了 validation/frozen 的细节？
- 审查：成功记录是否只包含 screening 阶段的数据？

### 3.3 llm_client.py — LLM 通信层变更（+38 行）

**T22: 分级重试**
- 审查：foreground/background 的分级是否正确传播？
- 审查：background fail-fast 是否会意外影响 foreground 调用？

**T27: 截断恢复**
- 审查：truncated response 的 retry 是否可能导致无限循环？
- 审查：部分内容返回后，下游是否能正确处理？

### 3.4 contract/gate.py — Contract Gate 变更（+57 行）

**T21: C9b_non_rng_random**
- 审查：检测模式是否完整？有没有遗漏的非 rng 随机源？
- 审查：`rng.*` 的跳过逻辑是否可能被恶意代码绕过？（比如 `rng = random; rng.random()`）

### 3.5 parameter/optimizer.py — 参数搜索变更（+223 行）

**T15b: Bayesian optimizer**
- 审查：optimizer 的 fallback chain（skopt → scipy → RandomLocal）是否可靠？
- 审查：scipy L-BFGS-B 对离散权重空间是否合适？（权重是连续的所以应该没问题）
- 审查：optimizer 是否确定性的（给定 seed）？
- 审查：optimize 结果是否只写入 champion snapshot，不影响 Decision？

### 3.6 core/stagnation.py — 全新模块（224 行）

**T25 + T23**
- 审查：四种停滞检测（collapse/oscillation/plateau/timeout_cascade）的阈值是否合理？
- 审查：CampaignDiagnosis 的 recommendation 是否只用于日志/报告，不回喂 Decision？
- 审查：与 Campaign 主循环的集成点是否正确？

### 3.7 engine.py + schemas.py — Proposal 校验变更（+87 行）

**T19: Pydantic 前置校验**
- 审查：ProposalValidationError 是否被正确路由为 category A 失败（retryable，不消耗分支预算）？
- 审查：Pydantic models 的 field validators 是否与 HypothesisProposal/PatchProposal 的 dataclass 定义一致？

### 3.8 runtime/subprocess_runner.py — 运行时变更（+38 行）

**T28: 输出外包**
- 审查：`__offloaded__:` 前缀的解析是否安全？是否可能被候选代码注入？
- 审查：VerificationGate 是否正确处理了 offloaded 引用？

---

## 4. 跨模块一致性检查

1. **新增模块是否注册到正确的依赖链？**
   - StagnationDetector → Campaign（已集成）
   - CircuitBreaker → Campaign（已集成）
   - HypothesisFamily → ContextManager → Campaign

2. **测试覆盖是否充分？**
   - 525 个测试全部通过
   - 每个 Sprint 都有独立的测试文件
   - 关注：是否有测试用 mock 掩盖了真实的集成问题？

3. **配置兼容性**
   - 新增的配置项（optimizer_type 等）是否有合理默认值？
   - 现有的 problem.yaml 是否仍然兼容？

---

## 5. 输入文档

审查所需的完整文档和代码：

### 5.1 架构参考（只读）

**[A1] 基石架构文档**
```
<在此粘贴 design/scion-architecture-v3.md 全文>
```

**[A2] v0.2 设计文档**
```
<在此粘贴 scion/design/scion-v0.2-design.md 全文>
```

**[A3] Sprint E 设计参考（CC 源码综合）**
```
<在此粘贴 scion/design/cc-design-reference-v2.md 的 §9 Sprint E 部分>
```

### 5.2 Sprint E 变更代码（审查对象）

以下是 Sprint E 的全部核心源码变更。每个文件只包含变更后的完整内容（不是 diff，方便你理解上下文）。

**[C1] scion/core/campaign.py**（主循环 — 重点审查）
```python
<在此粘贴 campaign.py 完整文件>
```

**[C2] scion/proposal/context_manager.py**（上下文构造 — 重点审查）
```python
<在此粘贴 context_manager.py 完整文件>
```

**[C3] scion/contract/gate.py**（Contract Gate）
```python
<在此粘贴 gate.py 完整文件>
```

**[C4] scion/core/stagnation.py**（全新模块）
```python
<在此粘贴 stagnation.py 完整文件>
```

**[C5] scion/parameter/optimizer.py**（参数优化器）
```python
<在此粘贴 optimizer.py 完整文件>
```

**[C6] scion/proposal/engine.py**（Proposal 引擎）
```python
<在此粘贴 engine.py 完整文件>
```

**[C7] scion/proposal/schemas.py**（Pydantic 校验）
```python
<在此粘贴 schemas.py 完整文件>
```

**[C8] scion/proposal/llm_client.py**（LLM 通信层）
```python
<在此粘贴 llm_client.py 完整文件>
```

**[C9] scion/runtime/subprocess_runner.py**（运行时）
```python
<在此粘贴 subprocess_runner.py 完整文件>
```

**[C10] scion/cli/main.py**（CLI）
```python
<在此粘贴 cli/main.py 完整文件>
```

**[C11] scion/core/models.py**（数据模型）
```python
<在此粘贴 models.py 完整文件>
```

**[C12] scion/verification/gate.py**（Verification Gate）
```python
<在此粘贴 verification/gate.py 完整文件>
```

---

## 6. 输出要求

请按以下结构输出审查结果：

### 6.1 架构合规性（Pass/Fail + 详细说明）

| 约束 | 结果 | 说明 |
|------|------|------|
| 三层控制模型完整性 | ? | |
| Decision Input Guard 无自由文本 | ? | |
| 暴露控制（validation/frozen 不泄露） | ? | |
| LLM 只能提案不能决策 | ? | |

### 6.2 重点审查项结果

每个 §3 中的审查项，逐项给出：
- **状态**：✅ 通过 / ⚠️ 需注意 / ❌ 违规
- **发现**：具体问题描述
- **建议**：修复方案（如果有问题）

### 6.3 跨模块一致性

### 6.4 代码质量问题

### 6.5 总结

- 总体评价
- 必须修复的问题（blocking Sprint F）
- 建议修复的问题（非 blocking）
- Sprint F 实验前的准备事项
