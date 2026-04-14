# 04 — 分支设计与调度

## Scion 的分支 ≠ git branch

karpathy autoresearch 用 git branch 做实验版本管理：一条线，改了好就 commit，不好就 reset。

Scion 的分支是**探索方向的容器**——一个有状态的对象，持有一个方向的完整探索历史和代码状态。

---

## 1 branch = 1 方向，可迭代演化

```
Branch A: 方向 "改善 subcategory 合并策略"
  H1: 改相似度度量 → screening fail → 继续迭代
  H2: 改合并顺序   → screening pass → 进 VALIDATE
  H3: (如果 H2 fail 了，继续在这个方向深挖)

Branch B: 方向 "引入新的车辆重建算子"（与 A 并行）
  H1: destroy-rebuild 全量 → ...
```

- 分支内做**深度探索**（同方向多次迭代）
- 分支间做**广度探索**（多方向并行，最多 3 个活跃）

---

## Branch 对象持有什么

```python
Branch:
  branch_id          # 唯一标识
  base_champion_id   # 从哪个 champion 分叉出来
  state              # 状态机当前状态
  workspace_dir      # 当前活跃的代码文件目录
  current_code_hash  # 当前分支的"最优代码快照"
  hypothesis_ids     # 本分支所有 hypothesis 的历史
```

每个 Branch 在文件系统上有一个独立的 `workspace_dir`，是一份完整的代码副本。

---

## 版本控制：没有 git，Scion 自己做

**WorkspaceMaterializer**：每次运行 hypothesis 前，把"当前分支代码基线"复制到隔离目录，LLM 的 patch 只作用在这个目录里。

**SQLite Lineage Registry**：记录每次 hypothesis 的 code_hash、结果、决策。版本回退不是 `git reset`，是：

```python
# verification 失败 → 回退到上一个 clean code_hash
branch.current_code_hash = branch.last_clean_code_hash
# WorkspaceMaterializer 从这个 hash 还原文件
```

---

## 分支内代码基线规则

```
上一个 hypothesis 的结果是：
  ├── verification 通过 + screening fail
  │   → 代码留着，基于当前代码继续迭代
  ├── verification 未通过
  │   → 回退到分支内最后一个 clean 版本
  └── 从未通过 verification
      → 回退到 champion
```

---

## 状态机

```
NEW
 ↓
EXPLORE ──── screen_pass ──────→ READY_VALIDATE
   ↑                                  ↓
   │ screen_fail/continue_explore  VALIDATING
   │                            ├── validate_pass → READY_FROZEN
   │                            │        ↓
   │                            │    FROZEN_TESTING
   │                            │    ├── frozen_pass → PROMOTED ✅
   │                            │    └── frozen_fail → ABANDONED ❌
   │                            └── validate_fail  → ABANDONED ❌
   └── screen_unclear → EXPLORE_EXPAND

横切状态（任意状态可进入）：
  STALE          ← champion 被其他分支更新，当前基线过期
  BLOCKED_INFRA  ← 基础设施故障
```

---

## Scheduler：谁来决定下一步

每轮 `run_one_step()` 开始，Scheduler 回答两个问题：
- **选谁**：哪个分支获得这一轮执行权
- **做什么**：这个分支当前状态对应什么操作

Scheduler **不决定**：LLM 在分支里提什么假设（那是 Proposal 系统的工作）。

### 词典序硬优先级

```
Priority 1: READY_FROZEN     ← 已过 screening+validation，最有价值，尽快裁决
Priority 2: READY_VALIDATE   ← 已过 screening，有初步信号，尽快推进
Priority 3: STALE            ← 基线过期，占用 slot，尽早清理
Priority 4: EXPLORE（有正信号）← 继续深挖已有方向
Priority 5: create_new       ← 开新分支，最不确定
```

同级内按**创建时间 FIFO**（不做加权打分）。

### 为什么不做打分

Screening 样本量小（N=17），win_rate 方差大，打分不可靠。硬优先级让行为可预测，方便调试和审计。多分支本身已是广度探索，刻意不选"最优"，保持方向多样性。

### at_capacity

```python
if len(active_branches) >= max_active_branches:  # 默认 3
    return ScheduleResult(action="at_capacity")   # skip，等待 slot 释放
```

限制 3 个的原因：串行执行下分支过多导致每个方向等待时间线性增长；champion 更新时 reconcile 成本随分支数增长。

### 终止条件

```python
should_stop = (
    n_experiments >= max_experiments          # 1000
    or wall_clock_hours >= 24
    or recent_abandoned_count >= 10           # 连续 10 个分支全废弃
    or (no_active_branches and not can_create_new)
)
```

**promote 成功会把 `recent_abandoned_count` 清零**——只要还在产出有效改进，campaign 不停。

---

## Sprint I：Stagnation 修复（v0.2 Sprint I 新增）

长时间无 promote 的 campaign 容易陷入局部搜索循环，Sprint I 引入 soft stagnation limit 和多样化逃逸机制。

**soft_stagnation_limit=15**：当单个分支连续 15 轮都是 `CONTINUE_EXPLORE`（无 screening pass），触发 soft stagnation 检测。该分支不立即 ABANDON，而是：

```
soft_stagnation 触发 →
  1. 记录 StagnationSignal(type="plateau", branch_id=...)
  2. Scheduler 降低该分支优先级
  3. 若有 slot：优先 create_new（开新方向）
  4. 原分支继续但预算警告（再 N 轮无进展 → 真正 ABANDON）
```

**diversify escape**：StagnationDetector 检测到 campaign 级平台期（多个分支同时 soft_stagnation）时，注入"多样化逃逸"信号，强制 Round 1 上下文排除最近 K 轮的 change_locus，引导 LLM 进入新维度。

---

## Sprint K1/K2：Hypothesis Zombie 清理（v0.2 Sprint K1/K2 新增）

**问题**：某些假设在 EXPLORE 状态下被反复重试，但从未通过 Verification Gate——这些"僵尸假设"占用分支预算，永远不会进入 screening。

**Sprint K1**：引入 `max_verification_retries`（每个 hypothesis 的 Verification 重试上限）。超出后该 hypothesis 标记 `ZOMBIE`，不再消耗重试机会。

**Sprint K2**：`BranchManager` 定期扫描（每 10 轮）活跃分支的 hypothesis 状态，批量清理 ZOMBIE hypothesis，释放分支预算。分支若全是 ZOMBIE hypothesis 且无其他 pending → 分支 ABANDON。

```python
# Sprint K2 清理逻辑
for branch in active_branches:
    zombie_count = count_zombie_hypotheses(branch)
    if zombie_count / total_hypotheses > 0.8:  # 80% 僵尸率
        branch.state = ABANDONED
        lineage.record_decision("zombie_dominated")
```

---

## Stale Branch：Scion 独有的机制

**触发**：某个分支 promote，champion 更新，其他活跃分支基线过期。

**处理（reconcile）**：
```
Branch B 标记 STALE（champion v1 → v2）
  ↓
把 Branch B 的 patch 重新应用到 Champion v2
  ↓
过 Contract → Verification → re-Screening（对比 v2）
  ↓
仍有正信号 → 恢复为 READY_VALIDATE
无信号     → ABANDONED（B 的改进已被 A 包含）
```

这保证了所有进入 validation/frozen 的算子，都是和**最新 champion** 比较的。

**Sprint K3 例外（v0.2 Sprint K3 新增）**：处于 `FROZEN_TESTING` 状态的分支在 `mark_all_stale()` 时**不被标记 STALE**。原因：frozen test 是最终判定阶段，使用的代码已锁定，中途打断并让其 reconcile 会浪费已完成的 frozen 评估代价，且 frozen 本身是与"分叉时的 champion"对比设计，不需要用最新 champion 重测。

**已知风险（v0.3 待解决）**：patch 文本层面合并成功，不代表语义正交。两个改动可能有交互效应，被误认为 B 的独立贡献。

---

## 并行与串行

**文件系统**：多分支 workspace **同时存在**（parallel）

**实验执行**：Scheduler **串行**推进（sequential）

原因：实验对比共享同一个 champion 基线，并行会产生 race condition；串行结果噪声更小。

---

## 与经典搜索算法的对比

### 与爬山算法（Hill Climbing）的区别

表面上 Scion 像爬山：找到更好的 → 替换当前最优 → 以新最优为起点继续探索。

但有四个本质差异：

| 维度 | 爬山 | Scion |
|------|------|-------|
| 接受条件 | 单次评估更好 | 三关统计验证（screening+validation+frozen） |
| 探索线数 | 1 条 | 最多 3 条并行 |
| 失败后行为 | 立刻 revert 回 champion | 分支留在当前代码，继续迭代假设 |
| 基线更新影响 | 仅影响下一步 | 全局广播，触发所有活跃分支 reconcile |

### 与分支定界（Branch & Bound）的类比

更准确的类比是 B&B：

| 分支定界 | Scion |
|---------|-------|
| 当前最优解（incumbent） | Champion Pool |
| 找到更好的可行解 → 更新 incumbent | Frozen 通过 → Promote → 新 Champion |
| 用新 incumbent 剪枝所有节点 | STALE → reconcile → 差的 ABANDONED |
| 子问题 upper bound < incumbent → 剪掉 | re-Screening 无正信号 → ABANDONED |

Champion 更新后的 STALE reconcile，本质上就是 B&B 的**回切剪枝**：拿新 incumbent 重新审视所有 open 节点，剪掉不再有希望的。

**类比在哪里断裂**：B&B 的 bound 是数学性的（可以证明剪枝安全），Scion 的是统计性的（re-Screening 失败不能证明方向无效，可能是误剪）。B&B 保证找到全局最优，Scion 没有这个保证。

> **一句话定位**：Scion 是**算子设计空间上的统计分支定界**——用统计显著性替代数学 bound，用 LLM 生成子问题替代穷举分割，保留了 B&B 的核心框架：维护最优参考点 + 基于参考点剪枝 + 系统更新。
