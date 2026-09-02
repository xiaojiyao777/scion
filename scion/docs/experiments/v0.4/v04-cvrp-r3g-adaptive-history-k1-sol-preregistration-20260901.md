# CVRP R3g adaptive-history K1 preregistration

Date: 2026-09-01 UTC

Predecessor evidence:
[`v04-cvrp-r3f-adaptive-history-k1-sol-postrun-20260901.md`](v04-cvrp-r3f-adaptive-history-k1-sol-postrun-20260901.md)

## Question

After repairing the candidate-side destroy/repair deadline boundary, preserving
ordinary proposal before-source evidence across exact-stage cleanup, and
clearing stale operational progress fields, can one fresh ordinary Scion
campaign generate an exact CVRP candidate that completes screening,
stage-held-out validation and frozen testing and earns deterministic
promotion?

R3g is a new experiment from the repaired launch tree and its fresh B0. It is
not a resume, extension, retry or fixed-candidate replay of R3f. It receives a
fresh output root, B0 workspace, branch state and provider session. It loads no
R3f candidate source, candidate workspace, SQLite state, status, metric,
provider response, branch process or tmux state. A similar proposal must be
independently selected and generated through the ordinary H/C path.

R3f finished validly at its 20-stage horizon with champion v1 unchanged. Its
one stage-held-out validation reached a finalized Decision but contained two
candidate-only timeouts, so Protocol abandoned the candidate for
`INCOMPLETE_EVIDENCE` and `CANDIDATE_RUNTIME_FAILURE`. Its final
exact-relocate candidate completed only an initial screen and requested an
expansion after the twentieth evaluated stage. R3g neither replays the failed
validation candidate nor resumes the horizon-censored candidate.

## Frozen scientific disposition

R3f narrows, but does not close, the proposal frontier:

- adaptive embedded-VNS scheduling is a strong negative and receives no
  host-directed further investment;
- the pre-polish tournament reached validation but failed runtime completeness,
  and the later initial-VNS budget direction did not justify another
  host-directed rung;
- exact inter-route evaluation remains potentially useful, but all observations
  are cumulative-candidate, association-only evidence and some are confounded
  by the old deadline boundary;
- the final exact-relocate initial screen is horizon-censored, not a pass or an
  executable candidate for R3g.

V3 cumulative-depth semantics remain authoritative. Accepted branch changes
are not rolled back to manufacture isolated current-step estimates. Every R3g
result is reported against its exact cumulative candidate and any mechanism
interpretation remains association-only. The host neither selects a mechanism
nor reconstructs a patch from these conclusions.

## Combined pre-R3g corrections

The launch tree contains three bounded corrections. They apply prospectively
to R3g and do not rewrite any R3f artifact or Decision.

### Candidate-side deadline safety

Every CVRP destroy and repair operator now receives the existing monotonic
runtime context and exit reserve explicitly and polls it inside its nested
customer, route and insertion-position loops. Reaching the reserve raises one
typed internal `_OperatorDeadlineExpired`. The scheduler records
`deadline_exhausted`, discards the partially mutated local candidate and exits
the ALNS loop before the reserved return boundary.

This directly addresses unbounded late work of the kind observed in R3f's two
`X-n401-k29` candidate timeouts. It does not convert those failures into
infrastructure, revise the R3f validation result or guarantee that an R3g
candidate cannot fail at runtime. The repaired behavior is part of both sides'
fresh R3g B0 execution boundary.

### Ordinary proposal evidence continuity

The plain source observed immediately before each accepted current-step file
change is captured at ordinary candidate materialization and passed with that
patch into evaluation. Proposal-subject construction enforces normalized exact
paths, declared before-source types, a one-to-one patch/source mapping and the
existing size bounds. An exact candidate's expanded evaluation can therefore
use the already captured before/after subject even after its transient
candidate workspace is cleaned up.

This fixes stale-workspace and `unavailable_current_source` evidence loss. It
does not expose validation or frozen results to H, Safe Features or Decision,
does not select a mechanism, and adds no object identity, lease, issuance,
registration, signature, receipt, request hash or repeated closure.

### Operational status reset

Each new Protocol stage writes `phase=<stage>_protocol`, `complete=false` and
clears prior child PID, child phase, child exit code and child elapsed time.
Each new subprocess launch also clears a prior child's exit and elapsed fields.
This prevents stale canary completion or an earlier child exit from appearing
as the current stage's operational status. It changes no metric, Protocol
feature, scientific Decision or terminal classification.

## Frozen history policy

Six external H-only files are loaded in this exact order:

1. R3 `research_history.jsonl`: 21 complete ordinary records;
2. R3b `research_history.jsonl`: one complete ordinary record;
3. R3c `research_history.jsonl`: two complete typed records;
4. R3d `research_history.jsonl`: one complete ordinary record;
5. R3e `research_history.jsonl`: one complete ordinary record;
6. R3f `research_history.jsonl`: 22 complete ordinary records.

The production loader accepts `[21,1,2,1,1,22] = 48` ordered strict `cvrp`
records, totalling 1,575,667 bytes. The common research input contains eight
ordinary prior observations, so the external ranges are:

- R3: `history-0009..0029`;
- R3b: `history-0030`;
- R3c: `history-0031..0032`;
- R3d: `history-0033`;
- R3e: `history-0034`;
- R3f: `history-0035..0056`.

R3f contributes 19 evaluated screening rows and three research-rejected rows.
It contributes no validation or frozen row. In particular, the held-out
validation timeouts and aggregate result are absent, while the final
exact-relocate initial screen is present only as an ordinary completed
screening record. That row cannot reconstruct source or branch state.

External history remains agent-optional. The host exposes the complete ordered
index but does not rank a reference, choose a mechanism, copy a patch or
require an external read. Mandatory used/rejected disposition applies only to
explicit failures at the latest ordinary live `current` and `sibling` relation
rounds, independently. Used evidence must be read and cited; rejected evidence
requires a bounded agent-authored reason.

Search, read, citation, selected-basis explanation and frontier disposition
remain separate facts. This single adaptive campaign cannot identify the
causal benefit of history.

## Scientific inputs and held-out interpretation

R3g runs the exact repaired isolated tree at
`/home/clawd/research/or-autoresearch-agent-r3g-dev/scion`. All repository-local
paths in the frozen command point to that same tree; none points to the older
main worktree.

The declared inputs are:

- fresh B0 problem package:
  `/home/clawd/research/or-autoresearch-agent-r3g-dev/scion/scion/problems/cvrp`;
- adapter: `scion/problems/cvrp/problem-v1.yaml`;
- Protocol: `scion/problems/cvrp/formal/protocol.yaml`;
- split: `scion/problems/cvrp/formal/split_manifest.yaml`;
- seeds: `scion/problems/cvrp/formal/seed_ledger.yaml`;
- research input:
  `experiments/cvrp_history_matched_study/research_input.json`;
- code-research limits:
  `docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json`;
- problem data root: `/home/clawd/research/or-autoresearch-agent/vrp`.

No R3f policy snapshot replaces R3g B0. Apart from the three prospective
corrections above, the prompts, Protocol, split, seed ledger, research input,
code-research limits, thresholds and scheduling remain unchanged. The split
still contains 12 screening, 12 validation and 12 frozen cases plus one
canary; the formal-data check resolves all 37 declared cases and 73 required
files with zero missing or unsafe inputs.

Screening remains the outcome-known adaptive development population.
Validation is stage-held-out from H/C and is prospective for each independently
generated exact R3g candidate, but it is not described as a globally
never-observed population: R3f already produced a validation result and its
candidate timeouts motivated the generic deadline correction. That prior
validation result remains absent from H, branch scheduling, Safe Features and
Decision. Frozen input remains unavailable until an exact R3g candidate earns
it. A separately frozen no-LLM retained-B0 population remains required after
promotion.

Existing activation falsifiers and public synthetic deadline checks are
tainted development diagnostics outside Safe Features and Decision. Missing
activation evidence cannot reverse Protocol or promotion; it is reported as
an audit gap.

## Frozen provider boundary

Provider SDK retries remain zero. R3g sets
`--provider-transient-retries 1`. `ProviderCaller` may redispatch the same
frozen request once, and only once, when the first dispatch raises
`LLMTimeoutError`, `LLMTransportError` or `LLMProviderError`.

Rate limit/429, authentication, authorization, balance, response-format,
schema, response-size, generic and interruption failures are not eligible.
Every physical dispatch consumes the fixed 340-call cap immediately before it
is sent and receives one terminal trace. A redispatch remains within the same
H/C logical turn and contributes no retry fact to H, research history,
Protocol or Decision.

No exactly-once property is claimed. A timed-out first request may remain in
flight upstream, but Scion never observes or uses a later response from it.
This boundary introduces no request identity, lease, issuance, registration,
signature, receipt, request hash or repeated finalization lifecycle.

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
- explicit Scion transient redispatches per frozen request: one;
- outer hardwall: 345600 seconds (96 hours);
- base subject time limit: 30 seconds, with the unchanged declared
  dimension-based overrides;
- output root:
  `/home/clawd/research/scion-experiments/v04-cvrp-r3g-normal-k1-sol-20260901-r1`.

The cap remains `20 x (8 H + 8 C + 1 C-finalize) = 340`. A transient
redispatch consumes the fixed allowance and may censor the logical horizon
earlier. Research rejections consume provider dispatches but not the evaluated
stage horizon. Exact candidates move only through new live branch state; no
history summary reconstructs one.

## Carrier boundary

R3g uses exactly one local tmux session named
`scion-r3g-normal-k1-sol-20260901-r1`. The wrapper creates one detached lazy
`sleep infinity` pane, sets window-local `remain-on-exit on`, and replaces that
pane exactly once with the foreground Scion command. The lazy process is gone
before any proxy, provider, solver or campaign action. The pane command ends in
`exec env`, so Python is the pane's foreground process.

If wrapper setup fails before successful respawn, its trap removes only the
new empty carrier. Once respawn succeeds, the wrapper clears that trap. Any
later in-pane precondition or proxy failure leaves one dead pane for read-only
inspection and does not authorize a second respawn under this preregistration.

`remain-on-exit` retains only operational exit information. tmux is not a
scientific authority, service, deployment, distribution, scheduler,
installation or build. It adds no PID registry, object identity, owner, lease,
issuance, registration, signature, receipt, hash or repeated closure. Only the
ordinary durable campaign artifacts establish result validity.

## Launch gate and current status

Launch is authorized only after all of the following are true on the exact
combined tree:

1. the R3f postrun classification and 22-row H-only history are frozen;
2. the full provider-free, non-campaign regression passes after all three
   combined corrections, and its exact collected/passed/skipped/failed counts
   are recorded here before launch;
3. focused deadline, exact-stage proposal-evidence, stage-progress,
   subprocess-progress, provider, history and CLI finalization tests pass;
4. the six history files load as `[21,1,2,1,1,22] = 48` ordered strict `cvrp`
   records in R3 through R3f order;
5. R3f history contains 22 rows and no validation/frozen row;
6. all 37 declared cases and 73 required files resolve under the data root;
7. the claw Python environment imports the declared runtime dependencies;
8. tmux is available and the exact R3g session name is absent;
9. the fresh R3g output root is absent;
10. the frozen wrapper below is shell-syntax valid and every repository-local
    path points to the isolated R3g launch tree;
11. one local proxy/model check confirms `gpt-5.6-sol` without printing the
    key, inside the respawned pane and before campaign root creation.

Items 1 and 3-10 are provider-free. Item 11 is the sole local network
precondition and is performed only inside a later authorized launch.

At preregistration time, the production loader reads exactly 48 records with
file counts `[21,1,2,1,1,22]`; formal readiness is 37 cases and 73 files; the
declared R3g root and tmux session are absent. The launch block is syntax-valid
and its paths are frozen to the isolated tree. The final full combined-tree
provider-free, non-campaign regression collected `2299` tests and completed
`2298 passed, 1 skipped, 0 failed` in 432.87 seconds. Ruff `E9,F,I` over the 18
changed Python files, with only the exact existing `F403/F405` ignores, and
`git diff --check` both pass. The temporary regression data symlink was removed
and no pytest or solver process remains. All static launch gates are green;
R3g status is **READY**. The sole remaining dynamic proxy/model check is item
11 inside the already frozen one-shot command.

## Frozen launch

After every launch gate is green, run the following block once from
`/home/clawd/research/or-autoresearch-agent-r3g-dev/scion`. This document does
not itself launch the proxy, provider, solver, tmux carrier or campaign.

```bash
set -Eeuo pipefail

carrier_session='scion-r3g-normal-k1-sol-20260901-r1'
carrier_workdir='/home/clawd/research/or-autoresearch-agent-r3g-dev/scion'
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

test ! -e /home/clawd/research/scion-experiments/v04-cvrp-r3g-normal-k1-sol-20260901-r1
test -x /home/clawd/miniconda3/envs/claw/bin/python
test -f "$r3_history"
test -f "$r3b_history"
test -f "$r3c_history"
test -f "$r3d_history"
test -f "$r3e_history"
test -f "$r3f_history"
test "$(wc -l < "$r3_history")" -eq 21
test "$(wc -l < "$r3b_history")" -eq 1
test "$(wc -l < "$r3c_history")" -eq 2
test "$(wc -l < "$r3d_history")" -eq 1
test "$(wc -l < "$r3e_history")" -eq 1
test "$(wc -l < "$r3f_history")" -eq 22

proxy_key_value=$(curl -fsS --connect-timeout 5 --max-time 15 \
  http://127.0.0.1:8080/auth/status | \
  jq -er ".proxy_api_key | select(type == \"string\" and length > 0)")

curl -fsS --connect-timeout 5 --max-time 15 \
  -H "Authorization: Bearer $proxy_key_value" \
  http://127.0.0.1:8080/v1/models | \
  jq -e --arg model gpt-5.6-sol \
    "any(.data[]?; .id == \$model)" >/dev/null

cd /home/clawd/research/or-autoresearch-agent-r3g-dev/scion
exec env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent-r3g-dev/scion \
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp \
  SCION_MODEL=gpt-5.6-sol \
  SCION_REASONING_EFFORT=high \
  SCION_BASE_URL=http://127.0.0.1:8080 \
  SCION_API_KEY="$proxy_key_value" \
  SCION_LLM_TIMEOUT_SEC=120 \
  SCION_LLM_HYPOTHESIS_RESEARCH_TURN_TIMEOUT_SEC=120 \
  SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC=240 \
  SCION_LLM_CODE_RESEARCH_FINALIZE_TIMEOUT_SEC=240 \
  /home/clawd/miniconda3/envs/claw/bin/python -B -m scion.cli.main run \
    --problem /home/clawd/research/or-autoresearch-agent-r3g-dev/scion/scion/problems/cvrp/problem-v1.yaml \
    --research-input /home/clawd/research/or-autoresearch-agent-r3g-dev/scion/experiments/cvrp_history_matched_study/research_input.json \
    --research-history "$r3_history" \
    --research-history "$r3b_history" \
    --research-history "$r3c_history" \
    --research-history "$r3d_history" \
    --research-history "$r3e_history" \
    --research-history "$r3f_history" \
    --code-research-limits /home/clawd/research/or-autoresearch-agent-r3g-dev/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json \
    --protocol /home/clawd/research/or-autoresearch-agent-r3g-dev/scion/scion/problems/cvrp/formal/protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent-r3g-dev/scion/scion/problems/cvrp/formal/split_manifest.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent-r3g-dev/scion/scion/problems/cvrp/formal/seed_ledger.yaml \
    --time-limit-sec 30 \
    --provider-call-cap 340 \
    --provider-transient-retries 1 \
    --outer-hardwall-sec 345600 \
    --rounds 20 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-r3g-normal-k1-sol-20260901-r1'

trap - EXIT
printf 'TMUX_SESSION=%s\n' "$carrier_session"
tmux display-message -p -t "${carrier_session}:run.0" \
  '#{session_name}\t#{pane_dead}\t#{pane_dead_status}\t#{pane_dead_signal}\t#{pane_pid}\t#{pane_current_command}\t#{socket_path}'
```

After that block returns, a separate read-only observation may run:

```bash
carrier_session='scion-r3g-normal-k1-sol-20260901-r1'
tmux has-session -t "$carrier_session"
tmux display-message -p -t "${carrier_session}:run.0" \
  '#{pane_dead}\t#{pane_dead_status}\t#{pane_dead_signal}\t#{pane_pid}\t#{pane_current_command}'
tmux capture-pane -p -t "${carrier_session}:run.0" -S -200
```

Running state is `pane_dead=0`. A dead pane retains an operational exit status
or signal but does not establish campaign validity. Only after Python is dead
and ordinary terminal artifacts have been inspected may the dead carrier be
removed with:

```bash
tmux kill-session -t scion-r3g-normal-k1-sol-20260901-r1
```

If a later user-requested graceful stop is necessary, send exactly one `C-c`
to `scion-r3g-normal-k1-sol-20260901-r1:run.0` and wait for Python's typed
finalization. `kill-session` is not a graceful stop and is never used against a
live campaign during ordinary monitoring.

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
not root-level infrastructure. A positive screen is not promotion, a
horizon-censored expansion request is not a pass, and postrun analysis cannot
override Decision. Retained-B0 remains unauthorized before promotion.
