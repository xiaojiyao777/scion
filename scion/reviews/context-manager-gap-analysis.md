# Scion ContextManager + CreativeLayer Prompt Gap 分析报告

*作者：架构审查 (Cris)*
*日期：2026-04-07*
*参考：scion-architecture-v3.md §5/§15，scion-engineering-arch-v1.md §2.3/§5.3*
*被审文件：scion/proposal/context_manager.py, schemas.py, engine.py*

---

## 一、设计 vs 实现对照表

### 1.1 §5.3 暴露控制矩阵 — Round 1 (Hypothesis) 上下文

| 设计要求（engineering-arch §5.3） | 实现状态 | 说明 |
|---|:---:|---|
| ✅ problem spec 摘要 | ⚠️ 部分实现 | 仅传入 `problem_name`（单个字符串），无问题域描述、约束说明、目标函数定义 |
| ✅ champion 算子代码 | ❌ 未实现 | `pool_summary` 只有算子名+权重+文件路径，**没有代码内容** |
| ✅ 当前分支最新代码（如不同于 champion） | ❌ 未实现 | `build_hypothesis_context` 完全没有 `branch_code` 字段 |
| ✅ 本分支历史结果（结构化摘要） | ⚠️ 部分实现 | 只有 `[status] change_locus/action → target_file`，缺少实验结果（win_rate、delta、failure reason） |
| ✅ 已失败 hypothesis 列表 | ⚠️ 部分实现 | blacklist 只有 `change_locus/action → target_file`，无失败原因、无 evidence_count |
| ✅ 兄弟分支状态（简要） | ⚠️ 部分实现 | 只写"N sibling branches active"，完全无内容 |
| ❌ validation/frozen 细节（禁止暴露） | ✅ 正确隔离 | 无这类数据暴露 |
| ✅ champion 性能统计 (champion_stats) | ❌ 未实现 | 设计文档 §5.2 prompt 模板明确要求 `{{ champion_stats }}`，实现中完全缺失 |
| ✅ operator_categories（枚举约束） | ✅ 实现 | `problem_spec.operator_categories` 正确传入 |

### 1.2 §5.3 暴露控制矩阵 — Round 2 (Code) 上下文

| 设计要求（engineering-arch §5.3） | 实现状态 | 说明 |
|---|:---:|---|
| ✅ problem spec 摘要 | ⚠️ 部分实现 | 仅 `problem_name`，同 Round 1 |
| ✅ approved hypothesis | ✅ 实现 | hypothesis_text, change_locus, action, target_file 均传入 |
| ✅ champion 算子代码 | ⚠️ 部分实现 | `_summarise_champion_code` 只读 `target_file` 对应的单个文件；当 champion.code_snapshot_path 无效或文件不可读时直接返回错误字符串 |
| ✅ 当前 target 文件内容 | ⚠️ 部分实现 | 由 `_summarise_champion_code` 兼顾，但设计上应独立区分 champion 参考代码 vs 当前 target 文件内容 |
| ✅ operator interface spec | ⚠️ 部分实现 | 仅在 prompt 硬编码了 `def execute(self, solution, rng):`，无具体类型签名、无 `Operator` 基类定义、无 `Solution`/`Instance`/`Random` 的接口说明 |
| ✅ import_whitelist | ✅ 实现 | 正确传入 |
| ❌ 历史结果 (禁止暴露) | ✅ 正确隔离 | Round 2 context 无实验统计 |
| ❌ 兄弟分支 (禁止暴露) | ✅ 正确隔离 | Round 2 context 无兄弟分支 |

### 1.3 §5.3 暴露控制矩阵 — Fix 上下文

| 设计要求 | 实现状态 | 说明 |
|---|:---:|---|
| ✅ problem spec 摘要 | ⚠️ 部分实现 | 同上 |
| ✅ 原代码 + 失败详情 | ✅ 实现 | code_content、failure_severity、first_failure、failure_details 均传入 |
| ✅ interface spec | ⚠️ 部分实现 | 同 Round 2 |
| ✅ import whitelist | ✅ 实现 | |
| ❌ champion 代码 (不暴露) | ✅ 正确隔离 | Fix context 确实未包含 champion code |

---

## 二、具体代码问题

### 2.1 champion 算子代码缺失（最严重 Gap）

**文件**：`context_manager.py`
**函数**：`build_hypothesis_context`（约第 37-55 行）
**问题**：`pool_summary = _summarise_pool(champion.operator_pool)` 只输出如下文本：
```
- swap_orders [order_level] weight=0.20 file=operators/swap_orders.py
- move_order [order_level] weight=0.20 file=operators/move_order.py
```
LLM 拿到的是**元数据**，根本看不到算子的实现逻辑。这直接导致 LLM 无法推理"哪里有改进空间"。调试输出的 1129 chars 的 hypothesis prompt 正是因为缺乏实际代码内容而极度简陋。

设计文档明确要求：`champion 算子代码 ✅`（architecture-v3 §5.1，engineering-arch §5.2 `{{ champion_operators }}`）。

**修复方向**：`_summarise_pool` 应该读取每个算子文件的实际代码，而不只是路径。

### 2.2 `_summarise_champion_code` 的失效路径

**文件**：`context_manager.py`
**函数**：`_summarise_champion_code`（约第 108-124 行）
**问题有两处**：

1. `champion.code_snapshot_path` 为空字符串或路径不存在时，直接 fallthrough 到 `return f"(champion code for '{target}' not readable)"`。这个字符串就是调试输出"champion code 不可读"的根因——**code_snapshot_path 在初期可能还没有形成合法快照**。
2. 只读取 `target_file` 对应的单个文件。但 Round 2 的目的是让 LLM 了解整个 champion operator pool 的代码风格和接口模式，仅看目标文件不够。

### 2.3 分支历史只有状态枚举，无实验结果

**文件**：`context_manager.py`
**函数**：`_summarise_hypothesis_history`（约第 130-143 行）
**问题**：
```python
f"  - [{h.status}] {h.change_locus}/{h.action}" + (f" → {h.target_file}" if h.target_file else "")
```
这给 LLM 的信息只是"这件事做了，状态是什么"。没有：
- 为何失败（失败原因码）
- 失败在哪一关（contract/verification/screening）
- 如果 screening 结果是 fail，win_rate 是多少

设计文档 §15.1 要求的是"当前分支最近 N 轮结果（**结构化**）"，包含实验摘要而非只是状态标签。

### 2.4 兄弟分支摘要完全无信息量

**文件**：`context_manager.py`
**函数**：`_summarise_siblings`（约第 149-152 行）
**问题**：
```python
return f"  {len(siblings)} sibling branch(es) currently active."
```
这句话什么实质信息都没有。设计要求是"简要状态"——至少应包含每个兄弟分支当前探索的方向（`change_locus`）、状态（EXPLORE/VALIDATING）和最近假设。否则 LLM 无法判断是否应该"差异化"探索。

### 2.5 problem spec 摘要只传名称

**文件**：`context_manager.py`
**两个函数**：`build_hypothesis_context`（第 47 行）、`build_code_context`（第 64 行）
**问题**：只传 `problem_spec.name`（如 `"warehouse_delivery"`）。
设计要求的是"problem spec 摘要"，应包含：
- 问题域描述（仓配协同，订单→车辆分配）
- 多目标函数（字典序：约束满足 > 成本 > 时间）
- 约束概述（锁定订单不可修改等）
- Solution 结构（`vehicles + assignment`）
- 可用的算子类别（已有，但缺上下文）

没有这些，LLM 对"要优化什么"的理解是零的。

### 2.6 operator interface spec 不够完整

**文件**：`schemas.py`
**位置**：`CODE_PROMPT_TEMPLATE` 中"## Required interface"段（约第 71-74 行）
**问题**：
```
All operator classes MUST implement:
    def execute(self, solution, rng):
        ...
```
只有函数签名，但 LLM 不知道：
- `solution` 的类型是什么（`Solution` dataclass 有哪些字段）
- `rng` 是 `random.Random`（不是全局 random）
- `Instance` 在构造函数里传入（`__init__(self, instance, phase)`）
- `Operator` 基类的要求（必须 deep_copy，不能修改原解）
- 不可操作锁定订单（`locked_vehicle_id is not None`）

这直接导致生成的算子代码很可能违反接口约定，从而触发 Verification Gate。

### 2.7 champion_stats 完全缺失

**文件**：`context_manager.py` + `schemas.py`
**位置**：`build_hypothesis_context` 返回值中没有 `champion_stats` 键；`HYPOTHESIS_PROMPT_TEMPLATE` 没有对应槽位
**问题**：engineering-arch §5.2 明确列出了 `{{ champion_stats }}` 作为 Round 1 必要输入槽位，用于让 LLM 理解 champion 当前的性能弱点（如哪个目标层表现差）。没有这个，LLM 的 `target_weakness` 字段只能是瞎填。

### 2.8 blacklist 缺少失败语义

**文件**：`context_manager.py`
**函数**：`_summarise_blacklist`（约第 145-152 行）
**问题**：blacklist 里只有 `change_locus/action → target_file`，没有失败原因。设计文档 §15.3 的 blacklist 机制包含 `scope_tags`、`evidence_count`、`expiry_round`，这些信息对于 LLM 判断"是否应该尝试类似方向"至关重要。

---

## 三、实际 Prompt 问题分析

### 3.1 Token 预算现状

根据调试输出：
- Hypothesis prompt：**1129 chars**（约 280 tokens）
- Code prompt：**1564 chars**（约 390 tokens）
- Pool 为空
- Champion code 不可读

**结论：当前 prompt 极度欠载，token 预算被严重低估。**

### 3.2 根因分析

**Pool 为空 → `_summarise_pool` 返回 `(empty pool)`**
这意味着 `champion.operator_pool` 字段在测试时是空字典。可能的原因：
1. 初始 champion 未正确从 `registry.yaml` 加载算子池
2. `ChampionState.operator_pool` 在初始化时没有从 surrogate 的 `registry.yaml` 填充

这是一个**数据流问题**，不是 ContextManager 本身的问题。但 ContextManager 对空 pool 没有任何防御性警告，直接生成了一个无意义的 prompt。

**Champion code 不可读 → `_summarise_champion_code` 路径问题**
`champion.code_snapshot_path` 在初始阶段可能是空字符串或路径指向一个尚未建立的快照目录。说明 `CampaignManager.run` 的初始化流程可能没有正确建立初始 champion 快照。

### 3.3 合理的 Token 预算分配（建议）

以 Sonnet 的 200K context window 为基准，单次 proposal 应有足够上下文：

| 内容块 | 当前实际 | 建议预算 | 说明 |
|---|:---:|:---:|---|
| Problem spec 摘要 | ~20 tokens | 200-400 tokens | 问题域描述 + 目标 + 约束概述 |
| Champion 算子代码（全部） | 0（pool 为空/代码不可读） | 1500-3000 tokens | 6个算子，每个约 50-100 行 |
| Champion 性能统计 | 0（缺失） | 50-100 tokens | win_rate, delta 等数值 |
| 分支历史（含失败原因） | ~50 tokens | 200-400 tokens | 最近 5 轮，含结果摘要 |
| Blacklist（含失败语义） | ~20 tokens | 100-200 tokens | 最多 10 条，含原因 |
| 兄弟分支摘要 | ~5 tokens | 50-100 tokens | 每个分支 1 行 |
| 输出 schema 说明 | ~100 tokens | ~100 tokens | 保持现状 |
| **Round 1 总计** | **~280 tokens** | **2200-4300 tokens** | |

| 内容块 | 当前实际 | 建议预算 | 说明 |
|---|:---:|:---:|---|
| Problem spec 摘要 | ~20 tokens | 200-400 tokens | |
| Hypothesis 详情 | ~80 tokens | ~100 tokens | 保持现状 |
| Champion 目标文件代码 | 0（不可读） | 500-1500 tokens | 目标文件完整代码 |
| 相关 champion 算子参考 | 0 | 300-600 tokens | 同类算子 1-2 个完整代码 |
| Operator interface spec | ~30 tokens | 150-300 tokens | 含 Solution/Instance 结构 |
| Import whitelist | ~20 tokens | ~20 tokens | 保持现状 |
| **Round 2 总计** | **~390 tokens** | **1270-2920 tokens** | |

**核心结论**：当前 token 使用量约为合理需求的 **1/10**，不是"省 token"，是"上下文真空"。

---

## 四、CC 上下文管理启示

### 4.1 CC 的三级上下文管理机制

从 `02-query-engine.md` 分析，CC 的上下文管理主要靠以下机制：

1. **结果截断（End Truncation）**：工具执行结果超过 `maxResultSizeChars` 时，保留预览 + 持久化全量到磁盘。模型只看预览，需要时再读文件。
2. **懒加载（On-demand）**：代码内容不预先全部推入 context，而是在 agent 需要时用 `read_file` 工具动态获取。
3. **紧凑压缩（Compact/Collapse）**：对话历史过长时，触发 `applyContextManagement` 做摘要压缩。

### 4.2 对 Scion 有价值的设计模式

**模式 1：代码按需注入，而非全量预填充**

CC 不会把项目所有代码全塞进 prompt，而是先给 LLM 一个"目录视图"，让 LLM 自己决定要读哪些文件。Scion 的 Round 1 可以借鉴：
- 先提供 pool 中各算子的**函数签名 + docstring 摘要**（类似 CC 的文件列表视图）
- 在 prompt 中标记"如果需要某算子完整代码，可以在 target_file 中指定"

但 Scion 有一个关键区别：它是**单轮推理**（直接 API 调用，非 agentic loop）。无法像 CC 一样在循环中按需取文件。因此 Scion 必须在一次 prompt 中提供足够上下文，**不能依赖多轮工具调用**。

**模式 2：大输出截断 + 磁盘落盘**

CC 的 BashTool 会截断大输出，保留预览。Scion 的 `_summarise_champion_code` 已经有 3000 chars 截断，这是对的。但问题是截断策略应该是"取最重要的部分"而非"取前 N 字节"——对于算子代码，关键逻辑通常在 `execute` 方法体，而不是 import 和 docstring。

**建议**：截断时优先保留 `execute` 方法的完整实现，而非简单截头。

**模式 3：结构化错误反馈**

CC 在 verification 失败（工具报错）时，会将完整错误信息结构化地传回给模型，包括 stderr、exit code 等。Scion 的 `fix.jinja2` 已经做了类似的事（failure_details），这一点设计是对的。

**模式 4：分层摘要替代完整历史**

CC 的 `applyContextManagement` 对长对话做摘要压缩，而不是硬截断或全量保留。Scion 的 `_summarise_hypothesis_history` 取最近 5 条也是类似思路，但摘要的信息密度太低。

**建议**：对"已失败"的 hypothesis，摘要应包含：
```
[screening_fail | win_rate=0.33] modify/move_order.py: 
  尝试改变距离度量 → 通过 Verification，screening 失败（负效果）
```
而不是仅：
```
[rejected] order_level/modify → operators/move_order.py
```

**模式 5：上下文优先级分层**

CC 的 `prependUserContext` 在消息序列中会把最重要的系统上下文放在最前面，防止被截断。Scion prompt 应遵循同样的优先级：
- 最前：问题定义（永远不能丢失）
- 其次：champion 代码（核心参考）
- 再次：失败历史（避免重蹈覆辙）
- 最后：兄弟分支（辅助信息，可裁剪）

---

## 五、修复建议（按优先级）

### P0：立即修复（影响 LLM 能否产生有意义输出）

**P0.1 修复 champion pool 初始化**
- 排查路径：`CampaignManager.__init__` → `ChampionStore` 如何加载初始 champion
- 确认 `ChampionState.operator_pool` 在 campaign 启动时从 `surrogate/registry.yaml` 正确填充
- ContextManager 中加防御断言：pool 为空时抛出明确错误，不允许生成空内容的 prompt

**P0.2 修复 champion code 读取**
- `_summarise_champion_code` 在 code_snapshot_path 无效时不应静默失败
- 初始 champion 快照应在 campaign init 时由 `WorkspaceMaterializer.create_champion_snapshot` 建立
- Round 1 应读取 **所有** champion 算子文件的代码（不只是 target_file 对应的那一个）
- 建议在 `build_hypothesis_context` 中增加 `champion_operators_code` 字段，调用新的 `_read_all_operator_code(champion)` 方法

**P0.3 补充 problem spec 摘要**
- `ProblemSpec` 应有一个 `description` 或 `summary` 字段（或自动生成）
- 内容至少包含：
  - 问题域一句话描述
  - 多目标函数定义（字典序优先级）
  - Solution 核心结构（vehicles dict + assignment dict）
  - 关键约束（锁定订单不可移动）
- 传入 prompt 的 `problem_name` 应改为 `problem_summary`

### P1：重要修复（影响 LLM 推理质量）

**P1.1 升级分支历史摘要**
- `_summarise_hypothesis_history` 应为每条历史 hypothesis 包含：
  - 失败阶段（contract/verification/screening）
  - 关键失败原因（failure code）
  - 如果到了 screening：win_rate 数值
- 来源：`HypothesisRecord.status` + 关联的 `ExperimentEvent`（需要 `HypothesisStore` 提供聚合接口）

**P1.2 升级 blacklist 摘要**
- `_summarise_blacklist` 应包含 `evidence_count` 和失败原因摘要
- 帮助 LLM 判断"这个方向是偶发失败还是强信号失败"

**P1.3 完善 operator interface spec**
- `CODE_PROMPT_TEMPLATE` 中的接口说明应包含：
  - `Operator` 基类的要求（deep_copy，不修改原解）
  - `Solution` 的核心字段（vehicles dict, assignment dict, objective）
  - `Instance` 的关键字段（orders dict, amount_limits）
  - 锁定订单检查规则
  - `rng` 的类型（`random.Random`，非全局 random）
- 这些是让代码通过 Verification Gate 的最低要求

**P1.4 增加 champion_stats**
- `build_hypothesis_context` 应增加 `champion_stats` 字段
- 内容：champion 最近一次 screening 的 aggregate 统计（如果有），或 baseline 评估数据
- 帮助 LLM 定位"target_weakness"

### P2：质量改进（影响搜索多样性和效率）

**P2.1 兄弟分支摘要有效化**
- `_summarise_siblings` 应改为：每个兄弟分支 1 行，包含方向（`change_locus`）和当前状态
- 帮助 LLM 做差异化探索

**P2.2 Round 2 区分目标文件与参考代码**
- `build_code_context` 应分离：
  - `target_file_content`：当前 modify 目标文件的完整代码（**修改起点**）
  - `reference_operators`：同类别算子 1-2 个的代码（**风格参考**）
- 当前 `champion_code` 字段把这两者混为一谈

**P2.3 代码截断策略改进**
- `_summarise_champion_code` 的 3000 chars 截断应改为"保留 execute 方法完整"
- 如果整个文件 > 3000 chars，保留 import + `__init__` + 完整 `execute` 方法，截断注释

**P2.4 建议 Token 预算配置化**
- 各上下文块的 token 限制应从 hardcode 改为可配置
- 建议在 `ProblemSpec` 或 `ContextManagerConfig` 中增加：
  ```
  max_operator_code_chars: 8000   # 全部算子代码总上限
  max_branch_history_items: 5     # 历史条目数
  max_blacklist_items: 10         # blacklist 上限
  ```

---

## 六、总结

### 核心发现

Scion ContextManager 的实现框架是正确的（三个 context builder，暴露控制边界基本正确），但**上下文内容极度欠载**：

1. LLM 看不到任何算子代码（pool 空 + code 不可读）
2. LLM 不知道要优化什么（problem spec 只有名称）
3. LLM 不知道历史失败的原因（history 只有状态枚举）
4. LLM 的代码生成缺乏接口约定细节（interface spec 不完整）

这四个问题叠加，导致当前生成的 hypothesis 只能是泛泛之谈，生成的代码大概率违反 Verification Gate 的接口要求。**调试输出中 1129/1564 chars 的 prompt、空 pool、代码不可读，是这四个问题在数据层面的直接体现。**

修复优先级：P0.1（pool 初始化）> P0.2（champion code）> P0.3（problem spec）> P1.3（interface spec）。这四个改完后，token 预算自然会从当前的 ~280/390 tokens 增长到合理的 2000-4000 tokens 区间，LLM 才有可能产生有价值的 hypothesis 和代码。

### 一句话判断

> 暴露控制边界做对了，上下文内容几乎是空的——现在 LLM 拿到的 prompt 约等于让人在蒙眼的情况下改代码。
