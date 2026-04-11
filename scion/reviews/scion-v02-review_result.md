# 📋 内容审核报告

- **审核时间**: 2026-04-11 13:58:38
- **审核模型**: gpt-5.4-pro
- **推理深度**: high
- **内容来源**: sprint-e-review-prompt.md
- **内容长度**: 551019 字符
- **审核耗时**: 957.2 秒

---

## 📝 审核意见

以下审查基于你提供的设计文档与源码做**静态架构审阅**。  
我没有实际运行单测/集成测，因此个别运行时结论仍有不确定性；但就**控制边界、协议正确性、模块耦合、实现一致性**而言，已经能明确识别出一批 **blocking 级**问题。

整体先给一句判断：

> **Scion v0.2 的“骨架方向”是对的，但当前实现还没有达到可直接进入 Sprint F 正式研究实验的可信程度。**  
> 最大问题不在“功能没写”，而在于：**若干关键路径虽然“看起来在跑”，但并不满足架构 v3 的严格边界和实验协议要求**。

---

# 6.1 架构合规性（Pass/Fail + 详细说明）

| 约束 | 结果 | 说明 |
|------|------|------|
| 三层控制模型完整性 | ❌ Fail | 主路径大体遵循 LLM → Contract → Verification → Protocol → Decision，但至少有 3 条关键绕行：1) `CampaignManager._attempt_fix()` 生成的 fix patch **未重新经过 Contract Gate**；2) `CampaignManager._run_reconcile_step()` 对 stale branch 仅重打 patch，**未重新走 Contract → Verification → re-screening**；3) `pending hypothesis` 复用时 **未重新经过 hypothesis Contract Gate**。这三处都违反了架构 v3 的“LLM 输出必须重新过双闸门”原则。 |
| Decision Input Guard 无自由文本 | ✅ Pass | 就已提供的 `DecisionFeatures`、`DecisionEngine` 和 `CampaignManager._evaluate()` 调用看，Decision Layer 仍只消费数值/枚举/布尔特征，没有直接读取 hypothesis_text、verification_detail、diagnosis recommendation 等自由文本。`StagnationDetector`/`CircuitBreaker` 也没有把自由文本塞进 `DecisionFeatures`。 |
| 暴露控制（validation/frozen 不泄露给 LLM） | ✅ Pass（但实现不完整） | 当前实现**没有看到 validation/frozen per-case 数据泄露给 LLM**。更准确地说：它是通过“`_step_history` 基本只记录 explore/screening 步”实现的，属于**偏保守且不完整**——安全上是好的，但研究反馈利用不足。 |
| LLM 只能提案不能决策 | ✅ Pass（有保留） | 决策仍由 `DecisionEngine` 确定性完成，LLM 没有直接晋升/淘汰权限。保留点在于：fix/reconcile 路径存在 Gate bypass，意味着 tainted patch 可直接进入后续验证，虽然仍未直接进入 Decision。 |
| 参数搜索与结构搜索隔离 | ⚠️ 基本 Pass | 隔离方向基本成立：promote 后触发、独立 workspace、副本上优化、回写 champion snapshot、写独立 lineage。**但参数优化的 baseline 判定有严重正确性 bug**（见下文），会导致“是否 improved”的结论不可靠。隔离成立，不代表结果可信。 |

---

# 6.2 模块级审查结果

---

## 3.1 `core/campaign.py` — 主循环（重点）

| 审查项 | 状态 | 发现 | 建议 |
|---|---|---|---|
| `run()` / `run_one_step()` 是否符合架构 v3 §18 | ⚠️ | 主框架顺序基本像伪代码，但有多处关键偏差：`verification_gate` 默认没有 runner、`experiment_protocol` 可为 `None`，CLI 也没把真实 runner/protocol 接上，导致默认运行只是“骨架模式”，不是完整研究闭环。 | 把“骨架模式”与“真实模式”显式分离；CLI 的默认 `run` 必须构造真实 `Runner + ExperimentProtocol + VerificationGate`。 |
| T20 降级恢复：pending hypothesis 复用是否重新过 Contract Gate | ❌ | `_run_explore_step()` 中 `pending = self._pending_hypotheses.pop(...)` 后直接跳过 Round 1 Contract Gate，进入 Round 2。 | 在 pending hypothesis 复用时，至少重新执行一次 `validate_hypothesis()`；哪怕对象未变，也应维持硬边界一致性。 |
| verification_light fix 是否重新过 Contract Gate | ❌ | `_attempt_fix()` 返回 fix patch 后，`_run_explore_step()` 直接 `apply_patch()` + `VerificationGate.run()`，**没有 `validate_patch(fixed)`**。这是最明显的 Gate1 绕过。 | fix patch 也必须走 `ContractGate.validate_patch()`；失败应按 Proposal/Contract failure 路由。 |
| T29 熔断器：连续 LLM 失败终止是否写 summary | ⚠️ | `CircuitBreaker` 会停止 campaign，`campaign_summary.json` 中有 `stopped_reason="circuit_breaker"`，但缺少更完整的 last error / failure chain。 | 在 summary 中补 `last_failure_detail`、trip round、trip phase。 |
| T25/T23 停滞检测是否回喂 Decision / LLM | ✅ | `_run_stagnation_check()` 仅写日志、写 `_diagnostics`、写 summary；未进入 `DecisionFeatures`，也未注入 prompt。 | 保持这一点；后续若要回喂 LLM，只能进 Creative Layer，不可进 Decision Layer。 |
| `_on_promote()` 权重优化 hook 是否独立 workspace | ✅ | `snapshot -> copy to eval_ws -> optimize -> improved 时写回 snapshot`，隔离方向正确。 | 保持；但修 baseline/improved 判定 bug。 |
| copytree 后 chmod 修复 | ✅ | `_run_weight_optimization()` 中对 `eval_ws` 递归 chmod；`WorkspaceMaterializer.create_branch_workspace()` 也调用 `_make_tree_writable()`。 | 通过。 |
| 分支状态机是否符合 v3 §11.3 | ⚠️ | 基本有 NEW/EXPLORE/READY_VALIDATE/...；但 **stale reconcile 语义不对**，且 expand 计数与 validation/screening 混用。 | 把 stale reconcile 改成“reapply → Contract → Verification → re-screening”；拆分 screening_expand_count 与 validation_expand_count。 |
| Budget 管理是否正确 | ❌ | 预算路径不统一：1) `FailureRouter` 的 retry/discard 决策多数没有被真正执行；2) `should_stop()` 总是传 `can_create_new=True`；3) expand 通过“新增 synthetic seeds”而不是协议定义的加 case。 | 统一 budget source of truth；把 retry/action 真正接入主循环；停止条件必须感知 max_active_branches / no-progress。 |
| 记录“最后 clean 代码基线”是否正确 | ❌ | `_run_explore_step()` 在**验证前**就执行 `self._branch_ctrl.record_verification_result(bid, True, code_hash)`，导致 `last_clean_code_hash` 被错误污染。 | 把 `record_verification_result(..., passed=True, ...)` 移到 verification pass 之后；验证前只能更新 `current_code_hash`，不能更新 `last_clean_code_hash`。 |
| stale 分支 reconcile 是否重新验证/重筛 | ❌ | `_run_reconcile_step()` 只是 fresh workspace + `apply_patch()`，成功就 `reconcile_stale(success=True)`，**没有 Contract、没有 Verification、没有 re-Screening**。 | 这是 blocking：必须重走 Gate1、Gate2 和 screening。 |
| eval-only 步骤是否被记录进 `step_history` | ❌ | `_run_eval_step()` 返回前没有 append `StepRecord`。因此 validation/frozen/expand 结果基本不进 step history / campaign summary。 | 在 `_run_eval_step()` 末尾补 `StepRecord` 记录；否则 T03/T06/T26/T10 都是残的。 |

**补充结论：**  
`core/campaign.py` 是当前**最需要整改**的文件。不是“有点瑕疵”，而是几处核心控制路径确实没有按照架构 v3 落地。

---

## 3.2 `proposal/context_manager.py` — 上下文构造（重点）

| 审查项 | 状态 | 发现 | 建议 |
|---|---|---|---|
| `build_hypothesis_context()` 是否只暴露 screening 数据 | ✅ | 目前实际只会看到 explore/screening history；validation/frozen 结果因为未入 `step_history`，所以没泄露。 | 安全上通过，但后续如果补记录，需要继续严控只暴露 aggregate。 |
| T07 HypothesisFamily 规则提取是否鲁棒 | ⚠️ | `_extract_mechanism_label()` 是纯关键词启发式，可作为 MVP，但**不持久化、只做 branch-local 重建**，且没有接到 lineage。 | 最少把 `family_id` 写进 `HypothesisRecord` / SQLite。 |
| T08 Strategy guidance 是否构成决策指令 | ⚠️ | 文本本身如果进入 prompt，不构成 Decision Layer 越权；但当前更大的问题是：**它根本没被真正注入 prompt**。 | 在 `_split_hypothesis_context()` 中显式加入 `strategy_guidance` block。 |
| T09 richer feedback 是否泄露 validation/frozen per-case | ✅ | `_render_case_feedback()` 只渲染 screening case feedback；validation/frozen per-case 没有进入。 | 通过。 |
| T10 Champion baseline hints 数据来源是否只来自 screening | ✅ / ❌ | 数据来源设计上来自最近 screening `pair_feedback`，方向对；但 **`champion_baselines` 构建结果没有真正进入 prompt**，而 `_render_case_feedback()` 依赖的 `champion_splits` 也没填充。 | 把 baseline hints 接到 `_split_hypothesis_context()`；并在 protocol 聚合时填入 `case_features["champion_splits"]`。 |
| T26 “What Worked” 是否只含 screening | ✅（被动成立） | 因为 `step_history` 没记录 validation/frozen，`What Worked` 实际只会从 screening/high-win-rate 来。安全上没泄露。 | 若后续补 validation/frozen 记录，需明确只允许 screening 正向记忆进入 LLM。 |
| Prompt caching 策略是否合理 | ⚠️ | 分 block + `cache_control` 的方向是对的；但 `build_hypothesis_context()` 产出的 `branch_code / branch_direction / exploration_coverage / strategy_guidance / champion_baselines` 全部**没有被 `_split_hypothesis_context()`使用**，导致很多 Sprint E 能力“写了但没生效”。 | 把这些字段真正接进 prompt，并把 cache stats 回填到 step record / summary。 |
| branch-specific code 是否展示给 LLM | ❌ | `_read_branch_code()` 已实现，但 `_split_hypothesis_context()` 根本没用 `branch_code`。这使得分支内“基于当前代码继续迭代”的语义大幅削弱。 | 在 hypothesis prompt 中明确加入 “Current branch code diff vs champion”。 |
| code retry 的 prior failure 是否反馈给 Round 2 | ❌ | `build_code_context()` 设置了 `prior_code_failure`，但 `_split_code_context()` 没有用。 | 把 prior failure 作为独立 section 注入 code prompt。 |

---

## 3.3 `proposal/engine.py` + `schemas.py` — Proposal 引擎

| 审查项 | 状态 | 发现 | 建议 |
|---|---|---|---|
| T19 Pydantic 校验是否与 dataclass 一致 | ⚠️ | `HypothesisProposalInput` 对 `action` 做了 validator；但 `predicted_direction` 没做 enum validator。`PatchProposalInput` **没有对 `action` 做 enum validator**。 | 为所有枚举字段补 validator；对 `suggested_weight` 加范围校验。 |
| `ProposalValidationError` 是否路由为 A 类失败 | ✅ | `_parse_*` 抛 `ProposalValidationError`，`CampaignManager` 捕获后按 `FailureEvent(category="proposal")` 路由，不消耗预算。 | 通过。 |
| 两轮 Proposal 上下文隔离是否正确 | ✅ | Round 2 `build_code_context()` 没有引入 experiment history / sibling / blacklist，符合设计。 | 保持。 |
| prompt split 是否真正吃到 ContextManager 的扩展字段 | ❌ | `CreativeLayer._split_hypothesis_context()` 与 `_split_code_context()` 没有消费多个 v0.2 扩展字段。 | 这是 prompt plumbing 断裂点，需优先修。 |

---

## 3.4 `proposal/llm_client.py` — LLM 通信层

| 审查项 | 状态 | 发现 | 建议 |
|---|---|---|---|
| T22 分级重试（foreground/background） | ⚠️ | 只有 429 rate limit 对 background 特判“立即放弃”；timeout / 529 / refusal 并没有真正按 source 分级。 | 把 timeout / overload / refusal 都纳入 query source 分级策略。 |
| T27 截断恢复是否会无限循环 | ✅ | `MAX_TRUNCATION_RETRIES = 2`，不会无限循环。 | 通过。 |
| 部分内容返回后下游能否处理 | ⚠️ | tool_use 截断后若仍截断，最终可能抛 `LLMFormatError`；没有“部分可用”恢复策略。 | 若要完全实现 T27，可在 tool input 缺字段时做结构化续写提示，而非仅重试。 |
| Prompt caching 是否正确实现 | ✅ | 支持 `system_blocks` + `cache_control`，并记录 usage。 | 通过。 |
| 429 / 529 / refusal / timeout 处理 | ⚠️ | 429、timeout 有；529 没有显式分类；refusal 也没有独立处理，只会落成 format/tool error。 | 增加错误分类函数，把 529/refusal 显式写入 failure taxonomy。 |
| cache stats 是否真正进入 campaign artifact | ❌ | client 里统计了 `_cache_stats`，但 `StepRecord.cache_stats` 基本没被填，summary 聚合结果会接近空。 | 在 `CreativeLayer`/`CampaignManager` 调用后把 cache stats 注入 step record。 |

---

## 3.5 `contract/gate.py` — Contract Gate

| 审查项 | 状态 | 发现 | 建议 |
|---|---|---|---|
| C1-C10 是否与架构 v3 §9 一致 | ✅（大体） | schema / locus / target / whitelist / frozen / syntax / interface / import / sensitive api / novelty 都在。 | 通过，但还有两点需要加强。 |
| T21 `C9b_non_rng_random` 检测是否完整 | ❌ | 只能抓 `ast.Attribute(Name(...), attr)` 形式；**抓不到** `from uuid import uuid4; uuid4()`、`import uuid as u; u.uuid4()`、`from random import choice`、alias、`time.time()` 等。 | 构建 import alias map，再做 call-site resolution；把 `time/time_ns`, `datetime.now`, `secrets`, `numpy.random` 等纳入。 |
| `rng.*` 跳过逻辑能否被绕过 | ⚠️ | 直接 alias `myrng = rng; myrng.choice()` 会被误判/漏判，语义不清。 | 最好做简单数据流：识别 `rng` 的别名绑定。 |
| import 白名单是否与 problem.yaml 一致 | ✅ | 当前使用 `self._spec.search_space.import_whitelist`，一致。 | 通过。 |
| sensitive API 是否足够 | ⚠️ | 可被 `__import__("os").system(...)`、`getattr(os, "system")(...)` 等绕过。 | 若安全边界要更硬，补 AST 调用模式分析；至少禁 `__import__`。 |

---

## 3.6 `verification/gate.py` — Verification Gate

| 审查项 | 状态 | 发现 | 建议 |
|---|---|---|---|
| V1-V9 检查顺序是否正确 | ✅ | 顺序是 syntax → interface → unit tests → regression → state_mutation → feasibility → objective → nondeterminism → perf_guard，顺序基本正确。 | 通过。 |
| 失败路由是否符合 v3 §10.4 | ⚠️ | Gate 本身正确区分 light/heavy；但 **CampaignManager 没有完整兑现 retry policy**。verification_light 理论可多次修复重试，实际只即时修一次，失败后就收尾。 | 把 FailureRouter 的返回动作真正接到主循环。 |
| V5/V8 拆分逻辑是否正确 | ❌ | `check_state_mutation()` **不是严格的 state-mutation check**，只是“输出解内部一致性 proxy”；`check_nondeterminism()` 才是真正双跑确定性检查。另有一个遗留 `state_leak.py` 与 `nondeterminism.py` 重复。 | 明确重构：要么实现真正的 V5 input mutation 检测，要么把当前 V5 改名为 `solution_consistency`，避免语义错位。 |
| 检查命名是否一致 | ❌ | 实际 `CheckResult.name` 用的是 `V3_feasibility / V4_objective / V6_perf_guard` 等旧编号，与 gate 顺序/架构文档不一致。 | 统一所有 V-code；否则 report/diagnosis 会长期混乱。 |

---

## 3.7 `core/stagnation.py` — 停滞检测

| 审查项 | 状态 | 发现 | 建议 |
|---|---|---|---|
| 四种检测阈值是否合理 | ⚠️ | 规则本身合理，但全部 hard-coded，没有与 protocol/budget 联动，也没有基于历史 campaign 校准。 | 先保留启发式，再把阈值配置化。 |
| recommendation 是否只用于日志/报告 | ✅ | 没有进入 DecisionFeatures，也没有自动驱动决策。 | 通过。 |
| 与 campaign 集成是否正确 | ✅ | `run()` 每轮后调用 `_run_stagnation_check()`，位置合理。 | 通过。 |
| 是否足够研究可用 | ⚠️ | 因 `step_history` 漏记 eval-only 步骤，诊断会偏向 explore/screening。 | 先补 step history，再校准 detector。 |

---

## 3.8 `parameter/` — 参数搜索层

| 审查项 | 状态 | 发现 | 建议 |
|---|---|---|---|
| `ParameterSearchSpace / evaluator / optimizer` 接口是否一致 | ⚠️ | 基本一致，但 baseline 语义断裂。`eval_fn` 返回“相对 baseline 的 median delta”，optimizer 却把**第一条随机观察**当 baseline。 | 修 baseline 定义。 |
| `RandomLocalWeightOptimizer` 是否 seed-deterministic | ✅ | 使用 `random.Random(seed)`，确定性成立。 | 通过。 |
| `BayesianWeightOptimizer` fallback chain 是否可靠 | ⚠️ | 实现为 `skopt -> scipy -> pure-python UCB`，不完全等于设计文档的 `skopt -> scipy -> RandomLocal`，但可接受。真正问题不在 fallback，而在 baseline/improved 判定错误。 | 修正确性优先于优化器 sophistication。 |
| 优化结果是否只写 champion snapshot | ✅ | 在 `_run_weight_optimization()` 的 eval_ws 上评估，只在 improved 时写回 snapshot。 | 通过。 |
| `WeightOptimizationResult` lineage 是否完整 | ❌ | `observations_ref` 始终是空字符串；没有记录 eval cases、seeds、strategy、bounds 等关键信息。 | 把 observations 落盘，并把 strategy/eval_cases/eval_seeds 写入 lineage。 |
| baseline 是否正确 | ❌ | `RandomLocalWeightOptimizer.optimize()` **没有评估当前 champion 权重**；`baseline_score` 和 `baseline_weights` 被错误设置成“第一条随机样本”。`improved = best_score > baseline_score` 因而是错的。 | 这是 blocking：必须先评估 current_weights，且 improved 应与 true baseline 比较。 |
| 可能写入更差权重吗 | ⚠️/❌ | 存在风险：若第一条随机样本更差，best 只要比它好就会 `improved=True`，即使依然比真实 baseline 差。 | `improved` 必须改成 `best_score > true_baseline_score (+ epsilon)`。 |

---

## 3.9 `runtime/` — 运行时隔离

| 审查项 | 状态 | 发现 | 建议 |
|---|---|---|---|
| subprocess env 是否 clean | ✅ | `_build_clean_env()` 只保留 `PATH/PYTHONPATH`，并固定 `PYTHONHASHSEED=0`。 | 通过。 |
| T28 输出外包 `__offloaded__:` 是否有注入风险 | ⚠️ | `resolve_offloaded()` 对任何以此前缀开头的字符串都会尝试读文件，若未来对不可信 stdout/stderr 使用，有任意文件读取风险。 | 限制可读取路径必须在 workspace/artifacts 目录下。 |
| workspace 隔离是否充分 | ⚠️ | champion snapshot readonly、副本 workspace 独立、weight opt 用 copy，方向正确；但 `record_verification_result(..., True, ...)` 过早调用会让**未验证代码被当成 clean base**。 | 修 branch baseline 逻辑。 |
| champion snapshot 只读 | ✅ | `create_champion_snapshot()` 递归只读。 | 通过。 |
| branch 独立 workspace | ✅ | 有。 | 通过。 |
| registry 同步是否完整 | ❌ | `WorkspaceMaterializer.apply_patch()` 只在 `create` 时追加 registry；**`remove` 不会删 registry entry**，`modify` 若 file_path 变化也不更新。 | 把 structural pool 更新统一走 `PoolManager`，不要靠零散 side effect。 |

---

## 3.10 `failure/router.py` — 失败路由

| 审查项 | 状态 | 发现 | 建议 |
|---|---|---|---|
| 四层分类是否与架构一致 | ⚠️ | Router 本身分类大体对；但 campaign 里很多失败并没有真正按 router 的 action 执行。 | 让主循环消费 `FailureAction.action`。 |
| 哪些失败消耗预算是否正确 | ⚠️ | Router 定义基本对；但 controller 实际行为不一致，比如 verification_light exhausted 理论应 discard/记忆，实际 often 直接结束；infra 几乎没真正走 `block_infra/retry_infra`。 | 统一“路由决策”和“主循环执行”。 |
| Proposal/Contract 失败是否重试 | ⚠️ | Router 会返回 `retry_llm`，但 `_run_explore_step()` 常常只是返回，下一轮未必重试同一步，而是可能重新生成全新 hypothesis。 | 引入 per-candidate retry state。 |
| Evaluation outcome 是否进入 memory | ❌ | 正常 screening fail / validation fail 没有经 `FailureRouter` 写 hypothesis memory，只是 mark `rejected`。 | 把 protocol outcome 也纳入统一 failure/memory policy。 |

---

## 3.11 `lineage/` — 追溯性

| 审查项 | 状态 | 发现 | 建议 |
|---|---|---|---|
| SQLite schema 是否覆盖架构 v3 §14.2 最低字段 | ❌ | 缺少或未稳定写入：`parent_hypothesis_id`、`base_champion_id`、`prompt_hash`、`model_version`、`problem_spec_hash`、`split_version`、`seed_version`、`protocol_version`、`decision_reason_codes` 等。 | 需要 schema 补齐 + 真正写入。 |
| `weight_optimizations` 是否完整 | ⚠️ | 表有了，但字段不足：没有 strategy、bounds、cases、seeds、eval workspace hash；`observations_ref` 为空。 | 扩字段或至少增加 `config_json`。 |
| hypothesis → code → evaluation → decision 全链路可追溯 | ❌ | `_record_step_lineage()` 把 `hypothesis_id` 写成空字符串；早期失败路径大量不入 registry；branches 表几乎没写；summary 只记录部分步骤。 | 这是另一处 blocking，需把全链路事件化。 |
| BranchStore / ChampionStore 使用是否一致 | ❌ | `BranchStore` / `ChampionStore` 基本未被 campaign 主流程使用。 | 统一持久化入口，避免双轨状态。 |

---

## 3.12 `cli/main.py` — CLI

| 审查项 | 状态 | 发现 | 建议 |
|---|---|---|---|
| `scion postmortem` 输出是否完整 | ⚠️ | 命令本身写得不错，但依赖 `campaign_summary.json`，而 summary 又缺 validation/frozen/eval-only 细节，因此报告天然不完整。 | 先修 summary，再谈 postmortem 完整性。 |
| `scion report` / `inspect` 是否反映 Sprint E 新功能 | ⚠️ | 有部分反映，如 postmortem / summary；但**缺 `inspect weights` 和 `optimize-weights`**。 | 补齐设计文档承诺的命令。 |
| 错误处理是否合理 | ⚠️ | 基础文件不存在处理还可以；但 `run` 命令最大问题是**没有构造真实 Runner/ExperimentProtocol**，实际跑不出真实研究 campaign。 | CLI 默认应接入 `LocalSubprocessRunner + ExperimentProtocol`。 |
| CLI 是否可用于真实 v0.2 实验 | ❌ | 当前 `run` 基本是 skeleton，不是生产研究用。 | 这是 Sprint F 前必须修。 |

---

## 3.13 `config/` — 配置层

| 审查项 | 状态 | 发现 | 建议 |
|---|---|---|---|
| ProblemSpec / ProtocolConfig / SplitManifest / SeedLedger 是否完整 | ❌ | 存在**双套 schema**：`config/problem.py` 里有简化版 `ProtocolConfig/SplitManifest/SeedLedgerConfig`，另有 `config/protocol_config.py` / `split_manifest.py` / `seed_ledger.py` 的增强版。运行路径用的是简化版。 | 立刻确定一套 authoritative schema。 |
| 新增配置项默认值是否合理 | ✅ | `parameter_search` 默认值总体合理。 | 通过。 |
| v0.1 problem.yaml 向后兼容 | ⚠️ | 由于 Pydantic 默认忽略 extra，旧配置能读；但同样也会**静默忽略新字段**，这会掩盖配置错误。 | 对关键新字段改成严格校验，或输出 warning。 |
| protocol/split/canary 是否真的被用上 | ❌ | `split_manifest.yaml` 里的 `version`、`canary`，`seed_ledger` 里的 `canary`，在主运行路径里基本都被忽略。 | 这是协议可信性问题，需尽快统一。 |

---

# 6.3 跨模块一致性

## 总体判断
**跨模块一致性目前是 v0.2 的第二大问题。**  
不是“某个文件不好看”，而是存在多组**并行但不一致的实现**。

### 关键一致性问题

1. **配置层 split-brain**
   - `config/problem.py` 定义了一套简化 `ProtocolConfig / SplitManifest / SeedLedgerConfig`
   - `config/protocol_config.py / split_manifest.py / seed_ledger.py` 又定义了一套增强 schema
   - CLI / CampaignManager 用的是前者，很多 v0.2 设计字段根本没进入运行路径  
   **结论：single source of truth 已破坏。**

2. **Memory / Store split-brain**
   - `lineage/branch_store.py` 里有 `HypothesisStore`
   - `memory/hypothesis_store.py` 又有另一版 `HypothesisStore`
   - 两者使用的数据结构还不完全一致  
   **结论：存在代码腐化风险，且会误导未来开发。**

3. **Verification split-brain**
   - `verification/nondeterminism.py`
   - `verification/state_leak.py`
   - `verification/state_mutation.py`
   - Gate 实际只用其中两者，命名/编号与设计文档又不一致  
   **结论：V5/V8 语义已经出现漂移。**

4. **Context plumbing 断裂**
   - `ContextManager.build_*_context()` 构造了很多字段
   - `CreativeLayer._split_*_context()` 实际没消费  
   **结论：Sprint E 多项功能“表面实现，实际未生效”。**

5. **PoolManager 未真正成为 single source of truth**
   - 结构搜索期间 registry 更新主要靠 `WorkspaceMaterializer.apply_patch()` 的 side effect
   - `PoolManager.build_candidate_pool()` 几乎没进入主链路  
   **结论：remove/modify 动作容易和 registry 状态失配。**

6. **CLI 与 Core 脱节**
   - CLI 默认不接入真实 runner/protocol
   - 这使得 CLI 看似能跑，实则不具备研究实验意义  
   **结论：工程入口与真实执行路径不一致。**

---

# 6.4 代码质量问题

## 1. 重复代码 / 冗余模块
- `_cr()` helper 在多个 verification/contract 文件中重复。
- `state_leak.py` 与 `nondeterminism.py` 高度重复。
- `HypothesisStore`、配置模型、Champion/Branch store 都有重复实现。
- `report_summary` 中的 family distribution 甚至和 `campaign_summary` 的 family_coverage 口径不一致。

**建议：**  
做一次“authoritative module”清理，保留唯一入口，其他模块要么删除、要么仅做 re-export。

---

## 2. 错误处理不完善
- 很多地方 `except Exception: pass` 或仅日志后继续，容易吞掉关键状态错误。
- `FailureRouter` 的 action 多数没有真正被执行。
- `verification_light` 重试只做一次即时 fix，和 router 配额不一致。
- `infra` 类失败几乎没有真正进入 `BLOCKED_INFRA` 状态机。

**建议：**  
让 `FailureAction` 成为主循环的一等输入，而不是仅记日志。

---

## 3. 命名与编号不一致
- V-code 编号明显混乱：`V3_feasibility`, `V4_objective`, `V6_perf_guard` 等。
- 文件/注释中有旧名 `state_leak` 与新名 `nondeterminism` 并存。
- `scion/runtime/pefrf_guard.py`（如果这不是粘贴笔误）存在明显命名错误。

**建议：**  
统一一次校验编号与文件命名；否则报告系统和 diagnosis 永远会错位。

---

## 4. 类型与模型边界不够稳
- `Any` 使用较多，尤其 CampaignManager 构造依赖。
- `HypothesisRecord` 在不同模块中的字段期待不一致。
- `PatchProposalInput` 未严格限制 `action`。
- `DecisionFeatures` 虽干净，但周边 feature extractor / lineage JSON 序列化未严格受控。

**建议：**  
对主要跨模块对象补严格类型，尤其是 Campaign → Proposal → Gate → Protocol → Registry 这一链。

---

## 5. 注释与实现不一致
- 多处 docstring 写着“按设计做了 X”，实际并没有。
- 例如 V5 注释声称检查 state mutation，但实现只是 proxy consistency check。
- `run_canary()` 文档上说 canary regression，实际却拿 screening 的头两个 case。

**建议：**  
要么修实现，要么修注释；目前两者冲突会误导后续开发和实验解释。

---

# 6.5 与设计文档的偏差

---

## A. 设计中有，但当前未真正实现

1. **stale reconcile 全链路**
   - 设计：reapply patch → Contract → Verification → re-Screening
   - 实现：只 reapply patch，成功就回 EXPLORE

2. **pending hypothesis 重过 Contract Gate**
   - 设计要求严格重过边界
   - 实现：直接跳过

3. **verification light fix patch 重新走 Contract Gate**
   - 设计应如此
   - 实现：绕过

4. **T07 family tracking 持久化 / lineage 化**
   - 设计里是独立机制
   - 实现只是 `context_manager.py` 内部临时 heuristic

5. **T08 strategy guidance 真正注入 prompt**
   - 设计有
   - 实现未接入 `_split_hypothesis_context()`

6. **T10 champion baseline hints 真正注入 prompt**
   - 设计有
   - 实现未接入 prompt，case_features 也未填值

7. **T17b CLI: `inspect weights` / `optimize-weights`**
   - 设计有
   - 实现缺失

8. **完整 artifact / summary**
   - 设计要求单文件可复盘
   - 当前 summary 缺 eval-only 步、缺真实 cache stats、缺完整 lineage linkage

9. **lineage 最低字段完整写入**
   - 设计有
   - 实现远未达到

---

## B. 已实现，但与设计不符

1. **canary 用例来源错误**
   - 设计：独立 canary split + canary seeds
   - 实现：screening 的前 2 个 case + 前 1 个 screening seed

2. **统计单位错误**
   - 设计：case 是统计单位，跨 seed 先聚合
   - 实现：直接把每个 `(case, seed)` pair 当独立样本

3. **expand 规则错误**
   - 设计：增加 case 样本，不换 seed
   - 实现：通过 `seed + 1000 * r` 人工扩 seed

4. **screening/validation/frozen 样本数与 action-specific 配置未遵守**
   - 设计：modify/remove 6, create 10 等
   - 实现：基本直接跑整 split，不按 `hypothesis_action` 选样本

5. **branch clean-base 规则错误**
   - 设计：verification pass 才更新 clean base
   - 实现：patch apply 后就先记成 verified clean

6. **PoolManager 集成不符合设计**
   - 设计：pool/registry 操作由统一组件管理
   - 实现：create 时在 workspace 里偷偷 append registry；remove/modify 不对称

---

## C. 实现超出设计范围，但方向可接受

1. **CircuitBreaker**
   - 超出原始 v0.2 核心设计，但合理

2. **`postmortem` CLI**
   - 超出 MVP，但对研究复盘有价值

3. **Bayesian + pure-python UCB fallback**
   - 比 MVP 更激进，但不是问题核心  
   **前提是先修 baseline correctness。**

---

# 6.6 总结

## 总体评价
**2.5 / 5**

- **优点**：  
  - 架构理念基本对；  
  - Decision Layer 边界总体干净；  
  - Contract / Verification / Protocol / Parameter Search 这些大模块都已经“有东西”；  
  - subprocess deterministic 环境修复已落地；  
  - promote 后参数搜索的生命周期绑定方向是对的。

- **缺点**：  
  - 关键控制路径存在绕过；  
  - 实验协议实现与设计偏差很大，影响研究结论可信度；  
  - 多套配置/存储/verification 实现并存，single source of truth 被破坏；  
  - 多个 Sprint E 功能“写了上下文构造，但没真正进入 prompt”；  
  - CLI 入口和真实研究执行路径不一致。

---

## 必须修复的问题（blocking）
**这些问题不修，不建议做 Sprint F 正式实验。**

### 1. 修复 Gate bypass
- `pending hypothesis` 必须重新过 hypothesis Contract Gate
- `fix_code` 生成的 patch 必须重新过 patch Contract Gate
- stale reconcile 必须重走 `Contract → Verification → re-screening`

### 2. 修复 branch clean-base 污染
- `record_verification_result(..., True, ...)` 不能在 verification 前调用

### 3. 修复实验协议正确性
- canary 必须使用独立 `canary` split/seed
- screening/validation/frozen 必须按配置选 case 数
- **统计单位必须改为 case-level**
- expand 不能通过造新 seed；必须按预注册规则增 case

### 4. 修复参数优化 baseline bug
- baseline 必须是当前 champion weights
- `improved` 必须与 true baseline 比较，不是和第一条随机样本比较

### 5. 修复结构搜索 / registry 同步
- `remove` 动作必须同步 registry
- `modify` 若 file_path 变化也必须同步 registry
- 最好统一走 `PoolManager`

### 6. 修复 lineage 不完整
- 事件必须写真实 `hypothesis_id`
- 早期失败路径也要入 lineage
- 补关键字段：reason codes、raw_metrics_ref、config versions 等

### 7. 修复 CLI 真实运行路径
- `scion run` 必须接入真实 `Runner + ExperimentProtocol + VerificationGate`
- 否则 CLI 只是 demo，不是研究入口

### 8. 修复 prompt plumbing 断裂
- `branch_code / strategy_guidance / exploration_coverage / champion_baselines / prior_code_failure` 必须真正进入 prompt  
否则 T07/T08/T10/T20 基本不算“实现完成”。

---

## 建议修复的问题（non-blocking）
1. 统一 V-code 编号与文件命名  
2. 删除/合并重复模块（双 HypothesisStore、双 config、state_leak/nondeterminism）  
3. 为 `C9b_non_rng_random` 增强 alias 检测  
4. 给 `resolve_offloaded()` 加路径沙箱  
5. 把 cache stats 真正写入 step artifact  
6. 分离 screening_expand_count 与 validation_expand_count  
7. 让 `FailureRouter` 的动作成为真正可执行状态，而不是“只算账不落地”  
8. 让 report/inspect 使用同一套 family coverage 口径

---

## Sprint F 实验前的准备事项

1. **先做一个“协议/控制流修复版”分支**，不要直接在当前版本上开新实验
2. 补至少一组 **真实 E2E 集成测试**
   - create_new → verify pass → screening → validation → frozen → promote → weight optimize
3. 加一组 **回归测试**
   - stale reconcile 重新验证
   - fix patch 再走 contract
   - case-level stats
   - canary split 不与 screening/validation/frozen 混用
   - remove action 正确更新 registry
4. 确认并冻结一套 **唯一配置 schema**
5. 重新跑一次短 campaign，验证：
   - no Gate bypass
   - no synthetic seed expansion
   - weight optimization baseline 正确
6. 之后再进入 Sprint F 正式实验

---

## v0.3 需要关注的架构债务

1. **统一配置与数据模型**
   - 彻底消灭双套 schema / 双 store / 双 verification 命名

2. **把 Protocol 层做成真正可审计组件**
   - case-level aggregation
   - exposure policy
   - split/seed versioning
   - pre-registered expand rules

3. **把 structural pool 管理统一收口**
   - `PoolManager` 成为唯一 registry writer / reader / mutator

4. **强化 runtime isolation**
   - offload path sandbox
   - 更明确的 tempdir / artifact / permissions policy

5. **提高 lineage 作为研究 artifact 的质量**
   - 完整 prompt hash / model version / config version / hypothesis lineage

6. **让 CLI 成为真实入口而不是 demo**
   - run / inspect / report / replay / optimize-weights 一套打通

---

# 6.7 优化方案

---

## 一、对 Scion 审计后的优化方向和实施方案

我建议把整改拆成 **四条主线**，顺序不能乱：

### 主线 A：先修“可信边界”
目标：确保任何 tainted LLM 输出都不会绕过 Gate1 / Gate2

**要做：**
- 修 `pending hypothesis` 重验
- 修 fix patch 重过 Contract
- 修 stale reconcile 全链路
- 修 verification 通过前污染 clean base

**价值：**
这是架构 v3 的根，不修的话后面所有实验都不值得相信。

---

### 主线 B：再修“协议正确性”
目标：确保统计结论符合设计，而不是“看上去像实验”

**要做：**
- canary 用真正 canary split/seed
- screening/validation/frozen 样本选择按 config
- 统计单位改为 case
- expand 改为扩 case，不造新 seed
- validation/frozen 的 aggregate 可记录，但不能暴露 per-case

**价值：**
这是研究可信性的核心，重要性不低于 Gate。

---

### 主线 C：修“参数搜索正确性”
目标：让 v0.2 核心卖点真正可信

**要做：**
- baseline = current champion weights
- improved 判断对 true baseline
- 保存 observations_ref
- snapshot hash / lineage 正确反映 registry 变化

**价值：**
当前参数层“隔离方向对，但结论可能错”。这会直接污染论文结果。

---

### 主线 D：补“prompt plumbing 与工程闭环”
目标：把已经写出来的 v0.2 能力真正接到运行链路里

**要做：**
- 把 strategy guidance / family coverage / branch code / prior failure / baseline hints 真正接入 prompt
- CLI 接真实 runner/protocol
- Lineage / summary / report 打通

**价值：**
修完 A/B/C 后，这条主线决定“好不好用”。

---

## 二、Sprint F 前的整改方案 PR 设计稿

下面给一版我建议的 **Sprint F 前整改 PR 方案**。  
建议至少拆成 **5 个 PR**，避免一个大 PR 把协议、控制流、参数层、CLI 全揉在一起。

---

## PR-1：`control-boundary-hardening`
**目标：补齐 Gate1/Gate2 硬边界，修 branch clean-base 语义**

### 修改函数
1. `scion/core/campaign.py`
   - `_run_explore_step()`
     - pending hypothesis 复用时，重新调用 `self._contract_gate.validate_hypothesis(...)`
     - verification pass 前不要调用 `record_verification_result(..., True, ...)`
     - fix patch 后先 `validate_patch(fixed)` 再 `apply_patch`
   - `_run_reconcile_step()`
     - 改成：`validate_patch -> apply_patch -> verification -> screening`
   - `_apply_decision_and_finalize()`
     - 明确 clean base 更新只在 verification pass 后执行

2. `scion/core/branch.py`
   - 新增一个只更新 `current_code_hash` 的接口，例如：
     - `record_candidate_code_hash(branch_id, code_hash)`
   - 保留 `record_verification_result(...passed...)` 只在 verification 后调用

### 新增测试
- `test_pending_hypothesis_repasses_contract_gate`
- `test_fix_patch_must_pass_contract_gate`
- `test_last_clean_hash_updates_only_after_verification_pass`
- `test_stale_reconcile_reruns_verification_and_screening`

---

## PR-2：`protocol-correctness-repair`
**目标：让 Protocol 层真正符合架构 v3 / v0.2 设计**

### 修改函数
1. `scion/protocol/experiment.py`
   - `run_canary()`
     - 改为使用 `manifest.canary` + `seed_ledger.canary`
   - `run_experiment()`
     - 按 `stage + hypothesis_action` 选 case 数
     - 先对每个 case 聚合 seeds，再做 stats
     - expand 改为增加 case，而不是造新 seed
   - 新增内部 helper：
     - `_select_cases_for_stage(stage, hypothesis_action, expand_round)`
     - `_aggregate_pairs_to_case_level(...)`

2. `scion/protocol/stats.py`
   - 新增 case-level stats 入口
   - bootstrap CI 基于 case-level delta

3. `scion/config/`
   - 统一只保留一套 `ProtocolConfig / SplitManifest / SeedLedger`

### 新增测试
- `test_canary_uses_canary_split_and_canary_seeds`
- `test_screening_respects_modify_vs_create_case_count`
- `test_stats_use_case_as_primary_unit`
- `test_expand_adds_cases_not_synthetic_seeds`
- `test_validation_and_frozen_expose_aggregate_only`

---

## PR-3：`prompt-plumbing-and-search-efficiency`
**目标：把已实现的 v0.2 搜索效率能力真正接入 prompt**

### 修改函数
1. `scion/proposal/engine.py`
   - `_split_hypothesis_context()`
     - 加入：
       - `branch_code`
       - `branch_direction`
       - `exploration_coverage`
       - `strategy_guidance`
       - `champion_baselines`
   - `_split_code_context()`
     - 加入 `prior_code_failure`

2. `scion/proposal/context_manager.py`
   - `build_hypothesis_context()`
     - 确保字段命名与 prompt split 使用一致
   - 在 hypothesis 创建时把 `family_id` 算出来并写入 `HypothesisRecord`

3. `scion/core/campaign.py`
   - `_round1_generate_hypothesis()`
     - 给 `HypothesisRecord` 填 `family_id`

### 新增测试
- `test_hypothesis_prompt_contains_strategy_guidance`
- `test_hypothesis_prompt_contains_branch_code`
- `test_hypothesis_prompt_contains_champion_baselines`
- `test_code_prompt_contains_prior_failure`
- `test_prompt_does_not_include_validation_or_frozen_per_case`

---

## PR-4：`parameter-search-correctness-fix`
**目标：修正 weight optimization 的 baseline 与 improved 判定**

### 修改函数
1. `scion/parameter/optimizer.py`
   - `RandomLocalWeightOptimizer.optimize()`
     - 先显式评估 baseline weights
     - `baseline_score` 应来自当前 weights，不是第一条随机样本
     - `improved = best_score > baseline_score`
   - `BayesianWeightOptimizer.optimize()`
     - 同样补 baseline 评估
   - 保存 observations 到 JSON，回填 `observations_ref`

2. `scion/core/campaign.py`
   - `_run_weight_optimization()`
     - 把 current weights 显式传入 optimizer
     - improved 判定后再写回 snapshot
     - 更新 champion snapshot hash 时应包含 registry 变化

3. `scion/runtime/workspace.py`
   - 新增 `compute_snapshot_hash()`，把 `registry.yaml` 也纳入 hash

### 新增测试
- `test_weight_optimizer_uses_current_weights_as_true_baseline`
- `test_negative_best_score_is_not_marked_improved`
- `test_weight_optimization_writes_observations_ref`
- `test_snapshot_hash_changes_after_registry_weight_update`

---

## PR-5：`lineage-cli-config-unification`
**目标：统一运行入口、配置层、lineage 与 CLI**

### 修改函数
1. `scion/config/problem.py`
   - 移除重复 `ProtocolConfig/SplitManifest/SeedLedgerConfig`
   - 改为 import/re-export 统一 schema

2. `scion/core/campaign.py`
   - 在关键状态点把 branch/champion 真正写入 `BranchStore/ChampionStore`

3. `scion/lineage/registry.py`
   - 给 `record_event()` 补齐最低字段
   - 记录真实 `hypothesis_id`
   - 记录 `decision_reason_codes`

4. `scion/cli/main.py`
   - `run` 中默认构造真实：
     - `LocalSubprocessRunner`
     - `ExperimentProtocol`
     - `VerificationGate`
   - 新增：
     - `scion inspect weights`
     - `scion optimize-weights`

### 新增测试
- `test_cli_run_constructs_real_protocol_and_runner`
- `test_lineage_event_contains_required_fields`
- `test_branch_store_persisted_during_campaign`
- `test_cli_inspect_weights`
- `test_cli_optimize_weights`

---

## 推荐整改顺序

### Sprint F 前必须完成
1. **PR-1**
2. **PR-2**
3. **PR-4**
4. **PR-5（至少把 CLI/run 与 config/lineage 主链修完）**

### 可以并行 / 次优先
5. **PR-3**

---

## 最后结论

如果只问一句：

> **Scion v0.2 现在能不能直接进入 Sprint F 正式实验？**

我的结论是：

> **不建议直接进入。**

原因不是它“没价值”，恰恰相反——  
它已经有相当不错的研究框架骨架；但当前版本仍存在几处会**实质性破坏实验可信度**的问题，尤其是：

1. **Gate bypass**
2. **协议统计单位错误**
3. **expand 规则错误**
4. **stale reconcile 不合规**
5. **参数搜索 baseline 判定错误**
6. **CLI 真实运行链未接通**

把这些修完之后，我会对它的评价明显提高，且我认为它就能进入一个更稳的 Sprint F。

如果你愿意，我下一步可以继续给你一版：

1. **按 blocking 优先级排序的修复 backlog**
2. **逐文件的 patch 级修改建议**
3. **一套 Sprint F 前必须补齐的测试清单（pytest 风格）**

可以直接作为开发任务单使用。
