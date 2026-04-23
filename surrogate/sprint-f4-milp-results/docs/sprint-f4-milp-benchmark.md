# Sprint F4：MILP Baseline Benchmark 实验记录

*日期：2026-04-21*
*状态：实验进行中 → 完成后更新结果*

---

## 1. 实验目的

为 Scion surrogate solver 建立 **MILP 精确解基线**，回答以下问题：

1. 当前 champion 在各规模实例上距离数学最优有多远（optimality gap）
2. 生产实例（production）与合成实例（synthetic）的难度差异
3. 各规模层级的 MILP 求解可行性（小规模能否 exact，大规模 gap 多大）

结果用于校准 Scion 的改进方向，不替代主搜索流程。

---

## 2. 两组实验

### A 组：Synthetic（48 实例）

- **Manifest**：`scion/problems/warehouse_delivery/split_manifest.yaml`
- **数据来源**：v3 + v4 合成实例（`surrogate/data/`）
- **规模覆盖**：small (22-39) → medium (54-93) → large (108-215) → xlarge (258-430) → xxlarge (540-675) → xxxlarge (975-990) orders
- **分组**：canary 3 + screening 17 + validation 10 + frozen 18

| split | 实例数 | 典型规模 |
|-------|--------|---------|
| canary | 3 | v3 medium + v4 small |
| screening | 17 | v3 medium/large + v4 small/medium-large |
| validation | 10 | v3 large/xlarge + v4 medium/xxlarge |
| frozen | 18 | v3 large/xlarge/xxlarge + v4 medium/large/xlarge/xxlarge/xxxlarge |

### B 组：Production（35 实例）

- **Manifest**：`scion/problems/warehouse_delivery/split_manifest_prod.yaml`
- **数据来源**：生产统计特征生成实例（`scion-data/production/`）+ 2 条真实数据
- **规模覆盖**：micro (~33-50) → small (~56-78) → medium-small (~85-122) → medium (~149-248) → medium-large (~255-282) → large (~338-497) → xlarge/xxlarge (~353-808) + day1 (383) + day2 (519) orders
- **特点**：subcat 数量多（12-250），比同等 order 数的 synthetic 实例更难

| split | 实例数 | 规模层级 |
|-------|--------|---------|
| canary | 2 | small |
| screening | 18 | micro / small / medium-small / medium / medium-large |
| validation | 6 | large / large-xl |
| frozen | 9 | xlarge / xxlarge + real day1/day2 |

---

## 3. 求解配置

| 参数 | 值 |
|------|----|
| 主求解器 | HiGHS（via PuLP） |
| warm start | surrogate VNS 200 iters → 注入 MIP start |
| 并行 workers | 2 per group（共 4 进程） |
| OMP_NUM_THREADS | 2（每 worker 限制 HiGHS 线程） |
| 结果验证 | oracle `check_feasibility` + `recompute_objective` |

**时间预算**（由 `estimate_budget()` 按规模自动分配）：

*Synthetic：*

| orders | budget (s) |
|--------|-----------|
| ≤ 25 | 600 |
| ≤ 45 | 1800 |
| ≤ 70 | 3600 |
| ≤ 100 | 1800 |
| > 100 | 1200 |

*Production（subcat 多，更难）：*

| orders | budget (s) |
|--------|-----------|
| ≤ 35 | 1200 |
| ≤ 60 | 1800 |
| ≤ 90 | 1200 |
| > 90 | 900 |

---

## 4. 结果目录

```
offline-milp-benchmark/
├── 20260421-002007/production/     ← 本次 production 实验（进行中）
├── 20260421-002145/synthetic/      ← 本次 synthetic 实验（进行中）
├── 20260420-234919-synthetic/synthetic/   ← 历史：synthetic 完整跑（旧代码，串行）
└── 20260420-234510/production/     ← 历史：production 前 3 条（被中断）
```

每个目录内：
- `<instance_name>.json`：单实例结果（run_one 完成后立即写入）
- `summary.partial.json`：实时更新的已完成汇总
- `summary.json`：全部完成后写入

---

## 5. 单实例结果字段说明

```jsonc
{
  // 元信息
  "provider": "milp",
  "family": "synthetic" | "production",
  "split": "canary" | "screening" | "validation" | "frozen",
  "instance_name": "...",
  "n_orders": 29,
  "n_active_subcats": 8,       // 活跃 subcat 数（越多越难）
  "n_locked_orders": 0,        // 已锁定订单数
  "scale": "small" | "medium" | "large" | "xlarge" | ...,
  "time_limit_s": 1200,
  "solver": "HiGHS",

  // Warm start（surrogate VNS）
  "warm_start_strategy": "surrogate_vns_200iters",
  "warm_start_time_s": 0.13,
  "warm_start_f1": 0,          // splits（越小越好）
  "warm_start_f2": 12000,      // cost（越小越好）

  // MILP 结果
  "elapsed_s": 24.09,          // MILP 求解耗时（不含 warm start）
  "milp_status": "optimal" | "time_limit" | "infeasible" | "error",
  "milp_verified": true,       // extract_solution_strict 通过
  "milp_exact": true,          // status=optimal AND phase1_gap=0 AND phase2_gap=0
  "milp_f1": 0,                // MILP 找到的 splits
  "milp_f2": 12000,            // MILP 找到的 cost
  "milp_lb_f1": 0,             // f1 下界（严格有效，即使 timeout）
  "milp_lb_f2": null,          // f2 下界（phase2 才有）
  "phase1_time_s": 0.17,       // phase1（minimize splits）耗时
  "phase2_time_s": 23.89,      // phase2（minimize cost）耗时
  "phase1_gap": 0.0,           // phase1 MIP gap
  "phase2_gap": 0.0,           // phase2 MIP gap
  "gap_f1_pct": null,          // (f1 - lb_f1) / lb_f1 × 100，null 表示 lb=0
  "gap_f2_pct": 0.5,           // (f2 - lb_f2) / lb_f2 × 100

  // Oracle 验证
  "oracle_feasible": true,
  "oracle_violations": [],
  "oracle_f1": 0,
  "oracle_f2": 12000,
  "oracle_consistent": true,   // oracle 重算与 MILP 报告一致

  // Champion（warm start）vs MILP 对比
  "champion_vs_milp_delta_f1": 0,   // warm_start_f1 - milp_f1（>0 表示 MILP 更好）
  "champion_vs_milp_delta_f2": 0
}
```

---

## 6. 关键结论读法

**milp_exact = True**：该实例已找到严格最优解，surrogate 与之对比可得精确 gap。

**milp_status = "time_limit"**：超时，但 `milp_lb_f1` / `milp_lb_f2` 仍是有效下界，`gap_f1_pct` / `gap_f2_pct` 是 optimality gap 的上界。

**champion_vs_milp_delta_f1 > 0**：warm start（surrogate champion）的 f1 比 MILP 解差，说明搜索空间还有改进余地。

**oracle_consistent = False**：MILP 报告的 f1/f2 与 oracle 重算不一致，该结果存疑，需检查。

---

## 7. 实验完成后：快速分析脚本

```python
import json, glob, pandas as pd

def load_results(out_dir):
    records = []
    for f in glob.glob(f'{out_dir}/*.json'):
        if 'summary' in f:
            continue
        records.append(json.load(open(f)))
    return pd.DataFrame(records)

prod = load_results('offline-milp-benchmark/20260421-002007/production')
synt = load_results('offline-milp-benchmark/20260421-002145/synthetic')
df = pd.concat([prod, synt], ignore_index=True)

# 各规模 exact 求解率
print(df.groupby(['family','scale'])['milp_exact'].mean())

# champion vs MILP gap（f1）
solved = df[df['milp_exact'] == True]
print(solved[['family','scale','champion_vs_milp_delta_f1','champion_vs_milp_delta_f2']])

# timeout 实例的 gap 分布
timeout = df[df['milp_status'] == 'time_limit']
print(timeout[['family','scale','gap_f1_pct','gap_f2_pct','elapsed_s']])
```

---

## 8. 运行命令（供复现）

```bash
PYTHON=/home/xjy-ubuntu/miniconda3/bin/python

# production（35 实例，--workers 2）
./surrogate/run_offline_milp_local.sh --family production --workers 2 --python $PYTHON

# synthetic（48 实例，--workers 2）
./surrogate/run_offline_milp_local.sh --family synthetic --workers 2 --python $PYTHON
```

资源参考：4 CPU / 16 GB RAM，两组同时跑时 CPU 刚好满载，内存峰值预计 < 4 GB。
大规模实例（xxxlarge 975 orders）单实例峰值约 2-4 GB，`--workers 2` 是安全上限。
