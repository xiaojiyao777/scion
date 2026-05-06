# Scion v0.3 设计方案 (Draft v2)

*Date: 2026-04-18 (updated)*
*Author: BigBOSS + Cris*
*Status: **Draft v2 — 根据 BigBOSS 定位反馈重构***
*Lineage: v0.2-final (cf50429) → v0.3 Draft v1 → **v0.3 Draft v2**（本文档）*

---

## 0. 文档定位

本文档是 **Scion v0.3 的开发总纲**，整合以下散落信息为一份权威规划：

- `docs/v0.2-final-state.md` 第 14 章技术债清单（D01-D17）
- `docs/archive/v0.2/understanding/08-known-issues-roadmap.md`
- `docs/archive/v0.2/sprint-g-summary.md` 八个 v0.3 Backlog 专题
- `docs/archive/v0.2/sprint-j-plan.md` §5/§6/§7 的 J4/J5/J6 详细设计
- `docs/archive/v0.2/v0.2-completion-report.md` §5 遗留问题表
- F6 实验发现（weight opt 生产数据失效、compute_delta 共用 scoring 的根因）
- BigBOSS 2026-04-18 定位反馈（§1.1）

所有 v0.3 开发工作以本文档为准；历史 sprint 文档不再更新。

---

## 1. v0.3 目标与边界

### 1.1 定位（BigBOSS 2026-04-18 确认）

> **工程固化 + 大规模验证 + 技术债清理 + 问题定义解耦 + 搜索研究体系化**

五个相互关联的目标，**排他性明确**：

| 目标 | 含义 |
|---|---|
| **工程固化** | v0.2 已铺未接通的骨架全部通电（D01/D02/D03/D04/D08） |
| **大规模验证** | 多 campaign 统计矩阵 + MILP gap 基线，把"搜索研究"当成研究对象本身 |
| **技术债清理** | D05-D17 全部消化，代码可读性到达可接受水平 |
| **问题定义解耦** | Scion 核心代码从 warehouse_delivery 语义中剥离，problem.yaml 驱动 prompt/oracle/objective |
| **搜索研究体系化** | weight opt / saturation / search memory / classifier 作为**研究机制的系统设计**，不是零散补丁 |

### 1.2 v0.3 做什么

- **解耦**：Scion 核心 = 通用组合优化研究框架；warehouse_delivery = 第一个 ProblemSpec instance
- **接电工程**：J5 Classifier、family_id 持久化、SearchMemory 持久化、async weight opt 闭环、token usage 持久化
- **生产数据 enable**：weight opt scoring 独立化，cost-only 场景重新可优化
- **早停**：自动平台期检测
- **绝对基线**：MILP 精确解集成（仅 `surrogate/` 内的 solver，v0.3 负责集成到 campaign）
- **大规模验证实验设计**：3 model × 2 problem_variant × 多 seed 统计矩阵（§13）
- **Tech debt**：D05/D09/D11/D12/D13/D14/D15/D16/D17 按成本收益决定做不做

### 1.3 v0.3 不做什么

- ❌ **Shadow deployment / 生产接入**（v1.0）
- ❌ **结构级搜索**（修改 solver 本身，v1.0）
- ❌ **第二个 ProblemSpec 的完整接入**（v0.3 做**解耦骨架**让 v1.0 能快速接，不做第二个 problem 本身）
- ❌ **论文 ablation 矩阵**（研究材料准备 ≠ 开发迭代；v0.3 验证实验产物可被未来论文引用，但 v0.3 不为发表做）
- ❌ **FunSearch-style 重写** / 框架大改

### 1.4 Sprint 顺序（BigBOSS 确认：N → O → P → Q）

- **Sprint N (v0.3-core)**：解耦 + P0 四项
- **Sprint O (memory-layer)**：语义记忆与失败智能（J5 接电是核心）
- **Sprint P (context-enrich)**：LLM 上下文升级与 V5 诊断升级
- **Sprint Q (cleanup + validation)**：tech debt + 大规模验证实验

---

## 2. 工作项总表

### 2.1 16 个工作项（v1 草案 14 个 + 新增 W15 解耦 + W16 验证实验）

| # | 代号 | 内容 | 优先级 | Sprint | 来源 |
|---|---|---|---|---|---|
| **W15** | **PROBLEM-DECOUPLE** | Scion 核心与 warehouse_delivery 解耦，problem.yaml 驱动 prompt/oracle/objective | **P0** | **N** | **BigBOSS 定位反馈** |
| W1 | SCORING-DECOUPLE | Weight opt scoring 独立化 + 生产数据 cost-dominant 模式 | P0 | N | D07 / F6 |
| W2 | ASYNC-WEIGHT-OPT | 补齐 STALE_WEIGHT_UPDATE writer，完成 async + reconcile 闭环 | P0 | N | D04 / J4 |
| W3 | EARLY-STOP | Plateau 检测 + 自动早停 | P0 | N | F4 浪费 |
| W4 | MILP-INTEGRATION | 集成 CC 产出的 MILP solver 到 campaign，算 optimality gap | P0 | N | 08-roadmap |
| W7 | CLASSIFIER-WIRE | J5 HypothesisFamilyClassifier 接入主路径（**BigBOSS 要求 P0→O**） | **P0** | **O** | D01 / J5 |
| W5 | SEARCH-MEM-PERSIST | SearchMemory 持久化到 SQLite | P1 | O | D03 |
| W6 | FAMILY-ID-PERSIST | HypothesisRecord.family_id 入 hypotheses 表 | P1 | O | D02 |
| W8 | FAILURE-ROUTER-V2 | 跨分支失败聚合 + LLM 上下文注入已知危险模式 | P1 | O | 09-failure-router |
| W9 | CAMPAIGN-JOURNAL | 完整 hypothesis、跨 branch history、champion 演化代码进 LLM 上下文 | P1 | P | sprint-g |
| W10 | WEIGHT-OPT-FEEDBACK | 最新 weight opt 结果作为"算子贡献估计"注入 Round 1 prompt | P1 | P | sprint-g |
| W11 | V5-DIAGNOSIS-3TIER | V5 分 ENV / CANDIDATE / UNKNOWN 三类 | P2 | P | D06 / v0.2 A2 |
| W12 | CANARY-UPGRADE | 手工对抗实例 + 失败实例自动积累 | P2 | P | 11-canary |
| W13 | TOKEN-USAGE-PERSIST | experiment_events 表 prompt/completion_tokens 写入 | P2 | Q | D08 |
| W14 | TECH-DEBT-CLEANUP | D05/D09/D11/D12 清理 | P3 | Q | D05/D09/D11/D12 |
| **W16** | **VALIDATION-CAMPAIGN** | **大规模验证实验矩阵（3 model × 2 data × 3 seed = 18 campaigns）** | **P0** | **Q** | **BigBOSS 定位反馈** |

### 2.2 Sprint 工作量估算

| Sprint | 工作项 | 代码量 | Tests | 预计工时 |
|---|---|---|---|---|
| N | W15 + W1 + W2 + W3 + W4 | ~2500-3000 行 | 50+ | CC 24-32h + Cris review 8h |
| O | W7 + W5 + W6 + W8 | ~1500-2000 行 | 35+ | CC 16-20h + Cris review 5h |
| P | W9 + W10 + W11 + W12 | ~1500 行 | 25+ | CC 16-20h + Cris review 5h |
| Q | W13 + W14 + W16 | ~500 行 + 验证实验 ~30h wall-clock | 10+ | CC 4h + Cris run 30h + review 3h |

**v0.3 总预估**：4-6 周（含实验 wall-clock）。最小可发版 = Sprint N + O 完成。

---

## 3. W15 — Problem Definition Decoupling（P0，Sprint N 核心）

### 3.1 背景

当前 Scion 核心代码对 warehouse_delivery 问题有深度耦合：

| 耦合位置 | 当前状态 |
|---|---|
| `proposal/context_manager.py` | prompt 里 hard-code "subcategory_splits / vehicle_type / pickup_name" 术语 |
| `proposal/saturation.py` | hard-code "splits 有绝对下界"的饱和判断逻辑 |
| `verification/feasibility.py` | `from surrogate.oracle import is_feasible` 硬依赖 |
| `verification/objective.py` | hard-code 读 `Solution.objective.subcategory_splits / total_cost` |
| `protocol/evaluation.py:compute_delta` | 目标函数字典序写死 `(splits, cost, runtime)` |
| `problems/warehouse_delivery/problem.yaml` | 只有参数，无 semantics / operator-interface-description / llm-hint |

**工程固化**要求：Scion 核心代码零 warehouse 术语；新 problem 接入只改 `problems/<name>/` 目录 + 配套 surrogate-style solver，不改 Scion 核心。

### 3.2 设计方案

#### (A) 扩展 `ProblemSpec` schema

```yaml
# problems/warehouse_delivery/problem.yaml
problem:
  id: warehouse_delivery
  display_name: "仓配协同优化"
  
  # ---- 问题语义（供 LLM 理解）----
  semantics:
    description: |
      Assign orders to vehicles to minimize (primary) the number of subcategory splits
      and (secondary) total vehicle cost. Each vehicle has a type with capacity and cost.
    domain_terms:
      - name: order
        definition: A shipment request with pallets, subcategory, region, pickup point
      - name: subcategory
        definition: A vehicle-compatibility group (e.g., temperature requirement)
      # ... 由 problem.yaml 声明，不在代码里硬编码
  
  # ---- 目标函数（字典序 + scoring 接口）----
  objectives:
    - name: subcategory_splits
      type: int
      direction: minimize
      priority: 1
      has_absolute_lower_bound: true   # 饱和检测依据
      lower_bound_rule: "|distinct(order.subcategory)| - 1"
    - name: total_cost
      type: int
      direction: minimize
      priority: 2
    - name: runtime_seconds
      type: float
      direction: minimize
      priority: 3
      tolerance: 2.0  # 字典序中 ≤ 2s 差异视为 tie
  
  # ---- Oracle（动态 import）----
  oracle:
    module: "surrogate.oracle"       # 由 Scion 动态 import
    is_feasible_fn: "is_feasible"
    evaluate_fn: "evaluate"
  
  # ---- Operator interface（供 LLM 生成代码）----
  operator_interface:
    base_class: "surrogate.operators.base.Operator"
    execute_signature: "execute(solution: Solution, rng: Random) -> Solution"
    solution_class: "surrogate.models.Solution"
    categories:
      - name: order_level
        description: "Modify order-to-vehicle assignments"
      - name: vehicle_level
        description: "Modify vehicle configurations (add/remove/change type)"
  
  # ---- LLM hint（prompt 模板片段）----
  llm_hints:
    problem_intro: |
      You are improving operators for a warehouse-delivery VRP-like problem.
      The core challenge is assigning heterogeneous orders to vehicles while
      minimizing subcategory splits (primary) and total cost (secondary).
    improvement_axes:
      - "reduce subcategory splits by consolidating same-subcategory orders"
      - "reduce vehicle count by repacking or upgrading vehicle types"
      - "eliminate weak vehicles (low utilization)"
```

#### (B) Scion 核心改造

**1. `proposal/context_manager.py`：**
- 删除所有 warehouse 术语 hard-code
- 从 `problem_spec.llm_hints.problem_intro` 读介绍段
- 从 `problem_spec.operator_interface` 渲染接口说明
- 从 `problem_spec.semantics.domain_terms` 渲染术语表

**2. `proposal/saturation.py`：**
- `ChampionSaturationAnalyzer` 接受 `problem_spec.objectives` 列表
- 对每个 `has_absolute_lower_bound=True` 的目标，计算实际下界（渲染 `lower_bound_rule`）
- 当前 splits-specific 逻辑改为通用 `is_at_absolute_minimum(objective_name)` 接口

**3. `verification/feasibility.py` / `objective.py`：**
- 动态 import：`importlib.import_module(problem_spec.oracle.module).is_feasible`
- Cache import 结果，避免每次 verify 都 reimport

**4. `protocol/evaluation.py:compute_delta`：**
- 删除 hard-code `(splits, cost, ...)` 元组
- 从 `problem_spec.objectives` 按 priority 排序比较
- `tolerance` 字段驱动 tie 判定
- **删除 SCION_SPLITS_WEIGHT 环境变量**（和 W1 合并实施）

**5. `core/models.py:Objective`：**
- 从 `@dataclass(subcategory_splits: int, total_cost: float, ...)` 改为 `dict[str, Union[int, float]]`
- 保留一个 `@cached_property` 访问器用于兼容

#### (C) 迁移检查

- 所有单元测试 pass
- F6-A 配置跑一次 minimal campaign（3-5 轮），验证新 problem.yaml 驱动下行为与 v0.2 一致
- 预留 `problems/toy_tsp/` 占位目录（只放空 problem.yaml 和 README），证明接入第二个 problem 只需新增目录

### 3.3 影响范围

| 文件 | 变更 |
|---|---|
| `problems/warehouse_delivery/problem.yaml` | **大幅扩充** semantics/objectives/oracle/operator_interface/llm_hints |
| `scion/config/problem.py` | `ProblemSpec` Pydantic model 增加新字段 |
| `scion/proposal/context_manager.py` | 移除 warehouse 术语 hard-code，改 yaml 驱动 |
| `scion/proposal/saturation.py` | `ChampionSaturationAnalyzer` 通用化 |
| `scion/verification/feasibility.py` + `objective.py` | 动态 import oracle |
| `scion/protocol/evaluation.py` | `compute_delta` 通用化 |
| `scion/core/models.py` | `Objective` 改 dict 化 |
| `problems/toy_tsp/` | **新建空占位** |
| Tests | `test_problem_spec_yaml.py` 覆盖新字段；`test_compute_delta_generic.py` 覆盖通用比较器；现有测试修复 |

### 3.4 验收标准

1. Scion `scion/` 目录下 `grep -ri "subcategory\|vehicle_type\|pickup_name" --include="*.py"` **无匹配**（术语解耦）
2. `grep -ri "surrogate" scion/scion/ --include="*.py"` **只命中 dynamic import 路径字符串和 test fixtures**
3. F6-A 配置 minimal campaign（5 轮）结果与 v0.2 bit-for-bit 一致（或 objective 值一致）
4. `problems/toy_tsp/problem.yaml` 占位文件 lint 通过
5. 文档：`design/scion-problem-interface-v1.md` 新建，说明如何接入新 problem

---

## 4. W1 — Weight Opt Scoring 独立化（P0，Sprint N）

*保持 Draft v1 §3 内容不变*，关键点：

- 拆出 `scion/parameter/scoring.py`，3 个实现：`LexicographicScoring` / `CostDominantScoring` / `AdaptiveScoring`
- `ParameterSearchConfig.scoring: ScoringConfig` 子模型
- 删除 `SCION_SPLITS_WEIGHT` 环境变量（与 W15 的 compute_delta 改造一起做）
- **合成数据问题**默认 `lexicographic`，**生产数据问题**默认 `adaptive`

**验收**：
- 合成数据 campaign `lexicographic` 下 weight opt improved ≥ 3/3
- 生产数据 campaign `adaptive` 下 **至少 1 次 weight opt improved=True**
- 实验协议 win/loss 判定结果与 v0.2 一致

---

## 5. W2 — Async Weight Opt 闭环（P0，Sprint N）

*保持 Draft v1 §4 内容不变*，关键点：

- `mark_all_stale` 加 `reason` 参数，区分 `"champion_promoted"` vs `"weight_updated"`
- 后台 weight opt 成功 → `mark_all_stale(reason="weight_updated")` → 写 `STALE_WEIGHT_UPDATE`
- reconcile 对 `STALE_WEIGHT_UPDATE` 只重做 screening，对 `STALE` 走完整 reconcile
- Double-promote 取消信号 + 15min 超时保护
- 默认 `async_mode: bool = True`

**验收**：
- 一次 promote 后 activeBranch 能走 `EXPLORE → STALE_WEIGHT_UPDATE → EXPLORE` 路径
- F6-A 同配置 campaign 总耗时 -40%
- 改善率不劣于 F6-A（3/3 improved）

---

## 6. W3 — 自动平台期检测与早停（P0，Sprint N）

*保持 Draft v1 §5 内容不变*，关键点：

- 新建 `scion/core/plateau.py`
- 三种 plateau 信号：`saturated_and_stagnant` / `no_progress` / `family_exhausted`
- `TerminationConfig.early_stop=True` 默认开
- `PlateauConfig.min_rounds_after_promote=30` 保护边界

**验收**：
- 复现 F4-A 数据，campaign 在 R80-R120 之间停止
- 保护边界：刚 promote 完不会误停
- Plateau 触发时写 campaign_summary 诊断快照

---

## 7. W4 — MILP Integration（P0，Sprint N）

### 7.1 调整（BigBOSS 2026-04-18 反馈）

**MILP 扩展范围**：

- **小实例 s01/s02/s03 (20-40 orders)**：必须求得最优解，作为主 gap 基线
- **中等实例 ml01-ml04 (73-93 orders)**：**能跑就跑，跑不动（超过 time_limit=1800s）就算了**，报告 best bound + gap
- **大实例 l/xl/fro_x (150+ orders)**：不尝试

### 7.2 实现点

*保持 Draft v1 §6 内容不变*，补充：

- `scion optimum compute` 命令加 `--attempt-medium` flag，默认 False（只跑 s 系列）
- ml 系列超时时写 `status="timeout"` + `best_feasible_obj` + `dual_bound`
- Gap 曲线显示 s 系列实线，ml 系列虚线（带 bound 不确定区间）

---

## 8. W7 — J5 Classifier 接电（P0，Sprint O）

### 8.1 升级依据（BigBOSS 反馈：关键词不够）

F4/F5 实验显示关键词法的局限：
- modify + vehicle_level + "让同品类订单聚合" ≡ create_new + order_level + "subcategory 合并"：**关键词分入不同 family，实际是同一方向**
- "evacuate / evict / purify / drain" 都是"清空低效车辆"族：关键词法无法识别同义

v0.2 `HypothesisFamilyClassifier` 只在 tests 里用。v0.3 必须接入主路径。

### 8.2 设计方案

*采用 sprint-j-plan §6.2*，关键点：

- **独立调用**：与主 proposal LLM 完全隔离；不注入"哪些家族已失败"信息
- **模型**：Sonnet 级即可（`SCION_CLASSIFIER_MODEL` env，默认 `claude-sonnet-4-6`）
- **Taxonomy**：9 类预定义（v0.2 classifier.py 已有）+ `NEW_FAMILY` 兜底
- **异步调用**：Round 1 hypothesis 生成后异步 classify，不阻塞主循环
- **降级**：classifier 调用失败 → 回退到 `_extract_mechanism_label` 关键词法（不阻塞）
- **超时**：≤ 3s（Sonnet Flash 级调用）

### 8.3 接入点

| 位置 | 改动 |
|---|---|
| `scion/core/campaign.py:run_one_step` | Round 1 hypothesis 生成后 spawn classifier thread |
| `scion/proposal/search_memory.py:record_hypothesis` | 优先用 classifier label，无结果回退 `_extract_mechanism_label` |
| `scion/lineage/branch_store.py:HypothesisStore.save` | 写入 `family_id`（与 W6 配合） |

### 8.4 验收

- 关键词法与 classifier 在同一批历史 hypothesis 上的分类结果对比报告：至少 15% 分类差异（说明 classifier 有价值）
- 跑 F4-B replay，classifier 至少识别出 RepackVehiclePair 系列的 "vehicle_elimination_cost" 和 "generic_merge" 差异
- Classifier 失败场景下（API 超时、schema 错误）主循环继续

---

## 9. Sprint O 其他项（P1）

*W5 SearchMemory 持久化 / W6 family_id 入表 / W8 FailureRouter v2 — 保持 Draft v1 §7 内容不变*

**关键接续**：
- W7 Classifier 接电 是 W5/W6 的前提（classifier 产出的 family_id 要能落盘）
- W8 FailureRouter v2 和 W5 共享全局 `failure_registry` 存储

---

## 10. Sprint P — 上下文丰富化与 V5 升级（P1/P2）

*W9 Research Journal / W10 Weight opt 反馈 / W11 V5 三分类 / W12 Canary 升级 — 保持 Draft v1 §8 内容不变*

---

## 11. Sprint Q — Cleanup 与大规模验证（P0/P2/P3）

### 11.1 W13：Token Usage 持久化（D08）

`experiment_events` 表 `prompt_tokens/completion_tokens` 两列已建但 `record_event` 不写。补写入路径；`scion inspect tokens` 命令展示累计用量。

### 11.2 W14：Tech Debt 清理

| # | 项 | 行动 |
|---|---|---|
| D05 | `verification/state_leak.py` 已 deprecated | **删除**文件 |
| D09 | V1-V9 命名不一致 | 统一为 `gate.py` 的外部命名（V1-V9），内部常量批量重命名 |
| D11 | `proposal/schemas.py FIX_TOOL.description` | 同步到新命名 |
| D12 | `[SATURATION DEBUG]` 前缀 | 改为 `logger.debug` 级别 |

D10/D14/D15/D16/D17 按 Draft v1 §10 归档，不做。

### 11.3 W16：大规模验证实验（P0）

**这是 v0.3 "大规模验证"目标的兑现项。**

#### 实验矩阵设计

| 变量 | 取值 |
|---|---|
| **Model** | `claude-opus-4-6` / `claude-sonnet-4-6` / `gpt-5.4`（3 个 proposal model） |
| **Problem variant** | `warehouse_synthetic` (v4 manifest) / `warehouse_prod` (生产实例) |
| **Seed** | 3 个独立 seed（11 / 29 / 47） |
| **Campaign rounds** | 100（W3 早停后实际会更短） |

**总计 3 × 2 × 3 = 18 个 campaigns**，预期总 wall-clock ~30-40h（async weight opt 启用后）。

#### 核心研究问题

v0.3 实验矩阵要回答的问题：

| RQ | 问题 | 对应实验切片 |
|---|---|---|
| RQ1 | **结构搜索** alone 的效果？ | 18 campaigns 全量 promotion / abandon 分布 |
| RQ2 | **参数搜索（weight opt）** alone 的效果？ | 每个 champion 版本的 weight opt improved 比例 |
| RQ3 | **结构 + 参数**叠加收益？ | 全流程 champion → weight opt → reconcile 完整链路的 gap 收敛 |
| RQ4 | **模型对 Scion 的影响**？ | opus vs sonnet vs gpt-5.4 在相同实验协议下的 promote 成功率、算子质量 |
| RQ5 | **合成 vs 生产数据的泛化**？ | 同一 model 在 synthetic vs prod variant 下的 F1/F2 gap 差异 |
| RQ6 | **距最优还有多远**？（配合 W4 MILP） | s01/s02/s03 的 optimality gap 在 18 campaigns 中的分布 |
| RQ7 | **Plateau 早停收益**？ | 18 campaigns 的实际终止轮数 vs 200 轮上限的节省 |

#### 实验产物（进 v0.3 最终报告）

- `reports/v0.3-validation/` 下 18 个 sub-dir，每个含 campaign_summary + gap 图
- 聚合分析：promotion rate、abandon wr 分布、算子类型 coverage
- `reports/v0.3-validation/SUMMARY.md` 一份研究分析，讲述 RQ1-RQ7 答案

#### 工程准备

- Sprint N+O+P 完成后才启动 W16
- 需要确保 async weight opt 稳定（W2）+ early stop 稳定（W3）
- ml 实例可选作为 optional gap 参考（W4 扩展范围）

---

## 12. 分支与 Review 流程

### 12.1 分支策略

- **`master`**：v0.2 归档稳定版，包含 `v0.2-final-state.md` + 文档整理
- **`v0.3-dev`**：v0.3 开发主分支，从 master 起
- **v0.3 完成后**：v0.3-dev → master merge，tag `v0.3.0`

### 12.2 Review Gate

- **每个 W 项完成**：pytest 全绿 + BigBOSS review commit
- **每个 Sprint 结束**：小规模 validation campaign（5-15 轮）+ BigBOSS 认可后进下一 Sprint
- **Sprint N 结束（最关键 checkpoint）**：
  - 解耦是否完整（grep 无 warehouse 术语）
  - Scoring 是否接通（生产数据 improved=True 出现）
  - Async 是否工作（STALE_WEIGHT_UPDATE 有 log）
  - Early stop 是否工作（F4-A replay 正确终止）
  - MILP gap 是否产出

---

## 13. 大规模验证实验的意义（BigBOSS "搜索研究体系化"定位回应）

### 13.1 v0.3 对 Scion 研究价值的核心贡献

v0.1/v0.2 证明"Scion 能跑、能发现改进"。v0.3 要回答**更深的问题**：

1. **Scion 的改进来自哪里**？（结构 vs 参数 vs 两者协同）
2. **LLM 模型能力差异如何传导到 Scion 的研究效率**？（RQ4 的意义）
3. **在什么问题特征下 Scion 有效 / 失效**？（RQ5 的意义：合成泛化 ≠ 生产泛化）
4. **Scion 离 exact 最优差距多少**？（RQ6 的意义：绝对锚）

这些问题的答案构成 Scion 作为**研究框架**本身的评估：不只是"能改进"，还要"改进的机制可解释"。

### 13.2 与 v1.0 的接力

v0.3 的大规模验证**不替代** v1.0 的论文级 ablation，但它产出：
- 稳定的 18 campaigns 数据基线（v1.0 论文用）
- 研究机制效果的结构化报告（v1.0 讨论的素材）
- 问题接入的通用接口（v1.0 多问题族验证的前置）

---

## 14. 已关闭的开放问题

BigBOSS 2026-04-18 回复：

| # | 问题 | 决定 |
|---|---|---|
| Q1 | v0.3 发版定位 | **工程固化 + 大规模验证 + 技术债清理 + 问题解耦 + 搜索研究体系化** |
| Q2 | J5 Classifier 真的需要吗？ | **需要**（关键词法不够）→ 升级为 P0（Sprint O） |
| Q3 | MILP 扩展到 ml 实例？ | **能跑就跑，跑不动就算了**（time_limit=1800s，超时写 bound） |
| Q4 | Shadow deployment | **不纳入**（留 v1.0） |
| Q5 | Sprint 顺序 N→O→P→Q | **接受** |

**新增决策**（本次反馈引入）：

| # | 问题 | 决定 |
|---|---|---|
| Q6 | Scion 核心与 warehouse_delivery 解耦 | **必做**，升级为 W15 P0（Sprint N 核心） |
| Q7 | 大规模验证实验矩阵 | **必做**，W16 进 Sprint Q |

---

## 15. 下一步

1. **BigBOSS review 本 Draft v2**
2. Review 通过 → rename `scion-v0.3-draft.md` → `scion-v0.3-design.md`（去 draft 标签）
3. `git checkout -b v0.3-dev` → Sprint N 启动
4. Sprint N 五个工作项（W15/W1/W2/W3/W4）分别出独立 task spec，CC 独立进程开发
5. W15 是 Sprint N 最大工作项，建议 **优先开始**（后续 W1/W2/W3/W4 都依赖 problem.yaml 驱动的 compute_delta / saturation / ProblemSpec schema）

---

*End of v0.3 Draft v2. Review 通过后定稿。历史 v0.3 backlog 文档（sprint-g-summary, sprint-j-plan, 08-known-issues-roadmap）不再更新，均归档。*
