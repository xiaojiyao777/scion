# Scion v0.2 — 设计评审笔记

*Date: 2026-04-10*  
*Reviewer: Cris (GPT-5.4-Pro)*  
*Branch: v0.2-dev*

---

## 0. 评审方法

分三轮进行：

1. **文档初审**：读 v0.2-design.md + task-manifest.md，对比 architecture-v3 / engineering-arch-v1 / v0.1-design 等基础文档
2. **代码读取**：读 v0.1 全量实现，交叉验证文档与代码的实际一致性
3. **结论修正**：纠正初审误判，锁定真正的实现 gap

---

## 1. 初审发现的问题（部分后来被纠正）

### 1.1 最初提出的 5 个问题

#### P1（设计缺陷）：T14 目标函数与主循环不对齐
- **初审判断**：`score = -(splits * 100_000 + total_cost)` 与字典序不一致
- **后来纠正**：`evaluation.py` 里的 `compute_delta()` 早就用了相同的 `SPLITS_WEIGHT = 100_000`，这是 v0.1 已建立的设计选择，不是新引入的问题。T14 应直接复用 `compute_delta()`，而不是另写公式。

#### P2（设计缺陷）：T15 依赖库未定
- **状态**：成立。codebase 里没有任何 BO/GP 相关实现，需要在 T12 前锁定。
- **结论**：v0.2 先做 random/local（T15a），BO 为增强阶段（T15b）。

#### P3：T16 权重优化时间估算
- **状态**：成立。粗算 n_iterations=20, n_eval_seeds=3, n_cases~8, solver~7s ≈ 56分钟/promote。
- **结论**：默认参数降为 n_iterations=8, n_eval_seeds=2。

#### P4：T07 family tracking keyword 规则未定
- **状态**：成立。设计未给出 keyword 列表，验收标准不够具体。
- **结论**：新增回测要求——v0.1 的 7 个 subcategory consolidation 变体必须被归入同一 family。

#### P5：T03 code_content vs archive_ref 未统一
- **状态**：成立。统一用 archive_ref，T04 负责写文件，T03 负责引用路径。

---

## 2. 深度文档交叉比对的关键发现

### 2.1 Architecture v3 §8.4 一开始就要求 per-case screening 暴露

```
per-case 原始结果 | Screening | 可见（LLM/人类）
subgroup breakdown | Screening | 可见
```

这不是 v0.2 的新增，而是 v0.1 蓝图里一直有的设计意图。

### 2.2 case-level-feedback-v1 的定位

这份文档（在 `scion/design/` 目录下）是 architecture 该设计意图的完整实现规格，包含：

- `ObjectiveBreakdown`, `PairwiseCaseFeedback`, `CaseAggregateFeedback`, `ScreeningPatternSummary`
- `compare_with_breakdown()` 评估函数
- `experiment.py` 的数据生产流程
- `context_manager.py` 的渲染流程（4级裁剪策略）

**初审误判**：认为"case-level-feedback-v1 在 v0.2 任务清单中被系统性低估"，建议补一个 T-CB 任务。  
**实际状态**：代码已全部实现，T09/T10 是增量改进。

### 2.3 Architecture v3 §7.2 的 median_delta 语义

> "对于字典序中最主要的竞争目标（通常是成本），计算 delta 用于 practical significance 判断。"

这说明 `median_delta` 在架构层面就是 cost 维度的 delta（通过 `SPLITS_WEIGHT` 标量化的扩展版本），不是一个通用标量。

### 2.4 v0.2-remediation-plan.md 的定位

这份文档是 v0.1 Sprint 3 **之前**的审计备忘，不是 v0.2 的设计输入。到 v0.1 完工时，里面的问题（SQLite、Verification Gate V1-V8、branch_code、CONTINUE_EXPLORE workspace）已全部修复。

---

## 3. 代码读取的关键发现

### 3.1 case-level feedback 完整实现状态（已实现）

| 组件 | 状态 | 位置 |
|---|---|---|
| `ObjectiveBreakdown` | ✅ 已实现 | `core/models.py` |
| `PairwiseCaseFeedback` | ✅ 已实现 | `core/models.py` |
| `CaseAggregateFeedback` | ✅ 已实现 | `core/models.py` |
| `ScreeningPatternSummary` | ✅ 已实现 | `core/models.py` |
| `ProtocolResult.case_feedback / pattern_summary` | ✅ 已实现 | `core/models.py` |
| `compare_with_breakdown()` | ✅ 已实现 | `protocol/evaluation.py` |
| screening 阶段 pair→case→pattern 聚合 | ✅ 已实现 | `protocol/experiment.py` |
| context_manager 渲染（最近3轮详情+选择+pattern）| ✅ 已实现 | `proposal/context_manager.py` |

### 3.2 确认缺失的项（真正的 v0.2 gap）

| 组件 | 状态 | 对应任务 |
|---|---|---|
| `PYTHONHASHSEED` 固定 | ❌ 缺失 | T01 |
| V5 结构化 diagnostics | ❌ 缺失（只有一行 diff） | T02 |
| campaign_summary 完整 artifact | ❌ 缺失 | T03/T04 |
| HypothesisFamily tracking | ❌ 缺失（完全不存在） | T07 |
| Strategy-shift guidance | ❌ 缺失 | T08 |
| parameter layer 全部 | ❌ 缺失 | T12-T18 |

### 3.3 campaign.py 中的关键观察

**`_on_promote()` 当前逻辑**：
```python
def _on_promote(self, branch):
    # 1. 创建 champion snapshot
    # 2. mark_all_stale
    # 无权重优化逻辑
```
T16 需要在此挂载。

**`ChampionState.operator_pool` stale 问题**：
```python
new_champion = ChampionState(
    operator_pool=self._champion.operator_pool,  # 直接沿用旧 pool！
    ...
)
```
当 create_new 操作发生后，新算子已写入 workspace registry.yaml，但 `operator_pool` 内存对象仍是旧状态。T16 必须在 promote 后从 `registry.yaml` 重建 operator_pool。

**`_record_step_lineage()` 存储内容**：
只存 aggregate stats（win_rate / median_delta / ci），不存 case_feedback、code_archive_ref、verification detail 结构化信息。T03 需要升级 campaign_summary 生成逻辑。

### 3.4 PoolManager 状态

`runtime/pool_manager.py` 已完整实现：
- `build_candidate_pool()`
- `export_registry()` + `_normalize_weights()`

但 `campaign.py` 没有任何 import 或调用。

**T13 正确做法**：扩展 PoolManager，新增 `read_registry()` / `read_weights()` / `update_weights()`，parameter layer 调用这些接口。

### 3.5 workspace.py 中的已有 archive 能力

`WorkspaceMaterializer` 已有 `archive_workspace()`：
- 复制 operators/ 到 `campaign_dir/archive/<short_branch_id>/`
- 已在 abandon 路径使用

T04 可以复用/扩展这个机制，给 verification heavy failure 也加上 archive。

### 3.6 compute_delta() 的语义

```python
def compute_delta(candidate_objective, champion_objective) -> float:
    if cand_splits != champ_splits:
        SPLITS_WEIGHT = 100_000
        return (champ_splits - cand_splits) * SPLITS_WEIGHT
    else:
        return champ_cost - cand_cost
```

注意：这**不等价于** `-(splits * W + cost)`。
- 当 splits 相等时，`compute_delta` 退化为 `champ_cost - cand_cost`（纯 cost delta）
- 而 `-(splits * W + cost)` 是把两者混合相加

对 T14 的含义：在权重优化中（通常 splits 变化不大），直接用 `compute_delta` 作为 per-pair score，median 聚合后作为 optimizer 目标函数，是与主循环最一致的做法。

### 3.7 CLI 现有结构

`cli/main.py` 有两个 sub-app：
- `inspect_app`（`inspect campaign`, `inspect branch`, `inspect hypothesis`）
- `report_app`（`report summary`, `report failures`）

T17 的 CLI 应扩展为：
- `inspect weights` 命令（加入 `inspect_app`）
- `scion optimize-weights` 顶级命令

---

## 4. 架构一致性核查结果

| 我初审提出的问题 | 代码核查后的判断 |
|---|---|
| T09 缺数据层 | ❌ 错误，数据层已实现 |
| T14 标量不一致 | 部分修正：compute_delta() 是正确复用目标，不应另写公式 |
| T15 依赖库未定 | ✅ 成立，T15a random/local MVP 先行 |
| T16 时间估算 | ✅ 成立，默认参数需缩减 |
| T07 keyword 规则 | ✅ 成立，需补回测验收标准 |
| T03 统一用 archive_ref | ✅ 成立，T04 写文件，T03 写引用 |

---

## 5. 对 v0.2 task manifest 的有效修正

### 修正 T09

不需要建数据层。仅需改善 `_render_case_feedback()` 的文字可读性：

**当前**：
```
decisive=business_aggregation  deltas: splits=+1.0, cost=-200.0
```

**改为**：
```
decisive: business_aggregation
candidate increased splits by 1 — strictly worse regardless of cost (-200)
```

### 修正 T13

**原设计**：新建 `parameter/registry_writer.py`

**修正**：扩展 `runtime/pool_manager.py`，新增：
```python
def read_registry(registry_path: str) -> Dict[str, OperatorConfig]: ...
def read_weights(registry_path: str) -> Dict[str, float]: ...
def update_weights(registry_path: str, weights: Dict[str, float]) -> None: ...
```

### 修正 T14 评估函数

**原设计**：
```python
score = -(splits * 100_000 + total_cost)
```

**修正**：
```python
# 直接复用 compute_delta() 语义
score = compute_delta(candidate_objective, champion_objective)
```

聚合为 `median(scores over all (case, seed) pairs)`。

### 修正 T16 promote 后的 operator_pool 重建

新增步骤（原设计缺失）：

```python
# 写回 best weights 后，从 registry.yaml 重建 operator_pool
from scion.runtime.pool_manager import read_registry
new_operator_pool = read_registry(
    os.path.join(new_champion_snapshot_path, "registry.yaml")
)
new_champion = ChampionState(
    operator_pool=new_operator_pool,
    ...
)
```

### 修正 T12 eval_cases 默认值语义

`eval_cases: List[str] = []` 的 fallback 语义需明确：
- 空列表 → 使用 `SplitManifest.screening` cases
- 该 fallback 在 parameter search 初始化时一次性解析，不放在 evaluator 函数内

---

## 6. 哪些问题初审是正确的

1. **T15 BO 依赖库**：codebase 里确实没有，需要在 T12 前决策（最终决策：先做 random/local）
2. **T16 时间估算**：确实过高，需降默认参数
3. **T07 keyword 规则**：确实无规则说明，需补验收条件
4. **T03 统一 archive_ref**：正确，已写入 detailed-design
5. **T13 另建 registry_writer 的风险**：正确，应复用 PoolManager

---

## 7. 小结

本次评审的最大收获不是发现了设计缺陷，而是：

1. **澄清了代码基线**：v0.1 已经实现了大量 v0.2 文档里描述的"未来功能"（case feedback、pattern summary、compare_with_breakdown 等）
2. **发现了真正的 gap**：PYTHONHASHSEED、V5 diagnostics、参数层、family tracking
3. **锁定了实现路径**：5 个关键决策避免了重复造轮子

开发启动后，这份笔记可作为"为什么这么设计"的参考。
