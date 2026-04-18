# 11 — Canary Regression Check

## 核心设计目的

> **Canary 选的是已知容易出问题的边界场景，作为确定性的基准检查。**

Canary 是三级实验协议之外的独立安全阀，回答的问题和三级协议不同：

```
Screening / Validation / Frozen  ← "这个算子更好吗？"（性能问题）
Canary                            ← "这个算子还安全吗？"（正确性问题）
```

哪怕 screening wr=0.90、frozen wr=1.0，只要 canary veto，就不 promote。这是一个**无法被统计结果覆盖的底线**。

---

## Veto 条件

```python
canary_passed = False 当：
  feasibility_violation > 0   # 产出了不可行解（订单丢失/容量超限）
  objective_mismatch          # 目标函数计算结果和参照不一致
  timeout > 阈值              # solver 运行时间异常
  obvious_regression          # 明显负退化（如 splits 翻倍）
```

只要触发一条，不管实验数据多好，不 promote。

---

## 为什么单独设立，不并入 Screening

**Screening 实例**：统计测量，问"有没有改善"，用概率门槛（wr ≥ 0.6）处理噪声。

**Canary 实例**：正确性检查，问"有没有崩"，结果是确定性的（passed/failed），不用统计阈值。

把 canary 混入 screening 有两个问题：
1. Canary 失败可能被其他 case 的胜利"平均"掉——算子崩了某个边界场景，但 screening 总体 wr 还是过了
2. Canary 的意义（固定基准）被 screening 的统计特性稀释

---

## 在流程里的位置

```
Contract Gate → Verification Gate
    ↓
每次实验（screening / validation / frozen）时同步运行 canary
    ↓
canary_result 写入 experiment_events
    ↓
Frozen Gate 检查：
  bootstrap_ci_low ≥ 0
  canary_passed == True   ← 必须都满足，缺一不可
```

Canary 不是跑一次，**每次实验都跑**，保证算子在整个验证过程中始终保持正确性。

---

## 当前实例集的局限

当前 3 个 canary 实例来自同一生成器（generate_v3.py 家族），和 screening/validation/frozen 有相同的系统性偏差。

**会漏掉的场景**（生成器不会自然产生）：
```
全部订单锁定（locked_vehicle_id 全设置）
单车辆恰好满载（容量差1单位溢出）
全部危险品订单（必须走 HQ40_DG 专用车型）
单一提货点极端集中（全部东莞提货）
订单数量恰好触碰各车型容量边界
```

一个算子在普通分布下表现好、canary 通过，但遇到上面这些业务边界场景会直接崩——当前 canary 不会发现。

这个局限和 Frozen Holdout 的"生成器偏差"问题属于同一类。

---

## v0.3 升级方案：两类实例来源

### 来源一：手工设计的对抗性实例（静态，入仓库）

覆盖已知业务边界场景，与 `test_oracle.py::TestHardConstraintViolations` 对齐：

```
canary_edge_01.json  全锁定订单（locked_vehicle_id 全设置）
canary_edge_02.json  容量满载边界（总 pallets = 车辆容量上限）
canary_edge_03.json  全危险品订单（HQ40_DG 专用车型）
canary_edge_04.json  单一提货点集中（测 Dongguan 极端场景）
canary_edge_05.json  容量边界±1（T10/HQ40 边界值）
```

这些实例**静态存储在仓库里**，不是生成出来的——本质是问题域的"单元测试"。

### 来源二：实验中总结的失败实例（动态积累）

**核心思路**：实验中实际出问题的场景，就是最好的 canary 候选。

自动积累机制：
```python
# 每次重度 verification failure
if failure_code in ["V5_state_mutation", "V8_nondeterminism"]:
    # 提取触发该失败的实例特征
    candidate_canary_pool.append(extract_instance_pattern(instance))

# 历史上 screening 大败的特定实例类型
if screening_win_rate < 0.2 and specific_instance_pattern_detected:
    candidate_canary_pool.append(instance)

# 人工审核后提升为正式 canary
# 保持 canary set 小而精（5-10 个），不做大规模扩张
```

这样 canary set 随着实验积累越来越聪明——每次发现新的"已知出错模式"都固化进去。

### 两类来源的互补关系

```
手工设计实例   ← 覆盖已知的先验边界场景（人类专家知识）
动态积累实例   ← 覆盖实验中发现的后验失败模式（数据驱动）
```

两者共同构成"已知容易出问题的边界场景"的完整知识库。

---

## F1 的实际情况

F1 的两个 promote（SubcategoryAwareMoveOrder + destroy_rebuild 车型升级）：
`canary_result: "passed"` 全部通过。

在当前生成器产出的 3 个实例上正确性无问题。但能否保证在业务边界场景上不崩，当前 canary 无法回答。这是 v0.3 需要补的安全保证。
