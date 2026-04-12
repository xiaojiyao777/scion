# 10 — Lineage Registry

## 定位

Scion 的**持久化审计层**——所有发生在 campaign 里的事情都被记录，append-only，不可修改。

**核心价值**：
- 任何决策都有完整的证据链（为什么 ABANDONED？用了什么代码？）
- Campaign 进程死掉后数据不丢失（持久化镜像）
- 事后可追溯、可重放、可调试

---

## 存储结构（SQLite，5 张表）

```
experiment_events   ← 主事件表（核心）
hypotheses          ← 假设记录
branches            ← 分支状态快照
champions           ← Champion 版本（当前 P2，还没写入）
weight_optimizations← 权重优化结果
```

### experiment_events 关键字段

```sql
event_id, campaign_id, branch_id, hypothesis_id
event_kind          -- "experiment" | "decision"（Sprint G2-patch 新增区分）
code_hash           -- 算子代码 SHA-256，可精确还原代码版本
stage               -- screening | validation | frozen
screening_win_rate, screening_median_delta, screening_ci_low, screening_ci_high
decision            -- continue_explore | queue_validate | promote | abandon...
decision_reason     -- 决策原因码（结构化，非自由文本）
model_id            -- 哪个 LLM（Sprint G2-patch 新增）
protocol_version    -- 实验协议版本（Sprint G2-patch 新增）
prompt_tokens, completion_tokens  -- token 用量审计
```

---

## Append-Only 的意义

Lineage 只追加，不修改。

保证：**每条记录都是当时发生时的真实状态，事后无法篡改**。

对"LLM 做决策"的系统，这个特性很重要——能回溯证明"当时的 DecisionFeatures 是什么、为什么做了这个决定"，不被覆盖。

---

## Hash 链：可追溯性的工程保证

每条记录包含多个 hash：

```
code_hash         → 精确定位这次实验用的是哪版算子代码
prompt_hash       → 精确定位 LLM 收到的是什么 prompt
problem_spec_hash → 问题定义有没有变
split_version     → 用的是哪版 split manifest
protocol_version  → 实验协议版本
```

这些 hash 组合起来，理论上可以**完整复现任何历史实验**：拿到 code_hash 对应的代码快照 + seed + instance，重跑得到相同结果。

---

## 双重角色：运行时写入 + 事后读取

```
SQLite Lineage
  ├── 运行时：接收写入（campaign 进行中持续追加）
  └── 事后：提供读取（分析、调试、CLI、恢复）

_step_history（内存）
  ├── 运行时：ContextManager 的数据源（速度快）
  └── 事后：丢弃（session 结束后消失）
```

**Lineage 是 `_step_history` 的持久化镜像**——内存数据即使进程死掉也不丢失。

---

## 运行时消费（ContextManager 不直接读 SQLite）

LLM 生成假设时的数据流：

```
campaign._step_history（内存）
    ↓
ContextManager.build_hypothesis_context()
    ↓
Round 1 prompt（结构化上下文）
    ↓
LLM API → 生成 HypothesisProposal
```

**为什么读内存而不读 SQLite**：
- 速度：内存访问比磁盘查询快，每轮都要构造上下文
- 一致性：内存状态和 campaign 当前状态完全同步，不需要合并

**SQLite 被直接读取的场景**：
- 事后 CLI 分析（`scion report / inspect / postmortem`）
- Campaign 恢复（理论上，当前未实现）：进程崩溃后从 SQLite 重建 `_step_history` 继续跑

---

## 事后分析场景

### CLI 工具

```bash
scion report    # 生成 campaign 汇总报告（promote 次数、win_rate 分布、token 消耗）
scion inspect   # 查询单个分支或 hypothesis 完整历史
scion postmortem # 根因分析，输出 CampaignDiagnosis
```

### 外部 SQL 查询

SQLite 直接可查，任何分析都能做：

```sql
-- 各模型 screening 通过率对比（F2 Opus vs F3 Sonnet）
SELECT model_id,
       AVG(CASE WHEN decision='queue_validate' THEN 1.0 ELSE 0.0 END) AS pass_rate
FROM experiment_events
WHERE event_kind='experiment' AND stage='screening'
GROUP BY model_id;

-- 哪类 action promote 成功率最高
SELECT patch_action,
       COUNT(*) FILTER (WHERE decision='promote') * 1.0 / COUNT(*) AS promote_rate
FROM experiment_events WHERE event_kind='experiment'
GROUP BY patch_action;
```

### campaign_summary.json

每次 campaign 结束，`_write_campaign_summary()` 生成 JSON 摘要——Lineage 的"快速视图"，不需要 SQL 就能了解 campaign 结果。Sprint F 的结果分析就是读这个文件。

---

## 当前 P2 缺口

`champions` 表为空——`_on_promote()` 只更新内存中的 `self._champion`，没有写 DB。

Champion 历史只能从文件系统 `champions/champion_vN/` 恢复，不能 SQL 查询。
v0.3 修复：`_on_promote()` 末尾调用 `registry.record_champion()`。

---

## Sprint G2-patch 新增字段

- `event_kind`：区分 "experiment"（实验结果）和 "decision"（决策事件），查询更清晰
- `model_id`：记录用了哪个 LLM，支持 Opus vs Sonnet 对比分析
- `protocol_version`：实验协议版本号，支持跨版本对比
- `prompt_tokens / completion_tokens`：token 用量审计，成本分析用
