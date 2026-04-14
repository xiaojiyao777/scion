# Sprint G — GPT-5.4-Pro 审查整改总结

*日期: 2026-04-11 23:00 → 2026-04-12 12:20*
*分支: v0.2-dev*
*起始 commit: d1053b3 → 终止 commit: 0dbe24f*

---

## 0. 背景

Sprint E 完成后，对 v0.2 全量代码（31 个源码文件 + 5 份设计文档）进行了 GPT-5.4-Pro 架构审查。审查产出：

- `scion/reviews/scion-v02-review_result.md`（779 行审查意见）
- `scion/reviews/SprintF前整改任务单.md`（1169 行整改 spec）

审查发现 4 类核心问题：控制边界违反、协议统计粒度错误、参数搜索基线偏差、CLI/Prompt 未接入。拆为 G1-G4 四个 Sprint 逐一修复。

---

## 1. Sprint G1 — Control Boundary Hardening + Hypothesis Lifecycle

**Commit**: `78c7a4c` | **改动**: 6 files, +872/-35

| Task | 内容 |
|---|---|
| T1 | Gate bypass 修复：fix patch / pending hypothesis 全部经完整 Contract+Verification |
| T2 | verification 前不污染 `last_clean_code_hash`（仅 verification 通过后更新） |
| T3 | screening→validation→frozen→promote 全链路保持同一 `hypothesis_id` |
| T4 | stale reconcile 重走 Contract→Verification→re-screening |
| T5 | eval-only 步骤（validation/frozen）写入 `step_history` |
| T6 | hypothesis 状态机完整：pending→screening→validated→promoted/abandoned |
| T7 | `create_branch` 动作增加 `max_active_branches` 上限检查 |

**新增测试**: 12 tests in `unit/core/test_campaign_control_boundaries.py`

---

## 2. Sprint G2 — Protocol Correctness

**Commit**: `3a33dec` | **改动**: 11 files, +784/-117

| Task | 内容 |
|---|---|
| T1 | 统一 config schema：移除 `config/problem.py` 中的简化版，全部 re-export 权威类 |
| T2 | Case-level 统计：`CaseLevelResult` + majority vote 聚合 + case-level bootstrap CI |
| T3 | Canary 使用独立 split（不复用 screening cases） |
| T4 | Expand 增加 cases 而非 seeds（修正：扩展样本量 = 增加 case 覆盖） |
| T5 | Action-specific case 选择（modify/remove vs create_new 区分 N） |
| T6 | `protocol.yaml` 更新为嵌套格式 |

**新增测试**: 14 tests in `unit/protocol/test_protocol_correctness.py`

---

## 3. Sprint G3 — Parameter Search Correctness

**Commit**: `40b8a19` | **改动**: 11 files, +2654/-343（含审查文档）

| Task | 内容 |
|---|---|
| T1 | True baseline：optimizer 先评估 `current_weights`，不依赖随机采样 |
| T2 | Observations to disk：`weight_opt_<ts>.json` 持久化全部评估记录 |
| T3 | Mutable staging：`create_mutable_staging()` + `freeze_snapshot()` 解决权限问题 |
| T4 | Snapshot hash 包含 `registry.yaml`（权重变化纳入 champion 指纹） |
| T5 | `_run_weight_optimization` 接收并传递 `current_weights` |

**新增测试**: 11 tests in `unit/parameter/test_weight_optimizer_correctness.py`

---

## 4. Sprint G4 — CLI Real Runtime + Prompt Plumbing + Cleanup

**Commits**: `3292b99` + `0dbe24f` (Cris 修复) | **改动**: 7 files, +772/-343

| Task | 内容 |
|---|---|
| T1 | `scion run` 接入真实 Runner/ExperimentProtocol/VerificationGate |
| T2 | hypothesis prompt 注入 branch code / coverage / strategy / baseline hints |
| T3 | code prompt 注入 `## Previous Attempt Failed` 上下文 |
| T4 | `_sync_pool_registry()` — apply_patch 后重建 registry（remove/modify 正确性） |
| T5 | lineage 写入真实 `hypothesis_id` + `decision_reason_codes` |
| T6 | `hypothesis_store.py` 瘦身为 re-export；V-code 注释补全 |
| T7 | `scion inspect weights` + `scion optimize-weights` CLI 命令 |

**新增测试**: 12 tests in `unit/test_g4_plumbing.py`

**Cris 修复**: T4 `_sync_pool_registry` 在 champion pool 为空时覆盖 registry 的回归 bug（`0dbe24f`）

---

## 5. 总体统计

| 指标 | 数值 |
|---|---|
| **Commits** | 5（G1-G4 + Cris hotfix） |
| **文件变更** | 33 files |
| **代码增减** | +5,081 / -837 行 |
| **新增测试** | 49 tests（12+14+11+12） |
| **测试总数** | 573 (全部 PASSED ✅) |
| **开发耗时** | CC ~3.5h + Cris 验收 ~1.5h |
| **审查文档** | 2 份（审查意见 779L + 整改任务单 1169L） |

---

## 6. 修复的架构偏差

Sprint G 修复了 Pro 审查发现的全部 P0 问题：

1. ✅ **Gate bypass** — fix patch / pending hypothesis 全部过 Contract+Verification
2. ✅ **Clean-base 污染** — verification 前不更新 `last_clean_code_hash`
3. ✅ **Hypothesis ID 断裂** — 全链路保持同一 ID
4. ✅ **统计粒度错误** — case-level 聚合（majority vote + case-level CI）
5. ✅ **Canary 复用 screening** — 独立 split
6. ✅ **Expand 语义** — 增加 cases 而非 seeds
7. ✅ **Optimizer 无 baseline** — true baseline 评估 + mutable staging
8. ✅ **CLI 空壳** — `scion run` 接入完整 runtime
9. ✅ **Prompt 信息缺失** — branch code / failure history / strategy 注入

---

## 7. 下一步

Sprint G 完成标志着 v0.2 架构整改全部到位。下一步：

1. **Sprint F（端到端验证 campaign）** — 跑完整 15+ round campaign，验证整改后的行为
2. **分析 Sprint F 结果** — 对比 v0.1 验证实验，确认改善
3. **文档固化** — 更新 architecture v3 文档，标记 Sprint G 变更

---

## v0.3 Backlog — Async Weight Optimization（2026-04-12）

### 背景

Sprint F 发现：weight optimization 在 `_on_promote()` 内同步执行，每次 promote 阻塞 campaign ~40 分钟（pure-Python UCB fallback，16次评估×34次 solver 调用）。

### 设计决策：Sprint F 暂不做 async

**原因**：async weight opt 会让后续分支与"未优化权重的 champion"做对比，产生系统性虚假胜率（false positive）。Sprint F 定位是完整验证实验，实验有效性优先于吞吐量。

**Sprint F 临时缓解**：`n_initial_random: 4, n_iterations: 4`（评估从16→8次，时间从41min→~20min）。

### v0.3 正确实现方案

#### 核心原则
Weight opt 完成前，不允许任何分支与未优化权重的 champion 做实验对比。

#### 实现步骤

**Step 1：_on_promote 异步化**
```python
# _on_promote 只做同步关键路径：
#   copytree → freeze → new_champion（暂用旧权重）→ 返回
# 后台 Thread 做 weight opt
```

**Step 2：配合 STALE 机制**
- weight opt 完成后，若结果有改善 → 触发 "soft champion update"
- `mark_all_stale(new_version, weight_update=True)` 标记活跃分支 STALE
- 活跃分支必须 reconcile：用新权重的 champion 重新 screening
- 有正信号则恢复，否则 ABANDONED

**Step 3：版本语义**
- weight opt 完成后 champion 版本号不变，但 `code_snapshot_hash` 更新（registry.yaml 变了）
- Lineage 记录 `weight_opt_result` 与对应 champion 版本绑定

**Step 4：Double-promote 处理**
- 第二次 promote 发生时，取消前一个 weight opt thread（或等待其完成后丢弃结果）
- 用 `asyncio.Event` 或 `threading.Event` 实现取消信号

#### 关键约束
- weight opt thread 必须在 STALE 触发前完成（否则 STALE 意义丧失）
- 如果 weight opt 超时（>15min），直接跳过权重更新，保持当前权重不变
- STALE reconcile 成本高：需要评估 weight opt 是否真的有改善（`improved=True`），改善不显著则不触发 STALE

#### 工程影响范围
- `scion/core/campaign.py`：`_on_promote`、`__init__`、`run()`
- `scion/core/branch.py`：`mark_all_stale` 增加 `weight_update` 参数
- `scion/parameter/optimizer.py`：增加取消信号支持
- Tests：async 行为 + STALE trigger 条件

---

## v0.3 Backlog 补充 — HypothesisFamily 语义分类（2026-04-12）

### 背景

当前 HypothesisFamily 用 `(change_locus, action, target_weakness)` 规则分类。
盲区：语义相近但字段不同的假设无法归族，例如：
- modify + vehicle_level + "改善 subcategory 合并"
- create_new + order_level + "让同品类订单聚合"
→ 规则认为不同族，实际是同一方向，无法触发"同方向失败预警"。

### 方案：双路设计

```
Hypothesis 生成（Round 1 LLM，tainted）
    ↓
Contract Gate
    ↓
[Classifier LLM] — 独立调用，小模型（Sonnet/Flash）
  输入：hypothesis_text + 当前 family 列表 + problem spec 摘要
  输出：family_label（预定义 taxonomy 中选，或 new_family）
  ← Classifier 不感知"哪些族已失败"，只做纯分类
    ↓
FamilyTracker 记录 family_failure_streak
    ↓
ContextManager 注入预警
```

### 关键设计决策

- **模型**：Sonnet 即可（分类任务不需要深度推理）
- **Taxonomy**：半开放，预定义 10-15 个核心 family，允许 new_family 但规范命名
- **Classifier 隔离**：不注入"已失败方向"信息，防止跨轮次措辞漂移
- **一致性**：few-shot 示例注入，提升同一假设的分类稳定性

### 为什么 Classifier LLM 不会被 proposing LLM 操纵

两次调用上下文完全独立（stateless），proposing LLM 不知道 classifier 的提示词和判断标准，无法操纵分类结果。之前担心的"自我作弊"是伪命题。

---

## v0.3 Backlog — FailureRouter 系统性升级（2026-04-12）

### 背景

当前 FailureRouter（Sprint G2-patch 落地）是可工作的简单实现：四层分类 + 四种路由动作，但每次失败独立处理，无历史记忆，无跨组件联动。F3 实验暴露了典型缺口：30 轮 V3_unit_tests 轻度失败无人感知，全部浪费。

### 五个设计缺口

1. **无时间记忆**：同类失败连续 N 次不升级，每次独立处理
2. **与 StagnationDetector 断联**：失败模式不流入 stagnation 检测
3. **评估路由粒度太粗**：wr=0.15 和 wr=0.55 走同一条 continue_explore
4. **无跨分支失败共享**：同类算子在不同分支踩同一坑，重复浪费
5. **LLM 拿到点状错误，看不到失败模式面**

### v0.3 升级方案

**FailureRouter 时间维度升级**：
```python
# 同类 light failure 连续 3 次 → 升级为 INFRA_SUSPECTED
# → 触发 circuit breaker 检查
# → 写入 CampaignDiagnosis
if consecutive_same_code >= 3 and severity == "light":
    action = FailureAction.INFRA_SUSPECTED
    
# 同方向 heavy failure 连续 2 次 → 提前 ABANDON
if consecutive_heavy >= 2:
    action = FailureAction.ABANDON_FAST
```

**StagnationDetector 第五种模式**：
```python
infra_loop: 同种 light failure 连续 5+ 次 → should_stop
```

**评估路由分级**：
```python
wr < 0.3     → ABANDON_FAST（碾压级失败，快速放弃）
wr 0.3-0.6   → CONTINUE_EXPLORE（有苗头，继续）
wr > 0.6 未过 → CONTINUE_EXPLORE + 提升 expand 优先级
```

**跨分支失败共享**（可选）：
- 全局 failure registry，按 (failure_code, operator_type) 索引
- 新分支创建时，ContextManager 注入"已知危险失败模式"

### 设计目标

把 FailureRouter 从"无状态点处理器"升级为"有记忆、有联动的失败智能系统"：
- 时间维度：失败模式升级
- 空间维度：跨分支学习
- 联动维度：与 StagnationDetector 双向数据流

---

## v0.3 Backlog 补充 — FailureRouter CC 参考设计（2026-04-12）

### CC 关键设计对 Scion 的启发

**1. Session 级持久计数器（最直接可用）**
CC 的 circuit breaker 计数在 session 生命周期内持久化，不是每轮重置。Scion 应在 CampaignManager 维护 `_failure_streak: Dict[str, int]`，跨轮次累积同类失败计数。

**2. Escalating Retry（CC: max_output_tokens 升级模式）**
CC 对同类失败主动升级处理强度（8K→64K→注入提示→抛出），Scion 应引入：
- RETRY_LLM 第 1-2 次：正常反馈
- RETRY_LLM 第 3 次：注入更强提示
- 第 4 次：升级为 INFRA_SUSPECTED

**3. 前台/后台分级（CC: querySource 区分）**
campaign 主循环 LLM 调用（保守重试）vs 诊断/分类调用（失败即放弃），策略不同。

**4. 预防性防御层（CC: API call 前多道预处理）**
CC 在每次 API 调用前执行 compact/budget/snip 防止错误发生。Scion 可在实验开始前加环境预检（pytest 可用性、磁盘空间等），避免 infra 问题进入主循环。

### CC 没有，Scion 特有的挑战
CC 的错误处理针对单次 LLM 对话；Scion 面对的是跨轮次、跨分支的实验失败模式。
CC 的熔断器保护"无限 autocompact 死循环"；Scion 需要保护"无限 infra_loop 浪费"。
两者问题结构不同，但熔断器的 session 级持久计数是通用原则。

---

## v0.3 Backlog — Weight Opt 结果反馈给 LLM（2026-04-12）

### 背景

当前 weight opt 结果（算子优化权重）不进入 LLM 上下文，形成信息断层。
weight opt 知道当前 pool 里每个算子的实际贡献，这对 LLM 提假设有指导价值：
- 低权重算子 = 改进机会信号（设计薄弱或与 pool 不互补）
- 高权重算子 = 深挖或多样化信号（可专项改进或分摊压力）

### 方案

在 Round 1 上下文里注入 weight opt 结果作为**弱信号**（不是指令）：

```
"当前算子贡献估计（weight opt 结果）：
  - destroy_rebuild: 高贡献（权重 4.97）
  - subcat_move: 中等贡献（权重 1.12）
  - move_order: 低贡献（权重 0.05）—— 可能是改进机会"
```

措辞为"贡献估计"而非"改进指令"，给 LLM 信息让它自行推断，不强制指挥。

### 风险控制

exploitation 偏差：高权重算子信息可能让 LLM 更集中在已成功方向。
缓解：与"未探索方向提示"（HypothesisFamily 语义分类 v0.3）配合使用，形成双向信号：
- weight opt 告诉"哪里弱"（改进机会）
- HypothesisFamily 告诉"哪里还没探索"（新方向机会）

### 时机

weight opt 完成后，写入 champion metadata；下一个分支创建时，ContextManager 读取并注入。

---

## v0.3 Backlog — ChampionStore 持久化（P2，2026-04-12）

### 问题

`champions` SQLite 表当前为空。`_on_promote()` 直接更新内存中的 `self._champion`，没有调用 `ChampionStore.record()` 写入 DB。

Champion 历史只能从文件系统 `champions/champion_vN/` 恢复，不能通过 DB 查询。
无法用 SQL 统计"历史上哪些 promote 最显著"或"champion 演化路径"。

### 修复

在 `_on_promote()` 末尾调用：
```python
self._registry.record_champion(
    campaign_id=self._campaign_id,
    version=new_version,
    operator_pool=new_champion.operator_pool,
    code_snapshot_hash=new_champion.code_snapshot_hash,
    promotion_experiment_id=promotion_event_id,
)
```

### 影响范围
- `scion/lineage/registry.py`：实现 `record_champion()`
- `scion/core/campaign.py`：`_on_promote()` 末尾调用
- 现有测试：补充 champion 写入验证

---

## v0.3 Backlog — Canary 实例设计升级（2026-04-12）

### 核心设计原则（不变）

> Canary 选的是**已知容易出问题的边界场景**，作为确定性的基准检查。

Canary 的设计目的是"正确性底线"，不是"性能采样"。这决定了 Canary 实例不应该来自随机生成器，而应该精心设计。

### 当前问题

当前 3 个 canary 实例（instance_v3_can_m01/m02, instance_v4_can_s01）来自同一生成器，
和 screening/validation/frozen 有相同的系统性偏差——无法测试业务边界场景的正确性。

### v0.3 升级方案：两类实例来源

**来源一：手工设计的对抗性实例（静态，入仓库）**

覆盖已知业务边界：
- 全部订单锁定（locked_vehicle_id 全设置）
- 容量满载边界（总 pallets = 车辆容量上限）
- 全危险品订单（必须走 HQ40_DG 专用车型）
- 单一提货点极端集中（与 test_oracle.py 设计的测试用例对齐）
- 订单数恰好触碰各车型边界（T10/HQ40/HQ40_DG 的 capacity 边界值）

**来源二：实验中总结出的失败实例（动态，自动积累）**

从历史实验记录中提取"已知出错的场景"：
- 触发过 V5_state_mutation 或 V8_nondeterminism 的实例模式
- 历史上 screening 大败（wr < 0.2）的特定实例类型
- 算子在某个实例上产出 feasibility_violation 的配置特征

自动积累机制：
```python
# 每次出现重度 verification failure
if failure_code in ["V5_state_mutation", "V8_nondeterminism"]:
    candidate_canary_pool.append(extract_instance_pattern(instance))
    
# 人工审核后提升为正式 canary
# 保持 canary set 小而精（5-10 个），不做大规模扩张
```

### 与 test_oracle.py 的对齐

test_oracle.py 的 TestHardConstraintViolations 测试用例本质上就是"手工设计的边界场景"。
canary 实例的设计可以直接参考这些测试用例，确保 canary 和 oracle 测试覆盖同一类边界。

---

## v0.2 P0 待查 — Oracle Bug（2026-04-12 发现）

### 问题描述

在调试 F3 环境问题时发现：`surrogate/tests/test_oracle.py` 的两个测试失败：

```
FAILED TestHardConstraintViolations::test_H1_capacity_exceeded
  # 构造容量超载解 → oracle 误报 is_feasible=True

FAILED TestHardConstraintViolations::test_H3_too_many_pickups_donguan
  # 构造东莞提货约束违反 → oracle 误报 is_feasible=True
```

### 影响链

Oracle 是整个系统的信任锚点：
- Verification Gate 的 feasibility check 调用 oracle
- Screening/Validation/Frozen 的字典序比较，Level 1 = feasibility

如果 oracle 把不可行解误判为可行：
1. 生成不可行解的算子可能通过 Verification Gate
2. 不可行解在 A/B 中被作为可行解比较，可能意外赢得 splits/cost 比较
3. **F1 的两个 promote 是否被此 bug 污染，目前不确定**

### 待做事项（F2/F3 完成后）

1. **诊断**：读 oracle.py，找出容量超载和东莞提货约束的检查逻辑缺失在哪里
2. **修复**：补齐约束检查（CC 任务）
3. **影响评估**：
   - F1 的 SubcategoryAwareMoveOrder 和 destroy_rebuild 车型升级，在实验中有没有产出不可行解？
   - 检查 experiment_events 中的 feasibility_violation 字段
   - 如有问题，需要用修复后的 oracle 重新评估
4. **回归测试**：oracle 修复后跑完整测试套件（600 tests）

### 优先级

**v0.2 必须解决**，不是 v0.3 backlog。Oracle 正确性是实验有效性的前提。
在 oracle 修复并验证前，Sprint F 的结论是"在已知有 oracle bug 的环境下的结果"，可信度存疑。

---

## v0.3 Backlog — 精确算法对比验证（2026-04-12）

### 背景

Scion 的改进目前只有"相对意义"（比上一个 champion 好）。在小规模实例上和精确算法（MILP）对比，可以给改进加上"绝对意义"。

### 方案

对 v4 small 实例（20-40 orders）：
1. 用 CBC/CPLEX/Gurobi 求解 MILP，得到最优解的 optimality gap
2. 记录 champion 的 optimality gap = (heuristic_cost - optimal_cost) / optimal_cost
3. 每次 Scion promote 后，重新计算新 champion 的 optimality gap
4. 观察 Scion 是否在持续压缩 gap

### 预期价值

如果 champion 在小规模上距最优 30%，Scion 改进把它压到 20%，这有绝对意义，不只是相对改进。
是对 "Scion 真的在改进算法" 这一命题的更强验证。

### 前置工作

需要先写出仓配协同问题的 MILP 数学模型（已规划：基于 surrogate 代码建模）。

---

## v0.3 Backlog — Campaign Research Journal（2026-04-13）

### 背景

当前 Scion 的 LLM 上下文只利用了 1M context 的约 2-3%（~23K tokens）。实验记录（SQLite lineage）具有双重用途：它既是供人工分析的研究日志，也是 LLM 上下文的重要组成部分。这两个用途不应割裂。

**关键原则**：不是"上下文堆砌"，而是"有组织地补充 LLM 的研究认知"。

### 当前 4 个严重未充分利用的信息点

**1. hypothesis_text 被截断（最严重）**

当前 Research Log 截断到 40 字，Sprint J-RL2 改到 200 字。但完整 hypothesis（300-600 字）描述了算子核心机制、与现有算子的区别、预期效果。只有看到完整文本，LLM 才能判断"这次假设和之前的是否本质相同"。

**修复方向**：Research Log 对所有 branch 展示完整 hypothesis_text，不截断。

**2. 跨 branch 的全局实验历史不在 user prompt 里**

当前 `experiment_history` 是 `## Experiment History — This Branch`，新 branch 永远是 `(no prior experiment rounds)`。20+ 个 branch 的完整轨迹全在 SQLite 里，LLM 根本看不到。

**修复方向**：user prompt 的 `experiment_history` 改为全局（所有 branch，按时间序，每个 branch 的完整轨迹）。或者 Research Log 承担这个职责，成为真正的"Campaign Research Journal"。

**3. 历史 champion 版本算子代码不可见**

当前只给 LLM 看当前 champion（最新版本）的算子代码。v1→v2 增加了 subcategory_consolidate，v2→v3 增加了 subcategory_redistribute——这些演化轨迹对 LLM 提出下一步改进假设至关重要。

**修复方向**：Research Log 的 champion 演化段加入"每个版本新增算子的完整代码"（不是仅文件名）。或者：加入每个版本新增算子的完整 hypothesis text + 简化实现说明。

**4. Weight optimization 权重不可见**

weight_optimizations 表记录了每次 champion 版本的算子权重。如 v4 中 `destroy_rebuild` 权重 3.51、`subcategory_aware_merge`（最新晋升）权重仅 0.21——直接告诉 LLM 哪个算子贡献高、哪个是改进机会。

**修复方向**：Research Log 加入最新 weight optimization 结果（已在 Sprint J-RL2 中实现）。

### 正确的组织原则

信息补充不是堆切，应该按"研究认知"组织：

```
## Campaign Research Journal

### 研究进展摘要（快速定向）
  目前: splits 改善 82%，cost 改善 12% → splits 接近饱和，重点转向 cost
  Champion 演化: consolidate → redistribute → aware_merge（品类合并系列深化）
  未探索: cost-focused 方向、order_level create_new（仅 3 次）

### 算子池当前状态
  高贡献: destroy_rebuild(3.51), subcategory_consolidate(3.54)
  中等: move_order(1.30), merge_vehicles(0.60), redistribute(0.51)
  低贡献/改进机会: subcategory_aware_merge(0.21), split_vehicle(0.08)

### 已探索方向（完整轨迹）
  [PROMOTED] ... （完整 hypothesis + 每阶段 wr）
  [FAILED]   ... （完整 hypothesis + 失败原因）
  ...

### 历史 Champion 演化
  v2 新增: subcategory_consolidate（品类感知合并）
  v3 新增: subcategory_redistribute（腾出空间策略）
  v4 新增: subcategory_aware_merge（低贡献，待改进）
```

这样 LLM 看到的是"一个有结构的研究日志"，而不是原始数据转储。

### 实施策略

- **短期（当前 sprint）**：Research Log 完整 hypothesis text + 权重 + 演化 diff（Sprint J-RL2 进行中）
- **中期（补充 sprint）**：全局 experiment_history 替代 branch-local；历史 champion 算子摘要
- **v0.3**：Campaign Research Journal 作为独立模块，统一管理 LLM 研究认知上下文；与 Search Memory / Saturation Signal 三位一体形成完整的 LLM 知识系统
