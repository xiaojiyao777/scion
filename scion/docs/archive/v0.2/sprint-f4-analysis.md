# Sprint F4 分析报告 + Sprint K 修复总结

*日期：2026-04-14*

---

## 实验概况

Sprint F4 是首次在**生产数据**上运行的正式实验，分两组并行：

| | Group A | Group B |
|---|---|---|
| 数据 | 合成基线（v3/v4 benchmark） | 生产风格（pickup_city 委托单级别）|
| Protocol | protocol.yaml (wr≥0.60) | protocol.yaml (wr≥0.60) |
| 轮次 | 200r，80r 时终止 | 200r，全程跑完 |
| Champion | v3（2次晋升） | v2（1次晋升） |
| 运行时间 | ~9h | ~8.2h |

---

## Group A 发现的 Bug

### Bug 1：reconcile 路径 hypothesis zombie（P0）

**触发链**：
```
02:02  Branch 93c35fa4 保存 hypothesis 62667848（modify destroy_rebuild.py）→ status=active
02:27  weight_opt 完成 → mark_all_stale → 分支（FROZEN_TESTING）打成 STALE
02:37  frozen 实验返回 decision=queue_validate → apply_decision(QUEUE_VALIDATE) on STALE
       ERROR: "Invalid transition: state=stale + decision=queue_validate"
02:39  reconcile re-screening 失败 → branch ABANDONED
       ★ 但 hypothesis status 未从 active → rejected
```

**影响**：hypothesis 62667848 作为 zombie 停留在 active 列表，C10 检查 active+blacklisted，
导致所有后续分支尝试 `(order_level, modify, operators/destroy_rebuild.py)` 被无限拦截，
持续 6 小时，触发 19 次无效 C10 block。

**根本原因**：`_run_reconcile_step` 的所有 abort 出口都调用了 `reconcile_stale(success=False)`，
但没有调用 `_hyp_store.mark_status(hypothesis_id, "rejected")`，hypothesis 生命周期管理不完整。

**次级原因**：`mark_all_stale` 将 FROZEN_TESTING 分支也打成 STALE，但 frozen 实验可能正在运行，
结果返回时触发 Invalid transition，这是触发上述 zombie 的前提条件。

---

## Group B 发现的设计缺陷

### 缺陷 1：C10 不检查 rejected 状态

**表现**：`repack_vehicle_pair.py modify` 被 rejected 17 次，每次都通过 C10。

**根因**：C10 只检查 `active + blacklisted`，rejected 不在范围内。
只要 class name 不同（text[:50] 不同，K6 修复方向），同文件 modify 可无限重试。

### 缺陷 2：exploitation 偏差 × stagnation 盲区

**表现**：165 轮，163 次 soft_abandon，RepackVehiclePair 占据 90%+ 轮次。

**根因**：
- RepackVehiclePair 是 champion v2 唯一新算子 → LLM 单点锚定
- soft_abandon（wr<0.3）不计入 `_recent_abandoned_count` → stagnation 从不触发
- 生产数据 splits≈0，cost 信号弱，wr 天花板约 0.5-0.6
- screening 阈值 0.667 系统性偏高（repack_group 4 次 wr=0.5 但无法晋升）

### 其他设计缺陷（同时修复）

- `active_hypotheses` 参数传给 ContextManager 但内部未使用 → LLM 不知道 occupied 文件
- C10 失败不写 `experiment_events` → research log 对拦截历史完全盲目
- search_memory family_key 不含 `target_file` → exhaustion 无法识别同文件多次失败
- K6 原始方案（text[:50]）被 class name 绕过

---

## Sprint K 修复清单

| 编号 | 内容 | commit |
|---|---|---|
| K1 | reconcile 所有 abort 出口加 `mark_status("rejected")` | 259d40b |
| K2 | eval_step abort 路径加 hypothesis cleanup | 259d40b |
| K3 | `mark_all_stale` 排除 FROZEN_TESTING（方案B） | 259d40b |
| K4 | R1 prompt 加 "Currently Occupied" 段 | 259d40b |
| K5 | C10 失败写入 experiment_events（event_kind='contract_fail'）| 259d40b |
| K6→K6-fix | modify key = (locus, action, file, champion_version) | 5edebf7 |
| K7 | search_memory family_key 含 target_file | 259d40b |
| K8 | C10 novelty 纳入 rejected（同 champion_version） | a59f510 |

### HypothesisRecord 新增字段

```python
base_champion_version: int = 0  # 创建时的 champion 版本，K8 过滤用
```

### K6-fix 设计原则

| 场景 | 行为 |
|---|---|
| 同文件 modify + 同 champion | 被 C10 拦截（同版本只能 modify 一次）|
| 同文件 modify + 新 champion | 放行（新基线可重试）|
| 同文件 create_new + 不同 text | 放行（K6 保留 text[:50]）|
| 真正重复的 modify | 被拦截 |

---

## protocol_prod.yaml

为生产数据场景创建专用协议配置（commit 359e6f7）：

| 参数 | 默认值 | 生产专用 | 理由 |
|---|---|---|---|
| `screening.win_rate_min` | 0.60 | **0.55** | cost 信号弱，0.5 wr 有统计意义 |
| `validation.win_rate_min` | 0.66 | **0.55** | 与 screening 对称 |
| `expand_to_modify` | 10 | **14** | 信号弱需更多样本 |
| `expand_to_create` | 16 | **20** | 同上 |
| frozen gate | 不变 | 不变 | 晋升标准不降低 |

---

## Sprint F5 配置

- Group A：protocol.yaml + split_manifest.yaml，200r，Opus
- Group B：protocol_prod.yaml + split_manifest_prod.yaml，200r，Opus
- 实验目录：`~/research/scion-experiments/sprint-f5/`
- launch script：`sprint-f5/launch_f5.sh`

---

## 测试状态

- Sprint K：793 tests pass（含 41 新测试）
- Sprint K8：249 tests pass
- Sprint K6-fix：259 tests pass
