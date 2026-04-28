# CVRP ALNS + VNS 算法文档

## 1. 目标和范围

当前项目实现的是一个可运行、可实验、可后续自动优化的 CVRP 启发式算法基线。
它的目标不是在现阶段追求最强性能，而是：

- 能完整跑通本地 CVRPLIB 数据集中的 EUC_2D 实例；
- 在 A/B/P/E 等小中规模 benchmark 上取得可接受 gap；
- 为后续自动优化研究提供稳定、可复现的 baseline；
- 对大实例有超时和内存保护，避免完整实验卡死。

当前只支持：

```text
EDGE_WEIGHT_TYPE = EUC_2D
```

`EXPLICIT` 等其他距离类型会在参考解校验脚本中被标记为 unsupported，常规实例发现逻辑也会跳过它们。

## 2. 问题建模

当前实现的核心问题是 CVRP：

- 一个 depot；
- 多个客户节点；
- 每个客户有 demand；
- 车辆容量相同；
- 每个客户必须且只能被访问一次；
- 每条路线从 depot 出发并回到 depot；
- 每条路线总 demand 不超过 vehicle capacity；
- 目标是最小化总行驶距离。

当前没有显式建模以下扩展约束：

- `DISTANCE`；
- `SERVICE_TIME`；
- route duration；
- time windows；
- fixed fleet as hard constraint。

因此，像 CMT 一类含有额外字段的实例，其 `.sol` 成本不一定能被当前纯 CVRP 模型严格复现。

为了避免“多用车导致距离更低，从而出现假负 gap”，实验 CSV 中额外记录：

- `routes`：算法使用的路线数；
- `bks_routes`：参考 `.sol` 中路线数；
- `route_gap = routes - bks_routes`；
- `benchmark_feasible`：当前解 CVRP 可行，且 `routes <= bks_routes` 时为 true。

最终 gap 汇总默认排除 `benchmark_feasible=False` 的行。

## 3. 文件结构

核心算法模块：

- `src/models.py`：`Instance`、`Route`、`Solution` 数据结构；
- `src/parser.py`：`.vrp` / `.sol` 解析和实例发现；
- `src/distance.py`：EUC_2D 距离矩阵；
- `src/construction.py`：初始解构造；
- `src/local_search/operators.py`：VNS 邻域算子；
- `src/local_search/vns.py`：VNS 框架；
- `src/alns/destroy.py`：destroy 算子；
- `src/alns/repair.py`：repair 算子；
- `src/alns/weights.py`：自适应算子权重；
- `src/acceptance.py`：模拟退火接受准则；
- `src/solver.py`：ALNS + VNS 主循环。

实验和工具脚本：

- `main.py`：单实例和批量 CLI；
- `benchmark.py`：基础批量 benchmark；
- `validate_solutions.py`：参考 `.sol` 校验；
- `solve_instance.py`：单实例子进程求解，支持内存限制；
- `run_full_experiment.py`：可恢复的完整实验 runner；
- `analyze_results.py`：实验 CSV 汇总分析；
- `run_full_experiment_seed0.sh`：本次 seed=0 完整实验脚本。

## 4. 数据结构

### 4.1 Instance

`Instance` 表示一个 CVRP 实例，主要字段包括：

- `name`；
- `dimension`；
- `capacity`；
- `depot`；
- `coords`；
- `demands`；
- `dist_matrix`；
- `use_integer_cost`。

内部节点编号全部使用 0-based。CVRPLIB 文件中的 1-based ID 在解析时转换为 0-based。

距离计算逻辑：

- 若 `dist_matrix` 存在，直接查矩阵；
- 否则按坐标现算欧氏距离。

整数距离使用 CVRPLIB 常见的 nearest integer rounding：

```text
nint(d) = floor(d + 0.5)
```

浮点坐标实例保留浮点距离。

### 4.2 Route

`Route` 表示一辆车的路线：

```text
depot -> customers -> depot
```

其中 `customers` 不包含 depot。

缓存字段：

- `load`；
- `cost`。

支持增量操作：

- `cost_of_insert(customer, position)`；
- `cost_of_remove(position)`；
- `insert(customer, position)`；
- `remove(position)`。

### 4.3 Solution

`Solution` 表示完整解，包含：

- `routes`；
- `total_cost`；
- customer 到 route 的索引；
- customer 到 route position 的索引。

可行性检查包括：

- 容量不超限；
- 所有客户恰好出现一次；
- 无重复客户；
- 无遗漏客户。

## 5. 解析和参考解校验

`parse_vrp` 解析 `.vrp` 文件，仅支持 `EUC_2D`。

`parse_sol` 解析 `.sol` 文件，返回：

- reference routes；
- reference cost。

`validate_solutions.py` 用来检查本地数据质量，检查项包括：

- `.sol` 缺失；
- `.vrp` 不支持；
- `.sol` 解析失败；
- 客户缺失；
- 客户重复；
- 非法客户编号；
- 容量超限；
- `.sol` cost 和回算 cost 不一致。

这一步很重要，因为本地数据集中确实存在少量异常参考解。

## 6. 初始解构造

当前有三类构造方法。

### 6.1 Clarke-Wright Savings

小中规模实例默认使用 Clarke-Wright parallel savings。

初始状态：

```text
每个客户单独一条路线
```

savings 定义：

```text
s(i, j) = d(depot, i) + d(depot, j) - d(i, j)
```

按 savings 从大到小尝试合并路线。合并条件：

- `i` 和 `j` 必须是各自路线端点；
- 合并后容量不超限。

该方法复杂度约为 O(n^2)，所以对大实例有阈值保护。

### 6.2 Nearest Neighbor

备用构造方法：

- 从 depot 出发；
- 每次选择当前节点最近的可行未访问客户；
- 当前路线无法继续时闭合路线并开启新路线。

### 6.3 Sweep Construction

大实例保护用构造方法。

步骤：

- 计算客户相对 depot 的极角；
- 按极角排序；
- 按排序顺序扫描客户；
- 当前路线容量足够则加入；
- 容量不足则开启新路线。

这个方法质量较弱，但非常快，适合保证 XL/AGS/XML 等大规模实例完整跑通。

### 6.4 Capacity Balanced Construction

代码中还提供了容量装箱式构造：

- 按 demand 降序处理客户；
- 使用 best-fit 将客户放入最多 `max_routes` 个 route bucket；
- 每个 bucket 内用 nearest neighbor 排序。

这个方法用于尝试构造固定车辆数解，但最终完整实验没有强制使用 fixed fleet，而是记录并分析 `benchmark_feasible`。

## 7. VNS 局部搜索

VNS 框架：

```text
k = 0
while k < K:
    if neighborhood[k] improves solution:
        accept
        k = 0
    else:
        k += 1
```

当前邻域顺序：

1. `two_opt_intra`：单路线内部 2-opt；
2. `relocate`：跨路线移动一个客户；
3. `or_opt_1`：移动长度 1 的连续片段；
4. `or_opt_2`：移动长度 2 的连续片段；
5. `or_opt_3`：移动长度 3 的连续片段；
6. `swap`：两条路线交换客户；
7. `two_opt_star`：两条路线交换尾段。

实验中使用阈值：

```text
vns_threshold = 200
```

超过该规模则跳过 VNS，防止中大实例被局部搜索拖住。

## 8. ALNS Destroy 算子

实现位置：

```text
src/alns/destroy.py
```

当前 destroy 算子：

1. Random removal：
   - 随机移除 `q` 个客户。

2. Worst removal：
   - 计算每个客户移除后节省的距离；
   - 按节省排序；
   - 使用随机偏置选择。

3. Shaw removal：
   - 选择相关性高的一批客户；
   - 相关性由距离、需求差、是否同路线共同决定。

4. Route removal：
   - 移除整条路线；
   - 直到移除客户数达到目标。

## 9. ALNS Repair 算子

实现位置：

```text
src/alns/repair.py
```

当前 repair 算子：

1. Greedy insertion：
   - 每次选择插入代价最小的客户和位置。

2. Regret-2 insertion：
   - 优先插入“第二好位置和最好位置差距大”的客户。

3. Regret-3 insertion：
   - 类似 Regret-2，但考虑前三个候选插入位置。

如果当前路线都无法插入某客户，会新建路线。这保证 CVRP 可行性，但可能超过 benchmark 的参考车辆数。

## 10. 自适应权重

destroy 和 repair 分别维护权重，并通过 roulette wheel 选择算子。

每个 segment 更新：

```text
w_new = max(min_weight, (1 - r) * w_old + r * (score / usage))
```

参数：

```text
reaction_factor = 0.1
min_weight = 0.1
segment_length = 100
```

得分：

```text
新全局最优: 33
优于当前解: 9
接受劣解: 13
拒绝或无效: 0
```

## 11. 模拟退火接受准则

接受规则：

```text
if candidate_cost <= current_cost:
    accept
else:
    accept with probability exp(-(candidate_cost - current_cost) / T)
```

温度：

```text
T_start = initial_cost * 0.05
T_end   = initial_cost * 0.0001
```

冷却：

```text
T = max(T_end, T * cooling_rate)
```

## 12. 主求解流程

`src/solver.py` 中的主流程：

```text
1. 构造初始解
2. 若规模允许，VNS 打磨初始解
3. 初始化 ALNS 权重和模拟退火
4. 在 time_limit 内循环:
   a. 拷贝当前解
   b. 选择 destroy / repair 算子
   c. 移除 q 个客户
   d. repair 重新插入
   e. 若规模允许，执行 VNS
   f. 检查可行性
   g. 使用 SA 判断是否接受
   h. 更新全局最优和算子得分
   i. 降温
5. 返回最优解
```

大实例保护逻辑：

- `num_customers > cw_threshold`：使用 sweep construction；
- `num_customers > alns_threshold`：跳过 ALNS，只返回构造解；
- `time_limit <= 0`：只构造，不搜索；
- `num_customers > vns_threshold`：跳过 VNS。

这些保护是为了完整实验能跑完，而不是为了追求大实例最优质量。

## 13. 完整实验使用的参数

最终完整实验参数：

```text
seed = 0
workers = 2
per-instance timeout = 20s
memory limit per child = 4096MB
OPENBLAS/OMP/MKL/NUMEXPR threads = 1

time_limit = 0s for no-.sol instances
bks_time_limit = 1s for instances with .sol
large_time_limit = 0s
large_dimension = 2001

cw_threshold = 1000
vns_threshold = 200
alns_threshold = 1000
max_destroy_customers = 80
vns_iterations = 50
```

解释：

- 有 `.sol` 的实例给 1 秒搜索预算；
- 没有 `.sol` 的实例主要验证可运行性和可行性；
- 大实例主要走 construction-only；
- 每个实例独立子进程运行，防止单个实例卡死或占用过多内存。

## 14. 当前限制

当前算法适合作为研究 baseline，但有明确限制：

- 不支持非 EUC_2D / EXPLICIT；
- 不建模 CMT 中的 `DISTANCE` 和 `SERVICE_TIME`；
- 最终完整实验不强制 fixed fleet，只记录 `benchmark_feasible`；
- X 集仍有明显优化空间；
- AGS/XL 大实例的 sweep construction 质量较弱；
- XML/XL 缺 `.sol`，不能直接计算 gap。

这些限制也是后续自动优化研究的主要切入点。
