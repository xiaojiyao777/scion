# CVRP R3h adaptive-history K1 preregistration

Date: 2026-09-02 UTC

Predecessor evidence:
[`v04-cvrp-r3g-adaptive-history-k1-sol-postrun-20260902.md`](v04-cvrp-r3g-adaptive-history-k1-sol-postrun-20260902.md)

## Status

**READY FOR ONE-SHOT BACKGROUND LAUNCH**

This document freezes prospective R3h inputs and the one-shot carrier command.
The provider-free launch gates are complete. The sole remaining launch-time
precondition is the local proxy/model check embedded before campaign-root
creation in the frozen block; failure leaves no campaign and authorizes no
second launch under this preregistration.

## Question

With R3g's completed evidence available but none of its executable or mutable
state restored, and with a slightly wider bounded provider-transient transport
boundary, can one fresh ordinary Scion campaign generate an exact CVRP
candidate that drains screening, stage-held-out validation and frozen testing
and earns deterministic promotion?

R3h starts from fresh repaired B0. It is not a resume, extension or retry of
R3g. It receives a fresh output root, B0 workspace, branch portfolio and
provider session. It loads no R3g candidate source, accepted workspace, status,
metric, SQLite state, trace response, provider session, branch process or tmux
state. A similar mechanism or patch must be independently selected and
generated through the ordinary H/C path.

R3g completed one safe but negative initial screen before a different new H
turn exhausted its one allowed transient redispatch on two provider 502
responses. The completed cyclic-exchange candidate returned
`SCREENING_FAIL_CASE_QUALITY`; the second turn exported no H. R3g is terminal
`valid_incomplete / execution_blocked_infra`, with champion v1 unchanged. R3h
does not reinterpret either fact.

## Frozen scientific disposition

- R3g's three-route cyclic exchange is one negative adaptive-development
  observation, not a host-selected next mechanism and not an executable R3h
  candidate.
- The R3g provider failure is infrastructure evidence, not scientific evidence
  against its source, history frontier or an unexported proposal.
- R3f's validation failure and all earlier negative directions retain their
  existing interpretations. No held-out result enters H/C.
- V3 cumulative-depth semantics remain authoritative. Every R3h result is
  reported against its exact live cumulative candidate; the host does not
  roll back accepted changes to manufacture isolated effects.
- Screening remains adaptive development, validation remains stage-held-out
  from H/C and prospective for each independently generated exact candidate,
  and frozen input remains unavailable until earned.
- A separate no-LLM retained-B0 population is still required after any
  promotion.

The only prospective runtime changes relative to R3g are the bounded
provider-transient redispatch/backoff boundary and explicit provider transport
ceilings below. Formal solver budgets, cases, seeds, splits, Protocol gates,
Decision mapping and promotion requirements do not change.

## Frozen history policy

Seven external H-only files are loaded in this exact order:

1. R3 `research_history.jsonl`: 21 complete ordinary records;
2. R3b `research_history.jsonl`: one complete ordinary record;
3. R3c `research_history.jsonl`: two complete typed records;
4. R3d `research_history.jsonl`: one complete ordinary record;
5. R3e `research_history.jsonl`: one complete ordinary record;
6. R3f `research_history.jsonl`: 22 complete ordinary records;
7. R3g `research_history.jsonl`: two complete typed records.

The required production-loader result is
`[21,1,2,1,1,22,2] = 50` ordered strict `cvrp` records. With the common eight
ordinary observations prepended by the proposal context, the external ranges
are:

- R3: `history-0009..0029`;
- R3b: `history-0030`;
- R3c: `history-0031..0032`;
- R3d: `history-0033`;
- R3e: `history-0034`;
- R3f: `history-0035..0056`;
- R3g: `history-0057..0058`.

R3g contributes exactly one evaluated screening row with a selected basis and
one null-H/null-basis `blocked_infra` row. It contributes no validation or
frozen result. The second row preserves the typed provider fact but supplies no
hypothesis, mechanism claim, Protocol result or Decision.

External history remains agent-optional. The host exposes the complete ordered
index but does not rank a reference, choose a mechanism, copy a patch or
require an external read. Mandatory used/rejected disposition applies only to
explicit failures at the latest ordinary live `current` and `sibling` relation
rounds, independently. Used evidence must be read and cited; rejected evidence
requires a bounded agent-authored reason.

Search, read, citation, selected-basis explanation and frontier disposition
remain separate facts. One adaptive R3h campaign cannot identify the causal
benefit of history.

## Scientific inputs and held-out interpretation

R3h is frozen to the clean detached worktree at
`/home/clawd/research/or-autoresearch-agent-r3h-dev/scion`, created from code
commit `44fff1356e253927e820fff88ad13ca701e87dbc`. Every repository-local path in
the launch block points to this same tree. The main worktree remains available
for later development and cannot mutate the live experiment subject.

The declared inputs are:

- fresh B0 problem package:
  `/home/clawd/research/or-autoresearch-agent-r3h-dev/scion/scion/problems/cvrp`;
- adapter: `scion/problems/cvrp/problem-v1.yaml`;
- Protocol: `scion/problems/cvrp/formal/protocol.yaml`;
- split: `scion/problems/cvrp/formal/split_manifest.yaml`;
- seeds: `scion/problems/cvrp/formal/seed_ledger.yaml`;
- research input:
  `experiments/cvrp_history_matched_study/research_input.json`;
- code-research limits:
  `docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json`;
- problem data root: `/home/clawd/research/or-autoresearch-agent/vrp`.

No R3g policy snapshot replaces R3h B0. The prompts, Protocol, split, seed
ledger, research input, code-research limits, statistical thresholds and
scheduler remain unchanged. The split still contains 12 screening, 12
validation and 12 frozen cases plus one canary. Formal readiness was
revalidated on the exact prospective tree; the prior R3g count was not
silently copied forward as a new result.

Existing activation falsifiers and public synthetic deadline checks remain
tainted development diagnostics outside Safe Features and Decision. Missing
activation evidence cannot reverse Protocol or promotion; it is reported as an
audit gap.

## Frozen provider boundary

Provider SDK retries remain zero. R3h sets
`--provider-transient-retries 2`. For one frozen request, `ProviderCaller` may
perform at most two redispatches, and only after `LLMTimeoutError`,
`LLMTransportError` or `LLMProviderError`. The maximum physical sequence is
therefore attempts `0,1,2`.

The ordinary code constants impose deterministic bounded backoff:

- 5 seconds before redispatch attempt 1;
- 20 seconds before redispatch attempt 2.

Backoff is not a new CLI field, resource identity, scientific gate or adaptive
policy. Rate limit/429, authentication, authorization, balance,
response-format, schema, response-size, generic and interruption failures are
not eligible. Every physical dispatch consumes the fixed 340-call cap
immediately before sending and receives one terminal trace. A redispatch stays
within the same H/C logical turn and contributes no retry fact to H, research
history, Protocol, Safe Features or Decision.

No exactly-once property is claimed. A timed-out request may remain in flight
upstream, but Scion never observes or uses a later response from it. The
boundary adds no request identity, owner, lease, issuance, registration,
signature, receipt, request hash or repeated finalization lifecycle. If all
three eligible dispatches fail, the existing typed invocation-terminal path
applies; R3h does not scheduler-forward into unbounded blocked branches.

R3d through R3g retain their historical configured retry counts and observed
attempt sequences. This prospective change does not rewrite their resource
artifacts, traces, outcomes or interpretations.

## Frozen runtime and resources

- model: `gpt-5.6-sol` through the local Codex proxy;
- reasoning effort: `high`;
- H candidate count: K=1;
- H maximum turns per attempt: eight;
- C research maximum turns per attempt: eight, plus one final decision;
- formal evaluated-stage horizon: 20;
- ordinary maximum active branches: three;
- physical provider dispatch cap: 340;
- provider SDK retries: zero;
- explicit Scion transient redispatches per frozen request: at most two;
- redispatch backoff constants: 5 seconds, then 20 seconds;
- default provider timeout: 180 seconds;
- H research-turn timeout: 180 seconds;
- C research-turn timeout: 300 seconds;
- C finalize timeout: 240 seconds;
- outer hardwall: 345600 seconds (96 hours);
- base subject time limit: 30 seconds, with the unchanged declared
  dimension-based overrides;
- output root:
  `/home/clawd/research/scion-experiments/v04-cvrp-r3h-normal-k1-sol-20260902-r1`.

The shared cap remains
`20 x (8 H + 8 C + 1 C-finalize) = 340`; redispatches do not enlarge it. A
redispatch consumes the fixed allowance and may censor the evaluated-stage
horizon earlier. Research rejections consume provider dispatches but not the
formal evaluated-stage horizon. Exact candidates progress only through new
live R3h branch state; no history summary reconstructs one.

The timeout values are provider transport ceilings, not scientific solver
budgets or hidden research-quality gates. All formal solver time limits,
Protocol expansion budgets and statistical thresholds remain unchanged.

## Carrier boundary

R3h uses exactly one local tmux session named
`scion-r3h-normal-k1-sol-20260902-r1`. As in R3g, the wrapper creates one
detached lazy `sleep infinity` pane, sets window-local `remain-on-exit on`, and
replaces that pane exactly once with the foreground Scion command. The lazy
process is gone before any proxy, provider, solver or campaign action. The pane
command ends in `exec env`, so Python is the pane's foreground process.

If wrapper setup fails before successful respawn, its trap removes only the new
empty carrier. Once respawn succeeds, the wrapper clears that trap. Any later
in-pane precondition or proxy failure leaves one dead pane for read-only
inspection and does not authorize a second respawn under this preregistration.

`remain-on-exit` retains only operational exit information. tmux is not a
scientific authority, service, deployment, distribution, scheduler,
installation or build. It adds no PID registry, object identity, owner, lease,
issuance, registration, signature, receipt, hash or repeated closure. Only the
ordinary durable campaign artifacts establish result validity.

## Launch gate

Launch is authorized only while every item below remains true on the exact
prospective tree:

1. the R3g postrun classification and two-row history boundary are frozen;
2. the provider retry/backoff implementation and timeout wiring pass focused
   unit and CLI tests;
3. the complete history/frontier/selected-basis path passes focused tests;
4. the full provider-free, non-campaign regression completes with zero
   failures;
5. focused Ruff `E9,F,I` and `git diff --check` pass;
6. the seven history files load through the production loader as
   `[21,1,2,1,1,22,2] = 50` ordered strict `cvrp` records;
7. R3g history contains exactly one screening row and one null-H
   proposal-infrastructure row, with no validation/frozen row;
8. all declared formal cases and required files resolve under the data root;
9. the claw Python environment imports the declared runtime dependencies;
10. tmux is available and the exact R3h session name is absent;
11. the fresh R3h output root is absent;
12. the frozen wrapper below is shell-syntax valid and every repository-local
    path points to the main prospective tree;
13. one local proxy/model check confirms `gpt-5.6-sol` without printing the
    key, inside the respawned pane and before campaign root creation.

Items 1-12 are provider-free and complete. Exact evidence: the full suite
collected 2302 items and completed `2301 passed, 1 skipped, 0 failed` in
475.77 seconds (478.81 seconds outer wall); the declared skip is
`scion/tests/test_sprint_n1.py:41` (`canary instance not available`). Focused
provider/resource/LLM/signal suites passed, focused Ruff `E9,F,I` and
`git diff --check` passed, the production loader returned
`[21,1,2,1,1,22,2] = 50` strict ordered `cvrp` records, and formal readiness
returned 37 cases / 73 required files with no missing or unsafe input. The
detached worktree is clean at the frozen code commit; the fresh root and exact
tmux session are absent; the wrapper is shell-syntax valid. Item 13 is the sole
local network precondition and runs only inside the one-shot block.

## Frozen launch block

The following block may run once from
`/home/clawd/research/or-autoresearch-agent-r3h-dev/scion`. Its proxy/model
check occurs before campaign-root creation.

```bash
set -Eeuo pipefail

carrier_session='scion-r3h-normal-k1-sol-20260902-r1'
carrier_workdir='/home/clawd/research/or-autoresearch-agent-r3h-dev/scion'
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

test ! -e /home/clawd/research/scion-experiments/v04-cvrp-r3h-normal-k1-sol-20260902-r1
test -x /home/clawd/miniconda3/envs/claw/bin/python
test -f "$r3_history"
test -f "$r3b_history"
test -f "$r3c_history"
test -f "$r3d_history"
test -f "$r3e_history"
test -f "$r3f_history"
test -f "$r3g_history"
test "$(wc -l < "$r3_history")" -eq 21
test "$(wc -l < "$r3b_history")" -eq 1
test "$(wc -l < "$r3c_history")" -eq 2
test "$(wc -l < "$r3d_history")" -eq 1
test "$(wc -l < "$r3e_history")" -eq 1
test "$(wc -l < "$r3f_history")" -eq 22
test "$(wc -l < "$r3g_history")" -eq 2

proxy_key_value=$(curl -fsS --connect-timeout 5 --max-time 15 \
  http://127.0.0.1:8080/auth/status | \
  jq -er ".proxy_api_key | select(type == \"string\" and length > 0)")

curl -fsS --connect-timeout 5 --max-time 15 \
  -H "Authorization: Bearer $proxy_key_value" \
  http://127.0.0.1:8080/v1/models | \
  jq -e --arg model gpt-5.6-sol \
    "any(.data[]?; .id == \$model)" >/dev/null

cd /home/clawd/research/or-autoresearch-agent-r3h-dev/scion
exec env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent-r3h-dev/scion \
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp \
  SCION_MODEL=gpt-5.6-sol \
  SCION_REASONING_EFFORT=high \
  SCION_BASE_URL=http://127.0.0.1:8080 \
  SCION_API_KEY="$proxy_key_value" \
  SCION_LLM_TIMEOUT_SEC=180 \
  SCION_LLM_HYPOTHESIS_RESEARCH_TURN_TIMEOUT_SEC=180 \
  SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC=300 \
  SCION_LLM_CODE_RESEARCH_FINALIZE_TIMEOUT_SEC=240 \
  /home/clawd/miniconda3/envs/claw/bin/python -B -m scion.cli.main run \
    --problem /home/clawd/research/or-autoresearch-agent-r3h-dev/scion/scion/problems/cvrp/problem-v1.yaml \
    --research-input /home/clawd/research/or-autoresearch-agent-r3h-dev/scion/experiments/cvrp_history_matched_study/research_input.json \
    --research-history "$r3_history" \
    --research-history "$r3b_history" \
    --research-history "$r3c_history" \
    --research-history "$r3d_history" \
    --research-history "$r3e_history" \
    --research-history "$r3f_history" \
    --research-history "$r3g_history" \
    --code-research-limits /home/clawd/research/or-autoresearch-agent-r3h-dev/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json \
    --protocol /home/clawd/research/or-autoresearch-agent-r3h-dev/scion/scion/problems/cvrp/formal/protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent-r3h-dev/scion/scion/problems/cvrp/formal/split_manifest.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent-r3h-dev/scion/scion/problems/cvrp/formal/seed_ledger.yaml \
    --time-limit-sec 30 \
    --provider-call-cap 340 \
    --provider-transient-retries 2 \
    --outer-hardwall-sec 345600 \
    --rounds 20 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-r3h-normal-k1-sol-20260902-r1'

trap - EXIT
printf 'TMUX_SESSION=%s\n' "$carrier_session"
tmux display-message -p -t "${carrier_session}:run.0" \
  '#{session_name}\t#{pane_dead}\t#{pane_dead_status}\t#{pane_dead_signal}\t#{pane_pid}\t#{pane_current_command}\t#{socket_path}'
```

After a separately authorized launch, read-only monitoring may use:

```bash
carrier_session='scion-r3h-normal-k1-sol-20260902-r1'
tmux has-session -t "$carrier_session"
tmux display-message -p -t "${carrier_session}:run.0" \
  '#{pane_dead}\t#{pane_dead_status}\t#{pane_dead_signal}\t#{pane_pid}\t#{pane_current_command}'
tmux capture-pane -p -t "${carrier_session}:run.0" -S -200
```

Running state is `pane_dead=0`. A dead pane retains operational exit
information but does not establish campaign validity. Only after Python is dead
and ordinary terminal artifacts have been inspected may the dead carrier be
removed. A later user-requested graceful stop must send exactly one `C-c` to
`scion-r3h-normal-k1-sol-20260902-r1:run.0` and wait for typed finalization;
`kill-session` is never a graceful stop for a live campaign.

## Outcome classification

- `PROMOTION_OBSERVED_RETAINED_PENDING`
- `PROMOTION_WITH_ACTIVATION_AUDIT_GAP`
- `VALID_20_STAGE_HORIZON_CENSORED`
- `VALID_20_STAGE_NO_PROMOTION`
- `PROVIDER_CAP_CENSORED`
- `OUTER_HARDWALL_EXCEEDED`
- `RUN_INVALID_INFRA`
- `INTERRUPTED`

Candidate-attributable timeout, invalid output, infeasibility or fleet
regression in a finalized Protocol result remains negative algorithm evidence,
not root infrastructure. A positive screen is not promotion, an uncompleted
expansion is not a pass, and postrun analysis cannot override Decision.
Retained-B0 remains unauthorized before promotion.
