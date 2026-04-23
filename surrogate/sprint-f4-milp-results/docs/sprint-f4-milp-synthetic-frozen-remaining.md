# Sprint F4：Synthetic Frozen 剩余实例说明

*日期：2026-04-21*
*状态：补跑进行中*

---

## 1. 背景

Sprint F4 synthetic 实验共 48 个实例，分两批运行。主批次（`split_manifest_synthetic_resume.yaml`）在运行过程中发现严重异常：**v3 系列中等规模实例的 phase1（minimize splits）运行时间远超预算，最长达 32355 秒（26 倍）**，导致整批任务被手动终止。

终止时已完成 34/48，剩余 14 个 frozen 实例未跑完。

---

## 2. 异常分析：phase1 无法在时间限制内完成

### 现象

| 实例 | n_orders | subcats | phase1_actual | budget | 倍数 |
|------|---------|---------|--------------|--------|------|
| v3_scr_l03 | 130 | 5 | **32355s** | 600s | 53x |
| v3_val_l03 | 168 | 5 | **12343s** | 600s | 20x |
| v3_val_l04 | 175 | 6 | **9715s** | 600s | 16x |
| v3_val_l02 | 143 | 8 | **4661s** | 600s | 7.8x |
| v3_val_l01 | 122 | 6 | **2418s** | 600s | 4x |
| v3_fro_l02 | 215 | 7 | **2102s** | 600s | 3.5x |

### 根本原因

**HiGHS 只在 B&B 节点切换时检查时间**，单个 LP relaxation 节点一旦开始就无法中断。v3 合成实例的 subcat 数量极少（5-8 个），导致 LP relaxation 极松，HiGHS 需要探索大量节点才能收紧 phase1 下界（即"证明" warm_start_f1 已是最优）。

关键观察：**warm_start_f1 在所有超时实例中均等于最终 milp_f1（最优值）**。surrogate VNS 已经找到最优解，但 HiGHS 还在耗费大量时间"证明"它。

### 为何 production 没有此问题

production 实例 subcat 数量远多（45-250），LP relaxation 天然更紧，B&B 树规模小，HiGHS 能迅速证明下界。

---

## 3. 代码修复：phase1 hard timeout + warm_start fallback

**文件**：`surrogate/milp_solver.py`

**修改内容**：

1. 新增 `_solve_phase_with_hard_limit()`：用 daemon thread 包装 `_solve_phase`，强制 wall-clock 上限 `hard_limit = phase1_time_limit + 120s`。
2. 在 `solve_exact()` 中：
   - 启动 phase1 前先记录 `_warm_sum_alpha_fallback`（来自 warm_start.objective.f1）
   - 若 phase1 触发 hard timeout（超过 `phase1_time_limit + 120s`）：
     - 用 `_warm_sum_alpha_fallback` 作为 f1*，跳过 phase1 证明
     - 直接进入 phase2，时间预算为剩余时间（至少 30s）
     - phase2 warm start 使用原始 champion（不读 vars1，因为 solver 线程可能仍在运行）
   - 结果中 `phase1_optimal=False`，`milp_lb_f1=None`，`milp_exact=False`

**语义**：hard timeout 后 f1* 来自 warm_start，是上界而非最优解。若 warm_start 不是最优，phase2 的 cost 也不是最优。从已有数据看，warm_start_f1 每次都命中真正最优，因此此 fallback 实际无损，只是不再提供 lb_f1 证明。

---

## 4. 剩余 14 个实例

**Manifest**：`scion/problems/warehouse_delivery/split_manifest_synthetic_frozen_remaining.yaml`

**输出目录**：沿用 `offline-milp-benchmark/20260421-002145/synthetic/`（与已完成结果同目录）

| 实例 | n_orders | subcats | 风险评估 |
|------|---------|---------|---------|
| v3_fro_l01 | 188 | 6 | **高风险**：与 val_l04 同规模，已触发 phase1 爆炸 |
| v4_fro_l03 | 180 | 5 | 中风险：subcats=5，v4 但规模相近 |
| v4_fro_l04 | 182 | 7 | 中风险：subcats=7，v4 |
| v4_fro_m01 | 60 | 5 | 低风险：小规模 |
| v4_fro_m02 | 67 | 6 | 低风险：小规模 |
| v3_fro_x04 | 430 | 9 | 低风险：大规模反而 LP 更紧 |
| v3_fro_xx01 | 540 | 8 | 低风险 |
| v3_fro_xx02 | 675 | 10 | 低风险 |
| v4_fro_x05 | 365 | 8 | 低风险 |
| v4_fro_x06 | 375 | 6 | 低风险 |
| v4_fro_xx03 | 555 | 9 | 低风险 |
| v4_fro_xx04 | 620 | 8 | 低风险 |
| v4_fro_xxx01 | 975 | 10 | 低风险（超大规模，LP tight） |
| v4_fro_xxx02 | 990 | 12 | 低风险（超大规模） |

有 hard timeout fallback 保护，高/中风险实例最多触发 720s phase1（600s + 120s grace），不再卡死数小时。

---

## 5. 运行命令

```bash
PYTHON=/home/xjy-ubuntu/miniconda3/bin/python
OUT=/home/xjy-ubuntu/research-local/or-autoresearch-agent/offline-milp-benchmark/20260421-002145/synthetic

nohup $PYTHON surrogate/run_offline_milp_batch.py \
  --manifest scion/problems/warehouse_delivery/split_manifest_synthetic_frozen_remaining.yaml \
  --family synthetic \
  --out-dir $OUT \
  --workers 4 \
  > /tmp/milp-synthetic-frozen-remaining.log 2>&1 &
```

**并发参数**：`--workers 4`
- 14 个实例，4 个并行 worker
- HiGHS 每 worker 限制 `OMP_NUM_THREADS = max(1, cpu_count // 4)` 线程
- 内存估算：xxx 实例峰值 ~4GB × 2 = 8GB；其余 ~1GB × 2 = 2GB；合计 ≤ 10GB，28GB WSL2 安全

**预计耗时**（有 hard timeout 保护后）：
- 高/中风险实例（v3_fro_l01/v4_fro_l03/l04）：~720s phase1 + ~480s phase2 ≈ 20min
- xxx 实例（975/990 orders）：budget=1200s，约 20-30min
- 4 workers 并行，总墙钟时间约 **1.5-2 小时**

---

## 6. 结果解读注意事项

对于触发 hard timeout fallback 的实例（主要是 v3_fro_l01）：

- `milp_status` 为 `"feasible"`（非 `"optimal"`），`milp_exact=False`
- `phase1_gap` 为 `inf`（标志 hard timeout）
- `milp_lb_f1=null`（无法给出 f1 下界证明）
- `milp_f1` 来自 warm_start，是上界，大概率是真正最优（与已完成类似实例的规律一致）
- `champion_vs_milp_delta_f1=0` 表示 warm_start 与 MILP 结果一致

这类结果仍有参考价值，只是缺少精确最优性证明。
