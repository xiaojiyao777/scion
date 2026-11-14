# Scion v0.4 诊断审查报告 — 为什么研究"能跑通但无效"

*日期: 2026-06-09*
*范围: A1(根因诊断) 为主线 + A3(架构/代码审查) 为辅*
*证据基础: 两组真实 12R 实验对照 (warehouse 晋升 / cvrp 零晋升) + v3 蓝图 + 核心代码*
*审查者: 代码审查（基于本地实验产物与源码）*

---

## 0. 一句话结论

**Scion 的框架治理骨架（v3 边界、状态机、闸门、可追溯）是健康的、可工作的——warehouse 实验完整走通 screening→validation→frozen 并成功晋升即为证明。CVRP 研究"无效"不是框架 bug，而是 research object 与评估协议的根本性错配：CVRP baseline 求解器在评估实例上已接近/达到全局最优，叠加 VNS 主导的确定性搜索使候选改动与最终解完全解耦，导致 A/B 比较在数学上注定 100% tie。**

换句话说：**问题不在"agent 不会做研究"，而在"给 agent 的研究对象没有可被现有评估协议测量的改进空间"。**

---

## 1. 对照实验事实（硬证据）

| 维度 | warehouse (成功) | cvrp (失败) |
|---|---|---|
| champion 版本 | v1 → **v2 (晋升1次)** | v1 (从未晋升) |
| 协议阶段流转 | screening:10 → validation:1 → **frozen:1** | screening:15 → **validation:0** |
| gate 结果分布 | pass / fail / expand 都有（**有区分度**） | 几乎全 fail (SCREENING_FAIL_WIN_RATE) + 3 unclear |
| 候选 vs champion 运行时比 | 0.60 ~ 3.42（**差异显著**） | 0.997 ~ 1.004（几乎相同，双方撞满时间预算） |
| telemetry effect=0 | 无 | 有（route_compaction 22/44 case 全 0） |
| runtime budget saturation | 0 | 大量（saturation_ratio > 1.0） |

### 1.1 决定性证据：CVRP 每个 (case, seed) 候选与 champion 的 total_distance 完全相同

| case | BKS | champ=cand 距离 | champ gap% | comparison |
|---|---|---|---|---|
| A-n32-k5 | 784 | 784 / 784 | 0.00% | tie |
| B-n52-k7 | 747 | 747 / 747 | 0.00% | tie |
| E-n22-k4 | 375 | 375 / 375 | 0.00% | tie |
| E-n33-k4 | 835 | 835 / 835 | 0.00% | tie |
| P-n40-k5 | 458 | 458 / 458 | 0.00% | tie |
| A-n80-k10 | 1763 | 1809 / 1809 | 2.61% | tie |
| **E-n101-k8** | 815 | **863 / 863** | **5.89%** | tie |
| **P-n101-k4** | 681 | **721 / 721** | **5.87%** | tie |

**关键观察**：即使在 baseline 离 BKS 还有 5~6% 差距的难实例上（E-n101, P-n101），候选与 champion 的解依然**逐位完全相同**。这不是"改进太小被噪声淹没"，而是**候选算子对最终解零影响**。

---

## 2. 根因分析

### 根因 A（评估天花板）：小实例 baseline 已达全局最优

CVRP formal split 的 screening 实例（A-n32, E-n22, E-n33, P-n16, P-n40, B-n52 等）规模小（16~52 节点），baseline ALNS+VNS 在 8 秒预算（10s × BASELINE_TIME_FRACTION=0.8）内**稳定求到已知最优 BKS**。

- champion 已是最优 → 任何候选最多打平，**数学上不可能 win**
- 字典序第一维 `fleet_violation` 在标准实例上几乎总是 0（都 feasible）→ 竞争退化到 `total_distance` 单维
- → win_rate 恒为 0 → 必然 `SCREENING_FAIL_WIN_RATE`

### 根因 B（搜索解耦）：VNS 主导 + RNG 同步，候选改动不改变收敛点

来自 A-n32-k5 单次 run 的 phase 分解：
```
solver_algorithm_phase_runtime_ms:
  vns_embedded:                 6805 ms   ← 占总时间 ~85%
  slack_aware_route_compaction:  173 ms   ← 新算子，仅 2%，且无成功改进
  construction:                   20 ms
  vns_initial:                    17 ms
solver_algorithm_phase_improvement_counts: {alns: 2, vns: 614}  ← 改进几乎全来自 VNS
```

- 内嵌 VNS（确定性局部搜索：2-opt/relocate/or-opt/swap）占据 ~85% 运行时间，并贡献几乎全部改进
- VNS 是确定性下降过程，在相同 seed 下收敛到相同局部最优
- 新算子（route_compaction）插在 destroy→repair 之后，但：
  1. 其触发条件极严（要求整条路线能被其他路线完全吸收且总距离下降），在接近最优车辆数的 CW 构造解上**几乎从不成功** → effect=0
  2. 即便偶尔改动中间状态，后续 VNS 仍把解拉回同一局部最优 → **最终解与候选改动解耦**

### 根因 C（评估协议噪声功效不足）：仅 2 个 seed

`seed_ledger.yaml`: screening 仅 `[11, 29]` 两个 seed。对一个解质量受 RNG 影响的元启发式，2 个 seed 的配对比较统计功效极低。即便候选有微弱真实改进，也难以稳定跨 seed 体现为 win_rate ≥ 0.60。（注：本次实验因根因 A/B 占主导，此项为次要放大因素。）

### 根因 D（context 退化为日志堆，验证蓝图风险 #4）

单次 hypothesis prompt 的字符预算分解（实测，CVRP 实验 prompt manifest）：
```
provider_visible_total_chars:          116,375  (LLM 实际看到)
  solver_design_full_algorithm_file_reads: 30,568  (26%)  算法源码全文
  active_solver_map_receipts:              23,226  (20%)  治理元数据
  agentic_proposal_tool_observations:      22,682  (19%)  工具观察
  ... 各类 boundary/preflight/do-not-claim 合规信息 ...
真正的研究反馈信号：
  experiment_history_this_branch:              81 字符  ← 本分支历史
  champion_state:                             114 字符
  sibling_branches:                            50 字符
  globally_failed_blacklisted_approaches:      52 字符
```

**~65% 的上下文是源码全文 + 治理/合规元数据，而"上一轮为什么失败、该换什么方向"的有效研究信号不足 300 字符。** agent 被淹没在合规信息里，得不到方向性反馈 → 反复提出"会 tie 的局部算子"，无法收敛到"能改变收敛点的结构性改动"（如改 acceptance 准则、改 VNS 邻域顺序、改扰动强度）。

---

## 3. 架构 / 代码审查（A3）

### 3.1 v3 边界保持良好（正面）

- 通用层（core/proposal/contract/protocol/runtime）领域词汇泄漏已大幅收敛：core 仅 13 处、proposal 仅 4 处（多为注释/示例），相比历史审查 P1-1 已基本修复。provider-hook 重构有效。
- warehouse 晋升证明：Contract→Verification→Protocol→Decision 全链路 + 状态机 + lineage 可正常驱动晋升。
- 数据权限边界（DecisionFeatures 无自由文本、LLM 输出 tainted）在 metrics 中可见落实（`decision_features_excluded: true`）。

### 3.2 模块膨胀（技术债，非当前瓶颈）

- `proposal/` 196 文件 / 69,974 行，**过度碎片化**。最大文件已从 1800 行降到 1496 行（拆分有效），但仍有 15 个文件 > 880 行。
- `core/` 108 文件 / 44,260 行。
- 风险：上下文组装逻辑分散在大量文件，"LLM 到底看到什么"难以追踪审计——这正是根因 D 难以被发现的结构性原因。

### 3.3 memory 层名存实亡（与根因 D 强相关）

- `scion/memory/` 仅 10 行：`__init__.py` + `hypothesis_store.py`（后者是对 `lineage.branch_store` 的兼容 re-export 空壳）。
- 蓝图 §15 设计的"Context Manager + 记忆压缩 + 可过期 blacklist + 研究信号提炼"**没有作为一等模块存在**，能力被分散进 proposal 各处。
- 后果：没有专门组件负责"把噪声日志压缩成方向性研究信号"，直接导致根因 D。

### 3.4 配置一致性风险

- 问题包内 `problems/cvrp/protocol.yaml`(smoke, n_cases=2) 与 `problems/cvrp/formal/protocol.yaml`(n_cases=8/12) 并存，实际由 launch 命令行选择。容易误用 smoke 配置跑"正式"实验。建议明确命名/校验。

---

## 4. 分优先级修复建议

### P0 — 立即可做，直接解除瓶颈（评估侧）

1. **更换/扩充 CVRP research split 为"baseline 远未收敛"的难实例**
   - 移除 baseline 已稳定求到 BKS 的小实例（A-n32, E-n22, E-n33, P-n16, P-n40, B-n31/52）
   - screening 用 X 系列大实例（X-n200+）或显著缩短 time-limit，使 baseline gap 稳定 > 3~5%，**留出可测量的改进空间**
   - 这是单点见效最快的改动：让"win 在数学上成为可能"

2. **增加 screening seed 数**：`[11, 29]` → 至少 4~5 个 seed，提升配对比较统计功效，降低 tie 的偶然性

3. **校验"评估天花板"为预检项**：campaign 启动前跑一次 baseline-vs-baseline，若候选与 champion 在所有 case 上 delta 恒为 0 / 全 tie，发出 `RESEARCH_OBJECT_SATURATED` 预警，避免烧 LLM 预算在无空间的对象上

### P1 — 解除"搜索解耦"与"context 淹没"（核心有效性）

4. **暴露搜索结构给 agent，而非只给局部算子**
   - 当前 surface 让 agent 反复加"会被 VNS 抹平"的局部算子。应让 agent 能改动**主导收敛的环节**：acceptance 准则（SA 温度/阈值）、VNS 邻域顺序与 max_no_improve、扰动强度 destroy_ratio、ALNS 权重自适应
   - 在 hypothesis context 中明确告知 agent："VNS 占 85% 运行时间并主导收敛，纯加局部算子通常无效"

5. **重建 memory/context 提炼层（对应蓝图 §15）**
   - 把 116K 字符上下文中的源码全文/合规元数据压缩，**腾出预算给方向性研究信号**：上一轮 per-case delta 分布、tie 的结构性原因、已失败方向的归纳
   - 目标：让 `experiment_history_this_branch` 这类信号从 81 字符提升到能真正指导决策的体量
   - 建议把它实现为 `scion/memory/` 下的一等模块，而非散落在 proposal

6. **effect=0 应升级为 agent 的强反馈信号**
   - 当前 telemetry_effect_zero 只是 diagnostic。应在下一轮 hypothesis context 中明确告诉 agent："你上次加的算子触发了但 0 改进，原因可能是 X；不要再提同类局部算子"

### P2 — 架构健康度（技术债）

7. 继续拆分 proposal/core 中 > 800 行的控制模块，特别是上下文组装路径，使"LLM 看到什么"可被单点审计
8. 统一 smoke/formal 协议配置的命名与启动校验，防止误用

---

## 5. 给"通用化"方向的提示（B，简述）

本次未深入 B，但诊断结论对通用化有直接启示：**Scion 通用化的关键不是支持更多问题，而是建立"research object 可研究性"的准入校验**——即 v0.5 onboarding memo 已识别的方向。本次 CVRP 失败恰好证明：一个 adapter/surface/protocol 都正确接入的问题，仍可能因"baseline 太强 / 改进空间不可测 / 搜索结构未暴露"而无法产出研究信号。**通用化框架应在 onboarding 阶段强制校验"该问题在该评估协议下是否存在可被测量的改进空间"。**

---

## 附录：证据文件索引

- CVRP 实验: `v04-post40r-repair-verify-cvrp-12r-gpt55-20260609T042719Z-claw-12r-...`
- warehouse 实验: `v04-post40r-repair-verify-warehouse-12r-gpt55-20260609T042719Z-claw`
- 关键 metrics: `campaign/metrics/1f6071d2-*.json`（A-n32-k5 per-case pairs，含 784=784 tie）
- effect=0 算子: `campaign/archive/ae995084/policies/baseline_modules/route_compaction.py`
- 搜索调度: `problems/cvrp/policies/baseline_modules/scheduler.py`（VNS 内嵌主导）
- prompt 字符预算: `agentic_sessions/88ffbd11-*/scratch/api_visible_prompt_manifest_0002_hypothesis.json`
- 评估协议: `problems/cvrp/formal/{protocol,split_manifest,seed_ledger}.yaml`
