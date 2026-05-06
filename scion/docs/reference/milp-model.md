# 仓配协同优化 MILP 数学模型

## 1. 集合与参数

### 1.1 集合

| 符号 | 含义 |
|------|------|
| $I$ | 订单集合，$\|I\| = n$ |
| $J$ | 车辆槽位集合，$J = \{1, 2, \dots, K\}$，$K$ 为车辆数上界（取 $K = n$） |
| $T$ | 车型集合，$T = \{\text{HQ40\_DG}, \text{HQ40}, \text{T10}, \text{T5}, \text{T3}\}$ |
| $S$ | 小类（vehicle\_subcategory）集合 |
| $C$ | 大类（vehicle\_category）集合 |
| $R$ | 片区集合，$R = \{\text{DG}, \text{SZ}\}$（Dongguan, Shenzhen） |
| $P$ | pickup\_name 集合 |
| $G$ | (destination\_country, ship\_method) 分组集合 |

### 1.2 订单参数

| 符号 | 含义 |
|------|------|
| $p_i$ | 订单 $i$ 的栈板数（calc\_pallets()） |
| $s_i \in S$ | 订单 $i$ 的小类 |
| $c_i \in C$ | 订单 $i$ 的大类 |
| $h_i$ | 订单 $i$ 的危险品数量（pcs），非危险品为 0 |
| $r_i \in R$ | 订单 $i$ 的片区 |
| $\pi_i \in P$ | 订单 $i$ 的 pickup\_name |
| $d_{ig}$ | 订单 $i$ 在分组 $g \in G$ 下的 declaration\_amount（不属于该分组则为 0） |
| $\ell_i \in J \cup \{\emptyset\}$ | 订单 $i$ 的锁定车辆，$\emptyset$ 表示可自由分配 |

### 1.3 车型参数

| 符号 | 含义 |
|------|------|
| $\text{cap}_t$ | 车型 $t$ 的栈板容量 |
| $\text{cost}_t$ | 车型 $t$ 的成本 |
| $\text{DG}_t$ | 车型 $t$ 是否为危险品专用车（$=1$ 当且仅当 $t = \text{HQ40\_DG}$） |

### 1.4 其他参数

| 符号 | 含义 |
|------|------|
| $L_r$ | 片区 $r$ 的 pickup\_name 数量上限：$L_{\text{DG}} = 2$，$L_{\text{SZ}} = 3$ |
| $H_{\max}$ | 非危险品专用车的危险品上限，$H_{\max} = 1800$ |
| $D_g$ | 分组 $g$ 对应的 declaration\_amount 上限 |
| $M$ | 足够大的常数（big-M），一般取 $M = n$ |

---

## 2. 决策变量

### 2.1 核心变量

| 变量 | 类型 | 含义 |
|------|------|------|
| $x_{ij} \in \{0, 1\}$ | Binary | 订单 $i$ 分配到车辆 $j$ |
| $y_j \in \{0, 1\}$ | Binary | 车辆 $j$ 被使用（至少装了一个订单） |
| $z_{jt} \in \{0, 1\}$ | Binary | 车辆 $j$ 被指定为车型 $t$ |

### 2.2 辅助变量

| 变量 | 类型 | 含义 |
|------|------|------|
| $w_{jr} \in \{0, 1\}$ | Binary | 车辆 $j$ 服务片区 $r$（H2 辅助） |
| $u_{jp} \in \{0, 1\}$ | Binary | 车辆 $j$ 包含 pickup\_name $p$ 的订单（H3 辅助） |
| $v_{jc} \in \{0, 1\}$ | Binary | 车辆 $j$ 包含大类 $c$ 的订单（H4 辅助） |
| $\alpha_{sj} \in \{0, 1\}$ | Binary | 小类 $s$ 的订单出现在车辆 $j$ 中（目标函数辅助） |
| $\phi_s \in \mathbb{Z}_{\geq 0}$ | Integer | 小类 $s$ 使用的车辆数（目标函数辅助） |

---

## 3. 目标函数

### 3.1 字典序处理方法

采用 **两阶段 epsilon-constraint** 方法：

- **阶段 1**：最小化主目标（subcategory\_splits），得到最优值 $f_1^*$
- **阶段 2**：固定 $f_1 = f_1^*$（作为等式约束），最小化次目标（total\_cost）

**选择理由**：两个目标量纲完全不同（分裂次数 vs. 成本金额），加权法需要人工调参且无法保证字典序严格性；epsilon-constraint 天然保证字典序优先级，且对小规模实例只需求解两次 MIP，开销可接受。

### 3.2 主目标：subcategory\_splits

$$
f_1 = \sum_{s \in S} (\phi_s - 1)^+ = \sum_{s \in S} \max(\phi_s - 1, 0)
$$

由于 $\phi_s \geq 1$ 对所有有订单的小类成立，可简化为：

$$
\min \quad f_1 = \sum_{s \in S} \phi_s - |S_{\text{active}}|
$$

其中 $|S_{\text{active}}|$ 是有订单的小类数（常数）。等价于：

$$
\boxed{\min \quad \sum_{s \in S} \phi_s}
$$

其中：
$$
\phi_s = \sum_{j \in J} \alpha_{sj}, \quad \forall s \in S
$$

### 3.3 次目标：total\_cost

$$
\boxed{\min \quad f_2 = \sum_{j \in J} \sum_{t \in T} \text{cost}_t \cdot z_{jt}}
$$

### 3.4 两阶段实现

**Phase 1 MIP**：
$$
\min \sum_{s \in S} \phi_s \quad \text{s.t. 所有约束}
$$

**Phase 2 MIP**：
$$
\min \sum_{j \in J} \sum_{t \in T} \text{cost}_t \cdot z_{jt} \quad \text{s.t. 所有约束} + \left[\sum_{s \in S} \phi_s = f_1^*\right]
$$

---

## 4. 约束条件

### 4.0 结构约束

**(C0a) 分配完整性** — 每个订单恰好分配到一辆车：
$$
\sum_{j \in J} x_{ij} = 1, \quad \forall i \in I
$$

**(C0b) 车辆使用逻辑** — 有订单才算使用：
$$
x_{ij} \leq y_j, \quad \forall i \in I, \; j \in J
$$

$$
y_j \leq \sum_{i \in I} x_{ij}, \quad \forall j \in J
$$

> 第一组保证未使用的车不接订单；第二组保证 $y_j = 0$ 当车辆为空。

**(C0c) 车型唯一** — 使用的车辆恰好选一个车型：
$$
\sum_{t \in T} z_{jt} = y_j, \quad \forall j \in J
$$

**(C0d) 小类-车辆关联**：
$$
\alpha_{sj} \geq x_{ij}, \quad \forall i \in I, \; j \in J, \; s_i = s
$$

$$
\alpha_{sj} \leq \sum_{i \in I: s_i = s} x_{ij}, \quad \forall s \in S, \; j \in J
$$

### 4.1 (H1) 容量约束

$$
\sum_{i \in I} p_i \cdot x_{ij} \leq \sum_{t \in T} \text{cap}_t \cdot z_{jt}, \quad \forall j \in J
$$

### 4.2 (H2) 片区一致性

每辆车最多服务一个片区：

$$
w_{jr} \geq x_{ij}, \quad \forall i \in I, \; j \in J, \; r_i = r
$$

$$
\sum_{r \in R} w_{jr} \leq 1, \quad \forall j \in J
$$

> 若 $x_{ij} = 1$ 则 $w_{j, r_i} = 1$；而同一车辆只能激活一个片区。

### 4.3 (H3) pickup\_name 数量上限

$$
u_{jp} \geq x_{ij}, \quad \forall i \in I, \; j \in J, \; \pi_i = p
$$

$$
u_{jp} \leq \sum_{i \in I: \pi_i = p} x_{ij}, \quad \forall p \in P, \; j \in J
$$

$$
\sum_{p \in P_r} u_{jp} \leq L_r + M \cdot (1 - w_{jr}), \quad \forall j \in J, \; r \in R
$$

其中 $P_r$ 是片区 $r$ 下的 pickup\_name 集合。当 $w_{jr} = 1$ 时（车 $j$ 服务片区 $r$），该片区下的不同 pickup\_name 数量不超过 $L_r$。

**更紧凑的写法**（无需 big-M，因为若 $w_{jr}=0$ 则该片区无订单，$u_{jp}=0$）：

$$
\sum_{p \in P_r} u_{jp} \leq L_r, \quad \forall j \in J, \; r \in R
$$

> 这已经足够，因为 H2 保证车辆只服务一个片区，另一个片区的 $u_{jp}$ 全为 0。

### 4.4 (H4) 大类一致性

$$
v_{jc} \geq x_{ij}, \quad \forall i \in I, \; j \in J, \; c_i = c
$$

$$
\sum_{c \in C} v_{jc} \leq 1, \quad \forall j \in J
$$

> 结构与 H2 完全对称：同一车辆只能包含一个大类的订单。

### 4.5 (H5 + H8) 危险品约束

定义车辆 $j$ 的危险品总量：
$$
H_j = \sum_{i \in I} h_i \cdot x_{ij}
$$

**(H8) 非 HQ40\_DG 的危险品上限**：
$$
H_j \leq H_{\max} + (M_H - H_{\max}) \cdot z_{j, \text{HQ40\_DG}}, \quad \forall j \in J
$$

其中 $M_H = \sum_{i \in I} h_i$（危险品总量上界）。

- 当 $z_{j,\text{HQ40\_DG}} = 0$ 时：$H_j \leq 1800$
- 当 $z_{j,\text{HQ40\_DG}} = 1$ 时：$H_j \leq M_H$（无实质限制）

> H5 是 H8 的逆否命题：$H_j > 1800 \Rightarrow z_{j,\text{HQ40\_DG}} = 1$，已被 H8 蕴含。

### 4.6 (H6) 申报金额上限

$$
\sum_{i \in I} d_{ig} \cdot x_{ij} \leq D_g, \quad \forall j \in J, \; g \in G
$$

> 每辆车内，每个 (destination\_country, ship\_method) 分组的 declaration\_amount 之和不超过上限 $D_g$。

### 4.7 (H7) 锁定分配

$$
x_{i, \ell_i} = 1, \quad \forall i \in I: \ell_i \neq \emptyset
$$

> 直接固定变量。对于有锁定的订单，其分配变量在对应车辆上固定为 1。

### 4.8 对称性破坏（可选，加速求解）

为减少对称解空间，添加以下对称性破坏约束：

$$
y_j \geq y_{j+1}, \quad \forall j \in \{1, \dots, K-1\}
$$

> 强制车辆按序号从小到大使用。注意：若存在 locked\_vehicle\_id，需确保锁定车辆不违反此序（实现时可仅对非锁定槽位施加）。

---

## 5. 完整模型汇总

$$
\boxed{
\begin{aligned}
\textbf{Phase 1:} \quad & \min \sum_{s \in S} \sum_{j \in J} \alpha_{sj} \\
\textbf{Phase 2:} \quad & \min \sum_{j \in J} \sum_{t \in T} \text{cost}_t \cdot z_{jt} \\
& \text{s.t.} \quad \sum_{s \in S} \sum_{j \in J} \alpha_{sj} = f_1^* \\[12pt]
\text{s.t.} \quad & \text{(C0a)} \;\; \sum_{j} x_{ij} = 1 & \forall i \\
& \text{(C0b)} \;\; x_{ij} \leq y_j & \forall i, j \\
& \text{(C0b')} \;\; y_j \leq \sum_i x_{ij} & \forall j \\
& \text{(C0c)} \;\; \sum_t z_{jt} = y_j & \forall j \\
& \text{(C0d)} \;\; \alpha_{sj} \geq x_{ij} & \forall i,j: s_i = s \\
& \text{(C0d')} \;\; \alpha_{sj} \leq \sum_{i: s_i=s} x_{ij} & \forall s, j \\
& \text{(H1)} \;\; \sum_i p_i x_{ij} \leq \sum_t \text{cap}_t \, z_{jt} & \forall j \\
& \text{(H2a)} \;\; w_{jr} \geq x_{ij} & \forall i,j: r_i = r \\
& \text{(H2b)} \;\; \sum_r w_{jr} \leq 1 & \forall j \\
& \text{(H3a)} \;\; u_{jp} \geq x_{ij} & \forall i,j: \pi_i = p \\
& \text{(H3b)} \;\; \sum_{p \in P_r} u_{jp} \leq L_r & \forall j, r \\
& \text{(H4a)} \;\; v_{jc} \geq x_{ij} & \forall i,j: c_i = c \\
& \text{(H4b)} \;\; \sum_c v_{jc} \leq 1 & \forall j \\
& \text{(H5/H8)} \;\; \sum_i h_i x_{ij} \leq 1800 + (M_H - 1800) z_{j,\text{DG}} & \forall j \\
& \text{(H6)} \;\; \sum_i d_{ig} x_{ij} \leq D_g & \forall j, g \\
& \text{(H7)} \;\; x_{i,\ell_i} = 1 & \forall i: \ell_i \neq \emptyset \\[6pt]
& x_{ij}, y_j, z_{jt}, w_{jr}, u_{jp}, v_{jc}, \alpha_{sj} \in \{0,1\} \\
& \phi_s \in \mathbb{Z}_{\geq 0}
\end{aligned}
}
$$

---

## 6. 复杂度分析

### 6.1 变量规模

| 变量 | 数量 | 说明 |
|------|------|------|
| $x_{ij}$ | $n \cdot K$ | 分配变量 |
| $y_j$ | $K$ | 车辆使用 |
| $z_{jt}$ | $K \cdot \|T\|$ | 车型选择 |
| $w_{jr}$ | $K \cdot \|R\| = 2K$ | 片区 |
| $u_{jp}$ | $K \cdot \|P\|$ | pickup\_name |
| $v_{jc}$ | $K \cdot \|C\|$ | 大类 |
| $\alpha_{sj}$ | $K \cdot \|S\|$ | 小类-车辆关联 |
| **总计** | $O(nK + K \cdot (\|T\| + \|P\| + \|C\| + \|S\|))$ | |

取 $K = n$，$\|T\|=5$，设 $\|P\|, \|C\|, \|S\| = O(n)$：

$$
\text{变量总数} = O(n^2)
$$

### 6.2 约束规模

| 约束 | 数量 |
|------|------|
| C0a | $n$ |
| C0b | $nK$ |
| C0b' | $K$ |
| C0c | $K$ |
| C0d, C0d' | $O(nK)$ |
| H1 | $K$ |
| H2a | $nK$ |
| H2b | $K$ |
| H3a | $nK$ |
| H3b | $K \cdot \|R\|$ |
| H4a | $nK$ |
| H4b | $K$ |
| H5/H8 | $K$ |
| H6 | $K \cdot \|G\|$ |
| **总计** | $O(nK) = O(n^2)$ |

### 6.3 求解时间预估

| 规模 $n$ | 变量数 | 约束数 | Gurobi 预计 | CBC 预计 |
|-----------|--------|--------|-------------|----------|
| 20 | ~400 binary | ~800 | **< 1s** | **1~5s** |
| 30 | ~900 binary | ~1800 | **1~10s** | **10~60s** |
| 40 | ~1600 binary | ~3200 | **5~60s** | **1~10min** |

> **注**：
> - 实际求解时间高度依赖约束紧度和对称性。加入对称性破坏约束后可显著加速。
> - H2/H4 的一致性约束天然剪枝大量不可行解，有利于 branch-and-bound。
> - Phase 1 的整数变量 $\phi_s$ 取值范围小（$[1, K]$），通常很快收敛。
> - 对于 $n \leq 40$ 的实例，Gurobi 在分钟级内可证明最优；CBC 可能需要更长但基本可行。
> - 可通过预处理减少 $K$（例如 $K = \lceil \sum_i p_i / \min_t \text{cap}_t \rceil + \text{locked\_count}$ 更紧的上界）。

---

## 7. 用途说明

### 7.1 Benchmark 角色

本 MILP 模型作为 **exact solver**，提供问题实例的全局最优解（或已证明的下界），用于：

1. **验证 Scion 的解质量**：计算 optimality gap

$$
\text{gap} = \frac{f_{\text{heuristic}} - f_{\text{optimal}}}{f_{\text{optimal}}}
$$

对于字典序目标，分别计算两个维度的 gap：

$$
\text{gap}_1 = \frac{f_{1,\text{heuristic}} - f_1^*}{f_1^*}, \quad
\text{gap}_2 = \frac{f_{2,\text{heuristic}} - f_2^*}{f_2^*} \quad (\text{在 } f_1 = f_1^* \text{ 条件下})
$$

2. **跟踪改进轨迹**：在 Scion 的迭代改进过程中，观察 gap 随迭代轮次的收敛曲线。

3. **识别瓶颈约束**：通过 MILP 的对偶信息（shadow price），识别哪些约束是制约成本优化的主要因素。

### 7.2 局限性

- 仅适用于 $n \leq 40$ 的小规模实例（作为 ground truth）
- 大规模实例（$n > 100$）需依赖 Scion 等启发式方法
- MILP 的最优解可用于训练 surrogate model 或校准 LLM 的改进策略

### 7.3 实现建议

- 使用 **gurobipy** 或 **PuLP + CBC** 实现
- Phase 1 求解后，通过 `model.addConstr(f1 == f1_star)` 固定主目标再求解 Phase 2
- 设置 `MIPGap=0`（要求精确最优）和合理的 `TimeLimit`
- 利用 warm start：将 Scion 的当前最优解作为 MIP start，加速求解
