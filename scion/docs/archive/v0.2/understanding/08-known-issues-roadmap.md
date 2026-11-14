# 08 — 已知问题与 v0.3 路线图

## 当前状态（v0.2 已归档，2026-04-14）

v0.2 全部 Sprint（A→M）已完成，共 6 轮正式实验（F1→F6），289 unit tests 全部通过。

**实验矩阵最终结果**：

| 实验 | 轮数 | 数据 | Promotions | Weight Opt |
|---|---|---|---|---|
| F1 | 30r Opus | 合成 | 2 (frozen wr=1.0) | 未记录 |
| F2 | 50r Opus | 合成 | — | — |
| F3 | 30r Sonnet | 合成 | — | — |
| F4 A/B | 200r Opus | 合成+生产 | 3+1 | 0/1 (未验证) |
| F5 A/B | 186r*/200r Opus | 合成+生产 | 3+1 | 0/3 + 0/1 (n=9，全部失败) |
| **F6 A** | **98r Opus** | **合成** | **3** | **3/3 improved ✅** |
| **F6 B** | **100r Opus** | **生产** | **1** | **0/1 (SPLITS_WEIGHT 信号淹没)** |
| **F6 C** | **30r Opus** | **生产 SW=1K** | **0** | **N/A** |

*F5-A: 186r，aihubmix 余额耗尽提前终止

---

## 已知问题

### P1：Weight Optimization 同步阻塞

**描述**：`_on_promote()` 内同步运行 weight optimization，每次 promote 阻塞 campaign 10-40 分钟。

**当前缓解**：`n_initial_random=4, n_iterations=4`（评估次数从 16→8）。

**根本修复**：见下方 v0.3 路线图中的"异步 + STALE 机制"。

**为什么 Sprint F 不做**：async 会让后续分支与未优化的 champion 比较，产生系统性虚假胜率，损害实验有效性。正确性 > 吞吐量。

---

### P2：ChampionStore 持久化未完成 ✅ FIXED (v0.2 Sprint M T4 新增)

**描述**：`champions` SQLite 表未被写入（`_on_promote` 直接更新内存中的 `self._champion`，未调用 `ChampionStore.record()`）。

**影响**：champion 历史无法从 DB 查询，只能从文件系统 `champions/champion_vN/` 目录恢复。

**修复状态**：✅ FIXED — Sprint M T4 在 `_on_promote()` 末尾调用 `registry.record_champion()`，F6 实验验证：Group A 3 records，Group B 1 record（DB 有数据）。

---

### P3：nohup 进程不健壮 ✅ FIXED

**描述**：F1 实验因 nohup bash 进程被外部 kill（原因：weight opt 耗时过长 + 终端断开），导致 campaign 在第 10 轮后中断。

**修复状态**：✅ FIXED — 改用 tmux 管理长时间运行的 campaign（F2/F3 起全部采用，F4→F6 均使用 tmux）。

---

### P4：Stale Reconcile 语义正交性不保证

**描述**：Branch B 的 patch 重新应用到 Champion v2 后，文本层面合并成功不代表语义上正交。可能产生：
- 两个改动的交互效应被误认为 B 的独立贡献
- B 的改进在 v2 上消失（被 A 包含），导致 B 被错误 ABANDON

**现状**：依赖统计实验作为最后防线，无语义正交性验证。

---

### P5：合成实例偏差（Benchmark Gap）

**描述**：所有实例来自同一生成器，Scion 的泛化证明仅限于生成器分布内，不等于生产泛化。

**修复路径**：
1. 短期：往 frozen 混入真实生产实例
2. 中期：生产 shadow deployment A/B 实验
3. 长期：提升生成器保真度（引入真实订单统计特征）

---

## v0.3 路线图

### 核心改进：异步 Weight Optimization + STALE 机制

**原则**：weight opt 完成前，不允许任何分支与未优化权重的 champion 做实验对比。

**实现方案**：

```
_on_promote() 新流程：
  1. copytree → freeze → 创建 new_champion（暂用旧权重）→ 返回（立刻）
  2. 后台 Thread 运行 weight optimization
  3. 完成后：
     a. 写回 registry.yaml
     b. 若有改善 → 触发 "soft champion update"
     c. mark_all_stale(weight_update=True)
     d. 活跃分支 reconcile（用新权重 champion 重新 screening）
```

**关键约束**：
- weight opt 超时（>15min）→ 跳过权重更新，保持当前权重
- Double-promote：第二次 promote 时，取消第一个 weight opt thread
- 版本语义：weight opt 完成后 champion 版本不变，但 `code_snapshot_hash` 更新

**工程影响范围**：
- `scion/core/campaign.py`：`_on_promote`、`__init__`、`run()`
- `scion/core/branch.py`：`mark_all_stale` 增加 `weight_update` 参数
- `scion/parameter/optimizer.py`：增加取消信号支持

---

### 其他 v0.3 候选项

**Reconcile 语义正交性检测**（P3 修复）：
- 引入 `touched_symbols` 碰撞检测
- 有重叠时标记"非正交 reconcile"，要求更严格验证路径

**ChampionStore 持久化**（P2 修复）：
- 在 `_on_promote` 中调用 `ChampionStore.record()`，写入 SQLite

**生产验证接入**（P5 部分修复）：
- 设计实验结构，支持将 Scion promote 的算子集成进生产 solver
- shadow deployment 结果接入，与 Scion frozen 结论对照

---

## 实验路线图

| 阶段 | 内容 | 状态 |
|------|------|------|
| **F1** | 30r Opus 合成，2 promotes，frozen wr=1.0 | ✅ 完成 |
| **F2** | 50r Opus 合成，验证实验 | ✅ 完成 |
| **F3** | 30r Sonnet 合成，模型对比 | ✅ 完成 |
| **F4** | 200r Opus 合成+生产，v3 manifest | ✅ 完成 |
| **F5** | 186r/200r Opus，weight opt n=9 验证（失败）| ✅ 完成 |
| **F6** | 98/100/30r Opus，Sprint M 全面验证，weight opt n=25（3/3 成功）| ✅ 完成 |
| **v0.3 开发** | 异步 weight opt + scoring 独立化 + 早停 | 规划中 |
| **生产接入** | MILP 精确验证 + shadow deployment | 规划中 |

---

## v0.3 — 精确算法对比验证

**目的**：给 Scion 的改进加上"绝对意义"——当前只有相对改进（比上一个 champion 好），和精确算法对比才能知道距离全局最优还有多远。

**方案**：对 small 实例（20-40 orders）用 MILP 求最优解，计算：
$$\text{gap} = \frac{f_{\text{champion}} - f_{\text{optimal}}}{f_{\text{optimal}}}$$

观察 Scion 迭代过程中 gap 的收敛曲线。

**MILP 模型**：已完成，见 `scion/docs/reference/milp-model.md`（Opus 建模，两阶段 epsilon-constraint，$O(n^2)$ 复杂度，$n=40$ 时 Gurobi 分钟级可证最优）。

**实现计划**：PuLP + CBC（无需商业 license），对接 v4_scr_s 系列实例，oracle 修复后统一实施。

---

## v0.3 Backlog — Weight Opt Scoring Function 独立化（2026-04-14 F6 实验发现）

### 问题

`compute_delta()` 被实验协议和 weight optimization 共用，但两者需求不同：

- **实验协议**：需要字典序严格分层（splits 绝对优先于 cost），用于 win/loss 判定。`SPLITS_WEIGHT=100K` 是正确的——任何 split 改善都必须压倒 cost。
- **Weight optimization**：需要连续可微的评分信号来引导搜索方向。当 splits≈0 时，随机 split 波动（0↔1）= ±100K，淹没 cost 信号 O(1K-10K)，优化器无法区分真实 cost 改善和 splits 噪声。

### F6 证据

- Group A（splits=23.8）：weight opt 2/2 improved=1，权重优化有效
- Group B（splits≈0, SPLITS_WEIGHT=100K）：weight opt improved=0，完全失灵
- Group C（splits≈0, SPLITS_WEIGHT=1K）：验证中，预期可恢复 cost 信号

### 设计方向

1. Weight opt evaluator 使用**独立的 scoring function**，不复用 `compute_delta()`
2. Scoring function 应可配置（per problem spec / per protocol）：
   - 合成数据：保持字典序大权重（与实验协议一致）
   - 生产数据 splits 饱和：自动检测饱和 → 切换为 cost-dominant scoring
   - 或直接暴露 `weight_opt_scoring` 配置项
3. 更深层：这与**问题定义**相关——不同问题实例的目标空间结构不同，weight opt 的评分函数应该是 problem spec 的一部分，不是框架硬编码

### 与 Saturation Signal 的关联

Sprint L2 已有 `ChampionSaturationAnalyzer` 检测 splits at_absolute_minimum。Weight opt 可复用此信号：当 `at_absolute_minimum=True` 时自动将 splits_weight 降阶（如 100K→1K 或直接 cost_only）。

### 临时方案（F6 已实施）

`SCION_SPLITS_WEIGHT` 环境变量注入 `compute_delta()`，影响全局（含实验协议）。v0.3 应改为 weight opt 专属配置。
