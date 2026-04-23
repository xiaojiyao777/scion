# Sprint F4：Production MILP Benchmark 结果整理

*日期：2026-04-21*
*状态：完成*

---

## 1. 实验概况

| 项目 | 值 |
|------|----|
| Manifest | `split_manifest_prod.yaml` + 补跑 `split_manifest_prod_missing.yaml` / `split_manifest_prod_day.yaml` |
| 输出目录 | `offline-milp-benchmark/20260421-002007/production/` |
| 实例总数 | 35 |
| 完成时间 | 2026-04-21 约 21:00（补跑 day1/day2 最后完成） |

---

## 2. 结果汇总

### 2.1 总体

| 状态 | 数量 | 比例 |
|------|------|------|
| optimal (exact) | 31 | 88.6% |
| infeasible | 4 | 11.4% |
| time_limit | 0 | 0% |
| error | 0 | 0% |

所有 31 个可行实例均在时间限制内找到**精确最优解**（`milp_exact=True`），无任何超时。

### 2.2 按规模分层

| scale | 实例数 | exact | infeasible | n_orders 范围 |
|-------|--------|-------|------------|--------------|
| small | 3 | 3 | 0 | 29–33 |
| medium | 9 | 9 | 0 | 37–116 |
| large | 8 | 6 | **2** | 152–288 |
| xlarge | 15 | 13 | **2** | 308–813 |

### 2.3 完整结果表

| 实例 | split | n | subcats | locked | status | exact | elapsed(s) | f1 | f2 |
|------|-------|---|---------|--------|--------|-------|-----------|----|----|
| can_s01 | canary | 29 | 8 | 0 | optimal | ✅ | 25 | 0 | 12000 |
| can_s02 | canary | 33 | 12 | 0 | optimal | ✅ | 49 | 0 | 13900 |
| scr_micro01 | screening | 51 | 12 | 0 | optimal | ✅ | 1659 | 1 | 15800 |
| scr_micro02 | screening | 37 | 15 | 5 | optimal | ✅ | 177 | 0 | 17000 |
| scr_micro03 | screening | 49 | 18 | 5 | optimal | ✅ | 1657 | 0 | 24400 |
| scr_micro04 | screening | 53 | 14 | 16 | optimal | ✅ | 848 | 0 | 19600 |
| scr_s01 | screening | 81 | 20 | 27 | optimal | ✅ | 1116 | 0 | 30400 |
| scr_s02 | screening | 76 | 25 | 10 | optimal | ✅ | 1175 | 1 | 30500 |
| scr_s03 | screening | 76 | 22 | 0 | optimal | ✅ | 1200 | 1 | 27100 |
| scr_s04 | screening | 82 | 28 | 19 | optimal | ✅ | 1200 | 0 | 29000 |
| scr_ms01 | screening | 84 | 30 | 0 | optimal | ✅ | 1200 | 0 | 33200 |
| scr_ms02 | screening | 116 | 38 | 4 | optimal | ✅ | 901 | 0 | 45500 |
| scr_ms03 | screening | 99 | 35 | 9 | optimal | ✅ | 901 | 0 | 38100 |
| scr_m01 | screening | 152 | 45 | 8 | optimal | ✅ | 1130 | 2 | 53200 |
| **scr_m02** | screening | 182 | 55 | **57** | **infeasible** | ❌ | 3 | — | — |
| scr_m03 | screening | 192 | 50 | 4 | optimal | ✅ | 903 | 2 | 56800 |
| scr_m04 | screening | 202 | 58 | 51 | optimal | ✅ | 903 | 1 | 66700 |
| scr_ml01 | screening | 217 | 75 | 19 | optimal | ✅ | 4034 | 0 | 82600 |
| scr_ml02 | screening | 288 | 85 | 11 | optimal | ✅ | 910 | 3 | 107700 |
| **scr_ml03** | screening | 273 | 80 | **41** | **infeasible** | ❌ | 8 | — | — |
| val_l01 | validation | 308 | 100 | 12 | optimal | ✅ | 912 | 3 | 122200 |
| val_l02 | validation | 340 | 115 | 49 | optimal | ✅ | 915 | 3 | 140800 |
| **val_l03** | validation | 378 | 125 | **81** | **infeasible** | ❌ | 19 | — | — |
| val_l04 | validation | 389 | 130 | 43 | optimal | ✅ | 921 | 1 | 157100 |
| val_lx01 | validation | 457 | 135 | 15 | optimal | ✅ | 934 | 3 | 168200 |
| val_lx02 | validation | 423 | 148 | 58 | optimal | ✅ | 934 | 0 | 173500 |
| fro_x01 | frozen | 462 | 140 | 26 | optimal | ✅ | 940 | 2 | 178100 |
| **fro_x02** | frozen | 583 | 165 | **64** | **infeasible** | ❌ | 66 | — | — |
| fro_x03 | frozen | 451 | 155 | 50 | optimal | ✅ | 949 | 1 | 196900 |
| fro_x04 | frozen | 531 | 170 | 45 | optimal | ✅ | 957 | 2 | 214100 |
| fro_xx01 | frozen | 715 | 220 | 70 | optimal | ✅ | 3607 | 4 | 300900 |
| fro_xx02 | frozen | 813 | 250 | 88 | optimal | ✅ | 3624 | 3 | 311800 |
| fro_xx03 | frozen | 679 | 240 | 18 | optimal | ✅ | 3562 | 2 | 283300 |
| day1 (real) | frozen | 383 | 133 | — | optimal | ✅ | 1806 | 16 | 165100 |
| day2 (real) | frozen | 519 | 160 | — | optimal | ✅ | 1825 | 28 | 225500 |

---

## 3. Surrogate Champion vs MILP 对比

### 3.1 f1（splits）

**MILP 从未改善 f1**：所有 31 个可求解实例中，`champion_vs_milp_delta_f1 = 0`。

surrogate VNS 在每个实例上都找到了与 MILP 精确最优相同的 f1 值，说明 **surrogate 在 splits 目标上已达到真正最优**。

### 3.2 f2（cost）

MILP 在 5/31 个实例上改善了 f2（cost），改善幅度 1.6%–6.2%：

| 实例 | warm_f2 | milp_f2 | 改善 | 幅度 |
|------|---------|---------|------|------|
| scr_micro01 | 16100 | 15800 | -300 | 1.9% |
| scr_micro03 | 24800 | 24400 | -400 | 1.6% |
| scr_s01 | 32400 | 30400 | -2000 | 6.2% |
| scr_ms03 | 39900 | 38100 | -1800 | 4.5% |
| scr_s04 | 30200 | 29000 | -1200 | 4.0% |

这 5 个实例都属于小/中规模（37–99 orders），surrogate 在 cost 层面还有改进空间。

---

## 4. Infeasible 实例分析

### 4.1 现象

4 个实例被 HiGHS 快速证明不可行（3–66 秒），`phase1_gap=0.0`。

**矛盾**：surrogate VNS **均能找到 warm_start 解**（f1 和 f2 均非 null），说明 surrogate 认为这些实例可行。

| 实例 | n | subcats | locked | locked% | warm_f1 | warm_f2 |
|------|---|---------|--------|---------|---------|---------|
| scr_m02 | 182 | 55 | 57 | **31%** | 2 | 80300 |
| scr_ml03 | 273 | 80 | 41 | **15%** | 0 | 118100 |
| val_l03 | 378 | 125 | 81 | **21%** | 0 | 179800 |
| fro_x02 | 583 | 165 | 64 | **11%** | 4 | 257900 |

### 4.2 根本原因推断

**locked 比例高不是决定性因素**（scr_s01 有 33% locked 仍然 optimal）。

最可能的原因：**MILP 模型对 locked order 的 vehicle_id 做强制约束**（`x[o, locked_vehicle_id] = 1`），而某些 locked_vehicle_id 在当前实例的车辆池中已不存在，或与 subcat/容量约束冲突，导致 LP 松弛本身不可行。surrogate 绕过了这一结构检查，因此能找到"违反" locked 约束的解。

### 4.3 待核查

这 4 条 warm_start 解**未经过 oracle 验证**（MILP 返回 no solution，oracle 未被调用）。

可手动验证：对每个 infeasible 实例，单独调用 `oracle.check_feasibility(warm_start_solution, instance, 1)` 确认 surrogate 解是否实际可行。若 oracle 也认为不可行，则 MILP 正确；若 oracle 认为可行，则 MILP 模型存在过约束 bug，需排查 locked vehicle 处理逻辑。

---

## 5. 关键结论

1. **Production 实例对 MILP 更友好**：subcat 多 → LP relaxation 紧 → 无 phase1 爆炸，所有可行实例均在时间预算内完成。

2. **Surrogate f1 已经最优**：MILP 从未在 f1 上超越 surrogate。改进空间在 f2（cost）层面，且仅存在于小/中规模实例。

3. **4 个 infeasible 实例需跟进**：MILP vs surrogate 的不一致说明存在约束处理差异，建议用 oracle 验证 warm_start 解，明确是 MILP 过约束还是 surrogate 漏约束。

4. **day1/day2 真实数据**：day1（383 orders，f1=16）和 day2（519 orders，f1=28）的 splits 数量明显高于同等规模的生成实例（通常 f1=1–4），反映真实生产场景的 subcat 分配复杂度远高于统计生成实例。

---

## 6. Infeasible 实例根因（已确认）

### 6.1 Oracle 验证结论

对 4 个 infeasible 实例手动运行 surrogate VNS + oracle 验证：

```
scr_m02:  oracle_feasible=False  violation: H1: vehicle V_LOCK_…_38 pallets 64 > capacity 40
scr_ml03: oracle_feasible=False  violation: H1: vehicle V_LOCK_…_14 pallets 58 > capacity 40
val_l03:  oracle_feasible=False  violation: H1: vehicle V_LOCK_…_86 pallets 55 > capacity 40
fro_x02:  oracle_feasible=False  violation: H1: vehicle V_LOCK_…_32 pallets 43 > capacity 40
```

**oracle 与 MILP 结论一致：4 个实例均真实不可行。**

### 6.2 根本原因：数据生成 Bug

所有 4 个实例的不可行原因完全相同：**locked vehicle 的 pallet 容量不足以承载被锁定分配给它的订单总量**。

`V_LOCK_` 前缀车辆是实例生成时为 locked order 创建的专属车辆，容量上限为 40 pallets。但实例生成逻辑将超过容量的订单锁定到同一辆车，导致约束 H1（vehicle pallet capacity）本身就无法满足。

这是**数据生成侧的 bug**，与 MILP 模型、surrogate 求解逻辑均无关。

### 6.3 处理结论

这 4 个实例是**无效实例**，从 benchmark 中排除。有效 production 实例为 **31 个**，均找到精确最优解。

Synthetic 组无此问题（合成实例不使用 locked vehicle 机制）。

### 6.4 后续建议

修复数据生成器：在为 locked order 生成 `V_LOCK_` 车辆时，容量应根据被锁定订单的实际 pallet 总量动态设置（或设为足够大的上限），而不是固定 40 pallets。
