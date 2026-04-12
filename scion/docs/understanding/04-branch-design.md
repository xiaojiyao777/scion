# 04 — 分支设计

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
  │   （方向有苗头，继续在这基础上改）
  ├── verification 未通过
  │   → 回退到分支内最后一个 clean 版本
  │   （代码有问题，不能作为基础）
  └── 从未通过 verification
      → 回退到 champion
      （这个方向完全跑不通，从头开始）
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

## Stale Branch：Scion 独有的机制

**触发**：某个分支 promote 成功，champion 更新，其他活跃分支的基线过期。

**处理（reconcile）**：
```
Branch B 标记 STALE（champion 从 v1 → v2）
  ↓
把 Branch B 的 patch 重新应用到 Champion v2
  ↓
过 Contract → Verification → re-Screening（对比 v2）
  ↓
仍有正信号 → 恢复到 READY_VALIDATE
无信号     → ABANDONED（B 的改进已被 A 包含）
```

**为什么这个机制重要**：保证所有进入 validation/frozen 的算子，都是和**最新 champion**比较的，不是和过时基线比较。

**已知风险**（v0.3 待解决）：patch 可能在文本层面干净应用，但语义上与 v2 有交互。当前没有语义正交性验证，依赖统计实验作为最后防线。

---

## 并行与串行

**文件系统**：多分支 workspace **同时存在**（parallel）

**实验执行**：Scheduler **串行**推进各分支（sequential）

原因：
1. 实验对比共享同一个 champion 基线，并行会产生 race condition
2. 串行实验结果噪声更小（单 CPU 不争抢资源）
3. Stale reconcile 逻辑在串行下更简单

---

## Scheduler 优先级（词典序）

```
Priority 1: READY_FROZEN（等待最终确认，最高优先）
Priority 2: READY_VALIDATE（等待正式验证）
Priority 3: STALE（待 reconcile）
Priority 4: EXPLORE 中已有正信号的分支
Priority 5: 创建新分支
```

同级内按创建时间 FIFO 排序。
