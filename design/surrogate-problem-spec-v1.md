# Scion Surrogate Problem Specification v1

*基于 BigBOSS 业务描述，2026-04-05*

---

## 1. 问题定义

### 1.1 业务场景

国际物流仓配协同：终端产品从国内央仓/工厂仓出发，经口岸出关运往海外。核心决策是将订单分配到运输车辆上，分两个阶段：

- **一次逻辑车（Phase 1）**：订单 → 车辆，目标是形成仓库理货单元
- **二次逻辑车（Phase 2）**：一次逻辑车 → 合并车辆，目标是运输整合降本

**统一建模**：Phase 2 是 Phase 1 的特殊实例——所有订单锁定在一次逻辑车内不可拆散，但整车可以合并。即 Phase 2 的"原子操作单元"是一次逻辑车（一组订单），而非单个订单。

### 1.2 输入

#### 订单（Order）

| 字段 | 类型 | 说明 |
|---|---|---|
| order_id | str | 订单唯一标识（loHeaderId） |
| vehicle_category | int | 分车大类序号 |
| vehicle_subcategory | int | 分车小类序号 |
| urgent | bool | 急单标识 |
| hazard_flag | bool | 是否危险品 |
| hazard_quantity | int | 危险品数量（pcs） |
| pickup_name | str | 提货点名称 |
| pickup_province | str | 提货点省份 |
| pickup_city | str | 提货点城市 |
| declaration_amount | float | 报关金额 |
| lsp | str | LSP承运商 |
| ship_method | str | 运输方式（海运/空运/铁路/陆运） |
| destination_country | str | 目的国 |
| spu_list | list[SPU] | SPU列表 |
| locked_vehicle_id | str \| None | 已锁定的逻辑车ID（None=新订单，可自由分配） |

#### SPU

| 字段 | 类型 | 说明 |
|---|---|---|
| packing_type | enum | 整板/尾板/木箱/整箱/散箱 |
| quantity | int | 数量 |

**栈板折算规则**：
- 整板、尾板、木箱：每个 = 1 栈板
- 整箱、散箱：每 8 个 = 1 栈板（向上取整）

```python
def calc_pallets(spu_list: list[SPU]) -> int:
    pallets = 0
    boxes = 0
    for spu in spu_list:
        if spu.packing_type in ("整板", "尾板", "木箱"):
            pallets += spu.quantity
        else:  # 整箱, 散箱
            boxes += spu.quantity
    pallets += math.ceil(boxes / 8)
    return pallets
```

#### 车型（VehicleType）

| 车型 | 代码 | 栈板容量 | 单车成本 | 备注 |
|---|---|---|---|---|
| 40HQ危险品专车 | HQ40_DG | 40 | 6600 | 仅危险品 |
| 40HQ普货车 | HQ40 | 40 | 3300 | |
| 10T | T10 | 14 | 1800 | |
| 5T | T5 | 6 | 1200 | |
| 3T | T3 | 3 | 800 | |

#### 线路（Region）

| 片区 | 仓库 | 最大提货点数 |
|---|---|---|
| 东莞 | 成品央仓、备件央仓、SKD仓、促销品仓等 | 2 |
| 深圳 | 2个工厂直发仓、1个成品央仓 | 3 |

线路由提货点的片区决定。同一辆车的所有订单的提货点必须属于同一片区。

#### 装车基线（Amount Limit）

按 (目的国, 运输方式) 维度配置，同车所有订单的报关金额之和不超过基线值。

```python
amount_limits: dict[tuple[str, str], float]  # (destination_country, ship_method) → max_amount
```

### 1.3 决策变量

每个订单（Phase 1）或每个一次逻辑车（Phase 2）分配到哪辆逻辑车，以及每辆逻辑车的车型选择。

### 1.4 输出

```python
@dataclass
class Solution:
    vehicles: dict[str, Vehicle]     # vehicle_id → Vehicle
    assignment: dict[str, str]       # order_id → vehicle_id
    objective: ObjectiveValue        # 目标函数值（由 oracle 计算）

@dataclass
class Vehicle:
    vehicle_id: str
    vehicle_type: str                # HQ40_DG | HQ40 | T10 | T5 | T3
    region: str                      # 东莞 | 深圳
    order_ids: list[str]             # 车上的订单ID列表

@dataclass
class ObjectiveValue:
    subcategory_splits: int          # 分车小类拆分数（越小越好）
    total_cost: int                  # 总运输成本（越小越好）
    solve_time_ms: int               # 求解时间（越小越好）
```

---

## 2. 约束体系

### 2.1 硬约束（违反 = 不可行）

| # | 约束 | 形式化 |
|---|---|---|
| H1 | 栈板容量 | sum(pallets(o) for o in vehicle.orders) ≤ vehicle_type.capacity |
| H2 | 片区一致 | 同车所有订单的 pickup 片区相同 |
| H3 | 提货点上限 | len(distinct_pickups(vehicle)) ≤ region_max_pickups |
| H4 | 分车大类隔离 | 同车订单的 vehicle_category 相同（Phase 1）|
| H5 | 危险品基线 | sum(hazard_quantity) > 1800 → vehicle_type == HQ40_DG |
| H6 | 装车基线 | sum(declaration_amount) ≤ amount_limit[(country, ship_method)] |
| H7 | 锁定不动 | locked_vehicle_id != None → 订单不可移动到其他车 |
| H8 | 非专车危险品上限 | 非危险品专车：sum(hazard_quantity) ≤ 1800pcs（危险品专车可混装普货，无限制）|

**注意**：H4 在 Phase 2 中由算法标识替代——不同大类但相同算法标识的一次逻辑车可以合并。

### 2.2 软约束

| # | 约束 | 量化 |
|---|---|---|
| S1 | 同小类聚合 | 拆分惩罚 = 该小类使用的车辆数 - 1 |

---

## 3. 目标函数

**字典序**（严格优先级）：

```
Level 1 > Level 2 > Level 3
```

| 优先级 | 指标 | 方向 | 定义 |
|---|---|---|---|
| Level 1 | 分车小类拆分总数 | min | sum(vehicles_used(subcat) - 1 for subcat in all_subcategories) |
| Level 2 | 运输总成本 | min | sum(vehicle_type.cost for v in vehicles) |
| Level 3 | 求解时间 | min | wall-clock ms（同等质量下更快更好）|

**字典序比较**：

```python
def is_better(a: ObjectiveValue, b: ObjectiveValue) -> bool:
    if a.subcategory_splits != b.subcategory_splits:
        return a.subcategory_splits < b.subcategory_splits
    if a.total_cost != b.total_cost:
        return a.total_cost < b.total_cost
    return a.solve_time_ms < b.solve_time_ms
```

**注**：Level 3（求解时间）在 Scion 框架内特殊——它不是解的属性而是算法的属性。在 Screening/Validation 评估中，时间作为辅助指标，不参与 A/B promotion 的统计检验。另一个隐性偏好是代码简洁度（同等性能下更简单的算子更优），这在 LLM 生成阶段由 prompt 引导，不进入目标函数。

---

## 4. 算法框架

### 4.1 整体流程

```
输入：订单列表 + 参数配置
    ↓
初始解生成（贪心）
    ↓
Solution Pool 初始化（pool_size = 40）
    ↓
VNS 迭代（终止：达到最大迭代次数，或连续多轮无任何指标改进）：
│   for each solution in pool:
│       算子 = 按概率选择一个算子
│       new_solution = 算子.execute(solution, rng)
│       检查可行性
│   新旧合并（40新 + 40旧）→ 排序 → 取 top-40 为新 pool
│   pool[0] 即为当前最优解
    ↓
输出最优解
```

### 4.2 初始解生成

**Phase 1**：
1. 按分车小类聚合订单
2. 贪心装箱：同小类订单依次装入当前车，满了就开新车
3. 车型选择：默认大车型（40HQ），后续优化阶段降级

**Phase 2**：
- 每个一次逻辑车 = 一个初始车辆（已确定）
- 输入即为基础解

### 4.3 Solution Pool

| 参数 | 值 | 说明 |
|---|---|---|
| pool_size | 40 | 超参数 |
| top_k | 1 | 每轮取最优解作为结果 |
| 淘汰策略 | 字典序排序 | 按目标函数比较 |
| 池更新 | 新旧合并取 top-40 | 每轮 40 新解 + 40 旧解 → 排序取 top-40 |

### 4.4 算子

**操作对象**：
- Phase 1：未锁定的单个订单，或已锁定订单的整体操作
- Phase 2：一次逻辑车（一组订单作为原子单元）

**分类**：

| 维度 | 粒度 | 操作类型 | 语义示例 |
|---|---|---|---|
| 订单级 | 单订单 | 交换 | 两辆车各取一个订单互换 |
| 订单级 | 单订单 | 移动 | 一个订单从A车移到B车 |
| 订单级 | 单订单 | 增减 | 从车移除订单（新建车）或插入订单到已有车 |
| 订单级 | 批量 | 打散 | 一辆车的订单全部释放，重新分配 |
| 订单级 | 批量 | 破坏重建 | 多辆车部分订单释放，贪心重装 |
| 车辆级 | — | 合并 | 两辆车订单合并到一辆 |
| 车辆级 | — | 换车型 | 改变车辆类型（降级节省成本） |
| 车辆级 | — | 减车 | 移除空车或将小车订单合并到其他车 |

**接口**：

```python
class Operator:
    def execute(self, solution: Solution, rng: Random) -> Solution
```

**概率选择**：
- 每个算子有一个权重（超参数）
- 按累积概率数组选择
- v0.1 权重冻结（不做动态自适应），但 Scion agent 可以建议初始权重

### 4.5 Phase 统一

| 特性 | Phase 1 | Phase 2 |
|---|---|---|
| 分配原子 | 订单 | 一次逻辑车（一组订单） |
| 大类隔离 | 严格（H4） | 按算法标识合并 |
| 可操作对象 | 未锁定订单 + 锁定订单整体 | 一次逻辑车整体 |
| 初始解 | 贪心生成 | 一次分车结果 |
| 车型选择 | 动态 | 动态（合并后可能升级车型） |

**框架复用**：同一个 VNS + Pool 引擎，通过 `phase` 参数切换约束和算子行为。

---

## 5. Feasibility Oracle Spec

**输入**：Solution
**输出**：(is_feasible: bool, violations: list[str])

检查顺序（fail-fast）：

```
1. H7: 锁定订单未被移动
2. H4: 分车大类隔离（Phase 1）/ 算法标识合并合规（Phase 2）
3. H2: 片区一致
4. H3: 提货点数 ≤ 上限
5. H1: 栈板容量
6. H5: 危险品基线 → 必须用专车
7. H8: 非专车危险品 ≤ 1800pcs
8. H6: 装车基线（金额）
```

### 5.1 伪代码

```python
def check_feasibility(solution: Solution, instance: Instance, phase: int) -> FeasibilityResult:
    violations = []
    
    for vid, vehicle in solution.vehicles.items():
        orders = [instance.orders[oid] for oid in vehicle.order_ids]
        
        # H7: 锁定检查
        for o in orders:
            if o.locked_vehicle_id is not None and o.locked_vehicle_id != vid:
                violations.append(f"H7: order {o.order_id} locked to {o.locked_vehicle_id}, assigned to {vid}")
                return FeasibilityResult(False, violations)  # fail-fast
        
        # H4: 大类隔离 (Phase 1)
        if phase == 1:
            categories = set(o.vehicle_category for o in orders)
            if len(categories) > 1:
                violations.append(f"H4: vehicle {vid} mixes categories {categories}")
                return FeasibilityResult(False, violations)
        
        # H2: 片区一致
        regions = set(get_region(o.pickup_city) for o in orders)
        if len(regions) > 1:
            violations.append(f"H2: vehicle {vid} mixes regions {regions}")
            return FeasibilityResult(False, violations)
        
        region = regions.pop()
        
        # H3: 提货点上限
        pickups = set(o.pickup_name for o in orders)
        max_pickups = 2 if region == "东莞" else 3
        if len(pickups) > max_pickups:
            violations.append(f"H3: vehicle {vid} has {len(pickups)} pickups > {max_pickups}")
            return FeasibilityResult(False, violations)
        
        # H1: 栈板容量
        total_pallets = sum(calc_pallets(o.spu_list) for o in orders)
        capacity = VEHICLE_TYPES[vehicle.vehicle_type].capacity
        if total_pallets > capacity:
            violations.append(f"H1: vehicle {vid} pallets {total_pallets} > capacity {capacity}")
            return FeasibilityResult(False, violations)
        
        # H5: 危险品基线 → 超 1800pcs 必须用专车
        total_hazard = sum(o.hazard_quantity for o in orders if o.hazard_flag)
        if total_hazard > 1800 and vehicle.vehicle_type != "HQ40_DG":
            violations.append(f"H5: vehicle {vid} hazard {total_hazard} > 1800 but type is {vehicle.vehicle_type}")
            return FeasibilityResult(False, violations)
        # 注意：危险品专车可以混装普货，无纯度约束
        
        # H6: 装车基线
        # 按 (destination_country, ship_method) 分组检查
        amount_groups = defaultdict(float)
        for o in orders:
            key = (o.destination_country, o.ship_method)
            amount_groups[key] += o.declaration_amount
        for key, total in amount_groups.items():
            if key in instance.amount_limits and total > instance.amount_limits[key]:
                violations.append(f"H6: vehicle {vid} amount {total} > limit for {key}")
                return FeasibilityResult(False, violations)
    
    return FeasibilityResult(True, [])
```

---

## 6. Objective Recompute Oracle Spec

**输入**：Solution + Instance
**输出**：ObjectiveValue

```python
def recompute_objective(solution: Solution, instance: Instance) -> ObjectiveValue:
    # Level 1: 分车小类拆分数
    subcat_vehicles = defaultdict(set)  # subcategory → set of vehicle_ids
    for oid, vid in solution.assignment.items():
        subcat = instance.orders[oid].vehicle_subcategory
        subcat_vehicles[subcat].add(vid)
    subcategory_splits = sum(len(vids) - 1 for vids in subcat_vehicles.values())
    
    # Level 2: 总成本
    total_cost = sum(
        VEHICLE_TYPES[v.vehicle_type].cost
        for v in solution.vehicles.values()
        if len(v.order_ids) > 0  # 空车不计费
    )
    
    # Level 3: 求解时间（外部测量，不在此计算）
    
    return ObjectiveValue(
        subcategory_splits=subcategory_splits,
        total_cost=total_cost,
        solve_time_ms=0  # placeholder, measured externally
    )
```

---

## 7. Surrogate 简化清单

以下是 surrogate 相对于生产系统的刻意简化：

| 项目 | 生产 | Surrogate | 理由 |
|---|---|---|---|
| 装车判定 | 栈板数经验 | 同（栈板数） | 保真 |
| 路线规划 | 不做 | 不做 | 保真 |
| 仓库数量 | 东莞5+深圳3 | 东莞3+深圳2 | 简化但保留双片区结构 |
| 订单规模 | 10~数百/天 | 合成数据20~200 | 覆盖典型范围 |
| 分车大类 | 业务定义 | 3~5类 | 保留隔离结构 |
| 分车小类 | LSP+目的国+运输方式等 | 10~20类 | 保留聚合目标 |
| 装车基线 | 按国家×运输方式 | 简化为3档 | 保留约束存在性 |
| 车型 | 5种 | 5种（原样） | 保真 |
| 危险品基线 | 1800pcs | 同 | 保真 |
| API 部署 | FastAPI + Docker | 本地 Python 调用 | 开发便利 |

---

## 8. 已确认问题（2026-04-05）

- [x] **Pool 更新策略**：新旧合并取 top-40
- [x] **VNS 终止条件**：最大迭代次数 + 连续多轮无任何指标改进则提前退出
- [x] **Phase 2 算法标识**：由 AlgorithmIdentifier 字段决定，同一标识的一次逻辑车可在 Phase 2 合并
- [x] **H6 装车基线**：按 (国家, 运输方式) 分组检查同车内该维度的金额之和
- [x] **危险品专车**：可混装普货，无纯度限制。约束仅在于非专车危险品 ≤ 1800pcs

---

*本文档定义 Scion surrogate 的问题结构，作为 Feasibility Oracle 和 Objective Recompute Oracle 的实现依据。*
*由人（BigBOSS）审核确认后冻结。*
