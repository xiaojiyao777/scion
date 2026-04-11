# Postmortem: V5_state_leak 的 UUID 非确定性根因

*Date: 2026-04-11*
*Author: Cris + BigBOSS*
*Severity: High — 连续拖累 v0.1 到 v0.2 Sprint D 的搜索效率*
*Status: Fixed (commit b783cbb)*

---

## 1. 事件概述

从 v0.1 首次实验到 v0.2 Sprint D，V5_state_leak 一直是假设失败的头号原因：

| 阶段 | V5 失败数 / 总假设数 | V5 失败率 |
|---|---|---|
| v0.1 首轮实验 | 6/10 | 60% |
| v0.2 Sprint D | 6/8 | 75% |

每次 V5 失败意味着一次 LLM 调用（~$0.10-0.30）+ 一次 solver 双跑（~30s）被完全浪费。
更严重的是，连续 V5 失败导致 LLM 被误导到错误的修复方向，产出 6 轮无效迭代。

---

## 2. 错误的诊断路径（我们走过的弯路）

### 2.1 v0.1 阶段的判断

> "V5 失败率 60%，可能是 PYTHONHASHSEED 未固定导致的环境侧伪随机。"

行动：在 v0.2 设计中加入 T01（修 PYTHONHASHSEED）+ T02（V5 诊断增强）。

**错在哪**：只看了 aggregate metric（60% 失败率），没有打开任何一个失败算子的代码做根因分析。

### 2.2 v0.2 设计阶段的判断

> "一部分 V5 是环境问题（PYTHONHASHSEED），另一部分是 LLM 生成的代码确实有 deterministic bug。需要修环境 + 增强诊断。"

行动：修了 PYTHONHASHSEED，跑 Sprint D。

**错在哪**：修了环境后没有建立对照实验验证"修环境能降低多少 V5 失败率"。Sprint D 跑完仍然 75% V5 失败，但我们没有在这个信号处停下来深挖。

### 2.3 Sprint D 后的判断

> "V5 仍是头号杀手，但第 7 轮突破了，说明 LLM 能学会。考虑框架层 deepcopy 兜底。"

行动：准备实施框架层 deepcopy。

**错在哪**：仍然没有读过失败算子的代码。"框架层 deepcopy"针对的是 mutation 假说，但 V5 的真实根因不是 mutation。

### 2.4 BigBOSS 追问后的真实根因

> "为什么 LLM 生成的算子连 deepcopy 都做不到？上下文中没有限制吗？之前的错误没发给 LLM 吗？"

这个问题促使我们第一次完整读了：
1. 6 个失败算子的代码
2. 1 个通过算子的代码
3. 基线算子的代码
4. V5 检测逻辑
5. LLM 上下文构造逻辑

发现：**真正的非确定性来源是 `uuid.uuid4()`，不是 deepcopy/mutation。**

---

## 3. 真实根因

### 3.1 技术根因

`uuid.uuid4()` 调用 `os.urandom()`，产出的 vehicle ID 不受 `rng` seed 控制。

在 200 轮 VNS solver 迭代中，任何一次 operator 调用中创建的 uuid-based vehicle ID 都会导致：
- 两次 solver run 的 vehicle dict 产生不同的 key
- 后续 operator 遍历 `solution.vehicles.items()` 时看到不同的顺序
- `rng.choice()` / `rng.sample()` 在不同的列表上操作 → 选中不同元素
- 从该点开始，两次 run 的整条执行路径发散

### 3.2 为什么基线不触发 V5？

基线 operator 中 `move_order.py`、`destroy_rebuild.py`、`split_vehicle.py` 都使用 uuid.uuid4()。
但在 V5 使用的小规模 canary case 上，这些 operator 很少被选中执行"创建新车辆"的分支（概率 10%，且需满足特定条件），因此 uuid 非确定性很少被触发。

当加入新 operator 后（特别是 create_new 类型的 subcategory consolidation），solver 行为改变，新车辆创建变多，级联概率升高，V5 开始频繁失败。

### 3.3 为什么通过的 SubcatAtomicMerge 没有触发？

SubcatAtomicMerge 也使用了 uuid.uuid4()，但它的内部迭代基于 `sorted(new_sol.assignment.items())`，按 order_id（稳定的字符串）排序，而非按 vehicle_id 排序。这回避了 uuid 引起的顺序不稳定。

**这不是"正确的代码"——它碰巧走了一条不受 uuid 影响的路径。**

---

## 4. 反馈链失效分析

V5 根因长期未被发现，不是因为缺少工具，而是反馈链在三个环节同时失效：

### 4.1 LLM 反馈方向错误

```python
_VERIFICATION_SUGGESTIONS["V5_state_leak"] = (
    "确保只修改 deep_copy 后的对象，不要引用原始 solution 的任何可变子对象"
)
```

这把 LLM 引向了 mutation 假说。6 轮迭代中 LLM 假设的演进：

1. "pure functional approach with no shared state"
2. "completely stateless execution"
3. "extreme care about state isolation"
4. "constructing entirely NEW Vehicle objects"
5. "never referencing any object from the original"
6. "minimal operator with zero aliasing"

每一轮都在更用力地解决一个不存在的问题。

### 4.2 V5 诊断精度不足

V5 返回的 detail 只有 run1/run2 的 objective 差异，没有差异来源。LLM 和人都无法从中定位根因。

### 4.3 Import 白名单漏洞

`uuid` 在 import 白名单中。ContractGate 无法拦截。operator interface spec 虽然说"use rng for all randomness"，但没有点名 uuid 是随机来源。LLM 看到基线算子用 uuid，自然模仿。

---

## 5. 修复措施

### 代码修复（commit b783cbb）

| 文件 | 变更 |
|---|---|
| `operators/base.py` | 新增 `generate_vehicle_id(rng)` helper |
| `move_order.py` | uuid → generate_vehicle_id(rng) |
| `split_vehicle.py` | uuid → generate_vehicle_id(rng) |
| `destroy_rebuild.py` | uuid → generate_vehicle_id(rng) |
| `problem.yaml` | 从 import_whitelist 移除 uuid |
| `context_manager.py` | 更新 V5 诊断建议，指向 uuid/set 迭代/rng |
| `engine.py` | 代码 prompt 中添加 generate_vehicle_id 指令 |

### 验证

- 368 个单元测试全部通过
- 基线 solver 双跑确定性测试通过（V5 PASS ✅）

---

## 6. 经验教训

### 教训 1：每次实验后必须做代码级根因分析

> **规则：当同一类失败出现 ≥ 3 次时，必须至少抽样 1 个 case 做代码级根因追溯，不能只看 aggregate metrics。**

我们设计了完整的 lineage 和 artifact 归档（archive 目录里 6 个失败算子的代码全在），但从未用这些 artifact 做事后分析。设计了可追溯性，却没有真正追溯。

### 教训 2：修复假说必须有对照验证

> **规则：任何假说修复（如 PYTHONHASHSEED）实施后，必须立即跑对照实验，验证"修复前后失败率变化"。**

我们修了 PYTHONHASHSEED 但没有验证效果。Sprint D 跑完 V5 仍然 75%，这个信号被忽略了。

### 教训 3：当 LLM 连续失败时，怀疑框架/环境而非 LLM

> **规则：LLM 连续 ≥ 3 轮在同一检查点失败，应首先排查框架/环境/诊断链的问题，而非默认"LLM 不够聪明"。**

6 轮连续 V5 失败不是 LLM 能力问题——是框架给了错误的诊断信号，且没有拦截真实的危险 API（uuid）。

### 教训 4：诊断建议必须基于证据，不能基于命名

> **规则：V-check 的 failure suggestion 必须基于对失败代码的实际分析，不能仅凭检查项的名字（"state_leak" → "别改 state"）推导。**

V5 叫 "state_leak"，但它检测的是"两次 run 的 objective 不一致"——这可能是 state mutation，也可能是非确定性 ID、set 迭代顺序、外部熵源等多种原因。诊断建议只覆盖了一种可能性。

### 教训 5：基线代码也可能有 bug

> **规则：不要假设"一直在用的代码就是对的"。新功能失败时，应同时审查新代码和它依赖的基线代码。**

uuid 非确定性从 v0.1 第一天就存在于基线算子中。它只是因为触发条件苛刻而没被暴露。新算子的加入改变了 solver 动力学，让潜伏 bug 浮出水面。

---

## 7. 流程改进

基于上述教训，在 Scion 实验操作流程中新增：

1. **Campaign 结束后的必做项**：对每类失败模式抽样至少 1 个 case，读代码，写 ≥ 3 句根因分析，记录在 campaign 报告中。
2. **修复验证**：任何环境/框架修复后，必须跑最小对照实验（修复前后 V5 失败率对比），不能直接进入下一阶段。
3. **连续失败升级**：LLM 连续 3+ 次在同一检查点失败 → 暂停 campaign，先做框架/环境审查。
4. **Diagnostic review**：每个 V-check 的 failure suggestion 必须有至少一个真实失败 case 的代码分析作为支撑。

---

*本文档是 Scion 框架的第一份事后分析报告。后续所有 P0 级 bug 和实验异常都应按此模板记录。*
