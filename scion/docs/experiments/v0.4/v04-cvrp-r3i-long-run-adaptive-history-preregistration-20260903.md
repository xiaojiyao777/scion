# CVRP R3i long-run adaptive-history preregistration

R3i tests whether Scion can continue ordinary CVRP algorithm research for a
multi-day run after removing invocation-level failure caused by proposal-local
capacity and transient provider conditions.

## Frozen scope

- Fresh B0; no R3h workspace, candidate, branch, metric, or database state is
  resumed.
- K=1 selected H per proposal and the existing three-branch depth/breadth
  scheduler.
- Target: 40 formally evaluated stages. Screening remains adaptive development;
  validation and frozen remain held out from H/C.
- Formal CVRP case/seed budgets and all correctness/safety/promotion rules are
  unchanged.
- Provider model `gpt-5.6-sol`, reasoning effort `high`; H/default timeout 180s,
  C turn/finalize timeout 300s.
- At most two Scion redispatches for the same frozen typed-transient/429 request,
  with traced and charged physical calls and Retry-After-aware backoff.
- Generous operator safety envelope: 2,000 physical provider dispatches and a
  14-day hardwall. These are not scientific gates and are far above the expected
  demand of 40 evaluated stages.
- Research limits are the explicit
  `inputs/v04-cvrp-r3i-long-run-code-research-limits.json`: 12 turns, 8 reads,
  8 searches, expanded result/test bounds, and no total transcript character
  limit. Reaching a local limit after work begins rejects only that attempt.

## History input

The production loader must read exactly eight files in this order:

`R3 -> R3b -> R3c -> R3d -> R3e -> R3f -> R3g -> R3h`

The frozen line counts are `[21,1,2,1,1,22,2,15] = 65`. Only ordinary
provider-safe history rows are inputs; no candidate source or held-out stage is
reconstructed. The current input bounds (16 files, 256 records, 64 MiB) leave
ample room for this run. Output projection reaching its own policy limit is
nonfatal.

## Launch identity and carrier

- Source worktree: `/home/clawd/research/or-autoresearch-agent-r3i-dev` at the
  commit containing this preregistration and the long-run fixes.
- Fresh root:
  `/home/clawd/research/scion-experiments/v04-cvrp-r3i-normal-k1-sol-20260903-r1`.
- Local tmux carrier: `scion-r3i-normal-k1-sol-20260903-r1`.

The carrier is only a local detached process owner. It is not a deployment,
service, build, scheduler, lease, registry, or scientific evidence source.
Durable campaign artifacts remain authoritative.

## Frozen launch block

```bash
set -Eeuo pipefail

carrier_session='scion-r3i-normal-k1-sol-20260903-r1'
carrier_workdir='/home/clawd/research/or-autoresearch-agent-r3i-dev/scion'
carrier_created=0

cleanup_carrier_on_error() {
  carrier_rc=$?
  trap - EXIT
  if (( carrier_rc != 0 && carrier_created == 1 )); then
    tmux kill-session -t "$carrier_session" 2>/dev/null || true
  fi
  exit "$carrier_rc"
}
trap cleanup_carrier_on_error EXIT

if tmux has-session -t "$carrier_session" 2>/dev/null; then
  printf 'refusing existing tmux session: %s\n' "$carrier_session" >&2
  exit 73
fi

tmux new-session -d -s "$carrier_session" -n run 'sleep infinity'
carrier_created=1
tmux set-option -w -t "${carrier_session}:run" remain-on-exit on
tmux respawn-pane -k -c "$carrier_workdir" -t "${carrier_session}:run.0" \
  'set -Eeuo pipefail
proxy_key_value=
trap "unset proxy_key_value" EXIT

r3_history=/home/clawd/research/scion-experiments/v04-cvrp-r3-normal-k1-sol-20260828-r1/research_history.jsonl
r3b_history=/home/clawd/research/scion-experiments/v04-cvrp-r3b-normal-k1-sol-20260829-r1/research_history.jsonl
r3c_history=/home/clawd/research/scion-experiments/v04-cvrp-r3c-normal-k1-sol-20260830-r1/research_history.jsonl
r3d_history=/home/clawd/research/scion-experiments/v04-cvrp-r3d-normal-k1-sol-20260830-r1/research_history.jsonl
r3e_history=/home/clawd/research/scion-experiments/v04-cvrp-r3e-normal-k1-sol-20260830-r1/research_history.jsonl
r3f_history=/home/clawd/research/scion-experiments/v04-cvrp-r3f-normal-k1-sol-20260831-r1/research_history.jsonl
r3g_history=/home/clawd/research/scion-experiments/v04-cvrp-r3g-normal-k1-sol-20260901-r1/research_history.jsonl
r3h_history=/home/clawd/research/scion-experiments/v04-cvrp-r3h-normal-k1-sol-20260902-r1/research_history.jsonl

test ! -e /home/clawd/research/scion-experiments/v04-cvrp-r3i-normal-k1-sol-20260903-r1
test -x /home/clawd/miniconda3/envs/claw/bin/python
for history_path in "$r3_history" "$r3b_history" "$r3c_history" \
  "$r3d_history" "$r3e_history" "$r3f_history" "$r3g_history" "$r3h_history"; do
  test -f "$history_path"
done
test "$(wc -l < "$r3_history")" -eq 21
test "$(wc -l < "$r3b_history")" -eq 1
test "$(wc -l < "$r3c_history")" -eq 2
test "$(wc -l < "$r3d_history")" -eq 1
test "$(wc -l < "$r3e_history")" -eq 1
test "$(wc -l < "$r3f_history")" -eq 22
test "$(wc -l < "$r3g_history")" -eq 2
test "$(wc -l < "$r3h_history")" -eq 15

proxy_key_value=$(curl -fsS --connect-timeout 5 --max-time 15 \
  http://127.0.0.1:8080/auth/status | \
  jq -er ".proxy_api_key | select(type == \"string\" and length > 0)")
curl -fsS --connect-timeout 5 --max-time 15 \
  -H "Authorization: Bearer $proxy_key_value" \
  http://127.0.0.1:8080/v1/models | \
  jq -e --arg model gpt-5.6-sol \
    "any(.data[]?; .id == \$model)" >/dev/null

cd /home/clawd/research/or-autoresearch-agent-r3i-dev/scion
exec env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent-r3i-dev/scion \
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp \
  SCION_MODEL=gpt-5.6-sol \
  SCION_REASONING_EFFORT=high \
  SCION_BASE_URL=http://127.0.0.1:8080 \
  SCION_API_KEY="$proxy_key_value" \
  SCION_LLM_TIMEOUT_SEC=180 \
  SCION_LLM_HYPOTHESIS_RESEARCH_TURN_TIMEOUT_SEC=180 \
  SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC=300 \
  SCION_LLM_CODE_RESEARCH_FINALIZE_TIMEOUT_SEC=300 \
  /home/clawd/miniconda3/envs/claw/bin/python -B -m scion.cli.main run \
    --problem /home/clawd/research/or-autoresearch-agent-r3i-dev/scion/scion/problems/cvrp/problem-v1.yaml \
    --research-input /home/clawd/research/or-autoresearch-agent-r3i-dev/scion/experiments/cvrp_history_matched_study/research_input.json \
    --research-history "$r3_history" \
    --research-history "$r3b_history" \
    --research-history "$r3c_history" \
    --research-history "$r3d_history" \
    --research-history "$r3e_history" \
    --research-history "$r3f_history" \
    --research-history "$r3g_history" \
    --research-history "$r3h_history" \
    --code-research-limits /home/clawd/research/or-autoresearch-agent-r3i-dev/scion/docs/experiments/v0.4/inputs/v04-cvrp-r3i-long-run-code-research-limits.json \
    --protocol /home/clawd/research/or-autoresearch-agent-r3i-dev/scion/scion/problems/cvrp/formal/protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent-r3i-dev/scion/scion/problems/cvrp/formal/split_manifest.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent-r3i-dev/scion/scion/problems/cvrp/formal/seed_ledger.yaml \
    --time-limit-sec 30 \
    --provider-call-cap 2000 \
    --provider-transient-retries 2 \
    --outer-hardwall-sec 1209600 \
    --rounds 40 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-r3i-normal-k1-sol-20260903-r1'

trap - EXIT
tmux display-message -p -t "${carrier_session}:run.0" \
  '#{session_name}\t#{pane_dead}\t#{pane_dead_status}\t#{pane_dead_signal}\t#{pane_pid}\t#{pane_current_command}'
```

Launch only after the exact tree's tests and static checks pass and both the
root and session are absent. Once launched, do not change its source or inputs.

Final prelaunch evidence: `2352` tests collected; `2351 passed, 1 skipped, 0
failed` in 467.79 seconds (469.59 seconds outer wall). The long-run focused set
passed `438` tests. Changed-file Ruff `E9,F,I`, `git diff --check`, JSON loading,
and launch-block shell syntax are green.
