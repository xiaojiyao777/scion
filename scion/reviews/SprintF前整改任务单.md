# SprintF前整改任务单

我基于你贴出的源码、设计文档和已有审计意见，结论是：

> **上一版审计的主结论成立，而且我建议再补 5 个同样应视为 blocking 的问题：**
>
> 1. **promote 后权重优化写回只读 snapshot，当前路径大概率会失败**
> 2. **eval-only 路径会伪造新的 `HypothesisRecord`，导致原 hypothesis 生命周期断裂**
> 3. **`record_event` + `record_decision` 双写同一张表，report 分母会失真**
> 4. **CLI 初始化 champion 时 `operator_pool={}`，没有从 `registry.yaml` 读取真实池**
> 5. **`compute_code_hash()` 不包含 `registry.yaml`，权重变化不会进入 champion hash**

所以，Sprint F 前建议不是“修几个小 bug”，而是要做一轮**可信边界 + 协议正确性 + 参数层正确性 + 运行入口统一**的收口。

---

# 一、按 blocking 优先级排序的修复 backlog

我把 backlog 分成 **P0-blocking / P1-强建议 / P2-可延后**。  
其中 **P0 是 Sprint F 前必须完成**。

---

## P0-1：补齐所有 Gate bypass，恢复架构 v3 的双硬闸门

### 为什么是 blocking
这是架构红线。当前有 3 条明确绕过：

1. `pending hypothesis` 复用时没有重新过 hypothesis Contract Gate  
2. `fix_code()` 生成的新 patch 没有重新过 patch Contract Gate  
3. stale reconcile 只重打 patch，没有重新走 `Contract -> Verification -> re-screening`

只要这三条不修，**Creative Layer 的 tainted 输出就不是被严格 gate 住的**。

### 涉及文件
- `scion/core/campaign.py`
- `scion/core/branch.py`
- `scion/contract/gate.py`（少量辅助）
- `scion/core/models.py`（可能需要补状态字段）

### 具体任务
- 在 `_run_explore_step()` 的 pending hypothesis 路径中重新执行 `validate_hypothesis()`
- 在 `_attempt_fix()` 后的应用路径中，先对 `fixed_patch` 跑 `validate_patch()`，再 `apply_patch()`
- 重写 `_run_reconcile_step()`：
  - fresh workspace
  - reapply patch
  - `validate_patch()`
  - `VerificationGate.run()`
  - `screening` 重新评估
- 修复 branch clean-base 语义：
  - patch apply 后只能更新 `current_code_hash`
  - 只有 verification pass 之后才能更新 `last_clean_code_hash`

### 验收标准
- 任意 fix patch 都不可能绕过 Contract Gate
- stale branch reconcile 会留下完整的 contract/verification/screening 记录
- verification fail 后 `last_clean_code_hash` 不会被污染

---

## P0-2：修正实验协议实现，使其真正符合 v3 / v0.2 设计

### 为什么是 blocking
当前 protocol 层最严重的问题不是“缺功能”，而是**统计语义错误**：

- canary 用的是 screening case，不是独立 canary split
- 统计单位用了 `(case, seed)` pair，而不是 **case**
- expand 用“造新 seed”，而不是“扩 case”
- screening/validation/frozen 没有按配置选样本数
- frozen 使用上限也没真正收口

这会直接破坏研究结论可信性。

### 涉及文件
- `scion/protocol/experiment.py`
- `scion/protocol/stats.py`
- `scion/protocol/evaluation.py`
- `scion/config/problem.py`
- `scion/config/protocol_config.py`
- `scion/config/split_manifest.py`
- `scion/config/seed_ledger.py`
- `problems/warehouse_delivery/protocol.yaml`
- `problems/warehouse_delivery/split_manifest.yaml`
- `problems/warehouse_delivery/seed_ledger.yaml`

### 具体任务
- `run_canary()` 改为真正使用 `manifest.canary + seed_ledger.canary`
- `run_experiment()` 改为：
  - 先按 stage + action 选择 cases
  - 对每个 case 聚合 seeds
  - 再对 case-level 比较结果计算 `win_rate / median_delta / CI`
- expand 改为：
  - screening: `n_cases_modify/create -> expand_to_modify/create`
  - validation: `n_cases -> expand_to`
  - **不新增 synthetic seeds**
- frozen 使用次数要有 campaign 级限制
- validation/frozen 仍然只允许 aggregate 暴露给 LLM

### 验收标准
- `stats.n_cases` 表示的是 **case 数**，不是 pair 数
- `expand=True` 时增加 case，不增加 seed
- canary 永不复用 screening cases
- validation/frozen 无 per-case 数据进入 ContextManager

---

## P0-3：修复 hypothesis 生命周期与 lineage 身份一致性

### 为什么是 blocking
这是我认为上一版审计里还应该上提的一个问题。

当前 `_run_eval_step()` 会新造一个 `HypothesisRecord(uuid4())`，而不是沿用 screening 阶段已经创建的 hypothesis。  
后果是：

- 原 hypothesis 可能永远停留在 `active`
- promoted / rejected 不会回写到真正那条 hypothesis 记录
- novelty check / family tracking / memory 都会被污染
- lineage 上 hypothesis -> code -> validation -> frozen 断链

这会直接影响后续 proposal 质量和可追溯性。

### 涉及文件
- `scion/core/campaign.py`
- `scion/core/models.py`
- `scion/lineage/branch_store.py`
- `scion/lineage/registry.py`

### 具体任务
- 引入 `branch_id -> current_hypothesis_record` 或 `branch.current_hypothesis_id`
- screening -> validation -> frozen 全链路都沿用**同一个 hypothesis_id**
- `_run_eval_step()` 禁止再构造 fake HypothesisRecord
- hypothesis 状态必须显式转移：
  - `active`
  - `rejected`
  - `promoted`
  - 如果保留 `code_failed` / `blacklisted` 也要统一
- `StepRecord` 中增加 `hypothesis_id`
- lineage event 写真实 hypothesis_id，而不是空字符串

### 验收标准
- 任意 promoted step 能反查到同一条原始 hypothesis 记录
- hypothesis status 在 screening/validation/frozen 完成后是收敛的，不会长期滞留 `active`
- `campaign_summary.json` 与 SQLite 查询结果一致

---

## P0-4：修正参数搜索 correctness，不让“伪 improved”进入 champion

### 为什么是 blocking
当前 parameter layer 的隔离方向是对的，但**正确性还不够**：

1. `RandomLocalWeightOptimizer` 把第一条随机样本当 baseline
2. `improved` 是和第一条随机样本比，不是真 baseline
3. promote 后 snapshot 是只读的，`update_weights(snapshot/registry.yaml)` 很可能直接失败
4. champion hash 不包含 registry，权重变化不进 hash

这意味着：  
**即使日志说“优化成功”，也不一定真的比当前 champion 权重更好。**

### 涉及文件
- `scion/parameter/optimizer.py`
- `scion/parameter/evaluator.py`
- `scion/core/campaign.py`
- `scion/runtime/workspace.py`
- `scion/runtime/pool_manager.py`
- `scion/lineage/registry.py`

### 具体任务
- optimizer 显式评估 `current_weights` 作为 true baseline
- `baseline_weights` 必须是真 baseline weights
- `improved = best_score > true_baseline_score (+ epsilon)`
- observations 必须落盘并写 `observations_ref`
- 调整 promote 路径：
  - **不要在只读 final snapshot 上回写**
  - 推荐改成：
    1. 从 promoted workspace 创建 mutable staging copy
    2. 在 optimization workspace 上搜索
    3. improved 时写回 staging
    4. 最后把 staging freeze 为 final champion snapshot
- 新增 `compute_snapshot_hash()`，把 `operators/*.py + registry.yaml` 一起纳入 hash

### 验收标准
- best 低于 true baseline 时绝不会写回 champion
- improved 路径实际能写入 final snapshot
- champion snapshot hash 会因权重变化而变化
- `weight_optimizations` 中能查到 observations artifact

---

## P0-5：统一 pool / registry 更新路径，修复 create / modify / remove 结构同步

### 为什么是 blocking
现在 structural change 对 registry 的处理是不一致的：

- `create_new` 主要靠 `WorkspaceMaterializer.apply_patch()` 里的 `_update_registry()` side effect
- `remove` 不会删 registry entry
- `modify` 只改文件，不保证 registry 同步
- 主链路没有真正让 `PoolManager` 成为唯一 source of truth

这会导致 solver 实际加载的池和 hypothesis/patch 想表达的池不一致。

### 涉及文件
- `scion/runtime/workspace.py`
- `scion/runtime/pool_manager.py`
- `scion/core/campaign.py`

### 具体任务
- 主链路改为：
  - `patch apply`
  - `PoolManager.build_candidate_pool(...)`
  - `PoolManager.export_registry(...)`
- `WorkspaceMaterializer.apply_patch()` 中对 registry 的隐式 side effect 最好移除，至少不要再依赖它
- `remove` 必须真正删除 operator registry entry 并归一化权重
- `modify` 若目标 operator file_path 变化，registry 也要同步
- 初始 champion pool 必须从真实 `registry.yaml` 加载，不是空 dict

### 验收标准
- create / modify / remove 三种 action 最终都能从 `workspace/registry.yaml` 准确反映
- candidate pool 与 solver 实际加载的 pool 一致
- CLI 启动时 champion pool 不是空

---

## P0-6：统一真实运行入口，修复 CLI / config / runtime 主链脱节

### 为什么是 blocking
现在 `scion run` 默认路径不是“真实研究运行路径”，而更像 skeleton：

- 没有默认接入真实 `Runner`
- 没有默认接入真实 `ExperimentProtocol`
- champion 初始 `operator_pool={}`
- 运行时 config 实际走的是简化 schema，而不是增强 schema

如果不修，Sprint F 的“正式实验入口”本身就是错的。

### 涉及文件
- `scion/cli/main.py`
- `scion/config/problem.py`
- `scion/config/protocol_config.py`
- `scion/config/split_manifest.py`
- `scion/config/seed_ledger.py`
- `scion/core/campaign.py`
- `scion/lineage/champion_store.py`

### 具体任务
- CLI 默认构造真实对象：
  - `LocalSubprocessRunner`
  - `ExperimentProtocol`
  - `VerificationGate(problem_spec, runner, metrics_dir=...)`
- champion 初始化从 `registry.yaml` 读取 `operator_pool`
- 统一配置 schema：
  - `ProblemSpec` 保留在 `config/problem.py`
  - `ProtocolConfig / SplitManifest / SeedLedger` 只保留一套 authoritative 实现
- promote 时真正写 champion store / champions table

### 验收标准
- `scion run` 不再是 skeleton mode
- `inspect campaign` / `report summary` 中 champion/version/weight optimization 都是可信的
- canary / screening / validation / frozen 在 CLI 入口上真正可用

---

## P1-1：让 FailureRouter 的 action 真正落地，而不是“只分类不执行”

### 涉及文件
- `scion/core/campaign.py`
- `scion/failure/router.py`
- `scion/core/branch.py`

### 关键点
- `retry_llm` 应保留 candidate 级重试状态，不是下一轮随缘重新 proposal
- `retry_infra` 应进入 `BLOCKED_INFRA` / unblock 流程
- `consumes_budget` 必须和主循环真实一致
- `branch.retry_count` 不应混用为“所有类型失败的统一计数器”

---

## P1-2：补完整 artifact / summary，让其成为真正研究 artifact

### 涉及文件
- `scion/core/campaign.py`
- `scion/lineage/registry.py`
- `scion/cli/main.py`

### 关键点
- eval-only 步骤也要进入 `step_history`
- validation/frozen aggregate 必须进 summary
- cache stats 需要 per-step 真实写入
- `record_event` 和 `record_decision` 需要区分 event kind，避免 report 分母失真

---

## P1-3：补 prompt plumbing，把已实现能力真正注入 prompt

### 涉及文件
- `scion/proposal/context_manager.py`
- `scion/proposal/engine.py`
- `scion/proposal/llm_client.py`

### 关键点
- hypothesis prompt 加入：
  - `branch_code`
  - `branch_direction`
  - `exploration_coverage`
  - `strategy_guidance`
  - `champion_baselines`
- code prompt 加入：
  - `prior_code_failure`
- 同时保证 validation/frozen 只允许 aggregate，不允许 per-case 泄露

---

## P1-4：收敛 verification 命名与职责，避免 V5/V8 语义漂移

### 涉及文件
- `scion/verification/gate.py`
- `scion/verification/state_mutation.py`
- `scion/verification/nondeterminism.py`
- `scion/verification/state_leak.py`

### 关键点
- 当前 `state_mutation.py` 其实更像 solution consistency check，不是严格 state mutation
- `state_leak.py` 与 `nondeterminism.py` 高度重复
- 建议：
  - 要么实现真正的 V5 mutation harness
  - 要么把当前 proxy 改名为 `solution_consistency`
  - 删除/弃用 `state_leak.py`

---

## P1-5：增强 ContractGate 的 non-rng randomness 检测

### 涉及文件
- `scion/contract/gate.py`

### 关键点
- 支持 alias/import-from 检测：
  - `from uuid import uuid4; uuid4()`
  - `import uuid as u; u.uuid4()`
  - `from random import choice`
- 至少增加：
  - `time.time/time_ns`
  - `datetime.now/utcnow`
  - `numpy.random`
  - `__import__`

---

## P1-6：修复 report / inspect 的口径一致性

### 涉及文件
- `scion/cli/main.py`
- `scion/lineage/registry.py`

### 关键点
- report 的 family distribution 不要再拿 `change_locus` 冒充 family
- champions table 为空时不要把 `n_champions` 当 latest champion version
- weight optimization summary 应读真实 lineage，而不是假定成功

---

# 二、逐文件的 patch 级修改建议

下面这一部分我按“**直接需要改哪些文件**”来列。  
我只列我认为应该进入 Sprint F 前整改 PR 的文件。

---

## 1）`scion/core/campaign.py` —— 本轮整改的头号文件

### 必改点 A：pending hypothesis 必须重过 hypothesis Contract Gate
**现状**  
`_run_explore_step()` 中如果 `_pending_hypotheses.pop(bid)` 命中，会直接跳过 Round 1 Contract。

**建议 patch**
- 在 pending 路径中加：
  - `validate_hypothesis(hypothesis, active, blacklist)`
- 如果失败：
  - 按 proposal/contract failure 路由
  - 标记 hypothesis rejected
  - 不再继续 Round 2

---

### 必改点 B：fix patch 必须重过 patch Contract Gate
**现状**  
`_attempt_fix()` 生成 `fixed` 后直接 `apply_patch()`。

**建议 patch**
- 在 `_run_explore_step()` 的 verification_light 分支里：
  1. `fixed = self._attempt_fix(...)`
  2. `fixed_contract = self._contract_gate.validate_patch(fixed)`
  3. 只有 contract pass 才能 apply
- 若失败：
  - 记 `failure_stage="patch_contract_after_fix"` 或归并到 `patch_contract`

---

### 必改点 C：verification 前不要写 clean base
**现状**  
`record_verification_result(bid, True, code_hash)` 在 verification 前调用。

**建议 patch**
- 拆成两个接口：
  - `record_candidate_code_hash(branch_id, code_hash)`
  - `record_verification_pass(branch_id, code_hash)`
- apply patch 后只调前者
- verification pass 后才调后者

---

### 必改点 D：`_run_eval_step()` 不能再造 fake hypothesis
**现状**  
新建 `HypothesisRecord(uuid4())`。

**建议 patch**
- 用一个 mapping 保存 branch 当前 hypothesis record：
  - 例如 `self._branch_hypothesis_records: Dict[str, HypothesisRecord]`
- `_run_eval_step()` 直接取回原 record
- 这样 screening -> validation -> frozen -> promote 是一条连续链

---

### 必改点 E：`_run_eval_step()` 需要写 StepRecord
**现状**  
eval-only 步骤没有写 step_history。

**建议 patch**
- 在 `_apply_decision_and_finalize()` 返回后追加 `StepRecord`
- `StepRecord` 至少要包含：
  - `hypothesis_id`
  - `stage`
  - `decision_reason_codes`
  - `protocol_result`
  - `verification_passed=True`
  - `failure_stage=None`

---

### 必改点 F：重写 `_run_reconcile_step()`
**现状**  
只做 apply patch 成功就恢复 EXPLORE。

**建议 patch**
改成：
1. fresh workspace from new champion
2. reapply patch
3. `validate_patch()`
4. `VerificationGate.run()`
5. `run_experiment(stage=screening)` against new champion
6. 根据 screening 结果：
   - positive signal -> `READY_VALIDATE`
   - else -> `ABANDONED`

如果需要保存 stale 前状态，给 Branch 增加 `stale_from_state`。

---

### 必改点 G：修 promote + weight opt 路径
**现状**
- 先生成只读 snapshot
- 再尝试写回 snapshot registry
- champion hash 不含 registry

**建议 patch**
- promote 改成三段式：
  1. `promoted_ws` -> `staging_snapshot_mutable`
  2. `staging_snapshot_mutable` -> `optimization_ws`
  3. 若 improved，写回 `staging_snapshot_mutable/registry.yaml`
  4. 再 freeze staging 成 final snapshot
- final champion hash 使用新 `compute_snapshot_hash(final_snapshot)`

---

### 必改点 H：不要把 proposal/contract failure 误记成 `Decision.ABANDON`
**现状**  
好多 early failure 都把 StepRecord.decision 写成 `ABANDON`，但 branch 并没真正 abandon。

**建议 patch**
二选一：
- 方案 1：`StepRecord.decision: Optional[Decision]`
- 方案 2：新增 `step_outcome` / `route_action` 字段

我更建议方案 1 + `failure_stage`。

---

## 2）`scion/core/branch.py`

### 必改点
- 新增：
  - `record_candidate_code_hash()`
  - `record_verification_pass()`
- `mark_all_stale()` 时记录 `stale_from_state`
- `Branch` 增加：
  - `screening_expand_count`
  - `validation_expand_count`
  - `stale_from_state: Optional[BranchState]`
  - 可选：`current_hypothesis_id`

### 说明
当前只用一个 `expand_count`，screening / validation 会混淆，建议拆开。

---

## 3）`scion/core/models.py`

### 必改点
- `Branch`：
  - 增加 `screening_expand_count`
  - 增加 `validation_expand_count`
  - 增加 `stale_from_state`
- `StepRecord`：
  - 增加 `hypothesis_id`
  - 增加 `stage`
  - 增加 `decision_reason_codes`
  - `decision` 改成 `Optional[Decision]`
- `HypothesisRecord`：
  - 把 `family_id` 真正纳入 store schema
- `WeightOptimizationResult`：
  - 增加：
    - `strategy`
    - `eval_cases`
    - `eval_seeds`
    - `baseline_snapshot_hash` 或 `registry_hash_before/after`

---

## 4）`scion/proposal/context_manager.py`

### 必改点 A：补 prompt plumbing
`build_hypothesis_context()` 已经构造了很多字段，但 prompt split 没吃。

**需要确保这些字段最终进入 hypothesis prompt**
- `branch_code`
- `branch_direction`
- `exploration_coverage`
- `strategy_guidance`
- `champion_baselines`

### 必改点 B：当你补了 eval-only step_history 后，要重新做 exposure filter
**当前安全是“因为没记到”，不是“因为正确过滤”。**

建议：
- screening：
  - 允许 case_feedback / pattern_summary
- validation：
  - 只允许 aggregate：`win_rate / median_delta / ci / gate_outcome`
- frozen：
  - 只允许 aggregate + pass/fail
- 永远不向 LLM 提供 validation/frozen per-case feedback

### 必改点 C：`_build_champion_baselines()` 和 `_render_case_feedback()` 打通
当前 `champion_splits` 没真正灌进 `case_features`。

---

## 5）`scion/proposal/engine.py`

### 必改点
- `_split_hypothesis_context()`：
  - 增加独立 section：
    - `Current Branch Code`
    - `Exploration Coverage`
    - `Strategy Guidance`
    - `Champion Baseline Hints`
- `_split_code_context()`：
  - 增加 `prior_code_failure`
- 让 Round 2 明确看到上一次 code generation 失败原因，但仍不暴露 experiment history

---

## 6）`scion/proposal/llm_client.py`

### 建议 patch
- 对 `call_with_tool()` / `call()` 加统一 error classifier：
  - timeout
  - 429
  - 529 / overload
  - refusal
  - format error
- 把 `priority=foreground/background` 真正用于：
  - timeout
  - overload
  - refusal
- 新增每次调用的增量 cache stats 获取接口
  - 例如 `get_last_call_cache_stats()`

这样 `CampaignManager` 才能把 cache stats 写入 `StepRecord.cache_stats`。

---

## 7）`scion/contract/gate.py`

### 必改点 A：增强 `C9b_non_rng_random`
需要支持 alias/import-from。

**建议实现方式**
- 先建立 import alias map
  - `import uuid as u` -> `u => uuid`
  - `from uuid import uuid4` -> `uuid4 => uuid.uuid4`
- 再在 `ast.Call` 上解析：
  - `Name(...)`
  - `Attribute(...)`

### 必加检测
- `time.time`, `time.time_ns`
- `datetime.now`, `datetime.utcnow`
- `numpy.random.*`
- `__import__`

### 可选增强
- 识别 `rng` 的简单 alias：
  - `myrng = rng`

---

## 8）`scion/verification/gate.py`

### 必改点
- 统一 check naming
- 删掉/移除未使用的 `resolve_offloaded` import
- 明确当前 V5 / V8 的职责
- 如果暂时不做真正 state mutation harness，就把当前 proxy check 更名，避免误导

---

## 9）`scion/verification/state_mutation.py`

### 二选一建议

#### 方案 A：Sprint F 前做最小可信修复
把这个 check 明确改名为 `V5_solution_consistency`，不要再叫 state_mutation。  
这样至少不会“名实不符”。

#### 方案 B：实现真正的 mutation harness
如果你愿意投入一点时间，建议在 surrogate 侧增加一个测试钩子，让 solver 在 operator 调用前后对输入 solution 做 hash / deep compare。  
但这会涉及 surrogate 修改，Sprint F 前不一定最划算。

**我建议 Sprint F 前优先走方案 A。**

---

## 10）`scion/verification/nondeterminism.py`

### 必改点
- 在 detail JSON 里加上 `classification`
  - `ENV_NONDETERMINISM`
  - `CANDIDATE_NONDETERMINISM`
  - `UNKNOWN_NONDETERMINISM`
- 继续保留：
  - `run1_ref`
  - `run2_ref`
  - `candidate_archive_ref`

### 说明
这和 T02 设计是对齐的。

---

## 11）`scion/verification/state_leak.py`

### 建议 patch
- **删除**
- 或保留为 deprecated wrapper，内部直接调用 `check_nondeterminism()`

### 原因
现在它和 `nondeterminism.py` 基本重复，只会继续制造 V5/V8 语义混乱。

---

## 12）`scion/protocol/experiment.py`

### 必改点 A：重写样本选择逻辑
新增 helper：
- `_select_cases(stage, hypothesis_action, expand_round)`
- `_select_seeds(stage)`

### 必改点 B：改成 case-level aggregation
建议流程：
1. 对每个 case 跑所有 seeds
2. 聚合成 case-level `win/loss/tie` + case-level delta
3. 对 case-level 列表做 stats

### 必改点 C：canary 使用独立 split
不要再 `screening[:2]`

### 必改点 D：补 frozen use cap
可以在 CampaignManager 里记，也可以 Protocol 内部记，但必须有一处 authoritative。

### 必改点 E：把 champion baseline 写入 case_feedback.case_features
给 T10 用。

---

## 13）`scion/protocol/stats.py`

### 必改点
- 接口要改成接收 case-level deltas
- bootstrap CI 对 case-level delta 重采样
- `n_cases` 必须对应真实 case 数

---

## 14）`scion/runtime/workspace.py`

### 必改点 A：停止依赖 `_update_registry()` side effect
主链路用 `PoolManager.export_registry()` 覆盖 registry。

### 必改点 B：新增 final snapshot hash
建议新增：
- `compute_snapshot_hash(workspace: str) -> str`
  - 包含 `operators/**/*.py`
  - 包含 `registry.yaml`

### 必改点 C：支持 mutable staging + freeze
新增 helper：
- `create_mutable_snapshot_from_workspace(...)`
- `freeze_snapshot(path)`

这样 promote 后参数优化路径就更干净。

---

## 15）`scion/runtime/pool_manager.py`

### 必改点
- 把 create / modify / remove 的 registry 变更统一收口到这里
- 新增更显式接口，例如：
  - `apply_hypothesis_patch_to_pool(champion_pool, hypothesis, patch) -> pool`
- `update_weights()` 保留
- `export_registry()` 成为唯一写 registry 的入口

---

## 16）`scion/runtime/subprocess_runner.py`

### 建议 patch
- `resolve_offloaded()` 增加路径沙箱
- 只允许读取指定 artifact 根目录下的文件
- 如果路径越界，抛 `ValueError`

---

## 17）`scion/parameter/optimizer.py`

### 必改点
- `optimize()` 接口改成显式接收 baseline weights，或者构造器传入 baseline weights
- baseline 必须先评估
- `baseline_weights` 不得再来自第一条随机样本
- `improved` 必须与 true baseline 比较
- observations 需要可落盘

---

## 18）`scion/parameter/evaluator.py`

### 建议 patch
- `collect_baseline()` 返回更完整结构：
  - baseline objectives
  - baseline weights
- `evaluate_weights()` 可接受 `baseline_objectives`
- 失败 pair 的处理要一致：
  - 当前直接 skip；最好记录到 observations 里，避免 silent bias

---

## 19）`scion/lineage/registry.py`

### 必改点 A：给 `experiment_events` 增加 `event_kind`
例如：
- `step`
- `decision`
- `promote`
- `weight_optimization`

否则 report 的总数会失真。

### 必改点 B：补关键字段
至少补：
- `hypothesis_id`
- `base_champion_id`
- `raw_metrics_ref`
- `decision_reason`
- `decision_reason_codes`
- `protocol_version`
- `split_version`
- `seed_version`

### 必改点 C：weight optimization 记录补全
- `strategy`
- `eval_cases_json`
- `eval_seeds_json`
- `observations_ref`

---

## 20）`scion/lineage/branch_store.py`

### 必改点
- hypotheses 表增加 `family_id`
- `mark_status()` 最好检查 rowcount，防止 silent fail
- 如果保留 current store，必须和 `core.models.HypothesisRecord` 字段对齐

---

## 21）`scion/lineage/champion_store.py`

### 必改点
- campaign promote 时真正调用 `ChampionStore.promote()`
- CLI/report 查询 champion 时优先读 champions table，而不是靠猜

---

## 22）`scion/config/problem.py`

### 必改点
- 只保留 `ProblemSpec / SearchSpace / SolverConfig / ParameterSearchConfig`
- 删掉或废弃内部那套简化版：
  - `ProtocolConfig`
  - `SplitManifest`
  - `SeedLedgerConfig`

---

## 23）`scion/config/protocol_config.py` / `split_manifest.py` / `seed_ledger.py`

### 必改点
- 成为唯一 authoritative schema
- 如果为了兼容旧调用，可以加兼容 property：
  - `screening_win_rate_threshold`
  - `validation_win_rate_threshold`
  - 等
- 让旧代码能平滑迁移，但底层只保留一套

---

## 24）`scion/cli/main.py`

### 必改点 A：`run` 默认接真实 runtime
- `LocalSubprocessRunner`
- `ExperimentProtocol`
- `VerificationGate`

### 必改点 B：初始 champion pool 从 registry 加载
- `from scion.runtime.pool_manager import read_registry`

### 必改点 C：补命令
- `scion inspect weights`
- `scion optimize-weights`

### 必改点 D：report 不要再误用 `n_champions` 当 latest version
要读真实 champion table 或 campaign summary。

---

## 25）`scion/memory/hypothesis_store.py`

### 建议 patch
- **删除**
- 或改成对 `lineage.branch_store.HypothesisStore` 的 thin wrapper

### 原因
这是一份和主链脱节的重复实现，会继续制造 split-brain。

---

## 26）`problems/warehouse_delivery/protocol.yaml`

### 必改点
如果你要切到 authoritative nested schema，这个文件也必须迁移。  
建议至少补成：

- `version`
- `screening.n_cases_modify`
- `screening.n_cases_create`
- `screening.n_seeds`
- `screening.expand_to_modify`
- `screening.expand_to_create`
- `validation.n_cases`
- `validation.n_seeds`
- `validation.expand_to`
- `frozen.n_cases`
- `frozen.n_seeds`
- `frozen.max_uses_per_campaign`
- `canary.cases`
- `canary.seeds`
- `gates.*`

---

# 三、Sprint F 前必须补齐的测试清单（pytest 风格）

下面给你一套**最少但够硬**的测试清单。  
我按“先保架构边界，再保协议，再保参数层，再保 CLI/集成”排序。

---

## A. 控制边界 / Campaign 主循环

**建议文件：**
- `tests/unit/core/test_campaign_control_boundaries.py`

### 必须有的测试
1. `test_pending_hypothesis_reruns_contract_gate_before_code_retry`
2. `test_fix_patch_must_pass_contract_gate_before_apply_patch`
3. `test_last_clean_code_hash_updates_only_after_verification_pass`
4. `test_verification_fail_does_not_promote_candidate_to_clean_base`
5. `test_eval_only_step_reuses_original_hypothesis_id`
6. `test_eval_only_step_is_written_to_step_history`
7. `test_promote_marks_original_hypothesis_as_promoted`
8. `test_abandon_marks_original_hypothesis_as_rejected`
9. `test_reconcile_reruns_contract_verification_and_rescreening`
10. `test_reconcile_fails_to_abandoned_when_rescreen_fails`

### 断言重点
- `validate_hypothesis()` / `validate_patch()` 的调用次数
- `last_clean_code_hash` 的更新时机
- hypothesis_id 在 screening -> validation -> frozen 一致
- stale reconcile 不是“apply 成功就恢复”

---

## B. Protocol 正确性

**建议文件：**
- `tests/unit/protocol/test_experiment_protocol.py`

### 必须有的测试
1. `test_run_canary_uses_canary_cases_and_canary_seeds`
2. `test_screening_selects_modify_case_count_from_config`
3. `test_screening_selects_create_case_count_from_config`
4. `test_validation_selects_configured_case_count`
5. `test_frozen_selects_configured_case_count`
6. `test_expand_increases_cases_not_seeds`
7. `test_case_is_primary_statistical_unit`
8. `test_case_level_majority_vote_is_used_for_seed_aggregation`
9. `test_validation_exposes_aggregate_only`
10. `test_frozen_exposes_pass_fail_and_aggregate_only`
11. `test_screening_retains_case_feedback_only_for_screening`
12. `test_frozen_usage_cap_is_enforced`

### 断言重点
- runner 实际收到的 `case` / `seed` 集合
- `stats.n_cases` 等于 case 数
- expand 前后 seed 集合不变
- validation/frozen 的 `case_feedback == ()`

---

## C. Parameter Search 正确性

**建议文件：**
- `tests/unit/parameter/test_weight_optimizer.py`

### 必须有的测试
1. `test_optimizer_evaluates_true_baseline_before_random_samples`
2. `test_random_local_optimizer_is_seed_deterministic`
3. `test_improved_false_when_best_score_below_true_baseline`
4. `test_improved_true_only_when_best_score_exceeds_true_baseline`
5. `test_weight_optimization_records_observations_ref`
6. `test_weight_optimization_writeback_uses_mutable_staging_not_readonly_snapshot`
7. `test_snapshot_hash_changes_when_registry_yaml_changes`
8. `test_weight_optimization_lineage_contains_cases_seeds_and_strategy`

### 断言重点
- `baseline_weights` 等于当前 registry weights
- `baseline_score` 是 baseline 实测结果
- best 不如 baseline 时 `improved is False`
- writeback 后 final snapshot 中权重真实变化

---

## D. Registry / Pool 一致性

**建议文件：**
- `tests/unit/runtime/test_pool_registry_sync.py`

### 必须有的测试
1. `test_create_new_updates_registry_via_pool_manager`
2. `test_modify_updates_registry_file_path_when_target_changes`
3. `test_remove_deletes_registry_entry`
4. `test_remove_renormalizes_remaining_weights`
5. `test_export_registry_matches_candidate_pool_exactly`
6. `test_initial_champion_pool_loaded_from_registry_yaml`

### 断言重点
- `workspace/registry.yaml` 最终内容
- solver 将看到的 pool 与 hypothesis/patch 一致

---

## E. Prompt plumbing / 暴露控制

**建议文件：**
- `tests/unit/proposal/test_prompt_plumbing.py`

### 必须有的测试
1. `test_hypothesis_prompt_contains_branch_code_when_branch_diff_exists`
2. `test_hypothesis_prompt_contains_strategy_guidance`
3. `test_hypothesis_prompt_contains_exploration_coverage`
4. `test_hypothesis_prompt_contains_champion_baselines`
5. `test_code_prompt_contains_prior_code_failure`
6. `test_hypothesis_prompt_never_contains_validation_per_case_feedback`
7. `test_hypothesis_prompt_never_contains_frozen_per_case_feedback`
8. `test_validation_and_frozen_history_render_aggregate_only`

### 断言重点
- prompt 文本里真有这些 section
- validation/frozen 没有 case_id / per-case delta 级细节

---

## F. Contract 安全检测

**建议文件：**
- `tests/unit/contract/test_non_rng_random_detection.py`

### 必须有的测试
1. `test_detects_uuid_uuid4_direct_call`
2. `test_detects_uuid_alias_call`
3. `test_detects_from_import_uuid4`
4. `test_detects_random_choice_from_import`
5. `test_detects_os_urandom`
6. `test_detects_time_time`
7. `test_allows_rng_choice`
8. `test_allows_rng_alias_if_supported`

### 断言重点
- alias/import-from 场景不漏检
- `rng.*` 不误杀

---

## G. Lineage / Artifact 完整性

**建议文件：**
- `tests/unit/lineage/test_registry_and_summary.py`

### 必须有的测试
1. `test_experiment_event_contains_real_hypothesis_id`
2. `test_experiment_event_contains_raw_metrics_ref`
3. `test_decision_reason_codes_are_recorded`
4. `test_event_kind_prevents_double_counting_in_summary`
5. `test_eval_only_steps_appear_in_campaign_summary`
6. `test_campaign_summary_contains_validation_and_frozen_aggregate_results`
7. `test_weight_optimization_record_contains_observations_ref`
8. `test_champion_promotion_is_persisted_to_champions_table`

### 断言重点
- summary / DB / in-memory state 三者口径一致
- total_events 不被 decision-only row 污染

---

## H. CLI / 真实运行入口

**建议文件：**
- `tests/integration/test_cli_real_run.py`

### 必须有的测试
1. `test_cli_run_constructs_real_runner_protocol_and_verification_gate`
2. `test_cli_run_loads_initial_champion_pool_from_registry`
3. `test_cli_inspect_campaign_reports_weight_optimization`
4. `test_cli_inspect_weights_works`
5. `test_cli_optimize_weights_works_on_existing_snapshot`

### 断言重点
- `CampaignManager` 不是在 `experiment_protocol=None` 的 skeleton 模式下运行
- inspect/report 能看到真实 champion/operator_pool/weight opt 记录

---

## I. 最小端到端集成测试

**建议文件：**
- `tests/integration/test_sprint_f_smoke.py`

### 必须有的测试
1. `test_screening_to_validation_to_frozen_to_promote_end_to_end`
2. `test_promote_triggers_weight_optimization_and_persists_result`
3. `test_stale_branch_reconcile_against_new_champion_end_to_end`
4. `test_create_modify_remove_all_produce_correct_registry_and_protocol_results`

### 说明
这些测试可以用：
- `FakeRunner`
- `QueueLLMClient`
- 小型临时 problem fixture
来做，不一定要跑真实 surrogate。

---

# 四、建议的测试 fixture 设计

为了让上面这些测试好写，我建议你先补 5 个 fixture：

1. `tmp_problem_tree`
   - 带最小 `problem.yaml / protocol.yaml / split_manifest.yaml / seed_ledger.yaml / registry.yaml`

2. `fake_runner`
   - 可根据 `(workspace, case, seed)` 返回可控 objective
   - 能记录被调用的 cases / seeds / registry_path

3. `queue_llm_client`
   - 按顺序吐出 hypothesis / patch / fix tool payload

4. `promoted_workspace_fixture`
   - 一个带 registry.yaml 和 operators 的 promoted candidate workspace

5. `stale_branch_fixture`
   - 模拟 champion v1 -> v2 后 stale branch 的 reconcile 场景

---

# 五、推荐的整改 PR 切分

为了减少回归风险，我建议按下面 5 个 PR 切：

### PR-1：`control-boundary-hardening`
- 修 gate bypass
- 修 clean-base 污染
- 修 reconcile

### PR-2：`protocol-correctness`
- case-level stats
- canary split
- expand 规则
- frozen cap

### PR-3：`hypothesis-lineage-identity`
- hypothesis 生命周期
- step_history / summary 完整性
- event_kind

### PR-4：`parameter-search-correctness`
- true baseline
- staging snapshot
- hash includes registry
- observations lineage

### PR-5：`cli-config-prompt-plumbing`
- CLI 真实入口
- config unification
- prompt plumbing
- inspect weights / optimize-weights

---

# 六、Sprint F 前的 go / no-go 门槛

我建议你把 Sprint F 启动条件写死为下面 6 条：

1. **所有 P0 测试通过**
2. `scion run` 默认路径已接入真实 runner/protocol
3. stale reconcile 的集成测试通过
4. canary / screening / validation / frozen 的 case/seed 使用完全符合配置
5. weight optimization 的 baseline / improved 判定已修正
6. `campaign_summary.json + scion.db + inspect/report` 三者口径一致

只要这 6 条没全绿，我都不建议进入 Sprint F 正式实验。

---

如果你愿意，我下一条可以继续直接给你：

1. **一版可执行的 Sprint F 整改任务表（按 PR / 子任务 / 验收标准 / 工时拆解）**
2. **`core/campaign.py` 和 `protocol/experiment.py` 的伪 diff 级修改草案**
3. **一套 pytest 文件树建议，直接能开工建测试文件**
