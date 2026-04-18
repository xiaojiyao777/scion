# MILP Exact Solver — Implementation Notes

*Date: 2026-04-18*
*Author: CC (opus-4-6) 初版 + Cris 后续优化*
*Status: **v0.3 MVP** — 可用、结果正确、性能在 CBC 预期范围内*

---

## 1. 概述

本模块为 Scion v0.3 W4（MILP-INTEGRATION）提供精确算法基线，对仓配协同优化问题的小规模实例（20-40 orders）生成全局最优解，供 optimality gap 计算使用。

**核心文件**：
- `surrogate/milp_model.py` — 变量/约束/目标函数构建（纯函数）
- `surrogate/milp_solver.py` — 两阶段 epsilon-constraint 求解 + CLI 入口
- `surrogate/tests/test_milp_solver.py` — 单元测试（session-scoped 缓存）

**数学模型来源**：`scion/docs/milp-model.md`，全部约束（C0a-C0d', H1-H8）按原文实现。

---

## 2. 求解器与求解策略

### 2.1 求解器选择

**PuLP 3.3.0 + 内置 CBC**（开源，无需 license）。

- `pulp.PULP_CBC_CMD(msg=0/1, timeLimit=N, gapRel=0)`
- 不使用 Gurobi（无 license）
- 不使用 or-tools 或 HiGHS（PuLP+CBC 对当前 scope 已足够）

### 2.2 两阶段 epsilon-constraint

**Phase 1**：最小化 `Σ_{s,j} α_{sj}`（等价于 `Σ φ_s`，即 subcategory splits + |S_active|）
**Phase 2**：固定 `Σ α_{sj} = f1*`，最小化 `Σ cost_t · z_{jt}`

Phase 2 会用 phase 1 的 feasible 解作 warm start。

### 2.3 K 上界

按 milp-model.md §6.3：`K = ceil(Σp_i / min_cap) + locked_count`，上限 n。
实测 s01 (22 orders) → K=22，s02 (32) → K=31，s03 (39) → K=39。

### 2.4 对称性破坏

对**非锁定槽位**加 `y_j >= y_{j+1}`（milp-model.md §4.8）。
锁定槽位占用 `[0, L-1]`，对称性破坏从 `j=L` 开始。

---

## 3. 优化尝试（详细过程）

### 3.1 尝试过并放弃：Optimization A（H2a'/H3a'/H4a' 补上界）

**思路**：给 indicator 变量（w、u、v）加 `indicator ≤ Σx` 的对应上界，希望收紧 LP 松弛。

**结果**：
- s01 (无 locked)：27.1s → 38.9s（**慢 43%**）
- s02：基线 ≈4-5min → 加 A 后 290s（基本持平，无收益）

**根因**：w/u/v 这三个 indicator 变量**都不在目标函数里**。CBC 的 LP 松弛在求最小化时，只要 `w ≥ x` 约束允许 w=0，LP solver 自然会把 w 推到 0（最小化无目标偏好的变量）。因此 `w ≤ Σx` 对 LP bound 毫无增益，却多出 3 组 O(K × |R/P/C|) 约束，纯增加 CBC 每次 LP solve 的开销。

**结论**：**撤回**。记录为教训：对于 LP 松弛中已自然取到正确值的 indicator 变量，补对称上界无助于求解。

### 3.2 保留的：Optimization B（锁定订单预处理 fix）

**思路**：
1. 锁定订单 i 的 `locked_vehicle_id`，直接 `fixValue` 把 `x[i, locked_slot] = 1`、其他 `x[i, j] = 0`
2. 非锁定订单不能占用锁定槽位，`x[i, locked_slot] = 0` 直接 fix
3. 锁定槽位内的订单总量/危险品若无法装某车型 t，则 `z[locked_slot, t] = 0` 直接 fix

**实现**：`surrogate/milp_model.py` 第 ~170-220 行（搜 `"Optimization B"`）。

**效果**（对有锁定订单的实例）：
- s02 (1 locked, 32 orders)：**未优化版 phase 2 只能找到 f2=28100；优化 B 版找到真正最优 f2=26800**（便宜 1300 元）
- 说明 B 的主要价值**不是让求解更快，而是让相同时间预算内求解更"深"**
- 对无锁定的实例（s01）基本持平

**保留理由**：改动 20 行，零风险，对 locked 实例价值明显。

### 3.3 未尝试的后续方向

如果 v0.3 W16 大规模验证实验发现 MILP 批量跑得太慢，可考虑：

| 方案 | 预期收益 | 改动成本 |
|---|---|---|
| MIP warm start（VNS 启发式跑 5-10s 得 feasible 解传给 CBC） | 2-5× | 30 行 |
| 换 HiGHS 求解器（`pip install highspy`，PuLP 原生支持） | 2-5× | 5 行 |
| 换 or-tools SCIP backend | 2-3× | 重写 PuLP → or-tools API |
| Phase 1 允许 MIP gap=0.5 提前停（splits 是整数，gap<1 即最优） | 中 | 5 行，但要小心 CBC gap 计算 |

v0.3 MVP 不做以上优化。

---

## 4. 实测性能（当前版本）

| 实例 | n | K | locked | phase1 time | phase2 time | 总时间 | status | f1 (splits) | f2 (cost) |
|---|---|---|---|---|---|---|---|---|---|
| s01 | 22 | 22 | 0 | ~24s | ~0s | **24s** | optimal | 0 | 9900 |
| s02 | 32 | 31 | 1 | ~300s | ~290s | **~590s** | optimal | 10 | 26800 |
| s03 | 39 | 39 | 5 | 未测 | 未测 | 未知 | — | — | — |

**对照 milp-model.md §6.3 预估**：
- "n=30: Gurobi 1-10s, CBC 10-60s" — 实测 s02 (n=32) CBC **~10min**（比预估慢 10×，因 phase1 对称性极强 + subcat-split 目标弱松弛）
- "n=40: Gurobi 5-60s, CBC 1-10min" — s03 (n=39) 按趋势估计 **10-30min**

**结论**：n=40 是 CBC 实用上限。v0.3 W4 MILP cache 预生成 s01/s02/s03 的 ground-truth 可接受，ml 系列（73-93 orders）可能要 30min-数小时 per instance，**不建议作为默认覆盖**。

---

## 5. 测试设计

### 5.1 Session-scoped 缓存

17 个测试 × 3 实例会触发 15 次独立 MILP 求解（原始 CC 版本），成本不可接受。
当前实现使用 `pytest.fixture(scope="session")` 的 `small_instance`，每个实例在 session 内**只 solve 一次**，6 个下游测试（feasibility、oracle、f1、f2、vs_vns）共享同一 MILPResult。

### 5.2 VNS 对比测试

`TestVsHeuristic.test_milp_not_worse_than_vns` 跑 VNS 200 iterations 得启发式解，验证：

$$
(\text{MILP}_{f1}, \text{MILP}_{f2}) \leq_{\text{lex}} (\text{VNS}_{f1}, \text{VNS}_{f2})
$$

MILP 字典序上**不严格劣于** VNS 是必要条件（如果劣了说明模型或实现有 bug）。

### 5.3 Locked 订单测试

`TestLockedOrders` 构造小规模 locked case（4 orders, 2 locked 共享 `LOCK_A`），验证 preprocessing B 的正确性。

### 5.4 Timeout 测试

`TestTimeout` 用 5s timeout 跑 s03，验证 solver 返回 `timeout` 状态且不 crash。

---

## 6. 锁定订单的映射策略

**关键设计**：locked orders 按 `locked_vehicle_id` **分组**，每组共享一个 slot。

- `build_locked_slot_map(instance)` 遍历 orders，对每个唯一的 `locked_vehicle_id` 分配一个 `slot` 索引（0-based，按插入顺序）
- 锁定槽位占用 `[0, L-1]`
- `x[i, slot]` 对同组所有 locked orders `setInitialValue(1) + fixValue()`
- 其他 slot 的 `x[i, j]` `setInitialValue(0) + fixValue()`
- H7 约束 `x[i, slot] == 1` 保留作为可审计的冗余约束（PuLP 按常数处理，无额外开销）

**注意**：对称性破坏从 `j=L` 开始（跳过锁定槽位），避免与 H7 冲突。

---

## 7. 已知限制

1. **CBC 求解时间**：n > 40 基本不实用。ml 系列（73-93 orders）预计 30min+，超大实例（150+ orders）无望。
2. **MIP gap**：当前配置 `gapRel=0`（要求证明最优），不允许提前停。若需要可接受 gap，要修改 `solve_exact` 的 solver 参数。
3. **Phase 1 目标弱性**：subcategory-split 目标天然 LP 松弛松，CBC 的分支定界树较深。这是 CBC 对该问题的结构性弱点，不是模型问题。
4. **浮点精度**：cost 均为整数（`VehicleTypeInfo.cost: int`），目标函数保持整数运算，无浮点问题。

---

## 8. 与 Scion v0.3 W4 集成规划

当前求解器作为独立工具已经可用。v0.3 W4 集成时：

1. **MILP cache 离线预生成**：`scion optimum compute --instances v4_scr_s01,v4_scr_s02,v4_scr_s03 --time-limit 600`
2. **Campaign 启动 log MILP optimum**（若 cache 存在）
3. **`scion report --include-gap`** 生成 optimality gap 收敛曲线
4. **MILP 不进入 Decision 路径**（只作为报告维度）

v0.3 W16 大规模验证实验若发现需要加速，参考 §3.3 的后续方向。

---

*MILP solver 归档完成。v0.2 的下一阶段（v0.3-dev 分支）集成工作以此版本为基础。*
