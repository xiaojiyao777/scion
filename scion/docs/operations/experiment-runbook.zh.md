# Scion v0.4 direct-v3 实验运行与验收手册

*适用分支：`v0.4-dev`*
*最后更新：2026-07-13*

本手册只描述当前 direct-v3 runtime。架构边界以
`scion/design/scion-architecture-v3.md` 和
`scion/design/scion-architecture-v3-v0.4-direct-runtime-addendum.md` 为准；
当前任务与状态分别见 `scion/TASK.md`、
`scion/docs/status/current-state.md`。

## 1. 正式实验的定义

当前正式研究路径是：

```text
完整且安全的问题/源码上下文
  -> 最多一次 Hypothesis 调用
  -> Hypothesis Contract
  -> 通过后，最多一次 Code 调用
  -> Patch Contract
  -> Workspace
  -> Verification
  -> Protocol
  -> Safe Features
  -> deterministic Decision
```

正式实验必须同时满足以下条件：

- 从 exact clean commit 准备并运行；准备后不得改变该提交或工作树；
- 先通过真实、非空响应的 completion preflight；
- 不绑定 surface、action 或 target file；
- 不从旧 campaign 恢复；
- 不跳过 postrun reports；
- warehouse 与 CVRP 的 `parameter_search.enabled` 都必须显式为 `false`；
  launcher/preflight 对缺失或启用状态 fail-closed；
- 先运行 warehouse control，确认框架闭环后再运行 clean/open CVRP；
- 用真实 Hypothesis、代码、执行行为和 Protocol 结果判断研究有效性，不能只凭测试通过或进程正常退出。

正式运行没有 Scion semantic budget、truncation 或 retry。`--rounds` 是操作员明确选择的“typed formal Protocol evaluated rounds”目标，不是模型调用次数上限或自动重试次数；一次 H/C 无效、infra failure 或未进入 `EVALUATED` 时，当前 invocation 可以在未达到目标轮数时停止。`--time-limit-sec` 是每次 solver/subprocess 的科学运行边界，必须随实验记录。

Anthropic transport 要求的 `max_tokens` 仅是 provider transport ceiling。它不是 Scion 的语义 token budget，不是 campaign 终止规则，也不授权截断、压缩或省略上下文。provider SDK retry 保持为零；新的 provider 调用必须是新的 durable attempt，不能由隐藏的 SDK 重放产生。

v0.4 production Scheduler 默认只允许一个 active research branch。这个设置让
screening fail 后的 `CONTINUE_EXPLORE` 在下一轮复用同一个 branch：第二个 H
能看到第一次 screening 的 canonical evidence，第二个 C 能从 SourceLedger
看到该 branch 已验证的当前源码。它只改变调度拓扑，不限制轮数、调用、token、
文件或持续时间；显式多分支配置仅用于后续 breadth ablation，不能替换正式
warehouse/CVRP control 的默认 runtime。

## 2. 运行环境

### 2.1 Server `claw`

用于聚焦测试和一次正式运行：

```bash
export SOURCE_REPO=/home/clawd/research/or-autoresearch-agent
export PY=/home/clawd/miniconda3/envs/claw/bin/python
export EXPERIMENTS_ROOT=/home/clawd/research/scion-experiments
```

若 source worktree 还保留不属于 v0.4 runtime commit 的用户文档或历史文件，
不要 stash、移动、删除或顺带提交它们。获得提交授权并完成最终 commit 后，从
`v0.4-dev` 的精确提交创建独立的 clean runtime worktree：

```bash
export CONTROL_COMMIT=$(git -C "$SOURCE_REPO" rev-parse v0.4-dev)
export CONTROL_REPO=/home/clawd/research/or-autoresearch-agent-v04-control-${CONTROL_COMMIT:0:12}

git -C "$SOURCE_REPO" merge-base --is-ancestor "$CONTROL_COMMIT" v0.4-dev
git -C "$SOURCE_REPO" worktree add --detach "$CONTROL_REPO" "$CONTROL_COMMIT"

export REPO_ROOT="$CONTROL_REPO"
test "$(git -C "$REPO_ROOT" rev-parse HEAD)" = "$CONTROL_COMMIT"
test -z "$(git -C "$REPO_ROOT" status --porcelain)"
```

`CONTROL_REPO` 是正式实验的 runtime checkout；prepared root、readiness 和
campaign 必须引用它。source worktree 中被排除的文件不属于 runtime，也不得
为了 preflight 被清理。

warehouse 数据默认位于：

```text
/home/clawd/research/scion-data
```

CVRP launcher 使用 repo-local 数据根：

```text
$REPO_ROOT/vrp
```

### 2.2 WSL `scion`

只在重新确认连接、代码同步和 completion preflight 后用于大型或并发验证：

```text
repo:        /home/xjy-ubuntu/research/or-autoresearch-agent
runner copy: /home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629
Python:      /home/xjy-ubuntu/miniconda3/envs/scion/bin/python
```

不要把 server 的 `claw` 路径直接复制到 WSL。两个环境都必须从各自的 clean commit 重新生成 prepared root；不得跨机器复用 `run.sh`、`launch.env` 或 prepared readiness 结果。

## 3. 正式运行前的共同检查

先在目标 runner 上执行：

```bash
cd "$REPO_ROOT"

git branch --show-current
git rev-parse HEAD
git status --short

test "$(git rev-parse HEAD)" = "$CONTROL_COMMIT"
git -C "$SOURCE_REPO" merge-base --is-ancestor "$CONTROL_COMMIT" v0.4-dev
test -z "$(git status --porcelain)"

"$PY" scion/tools/launch_warehouse_direct_campaign.py --help
"$PY" scion/tools/launch_cvrp_direct_campaign.py --help

cd "$REPO_ROOT/scion"
"$PY" -m scion.cli.main run --help
cd "$REPO_ROOT"
```

runtime worktree 的 `git status --short` 必须无输出。若有任何已跟踪修改或
未跟踪文件，不要临时绕过，也不要从该 worktree 启动正式实验。source
worktree 可以继续保留明确排除的用户文件，但它不能作为正式 runtime root。
prepared commit 必须与 runtime HEAD 完全相同；文档提交漂移也不能豁免。

检查数据：

```bash
test -d /home/clawd/research/scion-data/production/generated
test -d /home/clawd/research/scion-data/production/converted
test -d "$REPO_ROOT/vrp"
```

共享或远程代理密钥只通过环境变量提供。示例使用
`SCION_SHARED_PROXY_KEY`；不要把真实密钥写进命令行、`launch.env`、
`command.txt` 或文档：

```bash
export SCION_SHARED_PROXY_KEY='<set-in-current-shell>'
test -n "$SCION_SHARED_PROXY_KEY"
```

正式准备命令必须使用 `--api-key-env SCION_SHARED_PROXY_KEY`，不得使用
`--api-key <secret>`。

## 4. Warehouse control：准备、验收、启动

warehouse 必须先运行。以下示例使用 `gpt-5.6-sol`；若更换模型，manifest、
环境和 completion preflight 必须一致。

### 4.1 只准备，不启动

```bash
cd "$REPO_ROOT"

PREPARE_OUT=$("$PY" scion/tools/launch_warehouse_direct_campaign.py \
  --rounds 2 \
  --label v04-warehouse-direct-control \
  --model gpt-5.6-sol \
  --base-url http://127.0.0.1:8080 \
  --api-key-env SCION_SHARED_PROXY_KEY \
  --completion-preflight \
  --python "$PY" \
  --warehouse-data-root /home/clawd/research/scion-data \
  --time-limit-sec 30 \
  --experiments-root "$EXPERIMENTS_ROOT")

printf '%s\n' "$PREPARE_OUT"
export RUN_ROOT=$(printf '%s\n' "$PREPARE_OUT" | sed -n 's/^RUN_ROOT=//p')
test -n "$RUN_ROOT"
test -f "$RUN_ROOT/prepared_run_manifest.v1.json"
test -f "$RUN_ROOT/run.sh"
```

正式命令中不要加入 `--resume-from-campaign` 或
`--skip-postrun-reports`。

### 4.2 核对 prepared contract 与真实 completion

```bash
cd "$REPO_ROOT"

test -z "$(git status --porcelain)"
test "$(jq -r '.git.commit' "$RUN_ROOT/prepared_run_manifest.v1.json")" = \
  "$(git rev-parse --short HEAD)"
test "$(jq -r '.model.completion_preflight' "$RUN_ROOT/prepared_run_manifest.v1.json")" = true
test "$(jq -r '.resume_from_campaign' "$RUN_ROOT/prepared_run_manifest.v1.json")" = ""
test "$(jq -r '.report_metadata.postrun_reports' "$RUN_ROOT/prepared_run_manifest.v1.json")" = true

"$PY" scion/tools/check_launch_readiness.py "$RUN_ROOT" \
  --require-launch-ready \
  --api-key-env SCION_SHARED_PROXY_KEY \
  --format json \
  > "$RUN_ROOT/launch_readiness.operator.v1.json"

jq '{static_ready, launch_ready, readiness_scope, launch_blockers,
     completion_http_status, completion_classification,
     prepared_runtime_commit, actual_runtime_commit}' \
  "$RUN_ROOT/launch_readiness.operator.v1.json"
```

只有命令退出码为零且 `launch_ready` 为 `true` 时才可启动。preflight 必须实际完成 chat completion；只看到 `/v1/models` HTTP 200 不够。

### 4.3 后台启动

```bash
test -z "$(git -C "$REPO_ROOT" status --porcelain)"

cd "$RUN_ROOT"
nohup setsid bash run.sh > nohup.log 2>&1 &
echo $! > pid

cat pid
jq . run_status.json
```

`run.sh` 会再次检查 clean runtime commit 和 completion。这是启动瞬间的
TOCTOU 防护，不是 H/C 重试；任何失败都会在 campaign 执行前退出并写入
`run_status.json`。

## 5. 低频监控

普通轮询默认每三分钟一次；只有明确状态变化或接近结束时才在 2–5 分钟范围内调整。它只读取状态，不改变 campaign、Decision 或终止条件，也不是任何形式的预算。不要为了等待 H/C 响应进行秒级刷新。

一次性检查：

```bash
export CAMPAIGN_DIR="$RUN_ROOT/campaign"

date -u
jq . "$RUN_ROOT/run_status.json"
tail -n 40 "$RUN_ROOT/run.log"
ps -p "$(cat "$RUN_ROOT/pid")" -o pid,etime,stat,cmd
```

需要持续观察时，用三分钟间隔：

```bash
watch -n 180 'date -u; jq -c . "$RUN_ROOT/run_status.json" 2>/dev/null; tail -n 20 "$RUN_ROOT/run.log"'
```

如果 `ps` 已无进程，先读 `run_status.json`、`exit.txt` 和 `run.log`，不要因为目标轮数未满就自行重启。direct-v3 对 invalid response、Contract rejection、Verification failure、infra failure 和 interruption 都会保留不同的终态；是否再次运行由操作员根据证据显式决定。

## 6. Warehouse 通过后才进入 CVRP

warehouse 不是“进程退出为零即通过”。在启动 CVRP 前，至少确认：

- prepared、completion、runtime commit 和 postrun readiness 全部通过；
- H receipt、若 H 获批则 C receipt，均能与 durable attempt 对齐；
- Hypothesis/patch 不依赖隐藏目标提示；
- Contract、Verification、Protocol、Decision 的 owner 边界清楚；
- candidate 的代码和可观察 solver 行为可归因；
- Protocol 有有效 pair/metric evidence，而不是只有框架日志；
- 结果回答了一个真实 warehouse 研究问题，或给出了有充分证据的无收益结论。

若 warehouse 暴露框架错误，先修复并从新的 clean commit 重新准备 warehouse。不得保留旧 prepared root 继续跑 CVRP。

## 7. Clean/open CVRP：准备、验收、启动

CVRP 必须使用与通过 warehouse control 相同的 runtime commit，并从空白 campaign 开始。open 表示模型从完整安全上下文自行选择研究方向，没有 successor target、surface、action 或 target-file 绑定。

### 7.1 只准备，不启动

```bash
cd "$REPO_ROOT"
test -z "$(git status --porcelain)"

PREPARE_OUT=$("$PY" scion/tools/launch_cvrp_direct_campaign.py \
  --rounds 2 \
  --label v04-cvrp-open-direct-control \
  --model gpt-5.6-sol \
  --base-url http://127.0.0.1:8080 \
  --api-key-env SCION_SHARED_PROXY_KEY \
  --completion-preflight \
  --python "$PY" \
  --time-limit-sec 30 \
  --experiments-root "$EXPERIMENTS_ROOT")

printf '%s\n' "$PREPARE_OUT"
export RUN_ROOT=$(printf '%s\n' "$PREPARE_OUT" | sed -n 's/^RUN_ROOT=//p')
test -n "$RUN_ROOT"
```

正式 CVRP 命令不得出现：

- `--force-surface`；
- `--force-action`；
- `--force-target-file`；
- `--resume-from-campaign`；
- `--skip-postrun-reports`。

### 7.2 Readiness 与启动

```bash
cd "$REPO_ROOT"

test -z "$(git status --porcelain)"
test "$(jq -r '.git.commit' "$RUN_ROOT/prepared_run_manifest.v1.json")" = \
  "$(git rev-parse --short HEAD)"
test "$(jq -r '.resume_from_campaign' "$RUN_ROOT/prepared_run_manifest.v1.json")" = ""
test "$(jq -r '.execution.proposal_runtime_mode' "$RUN_ROOT/prepared_run_manifest.v1.json")" = direct_v3
test "$(jq -r '.report_metadata.postrun_reports' "$RUN_ROOT/prepared_run_manifest.v1.json")" = true

"$PY" scion/tools/check_launch_readiness.py "$RUN_ROOT" \
  --require-launch-ready \
  --api-key-env SCION_SHARED_PROXY_KEY \
  --format json \
  > "$RUN_ROOT/launch_readiness.operator.v1.json"

jq '{static_ready, launch_ready, launch_blockers,
     completion_http_status, completion_classification,
     prepared_runtime_commit, actual_runtime_commit}' \
  "$RUN_ROOT/launch_readiness.operator.v1.json"

cd "$RUN_ROOT"
nohup setsid bash run.sh > nohup.log 2>&1 &
echo $! > pid
```

对 CVRP 使用与 warehouse 相同的 2–5 分钟低频监控方法。

## 8. 当前产物地图

prepared root 和 campaign 的主要证据如下：

```text
$RUN_ROOT/
  prepared_run_manifest.v1.json     # launch/handoff contract
  prepared_run_manifest.md
  prepared_handoff/                 # prepared analysis brief/inventory/readiness/rebuild
  command.txt                        # 无密钥命令和配置摘要
  launch.env                         # 0600；密钥应为环境变量绑定
  run.sh                             # commit、completion、postrun lifecycle
  launch_readiness.operator.v1.json # 操作员实际执行的 readiness
  pre_campaign_completion_preflight.v1.json
  campaign_execution_marker.v1.json
  pid
  nohup.log
  run.log
  exit.txt
  run_status.json
  postrun_acceptance/
    summaries/
    failures/
    manifests/
    analysis_brief/
    inventory/
    readiness/
    rebuild/
  campaign/
    campaign_summary.json
    run_status.json
    scion.db
    llm_traces/                      # prompt manifest、response、provider trace
    metrics/                         # Protocol raw metric snapshots
    artifacts/
      formal_candidates/
        index.jsonl
```

`prepared_*` 和 postrun inventory 是 report-only 证据，不是 Decision input，也不替代实际研究质量判断。

## 9. 从 H/C 到 Decision 的诊断顺序

不要先从最后一个 reason code 猜原因。按所有权边界逐层检查。

### 9.1 H/C durable attempt 与 receipt

先看 durable transition：

```bash
export CAMPAIGN_DIR="$RUN_ROOT/campaign"

sqlite3 "$CAMPAIGN_DIR/scion.db" <<'SQL'
.headers on
.mode column
SELECT timestamp, branch_id, hypothesis_id, stage, audit_payload_json
FROM experiment_events
WHERE event_kind = 'proposal_attempt_transition'
ORDER BY timestamp, rowid;
SQL
```

再根据 `audit_payload_json` 中的 `attempt_id`、`phase`、`status`、
`transition_reason`、`trace_ref`、`prompt_manifest_ref` 和
`raw_response_ref` 找 `llm_traces/`。应看到：

- H 是一个独立 durable attempt；
- 只有 H 通过 Contract 后才存在绑定该 H 的 C attempt；
- provider receipt 的 request kind、trace、prompt hash/context digest 与 transition 对齐；
- 失败保持原始分类，不被改写成研究否决或自动再调用。

列出 trace：

```bash
find "$CAMPAIGN_DIR/llm_traces" -maxdepth 1 -type f -name '*.json' -print | sort
```

### 9.2 Hypothesis 与 Patch Contract

Contract 只判断结构和信任边界：schema、surface/locus、editable/frozen path、source digest、action、import/API/interface，以及 patch 是否绑定获批 H。它不应因为研究风格、机制偏好、遥测描述或“新颖性不足”而否决。

快速看每一步：

```bash
jq '.steps[] | {
  round, branch_id, hypothesis,
  contract_passed, contract_diagnostics,
  code_archive_ref, failure_stage, failure_detail,
  execution_outcome, execution_outcome_reason_code
}' "$CAMPAIGN_DIR/campaign_summary.json"
```

### 9.3 Verification

Verification 判断候选代码能否正确执行：语法、接口、状态泄漏、feasibility、
objective consistency、nondeterminism、crash、timeout 和 solver output。
缺失的诊断遥测本身不能让一个正确 solver 结果失败。

```bash
jq '.steps[] | {
  round, branch_id,
  verification_passed, verification_detail,
  canary_result, failure_stage, failure_detail
}' "$CAMPAIGN_DIR/campaign_summary.json"
```

### 9.4 Protocol

Protocol 是 comparative scientific judgment 的唯一 owner。检查 stage、case/seed、
attempted/valid/failed pairs、win/loss/tie、median delta、CI、runtime，以及
`raw_metrics_ref`。不要从 provider 自由文本或诊断遥测重算 Decision。

```bash
jq '.steps[] | {
  round, branch_id,
  protocol_result: (.protocol_result // null)
}' "$CAMPAIGN_DIR/campaign_summary.json"
```

按 `raw_metrics_ref` 打开 `campaign/metrics/*.json`，核对聚合值与 pair 级证据、
case/seed 和 candidate/champion 身份。`statistical expand` 是 Protocol 对预注册样本的动作，不是 provider retry。

### 9.5 Decision

Decision 只消费 Safe Features、Protocol gate outcome 和硬安全事实，并做确定性映射。核对 Protocol reason codes、Decision reason codes、最终 action 以及 formal candidate artifact；不要允许自由文本、遥测完整性或 scheduler prose 改写科学结论。

```bash
jq '.steps[] | {
  round, branch_id,
  protocol_gate: (.protocol_result.gate_outcome // null),
  protocol_codes: (.protocol_result.protocol_reason_codes // []),
  decision, decision_reason_codes,
  decision_features,
  formal_candidate_patch_artifact_ref
}' "$CAMPAIGN_DIR/campaign_summary.json"
```

Scheduler 只负责 branch state、priority/FIFO 和 active slot；若它改变 Protocol/Decision 结论或向模型注入机制偏好，应按框架错误处理。

如果某次 screening 结果是 `CONTINUE_EXPLORE`，下一次 evaluated candidate
还必须核对：

- `branch_id` 与上一轮相同；
- 第二个 H 的 canonical `experiment_history` 恰好包含该 branch 的上一条
  screening evidence；
- 第二个 C 的 `proposal_source_ledger` 对上一轮触及的文件使用
  `branch_history_current` provenance；
- 每个候选仍只有一次 H 和一次 C，不因同分支迭代增加隐式调用。

若在两次 candidate 之间重启 campaign，还必须得到同样的 history、provenance
与累计 workspace；durable/live screening 记录不能重复。若 branch hash 表明应
继续使用 verified workspace 但目录已经缺失，运行必须 fail-closed，不能静默
回退到 champion 后继续研究。

再检查每个 formal candidate 的 typed-edit 归一化记录：

```bash
jq '.patch.normalization_events // []' \
  "$CAMPAIGN_DIR"/artifacts/formal_candidates/*/*/candidate.patch.json
```

普通 `exact_replace` 物化为完整文件时出现 `typed_edit_normalization` 可以作为
clean evidence。若出现 `typed_edit_noop_dropped` 或 `patch_set_composition`，
该运行默认只能算 characterization；只有人工逐项对照原始 C response、source
digest 与 canonical patch 后，才能另行接受，不能由 runtime 自动放行成 clean
acceptance。

## 10. 结束后的 report-only 验收

launcher 默认自动重建并严格检查 postrun acceptance。结束后仍应由操作员读取：

```bash
cd "$REPO_ROOT"

"$PY" scion/tools/postrun_artifact_inventory.py "$RUN_ROOT" \
  --format markdown \
  > "$RUN_ROOT/operator-artifact-inventory.md"

"$PY" scion/tools/postrun_analysis_brief.py "$RUN_ROOT" \
  --format markdown \
  > "$RUN_ROOT/operator-analysis-brief.md"

"$PY" scion/tools/check_postrun_acceptance.py "$RUN_ROOT" \
  --require-current-run-ready \
  --format json \
  > "$RUN_ROOT/operator-postrun-readiness.v1.json"

jq . "$RUN_ROOT/operator-postrun-readiness.v1.json"
```

CLI 的当前只读入口：

```bash
cd "$REPO_ROOT/scion"

"$PY" -m scion.cli.main inspect campaign --campaign-dir "$CAMPAIGN_DIR"
"$PY" -m scion.cli.main report summary --campaign-dir "$CAMPAIGN_DIR" --markdown
"$PY" -m scion.cli.main report failures --campaign-dir "$CAMPAIGN_DIR"
```

已知 branch/hypothesis id 时再使用：

```bash
"$PY" -m scion.cli.main inspect branch '<branch-id>' --campaign-dir "$CAMPAIGN_DIR"
"$PY" -m scion.cli.main inspect hypothesis '<hypothesis-id>' --campaign-dir "$CAMPAIGN_DIR"
```

## 11. 有效研究的验收标准

框架验收与研究验收必须分开。

框架层至少证明：

- clean exact commit、prepared manifest、runtime guard 和 completion 一致；
- H/C 次数和 durable receipts 符合 direct-v3；
- Contract、Verification、Protocol、Decision 没有越权；
- multi-file patch 如有需要可完整物化、回滚、归档和复现；
- screening continuation 确实在同一 branch 上利用上一轮实验和 verified source，
  而不是创建互不知情的新分支；
- candidate artifact 的 normalization events 已审计，未把 no-op 丢弃或 patch
  composition 悄悄当成 clean evidence；
- postrun artifacts 完整，failure lane 没有混淆。

研究层至少回答：

- H 是否提出具体、可证伪并与当前源码相符的算法假设；
- C 是否真正实现该机制，而非注释、参数微调或无关重排；
- solver 行为是否能归因到修改后的执行路径；
- Protocol 是否提供足够的 case/seed/pair、质量与 runtime 证据；
- 结果是可复现的收益、有信息量的无收益，还是框架/基础设施失败；
- warehouse 和 open CVRP 是否都表明同一小型 runtime 能进行实际研究。

若只有正常退出、HTTP 200、测试通过或生成了一份 patch，不能关闭 v0.4。

## 12. 诊断运行与正式证据隔离

CVRP launcher 支持 `--force-surface`、`--force-action`、
`--force-target-file`，但它们只用于非正式诊断。例如确认某个 surface 的
Contract/Verification plumbing 时，可以另建明确标记为 diagnostic 的 prepared root。

任何 forced-target run：

- 不能开启 formal completion launch；
- 不能计入 warehouse/CVRP 研究有效性证据；
- 不能用于证明模型会自主选择该算法方向；
- 不能替代 clean/open CVRP control。

同样，恢复旧 campaign 只可用于历史复现或诊断，不属于 v0.4 formal control。

## 13. 失败处理

失败后按以下顺序保全证据：

1. 不删除或覆盖 run root；
2. 记录 `git rev-parse HEAD`、`prepared_run_manifest.v1.json` 和
   `launch_readiness.operator.v1.json`；
3. 读取 `run_status.json`、`exit.txt`、`run.log`；
4. 检查 durable proposal transitions 与 H/C trace；
5. 确认失败 owner：provider/infra、Contract、Verification、Protocol、Decision、postrun；
6. 若需代码修复，提交新 commit 后从头准备，不复用旧 prepared root；
7. 只有操作员显式决定后才启动新的 invocation。

不要把“请求轮数未完成”自动解释为需要重试。先看最后一个 typed
`execution_outcome` 和 `transition_reason`：direct-v3 有意在第一个非
`EVALUATED` outcome 后停止当前 invocation。

## 14. 最终清单

Warehouse：

- [ ] branch 为 `v0.4-dev`，工作树完全干净；
- [ ] prepared commit 与运行 commit 相同；
- [ ] 使用共享密钥环境变量；
- [ ] completion 返回真实非空响应；
- [ ] formal 无 resume、无跳过 postrun；
- [ ] H/C receipts、Contract、Verification、Protocol、Decision 全部可审计；
- [ ] postrun readiness 通过；
- [ ] 研究结果有实际算法与 solver 证据。

CVRP：

- [ ] warehouse 已先通过；
- [ ] 使用同一 runtime commit，从 clean campaign 开始；
- [ ] 无 forced surface/action/target file；
- [ ] 无 successor 目标绑定或历史 campaign 恢复；
- [ ] 低频监控不干预运行；
- [ ] open research direction、代码实现、Protocol 和 full-solver 行为可归因；
- [ ] postrun readiness 通过；
- [ ] 证据足以判断有效收益、有信息量的无收益或明确框架失败。

只有两组 control 都完成并经过上述验收后，才更新 `TASK.md` 和
`current-state.md` 的正式实验结论。
