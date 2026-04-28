# 完整实验结果总结：Seed 0

## 1. 实验目的

本次实验的目的不是证明当前算法已经性能最优，而是验证：

- 当前算法能否完整跑通本地 CVRPLIB 数据集；
- 每个可运行实例是否都能返回 CVRP 可行解；
- 在有可靠 `.sol` / BKS 的实例上，当前 baseline 的 gap 大致是多少；
- 哪些 subset 可以作为后续自动优化研究的主要评估对象；
- 哪些数据或约束差异会影响 gap 解读。

最终结论是：当前实现可以作为一个可运行 baseline，适合后续自动优化研究。

## 2. 输出文件

最终实验输出：

```text
results/full_experiment_seed0_final.csv
results/reference_validation_bad.csv
results/analysis_full_seed0_final/summary_by_subset.csv
results/analysis_full_seed0_final/per_instance.csv
results/analysis_full_seed0_final/top_gaps.csv
```

其中：

- `full_experiment_seed0_final.csv`：原始完整实验结果；
- `reference_validation_bad.csv`：参考 `.sol` 异常报告；
- `summary_by_subset.csv`：按 subset 汇总；
- `per_instance.csv`：按实例汇总；
- `top_gaps.csv`：gap 最大的实例列表。

## 3. 实验配置

运行保护：

```text
workers = 2
per-instance timeout = 20s
memory limit per child = 4096MB
OPENBLAS/OMP/MKL/NUMEXPR threads = 1
```

求解器参数：

```text
seed = 0
time_limit = 0s for instances without .sol
bks_time_limit = 1s for instances with .sol
large_time_limit = 0s
large_dimension = 2001

cw_threshold = 1000
vns_threshold = 200
alns_threshold = 1000
max_destroy_customers = 80
vns_iterations = 50
```

运行脚本：

```bash
bash run_full_experiment_seed0.sh
```

最终完成时间：

```text
Sat Apr 25 21:20:50 CST 2026
```

## 4. 参考解校验

完整实验前执行了参考解校验：

```bash
python validate_solutions.py cvrplib --output results/reference_validation_bad.csv --bad-only
```

校验结果：

| 状态 | 数量 |
|---|---:|
| ok .sol | 225 |
| missing_sol | 10100 |
| unsupported | 14 |
| cost_mismatch | 4 |
| infeasible .sol | 1 |

异常参考解：

| 实例 | 子集 | 状态 | 说明 |
|---|---|---|---|
| B-n50-k8 | B | infeasible | 客户 2 重复，客户 3 缺失 |
| B-n57-k7 | B | cost_mismatch | 回算成本差 2 |
| E-n30-k3 | E | cost_mismatch | 回算成本差 3 |
| F-n135-k7 | F | cost_mismatch | 回算成本差 8.653 |
| F-n45-k4 | F | cost_mismatch | 回算成本差 0.569 |

不支持实例主要是：

```text
EDGE_WEIGHT_TYPE = EXPLICIT
```

这些异常参考解在最终可比 gap 汇总中被排除。

## 5. 完整运行结果

原始完整实验覆盖：

| 指标 | 数值 |
|---|---:|
| 尝试的 EUC_2D 实例 | 10330 |
| status=ok | 10330 |
| status=timeout | 0 |
| status=error | 0 |
| CVRP feasible=True | 10330 |
| benchmark_feasible=True | 10249 |
| benchmark_feasible=False | 81 |
| 有 raw gap 的行 | 230 |

运行模式分布：

| 模式 | 数量 | 含义 |
|---|---:|---|
| clarke_wright_construction_only | 10000 | XML 等无 `.sol` 实例，只构造可行解 |
| clarke_wright_alns_vns | 220 | 有 `.sol` 的小中规模实例，运行短时 ALNS+VNS |
| sweep_construction_only | 110 | XL/AGS 等大实例，使用大规模保护构造 |

结论：

```text
所有 EUC_2D 实例都成功返回 CVRP 可行解，没有超时或崩溃。
```

## 6. Gap 汇总口径

最终 summary 使用以下过滤条件：

- 排除参考 `.sol` 异常的实例；
- 排除 `benchmark_feasible=False` 的结果；
- 对没有 `.sol` 的实例不计算 gap；
- `XL` / `XML` 保留可运行性统计，但 gap 字段为空。

`benchmark_feasible=False` 表示：

```text
当前解 CVRP 可行，但使用车辆数超过参考 .sol 的车辆数。
```

这类结果不能直接和 BKS 计算 gap，因为多用车可能降低距离。

## 7. 按子集汇总

来源：

```text
results/analysis_full_seed0_final/summary_by_subset.csv
```

| 子集 | 可比实例数 | Mean Gap % | Median Gap % | Max Gap % | <=1% | <=3% | <=5% |
|---|---:|---:|---:|---:|---:|---:|---:|
| ALL | 10246 | 7.779 | 1.664 | 790.875 | 41.1% | 61.6% | 77.4% |
| A | 24 | 0.836 | 0.335 | 4.821 | 66.7% | 91.7% | 100.0% |
| B | 18 | 0.851 | 0.060 | 4.264 | 72.2% | 88.9% | 100.0% |
| CMT | 13 | -3.305 | -0.397 | 4.897 | 76.9% | 84.6% | 100.0% |
| E | 8 | 1.193 | 1.120 | 3.067 | 37.5% | 87.5% | 100.0% |
| F | 1 | 3.376 | 3.376 | 3.376 | 0.0% | 0.0% | 100.0% |
| M | 4 | 3.752 | 3.651 | 7.586 | 50.0% | 50.0% | 50.0% |
| P | 20 | 0.807 | 0.287 | 4.553 | 70.0% | 90.0% | 100.0% |
| X | 48 | 5.857 | 5.524 | 12.855 | 2.1% | 16.7% | 39.6% |
| tai | 9 | 3.030 | 2.162 | 8.899 | 11.1% | 66.7% | 88.9% |
| AGS | 1 | 790.875 | 790.875 | 790.875 | 0.0% | 0.0% | 0.0% |
| XL | 100 | no BKS | no BKS | no BKS | no BKS | no BKS | no BKS |
| XML | 10000 | no BKS | no BKS | no BKS | no BKS | no BKS | no BKS |

注意：`XL` 和 `XML` 在本地数据中基本没有 `.sol`，所以只能验证可运行性和可行性，不能计算 gap。

## 8. 子集解读

### A / B / P / E

这些子集是当前 baseline 表现最稳定的部分。

结论：

- 可比实例全部在 5% gap 内；
- median gap 大多低于 1.2%；
- 适合作为自动优化研究的快速回归测试集合。

### X

X 是当前最有研究价值的中大规模 benchmark。

本次可比结果：

```text
可比实例：48 / 100
mean gap = 5.857%
median gap = 5.524%
<=5% = 39.6%
```

解读：

- 当前算法能跑 X 级别实例；
- gap 中位数约 5.5%；
- 不能说“X 全部 5% 内”，但已经是可用 baseline；
- 还有明显优化空间，适合后续自动调参或算子搜索。

### XL / XML

本地数据中 XL / XML 基本没有 `.sol`。

因此：

- 可以确认算法能跑完并返回 CVRP 可行解；
- 可以记录 cost、routes、feasible；
- 不能计算 benchmark gap。

### AGS

AGS 实例非常大，完整实验中触发了 sweep construction 保护。

因此 AGS 的大 gap 主要反映：

```text
当前大实例 fallback 构造质量弱
```

不代表完整 ALNS+VNS 在 AGS 上经过充分搜索后的质量。

### CMT

CMT 出现负 gap。

原因不是一定“超过 benchmark”，而是 CMT 文件中包含：

- `DISTANCE`；
- `SERVICE_TIME`；
- 其他可能影响参考成本的约束。

当前算法没有建模这些扩展约束，因此 CMT 结果应作为诊断参考，而不是严格 CVRP gap 结论。

## 9. 最大 Gap 实例

来源：

```text
results/analysis_full_seed0_final/top_gaps.csv
```

前几个大 gap：

| 实例 | 子集 | Gap % | 说明 |
|---|---|---:|---|
| Leuven2 | AGS | 790.875 | sweep construction only |
| X-n513-k21 | X | 12.855 | ALNS+VNS |
| X-n411-k19 | X | 11.896 | ALNS+VNS |
| X-n143-k7 | X | 11.038 | ALNS+VNS |
| X-n237-k14 | X | 10.336 | ALNS+VNS |
| X-n308-k13 | X | 9.881 | ALNS+VNS |
| X-n284-k15 | X | 9.849 | ALNS+VNS |
| X-n895-k37 | X | 9.235 | ALNS+VNS |
| Tai150a | tai | 8.899 | ALNS+VNS |
| X-n331-k15 | X | 8.861 | ALNS+VNS |

这些实例可以作为后续自动优化的重点观察对象。

## 10. 车辆数差异

原始 CSV 中有：

```text
benchmark_feasible=False: 81
```

这些解满足 CVRP 容量和客户覆盖约束，但使用了超过参考 `.sol` 的车辆数。

例子：

```text
B-n51-k7: routes=8, bks_routes=7
P-n22-k8: routes=9, bks_routes=8
```

这类结果可能出现负 gap，所以最终 summary 默认排除它们。

后续自动优化可以选择：

- 把 `benchmark_feasible=False` 直接视为不可比；
- 或者把 `route_gap` 作为惩罚项；
- 或者把 fixed fleet 加进 solver 的硬约束。

## 11. 总体结论

当前算法达到本阶段目标：

- 完整跑通 10330 个 EUC_2D 实例；
- 所有实例返回 CVRP 可行解；
- 没有 timeout 或 crash；
- A/B/P/E 等小中规模 subset gap 表现较好；
- X subset 在当前 1 秒保护配置下 median gap 约 5.5%；
- XL/XML 因缺少 `.sol`，只能确认可运行性，不能计算 gap。

当前 baseline 的主要不足：

- fixed fleet 不是硬约束；
- X 集仍有较大优化空间；
- 大规模 AGS/XL 的 fallback 构造质量较弱；
- CMT 扩展约束未建模；
- EXPLICIT 距离类型未支持。

建议后续自动优化优先关注：

1. 减少 `benchmark_feasible=False` 的多车解；
2. 提升 X 子集 gap；
3. 加强初始解构造和 repair 对车辆数的控制；
4. 针对大实例设计更强但仍可控的 construction；
5. 视研究需要补充 CMT / DIMACS 的扩展约束支持。
