# 03 — 三级实验协议

三级协议解决的是**统计有效性**问题：一个算子改进是真实的，还是只是运气？

---

## 设计原则

核心威胁：**过拟合到已见过的实例**。

LLM 在多轮实验中会从 screening/validation 的结果反馈中"学习"——它看到哪些实例容易赢，哪些容易输，并据此调整下一轮的假设方向。这是有益的搜索行为，也是潜在的数据污染。

解法：**分级暴露，frozen 永不回流**。

---

## 三级结构

| 级别 | 实例数 | 用途 | LLM 能看到反馈？ |
|------|--------|------|----------------|
| **Screening** | 17 | 快速粗筛，排除明显差的 | ✅ 完整 per-case 细节 |
| **Validation** | 10 | 正式验证，确认非运气 | ⚠️ 仅 aggregate |
| **Frozen Holdout** | 18 | 最终裁判，泛化性验证 | ❌ 永不暴露，仅 pass/fail |

**实例规模覆盖（v4 split manifest）：**
- Screening：small(20-40) + medium(50-70) + large(100-200) 实例
- Validation：large + xlarge(300-500)
- Frozen：large + xlarge + xxlarge(725-990)

---

## Frozen Holdout 的意义

"LLM 永远看不到 frozen 实例"的精确含义：**frozen 实验的结果永远不会进入 LLM 的上下文**。

不是 frozen 文件不可读，是 frozen 的结果只流向 `DecisionFeatures → Decision Engine`，这条路完全绕开 CreativeLayer。

类比机器学习：
- Screening = 训练集（看反馈，可以调整）
- Validation = 验证集（有限反馈）
- Frozen = 测试集（从未见过任何反馈）

---

## 晋升门槛（三级 Gate）

**Screening Gate（粗筛）：**
```
win_rate ≥ 0.60
median_delta ≥ δ_screen（实际意义阈值）
```
结果：pass → READY_VALIDATE / unclear → EXPLORE_EXPAND / fail → continue_explore

**Validation Gate（正式验证）：**
```
win_rate ≥ 0.66
median_delta ≥ δ_validate
bootstrap_ci_low ≥ 0（置信区间下界不穿零）
```
结果：pass → READY_FROZEN / expand → VALIDATING_EXPAND / fail → ABANDONED

**Frozen Gate（最终确认）：**
```
bootstrap_ci_low ≥ 0
canary_passed == True（独立回归探针通过）
无重度 verification/runtime 失败
```
结果：confirmed → PROMOTED / rejected → ABANDONED

---

## Canary Regression Check

独立于三级协议的 veto 机制，使用 3 个固定 canary 实例：
- **只做 veto，不做晋升证据**
- Veto 条件：feasibility violation / objective mismatch / 明显负退化
- 即使 frozen 通过，canary 失败则不 promote

---

## 统计设计细节

**评估单位**：case（实例）级别，不是 pair 级别。
每个 case 跨 seed 聚合（majority vote），得到 case-level win/loss/tie。

**种子（seeds）：**
```yaml
screening: [42, 137]          # 2 seeds per case
validation: [7, 19, 83]       # 3 seeds
frozen: [256, 512, 1024]      # 3 seeds
```

**Expand 规则（结果 unclear 时）：**
- Screening expand：6→10 或 10→16 cases
- Validation expand：10→20 cases
- 只能 expand 一次，不能无限刷

**不允许的操作：**
- 换 seed/case 重跑（换了就不是同一个实验）
- 反复刷直到过阈值

---

## 局限性：生成器偏差

**当前实现的局限**：所有实例（screening/validation/frozen）来自同一个生成器（`generate_v3.py` + `generate_v4_supplement.py`）。

Scion 目前能证明的是：**在同一生成器的分布内，改进能泛化**。

不是：**在真实生产数据上能泛化**。

**解法路径（尚未实现）：**
1. 往 frozen 池混入真实生产实例
2. 生产 shadow deployment（A/B）验证
3. 提升生成器保真度（引入真实订单的统计特征）
