# Sprint F2 实验分析 + Sprint I 修复记录

*日期: 2026-04-13*
*分析者: Cris*

---

## 一、Sprint F2 实验矩阵

| 实验 | 模型 | 轮次 | 时长 | champion 版本 | 晋升次数 |
|------|------|------|------|--------------|---------|
| F1 | claude-opus-4-6 | 80r | 315 min | v4 | 3 |
| F2 | claude-opus-4-6 | 80r | 141.5 min | v3 | 2 |
| F3 | claude-sonnet-4-6 | 80r | 396.5 min | v5 | 4 |

**目录**: `~/research/scion-experiments/sprint-f2/`

---

## 二、F2 提前终止根因分析

### 现象
F2 仅跑 24 轮（max_rounds=80）即触发 stagnation termination，浪费 56 轮预算。

### 根因链（三重耦合）

**第一层：Champion 强度差异**

F2 的前两个算子碰巧更强：
- F2 v2 `subcategory_consolidate` frozen md = **4,150,000**（F1 v2 仅 300,000，相差 14 倍）
- F2 v3 `subcat_destroy_rebuild` frozen md = **3,150,000**，且首次 screening wr=1.00

F2 比 F1 更快建立了极强的 champion，后续候选算子无法超越。

**第二层：Sprint H2 T4 改变了 wr<0.3 的路由**

Sprint H2 实现了 Tiered evaluation routing（设计文档"缺口三"）：
```python
# campaign.py
if features.win_rate < 0.3:
    decision = Decision.ABANDON   # 把 CONTINUE_EXPLORE 转成 ABANDON
```

- 修复前：wr=0.1 → CONTINUE_EXPLORE → `_recent_abandoned_count = 0`（重置）
- 修复后：wr=0.1 → ABANDON → `_recent_abandoned_count += 1`（累积）

**第三层：_recent_abandoned_count 达到 stagnation_limit=10**

F2 v3 晋升后，后续 14 个候选全部 wr<0.3，经 T4 转成 ABANDON，`_recent_abandoned_count` 连续到 10，触发 `TerminationChecker._stagnation_detected()` → campaign 终止。

### 为什么 F1 没有触发

F1 的 champion 较弱（v3 md=1,850,000），后续候选仍能得到 wr=0.30-0.40，恰好在 T4 阈值以上，触发 `continue_explore`（重置计数器），从而避免连续 10 次 abandon。

### 为什么 F3（Sonnet）跑完 80 轮 + 4 次晋升

F3 的 champion 轨迹更渐进（v3 md=1,050,000），搜索空间仍有 marginal improvement 余地，候选算子频繁出现 wr=0.30-0.44（continue_explore 边界），计数器持续被重置。

### 设计缺陷

设计文档（09-failure-router.md）的"缺口三"明确描述了 T4 的意图：**快速丢弃明显无效方向**。但实现时，T4 路径将 `Decision.ABANDON` 注入普通 dispatch 流，意外累积了原本用于检测"框架卡死"的 `_recent_abandoned_count`。两个机制的职责本应分离，但实现时合用了同一变量。

此外，PROMOTE 的早返回路径从未重置 `_recent_abandoned_count`（另一个遗漏 bug）。

---

## 三、Sprint F2 结论

| 指标 | F1 Opus | F2 Opus | F3 Sonnet |
|------|---------|---------|-----------|
| 晋升次数 | 3 | 2 | **4** |
| 轮数利用率 | 80/80 (100%) | 24/80 (30%) | 80/80 (100%) |
| 最终 frozen md | 3,900,000 | 3,150,000 | **2,950,000** (v5) |
| stagnation 触发 | ❌ | ✅（Sprint H2 T4 副作用） | ❌ |

**Sonnet 表现出色**：4 次晋升、跑满 80 轮，性价比明显优于 Opus（价格约 1/5）。  
**F2 的 2 次晋升不代表 Opus 弱**，而是框架 bug 导致提前终止——真实能力未完全发挥。

---

## 四、Sprint I 修复内容

**Commit**: `dbc9997`  
**分支**: `v0.2-dev`  
**日期**: 2026-04-13

### I1：T4 soft-abandon 独立路径（P0）

新增 `_apply_soft_abandon()` 方法。T4（wr<0.3）不再经过 ABANDON dispatch，不递增 `_recent_abandoned_count`，改用独立的 `_soft_abandon_streak` 计数。

```python
# 修复前：T4 路径 → Decision.ABANDON → _recent_abandoned_count += 1
# 修复后：T4 路径 → _apply_soft_abandon() → _soft_abandon_streak += 1
```

### I2：PROMOTE 重置计数器（P0）

`_on_promote()` 新增重置三个计数器：
```python
self._recent_abandoned_count = 0
self._soft_abandon_streak = 0
self._hard_stagnation_escape_used = False
```

### I3：soft-stagnation 触发 locus 多样化（P1）

`TerminationConfig` 新增 `soft_stagnation_limit=15`。当 `_soft_abandon_streak >= 15` 时，`_check_soft_stagnation()` 强制下一个分支使用对立 locus（vehicle_level ↔ order_level），并向 LLM prompt 注入 MANDATORY SEARCH CONSTRAINT。不触发 terminate。

### I4：hard-stagnation 先逃脱再终止（P1）

`should_stop()` 在首次触发 hard stagnation 时：
1. 重置 `_recent_abandoned_count = 0`
2. 设置 `_forced_next_locus`（由 StagnationDetector 诊断推荐）
3. 返回 `False`（不终止）
4. 设 `_hard_stagnation_escape_used = True`

第二次触发才真正 terminate。Promote 时重置 escape flag。

**测试覆盖**：19 个新测试（全过），unit 总计 106 passed。

---

## 五、Sprint F3 实验计划

**目录**: `~/research/scion-experiments/sprint-f3/`  
**启动时间**: 2026-04-13 08:51  
**状态**: 运行中

| 实验 | 模型 | 轮次 | 启动时间 | 目的 |
|------|------|------|---------|------|
| F1 | claude-opus-4-6 | 100r | 08:51 | Sprint I 修复验证（Opus） |
| F2 | claude-opus-4-6 | 100r | 08:52 | Sprint I 修复验证（Opus 复现） |
| F3 | claude-sonnet-4-6 | 100r | 08:53 | Sprint I 修复验证（Sonnet）+ 长程压测 |

三个并行独立进程，各差 1 分钟启动，共享同一 baseline（v1 champion），独立 DB。

**预期验证点**：
- F2 不再提前终止（soft-abort 不计入 stagnation）
- 三组轮次利用率均 ≥ 90%
- F4（中国模型）暂缓，待 LLMClient 支持 OpenAI 接口后加入

---

## 六、遗留待办

- [ ] LLMClient 增加 OpenAI 兼容路径（支持 GLM-5、Minimax M2.7、Qwen3.5 等）→ Sprint J
- [ ] ChampionStore 持久化（`_on_promote()` 调用 `record()`）→ v0.3 P2
- [ ] Frozen holdout 接入实例生成器（每次用全新实例）→ v0.3 P1
- [ ] F3 跑完后做三组对比分析
