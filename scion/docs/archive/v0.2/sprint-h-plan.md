# Sprint H — v0.2 关键修复计划

*创建：2026-04-12，待 F3 完成后启动*

---

## 背景

Sprint F 实验暴露了两个 v0.2 必须修复的问题，不能等 v0.3：

1. **Oracle bug（P0）**：feasibility 误判 → 实验结论可信度存疑
2. **FailureRouter V8 死循环（P1）**：F2 中 Branch 2 浪费 40 轮 → Sprint F 效率严重损失

两个问题修复后，需要重新跑 Sprint F 实验，拿到可信的完整结果。

---

## Sprint H1 — Oracle 修复

### 问题

`surrogate/tests/test_oracle.py` 失败：
- `TestHardConstraintViolations::test_H1_capacity_exceeded` — 容量超载误报可行
- `TestHardConstraintViolations::test_H3_too_many_pickups_donguan` — 东莞提货约束违反误报可行

### CC 任务

1. 读 `surrogate/oracle.py` 的 `check_feasibility()`，找到 H1 和 H3 检查的具体 bug
2. 修复（估计 10-20 行）
3. 运行 `pytest surrogate/tests/test_oracle.py -v` 全部通过
4. 运行完整测试套件 `python -m pytest scion/tests/ -q --tb=no`，600 tests pass
5. Commit：`fix(oracle): H1 capacity + H3 Dongguan pickup constraint checks`

### 影响评估（修复后）

检查 F1 的两个 promote 是否受 oracle bug 污染：
- 从 `experiment_events` 找 feasibility_violation 字段
- 对 F1 promote 的算子（subcat_move.py, destroy_rebuild.py）手动跑 oracle check
- 如无违规，F1 结论保留有效；如有违规，F1 需要重跑

---

## Sprint H2 — FailureRouter V8 最小修复

### 问题

Branch 积累多个 V8_nondeterminism 失败的算子后，workspace 陷入"脏环境"：
- LLM 在有 4 个坏算子的基础上继续提假设
- 每次新算子也因为代码环境问题失败
- 分支在泥潭里耗费 40 轮无法自救

### 修复范围（最小 viable，不做完整 v0.3 升级）

在 `CampaignManager` 里增加每分支的 V8 连续失败计数：

```python
# campaign.py 新增
self._branch_v8_streak: Dict[str, int] = {}  # branch_id → 连续V8失败次数

# _run_explore_step 里：
if failure_code == "V8_nondeterminism":
    self._branch_v8_streak[bid] = self._branch_v8_streak.get(bid, 0) + 1
    if self._branch_v8_streak[bid] >= 3:
        # 强制回滚到 champion baseline
        self._branch_workspaces[bid] = self._setup_workspace(branch, force_champion=True)
        self._branch_v8_streak[bid] = 0
        logger.info("Branch %s: V8 streak >= 3, workspace reset to champion baseline", bid)
else:
    self._branch_v8_streak[bid] = 0  # 任何非V8失败重置计数
```

### CC 任务

1. 在 `campaign.py` 实现 `_branch_v8_streak` 跟踪逻辑
2. 连续 3 次 V8 → `force_champion=True` 重建 workspace
3. V8 计数在 `_on_promote` 时清空所有分支（champion 更新后重来）
4. 新增测试：模拟 3 次 V8 失败后 workspace 被重置
5. 600 tests pass
6. Commit：`feat(failure): V8 streak reset — force workspace to champion after 3 consecutive V8`

---

## Sprint H 执行计划

**前置条件**：F3 实验完成

**Step 1**：CC 开发 H1（Oracle）+ H2（FailureRouter），写 task spec 给 CC
**Step 2**：验收测试（600 tests pass，oracle tests 全绿）
**Step 3**：影响评估（F1 两个 promote 是否受 oracle 污染）
**Step 4**：重跑 Sprint F（F1/F2/F3 全部重跑，基于修复后的代码）
**Step 5**：分析完整 Sprint F 结果，写最终报告

---

## Sprint F 重跑计划

使用 claw 环境，`~/miniconda3/envs/claw/bin/python`，串行执行：
- F1: 30r Claude Opus
- F2: 50r Claude Opus
- F3: 30r Claude Sonnet

预期：有了 FailureRouter V8 修复后，F2/F3 的轮次利用率应该显著提升。
