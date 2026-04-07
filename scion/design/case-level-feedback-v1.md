# Scion Case 级别 Screening Feedback 设计 v1

## 1. 问题分析

### 1.1 当前 feedback 丢失了什么

现状里，`ProtocolResult` 暴露给 LLM 的 screening 信息只有：

- `win_rate`
- `median_delta`
- `gate_outcome`
- 若干 `reason_codes`
- `raw_metrics_ref` 仅落盘，不进入 prompt

对应代码位置：

- `scion/protocol/experiment.py`：`raw_pairs` 只写入 JSON 文件，不进入 `ProtocolResult`
- `scion/core/models.py`：`ProtocolResult` 只有 aggregate 字段
- `scion/proposal/context_manager.py`：`_build_experiment_history()` 只渲染 aggregate

因此 LLM 看不到以下关键信息：

1. **哪几个 case 赢，哪几个 case 输**
2. **同一个 instance 在不同 seed 下是否稳定**
3. **输赢由哪个目标层级决定**
   - 是先输在业务聚合（`subcategory_splits`）
   - 还是业务聚合打平后输在成本（`total_cost`）
   - 未来如果加效率目标，也无法知道是输在效率
4. **create_new / modify 的作用范围是否匹配问题分布**
   - 例如新算子只在大实例有效，小实例全 tie
   - 或 modify 某个局部 operator 后，只改善特定 region/品类结构的实例
5. **pattern 无法自动归纳**
   - 当前 LLM只能从 `win_rate=0.42, median_delta=200` 猜问题
   - 无法知道“candidate 在 large instance 上普遍赢，但 small instance 上因 splits 增加而输”这类可操作结论

### 1.2 为什么这些信息重要

Scion 的 screening 不是纯单目标，而是**字典序多目标**。aggregate 统计压平后，丢掉了“为什么赢/输”的因果线索。

对下一轮 hypothesis 生成而言，真正有用的不是“平均表现如何”，而是：

- **失败是结构性失败，还是局部失败**
- **失败发生在哪个目标层级**
- **失败与 instance 特征是否相关**
- **当前尝试更适合继续 modify，还是改为 create_new，还是放弃该方向**

如果没有 case-level feedback，LLM 常见行为会退化成：

- 盲目重复前一轮思路的轻微变体
- 无法判断该优化是在“用成本换业务聚合”还是“纯粹无效”
- 无法提炼 instance pattern，因此难以提出有针对性的算子结构

### 1.3 当前 raw_pairs 仍然不够

`experiment.py` 当前已写出：

```python
{"case": case, "seed": seed, "comparison": cmp, "delta": delta}
```

这比 aggregate 多一步，但仍然不够，原因是：

1. `comparison` 只有 `win/loss/tie`，不知道**字典序在哪一层决出胜负**
2. `delta` 只有 `total_cost` 差值，无法解释：
   - 为什么 cost improved 但 overall 仍然 loss（因为 splits 变差）
   - 为什么 overall tie 但 candidate 实际在效率上有改善
3. 没有 case 特征摘要，无法做 pattern mining
4. 没有按 instance 聚合，seed-level 数据直接 dump 给 prompt 会浪费 token

---

## 2. 数据流设计

目标：让 screening 的信息流从“只保留 aggregate”升级为“保留结构化 case feedback，再由 ContextManager 压缩成 prompt 文本”。

建议新增三层数据：

1. **pair-level**：单个 `instance × seed` 的 A/B 对比
2. **case-level**：按 instance 聚合多个 seed 后的摘要
3. **pattern-level**：代码自动归纳的跨 case 模式总结

> 关键原则：
> - **screening 阶段保留 case-level 详情**，供下一轮 hypothesis 使用
> - **validation / frozen 仍保持严格 exposure control**，只给 aggregate，不给 per-case 明细

### 2.1 ProtocolResult 扩展

建议在 `scion/core/models.py` 中扩展数据结构。

#### 2.1.1 新增维度与 pair 结构

```python
from dataclasses import dataclass, field
from typing import Optional, Literal, Any

@dataclass(frozen=True)
class ObjectiveBreakdown:
    # 原始值
    candidate_subcategory_splits: Optional[float] = None
    champion_subcategory_splits: Optional[float] = None
    candidate_total_cost: Optional[float] = None
    champion_total_cost: Optional[float] = None
    candidate_route_count: Optional[float] = None
    champion_route_count: Optional[float] = None

    # 方向统一后的 delta（正数 = candidate 更好）
    delta_subcategory_splits: Optional[float] = None   # champion - candidate
    delta_total_cost: Optional[float] = None           # champion - candidate
    delta_route_count: Optional[float] = None          # champion - candidate

    # 决胜层级：字典序在哪一层分出胜负
    decisive_objective: Literal[
        "business_aggregation",
        "cost",
        "efficiency",
        "tie",
        "unknown",
    ] = "unknown"


@dataclass(frozen=True)
class PairwiseCaseFeedback:
    case_id: str
    seed: int
    comparison: Literal["win", "loss", "tie"]
    delta: float  # 兼容现有语义，保留 champion_cost - candidate_cost
    objective_breakdown: ObjectiveBreakdown
    case_features: dict[str, Any] = field(default_factory=dict)
```

说明：

- `delta` 保留现有字段，避免下游统计逻辑大改
- `objective_breakdown` 负责解释“为什么是这个比较结果”
- `case_features` 不是 solver output，而是从 instance path / manifest / 轻量特征提取器得到的摘要

#### 2.1.2 新增 case 聚合结构

```python
@dataclass(frozen=True)
class CaseAggregateFeedback:
    case_id: str
    n_pairs: int
    wins: int
    losses: int
    ties: int
    win_rate: float

    # 该 case 上的总体现象
    dominant_result: Literal["win", "loss", "tie", "mixed"]
    dominant_decisive_objective: Literal[
        "business_aggregation",
        "cost",
        "efficiency",
        "mixed",
        "unknown",
    ]

    # 各维度聚合 delta（正数 = candidate 更好）
    median_delta_total_cost: Optional[float] = None
    median_delta_subcategory_splits: Optional[float] = None
    median_delta_route_count: Optional[float] = None

    # 稳定性
    seed_consistency: float = 0.0   # max(win, loss, tie) / n_pairs

    # 方便 prompt 的轻量特征
    case_features: dict[str, Any] = field(default_factory=dict)
```

#### 2.1.3 新增 pattern 结构

```python
@dataclass(frozen=True)
class ScreeningPatternSummary:
    total_cases: int
    winning_cases: int
    losing_cases: int
    mixed_cases: int

    wins_by_decisive_objective: dict[str, int] = field(default_factory=dict)
    losses_by_decisive_objective: dict[str, int] = field(default_factory=dict)

    wins_by_size_bucket: dict[str, int] = field(default_factory=dict)
    losses_by_size_bucket: dict[str, int] = field(default_factory=dict)

    consistent_win_cases: list[str] = field(default_factory=list)
    consistent_loss_cases: list[str] = field(default_factory=list)

    key_observations: list[str] = field(default_factory=list)
```

#### 2.1.4 ProtocolResult 扩展后的建议形态

```python
@dataclass(frozen=True)
class ProtocolResult:
    stage: ExperimentStage
    stats: EvalStats
    gate_outcome: Literal["pass", "fail", "unclear", "expand"]
    reason_codes: Tuple[str, ...]
    exposed_summary: str
    raw_metrics_ref: str

    # 新增：仅 screening 会填充详情
    pair_feedback: Tuple[PairwiseCaseFeedback, ...] = ()
    case_feedback: Tuple[CaseAggregateFeedback, ...] = ()
    pattern_summary: Optional[ScreeningPatternSummary] = None
```

### 2.2 experiment.py 中的数据生产流程

建议修改 `scion/protocol/experiment.py`：

#### 当前流程

- 逐 pair 调 solver
- 计算 `comparison` + `delta`
- 追加到 `raw_pairs`
- 结束后算 `EvalStats`

#### 修改后流程

- 逐 pair 调 solver
- 调新的分解函数：
  - `compare_with_breakdown()`
  - `extract_case_features(case)`
- 生成 `PairwiseCaseFeedback`
- 所有 pair 完成后：
  - `aggregate_case_feedback(pair_feedback)`
  - `build_screening_pattern_summary(case_feedback)`
- 落盘 JSON 同时保存 raw pair / case / pattern
- `ProtocolResult` 在 `SCREENING` 阶段携带这些结构化字段
- `VALIDATION/FROZEN` 阶段字段可为空，继续 exposure control

伪代码：

```python
pair_feedback: list[PairwiseCaseFeedback] = []

for case in cases:
    case_features = extract_case_features(case)
    for seed in seeds:
        ... run champion / candidate ...
        comparison, breakdown = compare_with_breakdown(
            cand_r.output.objective,
            champ_r.output.objective,
        )
        delta = breakdown.delta_total_cost or 0.0
        pair_feedback.append(
            PairwiseCaseFeedback(
                case_id=case,
                seed=seed,
                comparison=comparison,
                delta=delta,
                objective_breakdown=breakdown,
                case_features=case_features,
            )
        )

case_feedback = aggregate_case_feedback(pair_feedback)
pattern_summary = build_screening_pattern_summary(case_feedback)
```

### 2.3 StepRecord 如何携带这些数据

当前 `StepRecord` 已经持有 `protocol_result: Optional[ProtocolResult]`。

这意味着**不需要额外给 `StepRecord` 再单独加一套字段**；只要扩展 `ProtocolResult` 即可，`StepRecord` 自动获得访问链路。

这是更好的做法，原因：

- 避免 `StepRecord` 与 `ProtocolResult` 双写
- screening / validation / frozen 仍统一经由 `protocol_result`
- ContextManager 只关心 `StepRecord.protocol_result`

因此建议：

- **不改 `StepRecord` 字段集合**
- 只改 `ProtocolResult` 的内部结构

若想提升类型可读性，可给 `StepRecord` 增加一个辅助 property（非必须）：

```python
@dataclass
class StepRecord:
    ...

    @property
    def screening_case_feedback(self) -> tuple[CaseAggregateFeedback, ...]:
        if self.protocol_result and self.protocol_result.stage == ExperimentStage.SCREENING:
            return self.protocol_result.case_feedback
        return ()
```

### 2.4 ContextManager 如何消费这些数据

`ContextManager.build_hypothesis_context()` 仍只接收 `step_history`，但 `_build_experiment_history()` 需要升级为两层渲染：

1. **round header**：保留当前 aggregate 摘要
2. **case feedback block**：仅对最近若干轮 screening 渲染精选详情
3. **pattern summary block**：自动生成、优先级高于 raw case dump

建议拆成：

```python
def _build_experiment_history(step_history: list[StepRecord], branch_id: str) -> str:
    ...


def _render_screening_feedback(pr: ProtocolResult, budget: PromptBudget) -> str:
    ...


def _render_pattern_summary(pattern: ScreeningPatternSummary) -> str:
    ...


def _select_case_feedback_for_prompt(
    case_feedback: list[CaseAggregateFeedback],
    max_cases: int,
) -> list[CaseAggregateFeedback]:
    ...
```

---

## 3. Prompt 格式设计

### 3.1 设计目标

prompt 里的 case feedback 不是为了“完整记录实验日志”，而是为了支持下一轮 hypothesis 生成，因此格式要满足：

1. **先给结论，再给证据**
2. **优先 case-level，不优先 pair-level**
3. **只展示最有信息量的 case**
4. **明确字典序决胜层级**
5. **让 modify / create_new 都能直接消费**

### 3.2 experiment_history 的建议模板

建议把每轮 screening 历史渲染成如下模板。

#### 3.2.1 Round 级模板

```text
Round {round_num} [{status}]
hypothesis: {change_locus}/{action}{target_suffix}
hypothesis_text: {hypothesis_text_short}
screening_aggregate: win_rate={win_rate:.2f} median_cost_delta={median_delta_total_cost:+.1f} outcome={gate_outcome}
reason_codes: {reason_codes}
pattern_summary:
{pattern_summary_block}
selected_cases:
{selected_cases_block}
```

其中：

- `target_suffix`：` -> {target_file}`，若存在
- `median_delta_total_cost`：沿用现有 `median_delta`
- `pattern_summary_block`：代码自动计算
- `selected_cases_block`：精选 case 列表

#### 3.2.2 Pattern summary 模板

```text
- case distribution: win={winning_cases}, loss={losing_cases}, mixed={mixed_cases}
- decisive objective (wins): business_aggregation={...}, cost={...}, efficiency={...}
- decisive objective (losses): business_aggregation={...}, cost={...}, efficiency={...}
- by size bucket: win[{size_stats_win}] / loss[{size_stats_loss}]
- consistent wins: {case_list_or_none}
- consistent losses: {case_list_or_none}
- key observations:
  - {obs1}
  - {obs2}
```

#### 3.2.3 单个 case 模板

```text
- {case_short}: result={dominant_result} (W/L/T={wins}/{losses}/{ties}, consistency={seed_consistency:.2f})
  decisive={dominant_decisive_objective}
  deltas: splits={median_delta_subcategory_splits:+.2f}, cost={median_delta_total_cost:+.1f}, routes={median_delta_route_count:+.1f}
  features: size={size_bucket}, orders={n_orders}, locked={locked_ratio}, region_mix={region_mix}
```

说明：

- `result=mixed` 适合表达 seed 不稳定
- `consistency` 帮助 LLM 判断这是不是随机噪声
- `deltas` 全部使用“正数 = candidate 更好”的统一方向
- `features` 只放少量、高信息密度字段

### 3.3 自动 pattern 总结的生成规则

必须由代码生成，而不是让 LLM 再自己总结。原因：

- 节约 token
- 避免二次 hallucination
- 保持不同轮之间描述风格稳定

建议规则：

#### 3.3.1 必出 observation 类型

1. **按目标层级的输赢归因**
   - 例：`Most losses were decided at business_aggregation, so candidate often reduced cost without preserving split quality.`
2. **按 size bucket 的差异**
   - 例：`Candidate won on large/xlarge cases but lost on small cases.`
3. **按稳定性筛选**
   - 例：`case large_2 was a consistent win across all seeds; screening_small_1 was a consistent loss.`
4. **mixed case 提醒**
   - 例：`Two cases were seed-sensitive (mixed results), suggesting instability rather than a structural gain.`

#### 3.3.2 observation 生成模板

建议不要自由生成自然语言，而是用 rule-based 模板：

```python
if losses_by_decisive_objective["business_aggregation"] >= 2:
    observations.append(
        "Most losses were decided at business_aggregation; candidate often harmed split quality before cost could matter."
    )

if wins_large > 0 and losses_small > 0:
    observations.append(
        "Candidate appears stronger on larger instances than on smaller ones."
    )

if mixed_cases > 0:
    observations.append(
        f"{mixed_cases} case(s) showed seed-sensitive behavior; treat gains there as unstable."
    )
```

### 3.4 token 预算下的裁剪策略

不是全量 dump。建议采用四级裁剪：

#### Level 1：按轮裁剪

- 最近 **3 轮**：保留 aggregate + pattern + selected cases
- 更早 **第 4~8 轮**：只保留 aggregate + 一行 pattern 摘要
- 更老：不展示

#### Level 2：按 case 裁剪

每轮最多展示 **4 个 case**，优先级：

1. consistent loss
2. consistent win
3. mixed case
4. 极端 delta case
5. 其余按 size bucket 覆盖补齐

目的是让 prompt 同时看到：

- 明确失败样本
- 明确成功样本
- 不稳定样本
- 不同规模样本

#### Level 3：按字段裁剪

默认只显示：

- dominant_result
- W/L/T
- seed_consistency
- decisive_objective
- 3 个 delta
- 3~4 个 case feature

不显示：

- 每个 seed 的逐条 pair 结果
- 原始 objective 全量字典
- solver 的具体 output path / JSON 内容

#### Level 4：pair-level 仅按需升级

只在 case 的 `dominant_result == mixed` 且该轮被选中时，追加 1 行 seed 展开：

```text
  pair_detail: seed42=win(cost), seed43=loss(business_aggregation), seed1042=tie
```

这样只在最需要解释“不稳定性”的地方支付 token。

---

## 4. 评估维度分解

### 4.1 当前逻辑的真实分解

从 `scion/protocol/evaluation.py` 看，当前实现实际上是：

1. 先最小化 `subcategory_splits`
2. 若相等，再最小化 `total_cost`
3. 否则 tie

也就是说，当前代码里还**没有实现效率维度**，但设计约束已经要求按：

- 业务聚合 > 成本 > 效率

因此这里建议分两层处理：

1. **v1 文档和数据结构按三层设计**，便于将来扩展
2. **当前代码先落地前两层**，效率字段允许缺省

### 4.2 面向 LLM 的可读维度命名

不建议直接把 prompt 写成 `subcategory_splits`。建议映射成面向 reasoning 的稳定术语：

| 内部字段 | prompt 命名 | 含义 |
|---|---|---|
| `subcategory_splits` | `business_aggregation` / `splits` | 越少越好；优先级最高 |
| `total_cost` | `cost` | 越少越好；第二优先级 |
| `route_count` 或未来效率指标 | `efficiency` / `routes` | 越少越好；第三优先级 |

建议内部仍保存原字段名，渲染时再映射。

### 4.3 每个维度的 delta 如何计算

统一约定：**正数表示 candidate 更好**。

#### 4.3.1 业务聚合

```python
delta_subcategory_splits = champ_splits - cand_splits
```

- 正数：candidate 减少了 splits
- 负数：candidate 增加了 splits
- 0：该维度打平

#### 4.3.2 成本

```python
delta_total_cost = champ_cost - cand_cost
```

- 正数：candidate 降低了成本
- 负数：candidate 提高了成本
- 0：打平

#### 4.3.3 效率

若当前 solver output 暂无效率字段，可先支持可选键：

```python
cand_routes = candidate_objective.get("route_count")
champ_routes = champion_objective.get("route_count")

if cand_routes is not None and champ_routes is not None:
    delta_route_count = champ_routes - cand_routes
else:
    delta_route_count = None
```

v1 推荐优先使用 `route_count` 作为效率代理，因为它可读、简单、与 VRP operator 行为高度相关。

### 4.4 决胜层级如何计算

新增：

```python
def compare_with_breakdown(candidate_objective: dict, champion_objective: dict) -> tuple[str, ObjectiveBreakdown]:
    ...
```

建议逻辑：

```python
if cand_splits < champ_splits:
    comparison = "win"
    decisive = "business_aggregation"
elif cand_splits > champ_splits:
    comparison = "loss"
    decisive = "business_aggregation"
elif cand_cost < champ_cost:
    comparison = "win"
    decisive = "cost"
elif cand_cost > champ_cost:
    comparison = "loss"
    decisive = "cost"
elif route_count_available:
    if cand_routes < champ_routes:
        comparison = "win"
        decisive = "efficiency"
    elif cand_routes > champ_routes:
        comparison = "loss"
        decisive = "efficiency"
    else:
        comparison = "tie"
        decisive = "tie"
else:
    comparison = "tie"
    decisive = "tie"
```

### 4.5 case 特征如何计算和呈现

为了支持“赢了的 instance 有什么共同特征”，建议加入轻量 case 特征提取器：

```python
@dataclass(frozen=True)
class CaseFeatures:
    size_bucket: str                  # small / medium / large / xlarge
    n_orders: Optional[int] = None
    n_locked_orders: Optional[int] = None
    locked_ratio: Optional[float] = None
    n_regions: Optional[int] = None
    hazard_ratio: Optional[float] = None
    path_stem: Optional[str] = None
```

### 4.5.1 最小可行版本

如果当前 protocol 层拿不到 instance 内容，先做**路径级特征**：

- `path_stem`：从文件名提取，如 `large_2`
- `size_bucket`：从命名规则推断，如 `small|medium|large|xlarge`

### 4.5.2 更好的版本

若实例 JSON 可轻量读取，再补充：

- `n_orders`
- `n_locked_orders`
- `n_regions`
- `hazard_ratio`

这些信息足以支撑 LLM 做更有针对性的 hypothesis。

---

## 5. 实现计划

### 5.1 需要修改的文件

#### A. `scion/core/models.py`

新增 dataclass：

- `ObjectiveBreakdown`
- `PairwiseCaseFeedback`
- `CaseAggregateFeedback`
- `ScreeningPatternSummary`
- 可选：`CaseFeatures`

修改：

- `ProtocolResult` 增加 `pair_feedback` / `case_feedback` / `pattern_summary`

改动量：**中等（~80-140 LOC）**

#### B. `scion/protocol/evaluation.py`

新增函数：

- `compare_with_breakdown()`
- `compute_objective_breakdown()`
- 可选：`extract_efficiency_metric()`

保留兼容：

- `lexicographic_compare()` 可内部调用新函数后返回 `comparison`
- `compute_delta()` 可继续返回 cost delta，供旧代码使用

改动量：**小到中等（~40-90 LOC）**

#### C. `scion/protocol/experiment.py`

新增：

- pair feedback 生成
- case 聚合
- pattern summary 构建
- metrics JSON 扩展
- screening 阶段把结构化详情塞进 `ProtocolResult`

建议新增若干 helper：

- `_extract_case_features(case_path)`
- `_aggregate_case_feedback(pair_feedback)`
- `_build_screening_pattern_summary(case_feedback)`

改动量：**中等（~120-220 LOC）**

#### D. `scion/proposal/context_manager.py`

重点改：

- `_build_experiment_history()`
- 新增 `_render_pattern_summary()`
- 新增 `_render_case_feedback()`
- 新增 `_select_case_feedback_for_prompt()`
- 可选：引入简单预算对象 `PromptBudget`

改动量：**中等（~120-220 LOC）**

#### E. `scion/proposal/engine.py`

大概率**无需逻辑改动**，因为上下文字段名 `experiment_history` 不变。

若要做得更稳，可在 `_split_hypothesis_context()` 的 task 段增加一句显式指令：

```text
Use the pattern_summary and selected_cases blocks to identify where the previous operator won/lost and why.
```

改动量：**小（~5-15 LOC）**

#### F. 架构文档 / 设计文档

- 本文档已作为新设计记录
- 若后续落实，建议同步更新 architecture 文档里的 exposure control 章节

### 5.2 建议的落地顺序

#### Phase 1：先打通结构化数据闭环

1. 改 `models.py`
2. 改 `evaluation.py`
3. 改 `experiment.py`
4. 让 `ProtocolResult` 能携带 case feedback

此阶段先不进 prompt，也要先把 JSON 落出来，方便离线检查。

#### Phase 2：ContextManager 渲染

1. 渲染 pattern summary
2. 渲染 selected cases
3. 接入最近 3 轮 history
4. 跑几轮 campaign，看 hypothesis 是否更具体

#### Phase 3：特征增强

1. 从路径推断 `size_bucket`
2. 若实例格式稳定，再补 `n_orders / locked_ratio / region_count`
3. 优化 case 选择器

### 5.3 向后兼容性

总体上**向后兼容性风险较低**。

#### 兼容点

1. `ProtocolResult` 新增字段给默认值即可，不破坏现有构造
2. `lexicographic_compare()` / `compute_delta()` 旧接口可以保留
3. `ContextManager` 若遇到旧 `ProtocolResult` 没有 case data，可自动降级为当前 aggregate 渲染

#### 潜在风险

1. 若有测试严格比较 `ProtocolResult` 的 dataclass 完整相等，需要同步更新
2. 若 `raw_metrics_ref` 的 JSON 消费方假设格式固定，需要兼容旧 schema
3. 若未来 validation/frozen 也误传了 case-level 数据，会破坏 exposure control，需要显式限制

### 5.4 边界情况

#### 边界 1：没有有效 pair

即当前已有的 `NO_VALID_RUNS` 场景。

建议：

- `pair_feedback=()`
- `case_feedback=()`
- `pattern_summary=None`
- prompt 中只保留 aggregate failure

#### 边界 2：某些 objective 缺失

例如当前没有 `route_count`。

建议：

- `delta_route_count=None`
- `decisive_objective` 不依赖该字段时照常计算
- 渲染时显示为 `routes=NA`

#### 边界 3：同一个 case 在 seed 上完全分裂

例如 2 win / 2 loss。

建议：

- `dominant_result="mixed"`
- `seed_consistency=0.5`
- 进入 selected cases 的优先级提高

#### 边界 4：create_new 动作没有 target_file

这不影响 case feedback；渲染时 `hypothesis: {change_locus}/create_new` 即可。

#### 边界 5：修改后的 champion 更新导致旧 case 特征 schema 变化

建议 metrics JSON 中显式写版本：

```json
{
  "schema_version": "case-feedback-v1",
  ...
}
```

---

## 6. Token 预算分析

### 6.1 当前增量的量级估算

典型 screening：

- 3 instances × 2~4 seeds = 6~12 pairs

如果把所有 pair 全量展开到 prompt，大致会是：

- 每个 pair 约 25~45 tokens
- 6~12 pairs ≈ 150~540 tokens / round
- 最近 8 轮就是 1200~4300 tokens

这是不划算的，因为其中大量信息重复：

- 同一 case 的 features 每个 seed 都重复
- 多个 seed 的结论常常可以压成 W/L/T + consistency
- 多数 round 的历史价值会快速衰减

### 6.2 推荐预算模型

#### 每轮 screening history 的预算上限

建议每轮最多：

- aggregate 行：40~60 tokens
- pattern summary：80~140 tokens
- selected cases（3~4 个）：150~280 tokens
- mixed case 的 seed detail（可选 1 个）：20~40 tokens

合计：**约 270~520 tokens / round**

#### 对最近历史的预算建议

- 最近 3 轮：3 × 270~520 = **810~1560 tokens**
- 更早 4~8 轮仅 aggregate：每轮 30~50 tokens，共 **120~250 tokens**

总计大约：**930~1810 tokens**

这个量级对当前 Scion hypothesis prompt 是可以接受的，尤其考虑你已经做了 cache，把大块 champion code 放在 system cache 里。

### 6.3 为什么 case-level 比 pair-level 更划算

假设 3 个 case、每个 case 4 个 seed：

#### 全量 pair-level

12 条 pair × 35 tokens ≈ 420 tokens

#### case-level 压缩

3 条 case × 45 tokens + pattern 120 tokens ≈ 255 tokens

而信息密度更高，因为它直接回答：

- 稳不稳定
- 在哪个维度赢/输
- 什么类型的 case 出问题

### 6.4 推荐裁剪策略（最终版）

建议按以下固定规则：

#### 规则 A：最近 3 轮有 case detail

- `round[-1], round[-2], round[-3]`
- 展示 pattern + 最多 4 case

#### 规则 B：更早历史只保留 aggregate

- `round[-4]` 到 `round[-8]`
- 只保留一行：

```text
Round 5 [CONTINUE_EXPLORE] screening: win_rate=0.33 median_cost_delta=+12.0 outcome=fail
```

#### 规则 C：selected cases 的选择算法

建议评分函数：

```python
score = 0
if dominant_result == "loss": score += 5
if dominant_result == "win": score += 4
if dominant_result == "mixed": score += 4
if seed_consistency >= 0.99: score += 2
score += min(abs(median_delta_total_cost or 0) / 100, 3)
if size_bucket not yet covered: score += 2
if decisive_objective == "business_aggregation": score += 2
```

然后按分数降序选 4 个，同时尽量覆盖不同 size bucket。

#### 规则 D：只有 mixed case 才展示 pair detail

这能把 token 花在最难解释的地方。

### 6.5 建议的默认 prompt 输出规模

建议默认配置：

```python
MAX_DETAILED_ROUNDS = 3
MAX_AGGREGATE_ONLY_ROUNDS = 5
MAX_CASES_PER_ROUND = 4
MAX_PAIR_DETAILS_PER_ROUND = 1
```

这是一个足够保守、但信息显著增强的起点。

---

## 7. 推荐的最小实现方案（我建议先这么做）

如果你想先低风险验证效果，我建议按下面的 MVP 顺序落：

### MVP-1：先支持前两级目标

只做：

- `business_aggregation = subcategory_splits`
- `cost = total_cost`
- efficiency 先留空

### MVP-2：case 特征先只做路径级

只提取：

- `case_id`
- `path_stem`
- `size_bucket`

这样不需要碰实例解析逻辑。

### MVP-3：prompt 中只给 case-level，不给 pair-level

每轮只显示：

- pattern summary
- 3 个 selected cases

先观察 hypothesis 质量是否提升；如果足够，就没必要更重。

### MVP-4：保留 pair-level 到 JSON，不默认进 prompt

这样离线排查仍然有全量证据，但 prompt 不炸。

---

## 8. 总结

这次设计的核心不是“把更多日志塞给 LLM”，而是把 screening 结果从**标量反馈**升级为**结构化、可归因、可裁剪的反馈**。

推荐方案的核心点：

1. **在 ProtocolResult 中增加三层结构**：pair / case / pattern
2. **StepRecord 不必改单独字段**，继续复用 `protocol_result`
3. **ContextManager 只向 hypothesis prompt 暴露 screening 的 case-level 摘要**
4. **字典序比较必须显式记录 decisive objective**，否则 LLM 无法知道输赢原因
5. **token 控制靠“最近轮详细 + 更早轮 aggregate + 每轮精选 case”**

如果只让我选一个最值得先做的点，我会选：

> **先实现 `compare_with_breakdown()` + `case_feedback` + `pattern_summary`，然后把最近 3 轮的精选 case 放进 `experiment_history`。**

这一步投入不大，但会直接改变 LLM 生成 hypothesis 时的信息结构，最有可能提升下一轮 proposal 的针对性。