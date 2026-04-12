# 08 — 已知问题与 v0.3 路线图

## 当前状态（v0.2，Sprint F 进行中）

- **Sprint F1**（30r Opus）：已完成，2 个 promote，frozen wr=1.0
  - SubcategoryAwareMoveOrder：frozen median_delta=850K
  - destroy_rebuild + 车型升级：frozen median_delta=3.25M
- **Sprint F2**（50r Opus）：运行中（tmux: scion-f2）
- **Sprint F3**（30r Sonnet）：运行中（tmux: scion-f3）

---

## 已知问题

### P1：Weight Optimization 同步阻塞

**描述**：`_on_promote()` 内同步运行 weight optimization，每次 promote 阻塞 campaign 10-40 分钟。

**当前缓解**：`n_initial_random=4, n_iterations=4`（评估次数从 16→8）。

**根本修复**：见下方 v0.3 路线图中的"异步 + STALE 机制"。

**为什么 Sprint F 不做**：async 会让后续分支与未优化的 champion 比较，产生系统性虚假胜率，损害实验有效性。正确性 > 吞吐量。

---

### P2：ChampionStore 持久化未完成

**描述**：`champions` SQLite 表未被写入（`_on_promote` 直接更新内存中的 `self._champion`，未调用 `ChampionStore.record()`）。

**影响**：champion 历史无法从 DB 查询，只能从文件系统 `champions/champion_vN/` 目录恢复。

**优先级**：P2（当前实验不受影响，lineage 可追溯）。

---

### P3：nohup 进程不健壮

**描述**：F1 实验因 nohup bash 进程被外部 kill（原因：weight opt 耗时过长 + 终端断开），导致 campaign 在第 10 轮后中断。

**修复**：改用 tmux 管理长时间运行的 campaign（F2/F3 已采用）。

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

| 阶段 | 内容 |
|------|------|
| **当前（v0.2 Sprint F）** | F2(50r Opus) + F3(30r Sonnet) 验证实验 |
| **v0.2 收尾** | Sprint F 结果分析 + 最终报告 |
| **v0.3 开发** | 异步 weight opt + STALE + ChampionStore |
| **生产接入** | 生成器扩充（引入真实统计） + shadow deployment |
