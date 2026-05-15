# Scion v0.4 本地实验运行、回溯与复现手册

*Last updated: 2026-05-07*

本文档面向需要自己在本地启动、监控、收尾、逐轮回溯、分析和复现
Scion v0.4 实验的人。目标是让你能回答三个问题：怎么跑、每一轮输入输出
在哪里、如何从 artifacts 重建完整实验过程。它不是架构设计文档；架构和边界先读
[`AGENT_ONBOARDING.md`](../AGENT_ONBOARDING.md)、
[`current-state.md`](../status/current-state.md) 和
[`framework-code-map`](../engineering/framework-code-map/README.md)。

## 1. 当前该用哪个入口

v0.4 的主入口是 CLI：

```bash
cd /home/clawd/research/or-autoresearch-agent/scion
/home/clawd/miniconda3/envs/claw/bin/python -m scion.cli.main run --help
```

不要用根目录早期脚本来判断 v0.4 CVRP formal 结果。它们大多是
v0.2/v0.3 的仓配验证脚本或专项 launcher。

当前建议：

| 目的 | 入口 |
| --- | --- |
| v0.4 CVRP real/VRP campaign | `python -m scion.cli.main run ...` |
| v0.4 CVRP synthetic controlled E2E smoke，无 API | `python run_cvrp_controlled_e2e.py --output-dir <run_root>` |
| 查看 campaign 概览 | `python -m scion.cli.main inspect campaign --campaign-dir <campaign>` |
| 生成 bounded summary/report | `python -m scion.cli.main report summary --campaign-dir <campaign>` |
| APS artifact 验证/列表 | `python -m scion.cli.main inspect agentic-sessions ...` |

根目录脚本清理判断：

| 文件 | 当前判断 |
| --- | --- |
| `run_cvrp_controlled_e2e.py` | 仍有价值，v0.4 controlled smoke / final-evidence plumbing。 |
| `archive/run-scripts/run_validation_campaign.py`, `archive/run-scripts/run_closure_validation.py`, `archive/run-scripts/launch_closure_validation.sh` | v0.3 closure/post-optimization validation。仅作历史复现，非 v0.4 主入口。 |
| `archive/run-scripts/run_w16_campaign.py`, `archive/run-scripts/launch_w16.sh`, `archive/run-scripts/auto_w16.sh` | v0.3 W16 validation launcher。历史入口。 |
| `archive/run-scripts/run_v3_campaign.py`, `archive/run-scripts/run_full_campaign.py`, `archive/run-scripts/run_mock_campaign.py` | 老的 warehouse/direct-construction runner。当前优先用 CLI。 |
| `archive/run-scripts/run_v02_*`, `archive/run-scripts/run_sprint_f4.sh` | v0.2/v0.3 sprint 历史脚本。 |

这些归档脚本原本写在 `scion/` 根目录下，部分脚本依赖
`Path(__file__).parent` 或硬编码绝对路径。需要历史复现实验时，先检查路径，
不要直接把它们当当前 v0.4 入口。

## 2. 固定路径和环境

项目根目录：

```text
/home/clawd/research/or-autoresearch-agent
```

Scion 包目录，也是多数 CLI 命令的运行目录：

```text
/home/clawd/research/or-autoresearch-agent/scion
```

Python 环境必须用 `claw`：

```text
/home/clawd/miniconda3/envs/claw/bin/python
```

本地实验输出统一放在：

```text
/home/clawd/research/scion-experiments
```

CVRP formal VRP 需要 repo-local `vrp` 数据根：

```bash
export SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp
```

真实 LLM campaign 需要：

```bash
export SCION_MODEL=claude-sonnet-4-6
export SCION_API_KEY=<your-key>
```

`LLMClient` 也支持 `SCION_BASE_URL`、`ANTHROPIC_AUTH_TOKEN`、
`ANTHROPIC_API_KEY` 和 `ANTHROPIC_BASE_URL`。本项目当前文档里的 Sonnet
实验默认走 `SCION_MODEL=claude-sonnet-4-6`。

重试控制：

```bash
export SCION_SDK_MAX_RETRIES=0
export SCION_LLM_MAX_RETRIES=2
```

默认关闭 provider SDK 内部重试，让 Scion 自己的 LLM retry trace 成为唯一
审计口径。只有在明确需要时才提高 `SCION_SDK_MAX_RETRIES`。实验阶段默认先
用 Sonnet；Opus 只用于明确需要的高质量研究尝试。

## 3. CVRP 配置怎么选

### Formal VRP path

用于真实 CVRPLIB-style formal smoke / readiness plumbing：

```text
problem  = scion/problems/cvrp/problem.yaml
protocol = scion/problems/cvrp/formal/protocol.yaml
split    = scion/problems/cvrp/formal/split_manifest.yaml
seeds    = scion/problems/cvrp/formal/seed_ledger.yaml
data     = /home/clawd/research/or-autoresearch-agent/vrp
```

这个路径会用 real `.vrp` cases，并要求 `SCION_PROBLEM_DATA_ROOT`。当前
v0.4 的 5-round Sonnet CVRP runs 都是这个路径。它适合验证真实 campaign
artifact、surface runtime audit、baseline plumbing，但短跑不等于 solver-quality
证据。

### Controlled synthetic path

用于本地快速 smoke，不需要 API key，不读 CVRPLIB raw data：

```text
scion/scion/problems/cvrp/controlled/
```

直接运行：

```bash
cd /home/clawd/research/or-autoresearch-agent/scion
RUN_ROOT=/home/clawd/research/scion-experiments/v04-cvrp-controlled-manual-$(date -u +%Y%m%dT%H%M%SZ)
/home/clawd/miniconda3/envs/claw/bin/python run_cvrp_controlled_e2e.py --output-dir "$RUN_ROOT"
```

这个路径适合验证框架和 evidence plumbing，不适合声明 benchmark 质量。

## 4. 前台启动一个 formal CVRP smoke

适合 1-5 rounds 的手动调试。先创建 run root：

```bash
cd /home/clawd/research/or-autoresearch-agent/scion
RUN_ROOT=/home/clawd/research/scion-experiments/v04-manual-cvrp-$(date -u +%Y%m%dT%H%M%SZ)
CAMPAIGN_DIR="$RUN_ROOT/campaign"
mkdir -p "$RUN_ROOT"
```

启动真实 Sonnet + APS 的 formal VRP smoke：

```bash
SCION_MODEL=claude-sonnet-4-6 \
SCION_SDK_MAX_RETRIES=0 \
SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp \
/home/clawd/miniconda3/envs/claw/bin/python -m scion.cli.main run \
  --problem scion/problems/cvrp/problem.yaml \
  --protocol scion/problems/cvrp/formal/protocol.yaml \
  --split scion/problems/cvrp/formal/split_manifest.yaml \
  --seeds scion/problems/cvrp/formal/seed_ledger.yaml \
  --campaign-dir "$CAMPAIGN_DIR" \
  --rounds 5 \
  --time-limit-sec 10 \
  --disable-early-stop \
  --agentic-proposal
```

说明：

- `--agentic-proposal` 启用 APS，是 v0.4 当前 proposal 主路径。
- `--disable-early-stop` 用于固定轮数诊断，避免 idle/stagnation 提前截断。
- `--time-limit-sec 10` 是当前 formal smoke 常用预算，不是最终 benchmark
  预算结论。
- 不要把 5-round smoke 当 solver-quality 证据；它通常只证明控制路径和
  artifact 是否健康。

## 5. 可复现后台启动模板

长一点的手动实验建议后台跑，并显式写 `launch.env`、`pid.txt`、
`run.log`、`exit.txt`。`launch.env` 是复现实验的最小入口记录：后续回溯时先
source 它，再从 `campaign_summary.json`、`scion.db`、`llm_traces/`、
`agentic_sessions/` 和 `metrics/` 找每轮证据。

不要把 API key 写进 `launch.env`。在启动前从 shell export
`SCION_API_KEY`，后台进程会继承它。

```bash
RUN_ROOT=/home/clawd/research/scion-experiments/v04-manual-cvrp-$(date -u +%Y%m%dT%H%M%SZ)
CAMPAIGN_DIR="$RUN_ROOT/campaign"
mkdir -p "$RUN_ROOT"

cat > "$RUN_ROOT/launch.env" <<EOF
RUN_ROOT=$RUN_ROOT
CAMPAIGN_DIR=$CAMPAIGN_DIR
REPO_ROOT=/home/clawd/research/or-autoresearch-agent
SCION_DIR=/home/clawd/research/or-autoresearch-agent/scion
PY=/home/clawd/miniconda3/envs/claw/bin/python
SCION_MODEL=claude-sonnet-4-6
SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp
PROBLEM=scion/problems/cvrp/problem.yaml
PROTOCOL=scion/problems/cvrp/formal/protocol.yaml
SPLIT=scion/problems/cvrp/formal/split_manifest.yaml
SEEDS=scion/problems/cvrp/formal/seed_ledger.yaml
ROUNDS=5
TIME_LIMIT_SEC=10
AGENTIC_PROPOSAL=1
DISABLE_EARLY_STOP=1
FORCE_SURFACE=
GIT_COMMIT=$(git -C /home/clawd/research/or-autoresearch-agent rev-parse --short HEAD)
STARTED_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

nohup bash -lc '
source "'"$RUN_ROOT"'/launch.env"
cd "$SCION_DIR"
export SCION_MODEL
export SCION_PROBLEM_DATA_ROOT
cmd=(
  "$PY" -m scion.cli.main run
  --problem "$PROBLEM"
  --protocol "$PROTOCOL"
  --split "$SPLIT"
  --seeds "$SEEDS"
  --campaign-dir "$CAMPAIGN_DIR"
  --rounds "$ROUNDS"
  --time-limit-sec "$TIME_LIMIT_SEC"
)
if [ "$DISABLE_EARLY_STOP" = "1" ]; then
  cmd+=(--disable-early-stop)
fi
if [ "$AGENTIC_PROPOSAL" = "1" ]; then
  cmd+=(--agentic-proposal)
fi
if [ -n "$FORCE_SURFACE" ]; then
  cmd+=(--force-surface "$FORCE_SURFACE")
fi
printf "COMMAND:" > "$RUN_ROOT/command.txt"
printf " %q" "${cmd[@]}" >> "$RUN_ROOT/command.txt"
printf "\n" >> "$RUN_ROOT/command.txt"
"${cmd[@]}"
code=$?
printf "EXIT_CODE:%s\n" "$code" > "'"$RUN_ROOT"'/exit.txt"
exit "$code"
' > "$RUN_ROOT/run.log" 2>&1 &

echo $! > "$RUN_ROOT/pid.txt"
```

验证启动：

```bash
ps -p "$(cat "$RUN_ROOT/pid.txt")" -o pid,ppid,stat,etime,cmd
tail -n 80 "$RUN_ROOT/run.log"
```

需要强制 `algorithm_blueprint` 时，只改 `launch.env`：

```bash
sed -i 's/^FORCE_SURFACE=.*/FORCE_SURFACE=algorithm_blueprint/' "$RUN_ROOT/launch.env"
```

为了复现同一次实验，至少保留这些文件：

```text
launch.env
command.txt
pid.txt
run.log
exit.txt
campaign/
```

注意：真实 LLM 调用不是严格 bitwise deterministic。完整复现的含义是：保留
同一 commit、同一配置、同一 LLM trace、同一 APS artifact、同一 candidate
workspace/archive、同一 protocol raw metrics，然后可以逐轮重建“当时模型看到了
什么、输出了什么、框架如何检查、协议如何统计、Decision 为什么这么判”。如果
重新调用模型，可能得到不同 proposal。

## 6. 强制某个 research surface

当你要验证某个 surface 的控制路径，而不是让 APS 自由选 surface，可以用
`--force-surface`。

当前 `algorithm_blueprint` 报告链路验证使用：

```bash
SCION_MODEL=claude-sonnet-4-6 \
SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp \
/home/clawd/miniconda3/envs/claw/bin/python -m scion.cli.main run \
  --problem scion/problems/cvrp/problem.yaml \
  --protocol scion/problems/cvrp/formal/protocol.yaml \
  --split scion/problems/cvrp/formal/split_manifest.yaml \
  --seeds scion/problems/cvrp/formal/seed_ledger.yaml \
  --campaign-dir "$CAMPAIGN_DIR" \
  --rounds 5 \
  --time-limit-sec 10 \
  --disable-early-stop \
  --agentic-proposal \
  --force-surface algorithm_blueprint
```

注意：

- `--force-surface` 是诊断控制，不是 Decision input。
- 它用于提高某个 declared surface 的覆盖率，不代表该 surface 必然会产生
  solver-quality 改进。
- 对 singleton surface，CLI 通常能从 spec 推导 `action=modify` 和 target file。
  只有需要非常明确复现时再加：

```bash
--force-action modify --force-target-file policies/algorithm_blueprint.py
```

## 7. 运行中怎么看

设定：

```bash
RUN_ROOT=/home/clawd/research/scion-experiments/<run-id>
CAMPAIGN_DIR="$RUN_ROOT/campaign"
PY=/home/clawd/miniconda3/envs/claw/bin/python
```

进程是否还在：

```bash
ps -p "$(cat "$RUN_ROOT/pid.txt")" -o pid,ppid,stat,etime,cmd
```

日志尾部：

```bash
tail -n 80 "$RUN_ROOT/run.log"
```

轻量 status：

```bash
jq '{
  n_experiments,
  champion_version,
  n_active_branches,
  protocol_progress,
  weight_optimization
}' "$CAMPAIGN_DIR/status.json"
```

SQLite/campaign 概览：

```bash
cd /home/clawd/research/or-autoresearch-agent/scion
$PY -m scion.cli.main inspect campaign --campaign-dir "$CAMPAIGN_DIR"
```

APS sessions 列表。当前 `run` 默认把 APS artifacts 放在
`campaign/agentic_sessions`，所以手动指定 `--artifact-dir`，避免走到旧的
inspect 默认路径：

```bash
$PY -m scion.cli.main inspect agentic-sessions \
  --campaign-dir "$CAMPAIGN_DIR" \
  --artifact-dir "$CAMPAIGN_DIR/agentic_sessions"
```

普通监控不要展开 `llm_traces/` 和完整 APS transcript。它们是 tainted proposal
artifact，通常只需要看 digest、status、validation 是否 ok。

## 8. 实验 artifact 地图

一个 v0.4 campaign 的核心目录结构：

```text
<RUN_ROOT>/
  launch.env                         # 人写的环境/配置快照，建议每次都有
  command.txt                        # 实际执行的 CLI command，建议每次都有
  pid.txt                            # 后台进程 PID
  run.log                            # stdout/stderr
  exit.txt                           # EXIT_CODE:N
  campaign/
    campaign_summary.json            # 首选分析入口，每轮 bounded summary
    status.json                      # 运行中状态和 protocol progress
    scion.db                         # lineage SQLite，append-only 事件、hypotheses、branches、champions
    llm_traces/                      # LLM prompt/response trace，含 hypothesis/code/tool_selection
    agentic_sessions/                # APS compact artifact + recovery index
    metrics/                         # protocol raw metrics，每个 evaluated stage 一个 JSON
    workspaces/                      # 运行中 branch workspace，结束后通常为空或被清理
    archive/                         # abandoned/failed branch 的 operators/ 归档
    champions/                       # champion snapshot，例如 champion_v1
```

每一轮的输入输出对应关系：

| 阶段 | 输入在哪里 | 输出在哪里 |
| --- | --- | --- |
| Proposal context | `llm_traces/*_hypothesis_*.json` 的 `system_blocks` / `user_prompt`；APS 路径还看 `agentic_sessions/*/output.json` | `hypothesis`：`campaign_summary.json.steps[].hypothesis`、`scion.db.hypotheses`、LLM trace response |
| Patch/code | `llm_traces/*_code_*.json` 的 prompt；APS completed artifact | `patch`：LLM trace response、candidate workspace、`campaign_summary.steps[].code_archive_ref` 或 `campaign/archive/<branch>` |
| Contract | `hypothesis` + `patch` + `problem-v1.yaml` surface metadata | `campaign_summary.steps[].contract_passed/failure_detail`、`scion.db.experiment_events.contract_result` |
| Workspace | champion snapshot + patch | `campaign/workspaces/<branch_id>` 运行中可见；失败/abandon 后通常归档到 `campaign/archive/<branch_short>` |
| Verification | candidate workspace + adapter + canary/runtime checks | `campaign_summary.steps[].verification_passed/verification_detail`、`scion.db.experiment_events.decision_features_json.verification_checks` |
| Protocol | champion snapshot + candidate workspace + split/seeds/protocol | `campaign_summary.steps[].protocol_result`、`protocol_result.raw_metrics_ref` 指向 `campaign/metrics/*.json` |
| Decision | deterministic `DecisionFeatures`，不读 LLM 自由文本 | `campaign_summary.steps[].decision`、`decision_reason_codes`、`scion.db.experiment_events.decision` |

## 9. 逐轮回溯输入输出

设定变量：

```bash
source /home/clawd/research/scion-experiments/<run-id>/launch.env
SUMMARY="$CAMPAIGN_DIR/campaign_summary.json"
DB="$CAMPAIGN_DIR/scion.db"
```

### 9.1 列出每轮索引

```bash
jq -r '
  .steps[]
  | [
      .round,
      .branch_id,
      .hypothesis.change_locus,
      .hypothesis.action,
      (.hypothesis.target_file // ""),
      .decision,
      ((.decision_reason_codes // .protocol_result.effective_reason_codes // []) | join(";")),
      (.protocol_result.raw_metrics_ref // "")
    ]
  | @tsv
' "$SUMMARY"
```

### 9.2 取第 N 轮的核心变量

```bash
ROUND=1
BRANCH=$(jq -r --argjson r "$ROUND" '.steps[] | select(.round == $r) | .branch_id' "$SUMMARY")
METRICS=$(jq -r --argjson r "$ROUND" '.steps[] | select(.round == $r) | .protocol_result.raw_metrics_ref // empty' "$SUMMARY")
ARCHIVE=$(jq -r --argjson r "$ROUND" '.steps[] | select(.round == $r) | .code_archive_ref // empty' "$SUMMARY")
APS_REF=$(jq -r --argjson r "$ROUND" '.steps[] | select(.round == $r) | .proposal_session_ref.artifact_ref // empty' "$SUMMARY")
echo "BRANCH=$BRANCH"
echo "METRICS=$METRICS"
echo "ARCHIVE=$ARCHIVE"
echo "APS_REF=$APS_REF"
```

### 9.3 看该轮 hypothesis 和决策摘要

```bash
jq --argjson r "$ROUND" '
  .steps[]
  | select(.round == $r)
  | {
      round,
      branch_id,
      hypothesis,
      proposal_session_ref,
      contract_passed,
      verification_passed,
      verification_detail,
      failure_stage,
      failure_detail,
      decision,
      decision_reason_codes,
      protocol_result
    }
' "$SUMMARY"
```

### 9.4 从 SQLite 查该 branch 的 lineage 事件

```bash
sqlite3 "$DB" -header -column "
SELECT
  event_kind,
  timestamp,
  branch_id,
  hypothesis_id,
  patch_action,
  patch_file,
  contract_result,
  verification_result,
  canary_result,
  stage,
  screening_win_rate,
  screening_median_delta,
  decision,
  raw_metrics_ref
FROM experiment_events
WHERE branch_id = '$BRANCH'
ORDER BY timestamp;
"
```

查 hypothesis 记录：

```bash
sqlite3 "$DB" -header -column "
SELECT
  hypothesis_id,
  branch_id,
  change_locus,
  action,
  target_file,
  status,
  predicted_direction,
  target_objectives_json,
  protected_objectives_json,
  substr(hypothesis_text, 1, 160) AS hypothesis_text
FROM hypotheses
WHERE branch_id = '$BRANCH'
ORDER BY created_at;
"
```

### 9.5 找这一轮对应的 LLM traces

如果走 APS，先从 `proposal_session_ref.artifact_ref` 查 session：

```bash
jq '{
  status,
  session_id,
  request_id,
  idempotency_key,
  selected_surface,
  action,
  hypothesis,
  patch,
  termination_reason,
  tool_budget_used,
  transcript_digest,
  self_check
}' "$APS_REF"
```

再用 `request_id`、`branch_id` 或时间顺序找 `llm_traces/`：

```bash
ls -1 "$CAMPAIGN_DIR/llm_traces" | sort
```

查看某个 trace 的输入输出：

```bash
TRACE="$CAMPAIGN_DIR/llm_traces/<trace-file>.json"
jq '{
  trace_id,
  request_kind,
  model,
  branch_id,
  champion_version,
  prompt_hash,
  ok,
  error,
  response
}' "$TRACE"
```

需要看模型当时具体看到什么，再打开：

```bash
jq '{system_blocks, user_prompt, tool_schema}' "$TRACE"
```

这一步会暴露 tainted proposal context。不要把大段 prompt/response 粘贴到
current-state 或实验总结里，只提炼 bounded 结论和 trace ref。

### 9.6 看该轮 patch/candidate 代码

如果该轮有 APS completed artifact，patch 在：

```bash
jq '.patch | {file_path, action, test_hint, code_chars: (.code_content | length)}' "$APS_REF"
```

如果想看代码正文：

```bash
jq -r '.patch.code_content' "$APS_REF"
```

如果该轮被 abandon，通常会有 archive：

```bash
find "$ARCHIVE" -maxdepth 3 -type f | sort
```

当前 `archive_workspace()` 主要归档 `operators/`。如果候选改的是
`policies/*.py`，优先从 APS artifact 或 `llm_traces/*_code_*.json` 的 response
找 patch 内容；必要时在运行中查看 `campaign/workspaces/<branch_id>/`。如果
campaign 已完成且 workspace 被清理，policy patch 可能只在 APS/LLM trace 中。

### 9.7 看 Verification 细节

`campaign_summary.json` 只放 bounded 字段。更详细的 check metadata 在 SQLite 的
`decision_features_json` 里：

```bash
sqlite3 "$DB" -json "
SELECT decision_features_json
FROM experiment_events
WHERE branch_id = '$BRANCH'
  AND event_kind = 'experiment'
ORDER BY timestamp DESC
LIMIT 1;
" | jq '.[0].decision_features_json | fromjson | {
  selected_surface,
  verification_checks,
  runtime_guard,
  runtime_stats,
  decision_reason_codes,
  metrics_refs
}'
```

V8 adapter-backed 成功时，通常可在 `verification_checks[]` 的 metadata 看到
`comparison_mode=adapter_canonical_signature`、`comparison_equal=true` 等审计信息。

### 9.8 看 Protocol pair 级输入输出

先看 raw metrics 顶层：

```bash
jq '{
  stage,
  selected_surface,
  case_ids,
  seed_set,
  complete,
  attempted_pairs,
  valid_pairs,
  failed_pairs,
  runtime_stats,
  candidate_surface_runtime_summary
}' "$METRICS"
```

再看每个 case×seed：

```bash
jq -r '
  .pairs[]
  | [
      .case,
      .seed,
      .comparison,
      .delta,
      .decisive_metric,
      (.metric_deltas | tostring),
      (.candidate_elapsed_ms // ""),
      (.champion_elapsed_ms // ""),
      (.runtime_ratio // "")
    ]
  | @tsv
' "$METRICS"
```

失败 pair：

```bash
jq '.failures' "$METRICS"
```

### 9.9 重建一轮的完整故事

每轮分析按这个顺序写：

```text
Round N / branch_id
1. APS/LLM 看到的输入：trace prompt hash + selected context 类型，不粘贴全文。
2. LLM/APS 输出：hypothesis surface/action/target + patch file。
3. Contract：pass/fail；失败码或失败原因。
4. Verification：pass/fail；首个失败 check；adapter/runtime metadata。
5. Protocol：stage、cases、seeds、valid/failed pairs、win/loss/tie、median_delta、runtime。
6. Decision：decision + reason codes。
7. 解释：这是 proposal 问题、实现问题、runtime/环境问题、还是算法质量问题。
```

### 9.10 复跑同一配置

不要在原 `CAMPAIGN_DIR` 上直接复跑，除非你明确要污染/续写同一个 lineage。
复现实验配置时，新建 run root，但 source 原始 `launch.env`：

```bash
OLD_RUN_ROOT=/home/clawd/research/scion-experiments/<old-run-id>
source "$OLD_RUN_ROOT/launch.env"

NEW_RUN_ROOT=/home/clawd/research/scion-experiments/repro-$(basename "$OLD_RUN_ROOT")-$(date -u +%Y%m%dT%H%M%SZ)
NEW_CAMPAIGN_DIR="$NEW_RUN_ROOT/campaign"
mkdir -p "$NEW_RUN_ROOT"

cp "$OLD_RUN_ROOT/launch.env" "$NEW_RUN_ROOT/launch.env"
sed -i "s|^RUN_ROOT=.*|RUN_ROOT=$NEW_RUN_ROOT|" "$NEW_RUN_ROOT/launch.env"
sed -i "s|^CAMPAIGN_DIR=.*|CAMPAIGN_DIR=$NEW_CAMPAIGN_DIR|" "$NEW_RUN_ROOT/launch.env"
```

如果要严格复现某个旧 commit，先确认：

```bash
grep '^GIT_COMMIT=' "$OLD_RUN_ROOT/launch.env"
git -C /home/clawd/research/or-autoresearch-agent status --short
```

有未提交工作区改动时，先判断这些改动是否属于实验。如果旧实验对应的代码没有
保留成 commit，就只能复现“配置和 artifact 分析”，不能保证重跑代码完全一致。

### 9.11 手动复跑某个 solver pair

当你怀疑某个 case×seed 的 solver 输出，可以直接在 champion/candidate
workspace 上复跑 CVRP solver。

先从 raw metrics 取一个 pair：

```bash
CASE=$(jq -r '.pairs[0].case' "$METRICS")
SEED=$(jq -r '.pairs[0].seed' "$METRICS")
```

Champion workspace 通常在：

```bash
CHAMP_WS="$CAMPAIGN_DIR/champions/champion_v1"
```

Candidate workspace 如果还在运行中，可能在：

```bash
CAND_WS="$CAMPAIGN_DIR/workspaces/$BRANCH"
```

如果 workspace 已被清理，先用 `ARCHIVE`、APS patch 或 LLM trace 在临时目录重建
candidate；当前 abandoned operator 会归档到 `campaign/archive/<branch_short>`，
policy/config surface 的 patch 需要从 APS/LLM trace 取回。

复跑 champion：

```bash
OUT=/tmp/scion_pair_champion.json
(
  cd "$CHAMP_WS"
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp \
  "$PY" solver.py "$CASE" \
    --seed "$SEED" \
    --time-limit "$TIME_LIMIT_SEC" \
    --registry "$CHAMP_WS/registry.yaml" \
    --output "$OUT"
)
jq '{objective, runtime}' "$OUT"
```

复跑 candidate：

```bash
OUT=/tmp/scion_pair_candidate.json
(
  cd "$CAND_WS"
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp \
  "$PY" solver.py "$CASE" \
    --seed "$SEED" \
    --time-limit "$TIME_LIMIT_SEC" \
    --registry "$CAND_WS/registry.yaml" \
    --output "$OUT"
)
jq '{objective, runtime}' "$OUT"
```

这个手动复跑只验证 solver 层。Protocol 的 win-rate、case aggregation、CI、
Decision reason 仍以 `campaign/metrics/*.json` 和 `campaign_summary.json` 为准。

## 10. 完成后第一轮检查

先看 exit 和 summary 是否存在：

```bash
cat "$RUN_ROOT/exit.txt"
test -f "$CAMPAIGN_DIR/campaign_summary.json"
```

`exit.txt` 应该是：

```text
EXIT_CODE:0
```

读取 campaign 顶层摘要：

```bash
SUMMARY="$CAMPAIGN_DIR/campaign_summary.json"
jq '{
  total_rounds,
  champion_version,
  champion_weight_revision,
  n_active_branches,
  stopped_reason,
  frozen_budget,
  formal_readiness,
  action_locus_coverage,
  family_coverage,
  verification_failure_breakdown
}' "$SUMMARY"
```

输出每轮的核心表：

```bash
jq -r '
  .steps[]
  | [
      .round,
      .hypothesis.change_locus,
      .hypothesis.action,
      .hypothesis.target_file,
      .contract_passed,
      .verification_passed,
      .decision,
      ((.decision_reason_codes // []) | join(";")),
      (.protocol_result.stage // ""),
      (.protocol_result.win_rate // ""),
      (.protocol_result.median_delta // ""),
      (.protocol_result.runtime_ratio_median // "")
    ]
  | @tsv
' "$SUMMARY"
```

如果没有 `campaign_summary.json`，说明 campaign 可能还没正常 closeout，或进程
仍在跑。先看 `ps`、`run.log`、`status.json`，不要急着从 raw metrics 得结论。

## 11. 分析顺序

分析时按这个顺序走，避免一开始陷入 raw JSON。

### 11.1 判断这是控制路径证据还是质量证据

短跑通常只回答：

- Contract/Verification/Protocol 是否能跑通；
- real `.vrp` baseline 是否可用；
- APS artifact 是否健康；
- selected surface 的 runtime fields 是否被记录；
- 候选是否至少进入 screening。

只有出现 promotion、validation/frozen evidence、final evidence refs，才开始讨论
solver-quality 证据。当前 v0.4 CVRP 短跑多数是 control-path evidence。

### 11.2 先看失败在哪一层

```bash
jq '
  [.steps[]
  | {
      round,
      surface: .hypothesis.change_locus,
      action: .hypothesis.action,
      target: .hypothesis.target_file,
      contract_passed,
      verification_passed,
      decision,
      failure_stage,
      failure_detail,
      reasons: (.decision_reason_codes // .protocol_result.effective_reason_codes // .protocol_result.reason_codes // [])
    }]
' "$SUMMARY"
```

解释：

| 层 | 常见含义 |
| --- | --- |
| Contract fail | patch 越界、接口缺失、复杂度风险、surface target 不合法。 |
| Verification fail | 适配器语义、可行性、目标重算、V8 确定性或 runtime audit 失败。 |
| Canary fail | 小样本回归或 selected-surface runtime audit 在 canary 阶段失败。 |
| Screening fail | 候选能跑，但统计证据不够；CVRP 当前常见 `SCREENING_FAIL_WIN_RATE`。 |
| Validation/Frozen fail | 更高阶段证据不足或 runtime evidence 不完整。 |

### 11.3 看 surface 覆盖是否符合实验目的

```bash
jq '{action_locus_coverage, family_coverage}' "$SUMMARY"
```

如果你在验证 `algorithm_blueprint`，至少要看到
`modify/algorithm_blueprint` 或 step 里 `hypothesis.change_locus =
"algorithm_blueprint"`。如果没有，先解决 proposal/surface selection，再谈质量。

### 11.4 看 protocol summary

```bash
jq '
  [.steps[]
  | select(.protocol_result != null)
  | {
      round,
      surface: .hypothesis.change_locus,
      selected_surface: .protocol_result.selected_surface,
      gate: .protocol_result.gate_outcome,
      reasons: .protocol_result.effective_reason_codes,
      win_rate: .protocol_result.win_rate,
      median_delta: .protocol_result.median_delta,
      ci_low: .protocol_result.ci_low,
      valid_pairs: .protocol_result.valid_pairs,
      failed_pairs: .protocol_result.failed_pairs,
      runtime_ratio_median: .protocol_result.runtime_ratio_median,
      runtime_delta_median_ms: .protocol_result.runtime_delta_median_ms,
      candidate_runtime_failure_categories: .protocol_result.candidate_runtime_failure_categories,
      candidate_runtime_stop_reasons: .protocol_result.candidate_runtime_stop_reasons
    }]
' "$SUMMARY"
```

CVRP 当前要特别区分：

| 信号 | 含义 |
| --- | --- |
| `baseline_error` | 环境或 required baseline 问题，不是候选算法质量问题。 |
| `policy_error`, `construction_error`, `portfolio_error` | 对应 policy surface 返回值/API 不合法。 |
| `surface_contract_error` | selected surface 宣告的 required runtime field 缺失/为空/失败。 |
| `no_accepted_moves` | 运行了但没有有效接受移动，常见于 post-baseline operator no-op。 |
| `SCREENING_FAIL_WIN_RATE` + `median_delta=0` | 候选可运行，但 tie/no-op 主导。 |
| `runtime_ratio_median < 1` | 候选更快。若 objective 非退化且达到 `runtime.tie_speedup_ratio`，可作为 tie-preserving speedup 经过 validation/frozen 晋升；不能绕过三层验证。 |

### 11.5 专门检查 `algorithm_blueprint`

`algorithm_blueprint` 是当前 v0.4 CVRP 的关键 surface。它应该写出这些
required runtime fields：

```text
algorithm_blueprint_loaded
algorithm_blueprint_active
algorithm_blueprint_errors
algorithm_plan
algorithm_phases_executed
algorithm_construction_methods
algorithm_baseline_time_fraction
algorithm_operator_round_limit
algorithm_post_baseline_operators_enabled
algorithm_local_search_components
algorithm_local_search_rounds
algorithm_local_search_attempts
algorithm_local_search_accepted
algorithm_restart_enabled
algorithm_restart_stagnation_rounds
algorithm_restart_count
algorithm_best_delta_by_phase
algorithm_phase_runtime_ms
algorithm_stop_reason
```

在 summary 中检查：

```bash
jq '
  [.steps[]
  | select(.protocol_result.selected_surface == "algorithm_blueprint")
  | {
      round,
      decision,
      win_rate: .protocol_result.win_rate,
      median_delta: .protocol_result.median_delta,
      surface_summary: .protocol_result.candidate_surface_runtime_summary
    }]
' "$SUMMARY"
```

快速看哪些字段出现了：

```bash
jq '
  [.steps[]
  | select(.protocol_result.selected_surface == "algorithm_blueprint")
  | {
      round,
      required: .protocol_result.candidate_surface_runtime_summary.required_runtime_fields,
      fields: (.protocol_result.candidate_surface_runtime_summary.fields | keys)
    }]
' "$SUMMARY"
```

如果 `selected_surface` 还是 `null`，说明你看的 run 早于 reporting refinement，
或者 fresh smoke 没有覆盖新 reporting path。不要用它判断当前 reporting 是否修好。

## 12. 什么时候读 raw metrics

先用 `campaign_summary.json` 和 CLI inspect。只有需要回答以下问题时再打开
`raw_metrics_ref`：

- 每个 case/seed 的 win/loss/tie 分布是什么；
- 某个 runtime field 是否在 pair 级 candidate runtime 中存在；
- `algorithm_blueprint` 的 plan 在不同 pair 中是否一致；
- 哪些 cases 有 win/loss，而不是只看总体 win_rate。

取某一轮的 raw metrics path：

```bash
METRICS=$(jq -r '
  .steps[]
  | select(.round == 1)
  | .protocol_result.raw_metrics_ref
' "$SUMMARY")
```

先看 bounded 顶层：

```bash
jq '{
  stage,
  selected_surface,
  complete,
  attempted_pairs,
  valid_pairs,
  failed_pairs,
  runtime_stats,
  candidate_surface_runtime_summary
}' "$METRICS"
```

再看 pair-level 简表：

```bash
jq -r '
  .pairs[]
  | [
      .case,
      .seed,
      .comparison,
      .delta,
      .decisive_metric,
      .runtime_ratio,
      (.candidate_runtime.algorithm_blueprint_active // ""),
      (.candidate_runtime.algorithm_local_search_attempts // ""),
      (.candidate_runtime.algorithm_local_search_accepted // ""),
      (.candidate_runtime.algorithm_stop_reason // "")
    ]
  | @tsv
' "$METRICS"
```

不要把 raw metrics 大段复制进 docs。实验文档里只写 artifact ref 和 bounded
结论。

## 13. VRP 优化瓶颈的手动分析问题清单

当前 CVRP 主要瓶颈不是“框架没有跑起来”，而是候选在 real VRP screening 中
经常 tie/no-op，难以达到 win-rate gate。分析时按下面问题拆：

1. 环境是否健康？
   `failed_pairs=0`、没有 `baseline_error`、baseline 使用 repo-local real VRP
   路径，才可讨论算法质量。
2. Surface 是否真的被选中并执行？
   看 `hypothesis.change_locus`、`protocol_result.selected_surface`、
   `candidate_surface_runtime_summary`。
3. Blueprint 是否 active？
   看 `algorithm_blueprint_active=true`、`algorithm_blueprint_errors=0`。
4. Construction ensemble 是否真的产生差异？
   看 `algorithm_construction_methods`、`algorithm_plan`、
   `algorithm_best_delta_by_phase`。注意 `construction_keep_top_k` 可能导致某些
   declared methods 没有实际进入后续阶段。
5. Local search 是否有尝试和接受？
   看 `algorithm_local_search_attempts` 和 `algorithm_local_search_accepted`。
   尝试多但 accepted 低，说明 neighborhood/acceptance 设计弱；尝试为 0，说明
   plan 或 budget 没有触发这段。
6. Baseline budget 是否把 candidate 空间挤没了？
   看 `algorithm_baseline_time_fraction`、runtime ratio、objective tie 分布。
7. Post-baseline registry operator 是否为空？
   `neighborhood_portfolio` 遇到 `no_registry_operators` 不是 portfolio 本身一定
   无效，而是没有 generated registry operators 可调度。
8. objective 失败是质量、速度，还是 gate 阈值？
   `runtime_ratio_median < 1` 是算法效率信号。若 lexicographic objective
   非退化、没有 runtime failure，且达到 `runtime.tie_speedup_ratio`，Decision
   可以走 `*_PASS_RUNTIME_TIE_IMPROVEMENT`，但仍必须通过 validation/frozen。

把结论写成“哪一层阻塞 + 下一步要验证的假设”，不要直接写“模型不行”。

## 14. 写实验分析文档

完成一次手动分析后，在 `docs/experiments/v0.4/` 新建或更新文档。建议模板：

````markdown
# <Run Name>

Date: <UTC date>

Run root:

```text
<absolute run root>
```

## Configuration

```text
model=
rounds=
agentic_proposal=
force_surface=
time_limit_sec=
python=
data_root=
protocol=
split=
seeds=
```

## Outcome

```text
exit_code=
total_rounds=
experiments=
champion=
promotions=
stopped_reason=
formal_ready=
final_evidence_refs=
```

## Interpretation

- 这是 control-path evidence 还是 solver-quality evidence。
- 哪些 surfaces 被覆盖。
- Contract / Verification / Protocol 分别是否阻塞。
- CVRP 质量信号：win/loss/tie、median_delta、runtime、accepted moves。
- 对当前瓶颈的解释。

## Artifact refs

```text
summary=
status=
agentic_index=
raw_metrics_refs=<只列关键 ref，不粘贴内容>
```

## Next actions

- 下一轮要验证什么。
- 哪些代码/文档需要改。
````

写完后同步更新：

- `docs/experiments/v0.4/README.md`
- `docs/status/current-state.md`

如果是 code change 后的实验，还要更新对应
`docs/engineering/framework-code-map/` 文档。

## 15. 当前正在跑的 validation 怎么看

截至本文档更新时间，当前记录中的运行是：

```text
/home/clawd/research/scion-experiments/v04-blueprint-reporting-sonnet-5r-20260507T141342Z
```

目的：验证 selected-surface runtime reporting refinement 后，
`algorithm_blueprint` 的 `algorithm_*` required runtime fields 是否进入
formal screening pair metrics 和 `campaign_summary.json`。

查看：

```bash
RUN_ROOT=/home/clawd/research/scion-experiments/v04-blueprint-reporting-sonnet-5r-20260507T141342Z
CAMPAIGN_DIR="$RUN_ROOT/campaign"
PY=/home/clawd/miniconda3/envs/claw/bin/python

ps -p "$(cat "$RUN_ROOT/pid.txt")" -o pid,ppid,stat,etime,cmd
tail -n 80 "$RUN_ROOT/run.log"
$PY -m scion.cli.main inspect campaign --campaign-dir "$CAMPAIGN_DIR"
$PY -m scion.cli.main inspect agentic-sessions \
  --campaign-dir "$CAMPAIGN_DIR" \
  --artifact-dir "$CAMPAIGN_DIR/agentic_sessions"
```

完成后先跑第 10 节和第 11.5 节的 summary 检查。该 run 的验收重点不是
promotion，而是：

- `exit.txt` 为 `EXIT_CODE:0`；
- `campaign_summary.json` 存在；
- 至少一轮是 `algorithm_blueprint`；
- 对应 `protocol_result.selected_surface=algorithm_blueprint`；
- `candidate_surface_runtime_summary.fields` 含非空 `algorithm_*` 字段；
- raw metrics pair 的 `candidate_runtime` 也含这些字段。
