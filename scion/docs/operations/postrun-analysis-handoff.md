# Scion v0.4 direct-v3 运行后分析交接

*最后更新：2026-07-13*

本交接用于 warehouse 或 clean/open CVRP 正式运行结束后的只读分析。分析者必须沿
direct-v3 的所有权边界逐层还原证据，并分别回答两个问题：框架是否正确执行，模型
是否完成了有效研究。进程退出、completion 成功、生成 patch 或 postrun readiness
通过，都不能单独证明研究有效。

架构边界以以下文档为准：

- `scion/design/scion-architecture-v3.md`；
- `scion/design/scion-architecture-v3-v0.4-direct-runtime-addendum.md`；
- `scion/docs/operations/experiment-runbook.zh.md`。

## 1. 交给分析者的输入与约束

提供：

- `RUN_ROOT`：`/home/clawd/research/scion-experiments/` 下的本次运行目录；
- `CAMPAIGN_DIR`：通常为 `$RUN_ROOT/campaign`；
- 本次实验要回答的研究问题，以及 warehouse 或 CVRP 身份；
- exact runtime commit 和预先声明的 rounds、model、protocol、split、seeds、
  solver time limit。

分析者只能读取产物，不修改源码或 campaign 状态，不启动新的 invocation，也不调用
外部模型。每个结论必须附带可复核定位：文件路径和 JSON field、数据库 event id、
branch/hypothesis id、trace ref、formal candidate ref 或 raw metrics ref。

`postrun_acceptance/analysis_brief/` 与 `postrun_acceptance/inventory/` 是 report-only
索引，不是质量结论，也不是 Decision 输入。若它们与 raw artifact 不一致，以 durable
event、正式候选和 Protocol 原始指标为准，并把不一致记为框架问题。

## 2. 先确定本次运行是否产生当前运行证据

先读：

```text
$RUN_ROOT/prepared_run_manifest.v1.json
$RUN_ROOT/command.txt
$RUN_ROOT/launch.env
$RUN_ROOT/run_status.json
$RUN_ROOT/exit.txt
$RUN_ROOT/run.log
$RUN_ROOT/pre_campaign_completion_preflight.v1.json
$RUN_ROOT/campaign_execution_marker.v1.json
```

确认 prepared commit、实际 runtime commit、completion、启动状态和结束状态属于同一
次运行。若只完成准备，或在 campaign 执行前因 completion、commit、环境、数据等原因
退出，应归类为 pre-campaign infra failure；此时停止算法质量判断，旧 campaign 副本
或 prepared handoff 不能当作当前运行研究证据。

若 launcher 已生成 postrun bundle，继续读取：

```text
$RUN_ROOT/postrun_acceptance/rebuild/rebuild_manifest.v1.json
$RUN_ROOT/postrun_acceptance/readiness/*.postrun_acceptance_readiness.v1.json
$RUN_ROOT/postrun_acceptance/analysis_brief/*.postrun_analysis_brief.v1.json
$RUN_ROOT/postrun_acceptance/inventory/*.postrun_artifact_inventory.v1.json
$RUN_ROOT/postrun_acceptance/summaries/*.summary.json
$RUN_ROOT/postrun_acceptance/failures/*.failures.json
$RUN_ROOT/postrun_acceptance/manifests/*.proposal_trajectory_manifest.v1.json
```

若 bundle 缺失或不完整，应由操作员在交付分析前重建并检查。以下命令只更新
report-only bundle 和操作员报告，不改变 campaign、Decision 或 promotion state；受托
分析者本身仍保持只读：

```bash
cd /home/clawd/research/or-autoresearch-agent

python scion/tools/rebuild_postrun_acceptance.py "$RUN_ROOT" \
  --strict --format json \
  > "$RUN_ROOT/operator-postrun-rebuild.v1.json"

python scion/tools/check_postrun_acceptance.py "$RUN_ROOT" \
  --require-current-run-ready --format json \
  > "$RUN_ROOT/operator-postrun-readiness.v1.json"
```

## 3. 原始证据地图

完整分析至少检查存在的以下产物：

```text
$CAMPAIGN_DIR/campaign_summary.json
$CAMPAIGN_DIR/run_status.json
$CAMPAIGN_DIR/status.json
$CAMPAIGN_DIR/scion.db
$CAMPAIGN_DIR/llm_traces/*.json
$CAMPAIGN_DIR/metrics/*.json
$CAMPAIGN_DIR/artifacts/formal_candidates/index.jsonl
$CAMPAIGN_DIR/artifacts/formal_candidates/**/candidate.patch.json
```

若 summary 引用了 archive、workspace、champion、promotion dossier 或其他 artifact，按
引用继续打开，而不是猜测候选身份或代码内容。不要用 provider 自由文本替代 Contract、
Verification、Protocol 或 Decision 的 typed evidence。

当前 CLI 的只读入口为：

```bash
cd /home/clawd/research/or-autoresearch-agent/scion
export CAMPAIGN_DIR="$RUN_ROOT/campaign"

python -m scion.cli.main inspect campaign --campaign-dir "$CAMPAIGN_DIR"
python -m scion.cli.main report summary --campaign-dir "$CAMPAIGN_DIR" --markdown
python -m scion.cli.main report failures --campaign-dir "$CAMPAIGN_DIR"
```

已知标识后再深入：

```bash
python -m scion.cli.main inspect branch '<branch-id>' \
  --campaign-dir "$CAMPAIGN_DIR"
python -m scion.cli.main inspect hypothesis '<hypothesis-id>' \
  --campaign-dir "$CAMPAIGN_DIR"
```

## 4. 强制分析顺序

### 4.1 H/C durable attempt 与 provider receipt

先从 append-only event 还原每个 attempt，不从最终 reason code 倒推：

```bash
sqlite3 "$CAMPAIGN_DIR/scion.db" <<'SQL'
.headers on
.mode column
SELECT timestamp, event_id, branch_id, hypothesis_id, stage, audit_payload_json
FROM experiment_events
WHERE event_kind = 'proposal_attempt_transition'
ORDER BY timestamp, rowid;
SQL
```

对每个 `attempt_id` 核对：

- hypothesis phase 是否只有一条合法生命周期；
- 只有获批 H 才有与其绑定的 code phase；
- `status`、`transition_reason`、`failure_lane` 与实际终态一致；
- `prompt_call.trace_ref`、`prompt_manifest_ref`、`raw_response_ref` 指向存在的
  `llm_traces/` 产物；
- request kind、context digest、prompt hash、provider receipt 与 durable transition
  一致；
- H 是否看到完整且安全的问题对象与源码上下文，C 是否看到获批 H、目标文件及其依赖；
- 原始响应失效或 infra failure 是否保持原分类，没有被伪装成算法结论。

分析 H 的研究质量时，检查它是否提出具体、可证伪、与当前源码相符的机制和预期证据；
分析 C 时，检查多文件 patch 是否完整实现获批 H，而非注释、无关重排或只迎合结构要求。

### 4.2 Contract

从 `campaign_summary.json.steps[]` 的 hypothesis、`contract_passed`、
`contract_diagnostics`、`contract_not_run_reason`、`failure_stage` 与
`failure_detail` 判断 Contract 是否只执行结构和信任边界检查：schema、surface/locus、
editable/frozen path、source digest、action、import/API/interface，以及 patch 与获批 H 的
绑定。

需要回答：

- 拒绝是否来自真实结构错误或越界；
- 是否把机制偏好、自由文本写法、非必要遥测或研究结果提前当成硬条件；
- Contract 通过的 patch 是否与 receipt 和归档代码完全一致。

### 4.3 Verification

读取每一步的 `verification_passed`、`verification_detail`、`canary_result`、
`primary_failure` 和 `secondary_observations`，再打开相关 workspace/archive 引用。

Verification 应检查候选代码能否正确运行，包括语法、接口、状态泄漏、feasibility、
objective consistency、nondeterminism、crash、timeout 与 solver output。缺失非必要诊断
不能覆盖正确的 solver 结果。分析者必须判断失败来自候选实现，还是 framework harness、
problem adapter、数据或环境。

### 4.4 Protocol

只有进入 Protocol 的候选才能产生比较性科学结论。读取
`campaign_summary.json.steps[].protocol_result`，并逐个打开其中的
`raw_metrics_ref`：

- 核对 stage、case ids、seed set、candidate/champion identity；
- 核对 attempted、valid、failed pairs 及失败归属；
- 核对每个 metric 的方向、median delta、CI 和 win/loss/tie；
- 核对 runtime ratio/delta、solver time limit 与 timeout 事实；
- 核对 summary 聚合值能由 `metrics/*.json` 的 pair-level 证据解释；
- statistical expand 只能扩展预注册样本，不能变成另一次模型调用。

不要从 provider prose、diagnostic telemetry 或 postrun 汇总重新发明 Protocol 结论。

### 4.5 Decision

读取每一步的 `decision_features`、Protocol `gate_outcome`、
`protocol_reason_codes`、`decision`、`decision_reason_codes`、
`decision_engine_reason_codes` 与 `formal_candidate_patch_artifact_ref`。

确认：

- Decision 只消费 Safe Features、Protocol outcome 和硬安全事实；
- typed features 与 raw Protocol evidence 一致；
- 相同输入可得到相同 action；
- provider 自由文本、诊断完整性和 scheduler prose 没有改变科学结论；
- formal candidate index、`candidate.patch.json`、summary 与 Decision 指向同一代码身份。

### 4.6 Solver 与完整研究结果

最后回到实际算法行为，而不是停在 gate 状态：

- 从 formal candidate 还原完整 patch，确认关键执行路径实际调用了新机制；
- 用 raw metrics 的 candidate/champion 输出证明行为变化可归因于该 patch；
- 检查 feasibility、objective、质量、runtime 和失败案例，而非只看总分；
- 对 warehouse 判断是否回答了真实 warehouse 研究问题；
- 对 clean/open CVRP 判断模型是否自主选择并实现了有意义的 VRP 算法方向；
- 把可复现收益、有信息量的无收益、候选实现失败、框架失败和 infra failure 分开。

## 5. 两层 verdict

### 5.1 框架正确

至少需要证明：

- prepared、runtime commit、completion 和 current-run identity 一致；
- H/C durable transitions、receipts 和 trace 一一对应；
- H 通过后才发生 C，失败 lane 没有混淆；
- Contract、Verification、Protocol、Decision 各守所有权边界；
- formal candidate、metrics、summary、数据库和 postrun inventory 可相互对账；
- 多文件 patch 能完整物化、归档、回滚和复核。

### 5.2 研究有效

至少需要证明：

- H 基于真实源码提出具体机制，而不是泛化建议；
- C 实现了该机制且修改进入实际 solver 路径；
- Protocol 有足够的 case/seed/pair-level 质量与 runtime 证据；
- 结果能归类为可复现收益或有信息量的无收益；
- 结论不是由隐藏目标、过重边界条件、框架错误或基础设施状态制造。

框架正确但研究无效时，必须明确写成两项不同结论。框架错误时，不得把候选算法判为
无效；只产生 pre-campaign evidence 时，不得评价模型研究能力。

## 6. 必答问题

1. 本次是否产生了可归属于当前运行的 formal Protocol evidence？
2. 每个 H/C attempt 的 durable transition、receipt、trace 和输出是否一致？
3. H 是否看到了足够的问题与源码上下文，并提出可证伪的算法机制？
4. C 是否完整实现获批 H，并进入实际 solver 执行路径？
5. Contract 是否只拦截结构/信任边界问题？
6. Verification 失败若有，归因于候选、框架、problem layer、数据还是 infra？
7. Protocol 的 pair-level 数据能否支持其聚合与 gate outcome？
8. Decision 是否只由 typed safe evidence 确定性产生？
9. formal candidate、归档代码、metrics 和 summary 的身份是否闭合？
10. warehouse 或 CVRP 的完整结果是收益、有信息量的无收益、实现失败、框架失败，
    还是 infra failure？
11. 框架正确性 verdict 与研究有效性 verdict 分别是什么？
12. 下一步应修框架、改问题上下文/接口、保留研究发现，还是从新 clean commit 发起
    新 invocation？

## 7. 交付格式

```markdown
# <run name> Postrun Analysis

## Verdict
- Current-run evidence:
- Framework correctness:
- Research effectiveness:
- Algorithm outcome:
- Next action:

## Evidence Identity
- Run root / campaign dir:
- Prepared commit / runtime commit:
- Problem / model / protocol / split / seeds / solver time limit:
- Lifecycle and postrun readiness:

## H/C Durable Attempts
| Attempt | Branch | Phase | Transition/events | Receipt/trace | Output | Judgment |
|---|---|---|---|---|---|---|

## Contract
- Evidence:
- Correct intercepts:
- Suspected overreach or missed boundary:

## Verification
- Evidence:
- Candidate failures:
- Framework/problem/infra failures:

## Protocol
- Candidate and champion identity:
- Stage/cases/seeds/pairs:
- Quality and runtime evidence:
- Raw metrics reconciliation:

## Decision
- Safe Features:
- Protocol outcome and reason codes:
- Decision and reason codes:
- Determinism/boundary judgment:

## Solver And Full Outcome
- Mechanism actually executed:
- Behavior attributable to patch:
- Feasibility/objective/quality/runtime:
- Useful finding or failure class:

## Required Answers
1. ...

## Evidence-Backed Next Action
- Preserve:
- Repair:
- New clean invocation prerequisite:
```

主会话只接受带上述证据定位的结论。若结果改变 v0.4 项目状态，再更新对应实验文档、
`scion/TASK.md` 与 `scion/docs/status/current-state.md`；不要把推测写成已验证结论。
