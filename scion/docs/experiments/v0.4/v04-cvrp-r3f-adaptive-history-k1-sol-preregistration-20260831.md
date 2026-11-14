# CVRP R3f adaptive-history K1 preregistration

Date: 2026-08-31 UTC

## Question

After replacing the tool-owned process lifetime with one verified local tmux
carrier, can a fresh ordinary Scion campaign start from CVRP B0, voluntarily
use the complete R3 through R3e ordinary histories, and produce an exact
candidate that drains screening, validation and frozen testing into
deterministic promotion?

R3f is a new experiment after an operational carrier correction. It is not a
resume, retry, extension or fixed-candidate replay of R3e. It receives a fresh
output root, B0 workspace, branch state and provider session. It loads no R3e
candidate source, workspace, SQLite file, status file, metric file, process
state, provider response or expanded counter. A similar proposal must be
independently selected and generated in R3f.

The interrupted R3e root remains untouched. Its classification and usable
evidence are frozen in the
[`R3e interruption report`](v04-cvrp-r3e-adaptive-history-k1-sol-interruption-20260831.md).

## Frozen history policy

Five external H-only files are loaded in this exact order:

1. R3 `research_history.jsonl`: 21 complete ordinary records;
2. R3b `research_history.jsonl`: one complete initial-screen record;
3. R3c `research_history.jsonl`: two complete typed records, one evaluated
   initial screen followed by one proposal-hypothesis infrastructure block;
4. R3d `research_history.jsonl`: one complete evaluated initial-screen record;
5. R3e `research_history.jsonl`: one complete evaluated initial-screen record.

The production loader accepts the concatenation as exactly 26 ordered strict
`cvrp` records (`21 + 1 + 2 + 1 + 1`). The common research input contains
eight ordinary prior observations, so the external ranges are:

- R3: `history-0009..0029`;
- R3b: `history-0030`;
- R3c: `history-0031..0032`;
- R3d: `history-0033`;
- R3e: `history-0034`.

R3e's history file contains only its completed `32/32` initial screen with
`EVALUATION_COMPLETED` and Decision `expand_screening`. It was written before
the later expanded-screen heartbeats. The unfinalized `59` attempted and `58`
completed/valid of `96` planned expansion is absent from that file and is
excluded from R3f. No host-authored interruption row is added.

External history remains agent-optional. The host exposes the complete ordered
index but does not rank a reference, select a mechanism, copy a patch or
require an external read. Mandatory used/rejected disposition applies only to
explicit failures at the latest ordinary live `current` and `sibling` relation
rounds, independently. Used evidence must be read and cited; rejected evidence
needs a bounded agent-authored reason.

Search, read, citation, selected-basis explanation and frontier disposition are
reported separately. Uptake requires an actual read and citation. This single
adaptive campaign cannot identify the causal benefit of history.

## Scientific inputs and interpretation

The formal problem and science inputs are unchanged from R3e:

- B0 problem package:
  `/home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp`;
- adapter: `scion/problems/cvrp/problem-v1.yaml`;
- Protocol: `scion/problems/cvrp/formal/protocol.yaml`;
- split: `scion/problems/cvrp/formal/split_manifest.yaml`;
- seeds: `scion/problems/cvrp/formal/seed_ledger.yaml`;
- research input:
  `experiments/cvrp_history_matched_study/research_input.json`;
- code-research limits:
  `docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json`;
- problem data root: `/home/clawd/research/or-autoresearch-agent/vrp`.

No B0 policy file is replaced by an earlier candidate. The tmux correction
does not alter the CVRP algorithm, prompts, Protocol, split, seed ledger,
research input, code-research limits, thresholds or scheduling. In particular,
neither R3e's completed initial result nor its partial expanded counters are
used to choose a host mechanism, replay the beam candidate, change a case or
seed, or relax a gate.

The split remains 12 screening, 12 validation and 12 frozen cases plus one
canary. The production formal-data check resolves all 37 declared cases and 73
required files under the data root, with zero missing cases, missing companion
solutions or unsafe files. Screening remains the outcome-known adaptive
development population used by R3 through R3e; it is not independent
generalization evidence. Validation and frozen inputs remain prospective for
an exact R3f candidate. Retained-B0 evaluation remains blocked until
promotion.

Existing activation falsifiers and public synthetic deadline checks remain
tainted development diagnostics outside Safe Features and Decision. Missing
activation evidence cannot reverse Protocol or promotion; it is reported as an
audit gap.

## Frozen provider boundary

Provider SDK retries remain zero. R3f explicitly sets
`--provider-transient-retries 1`. ProviderCaller may redispatch the same frozen
request once, and only once, when the first dispatch raises
`LLMTimeoutError`, `LLMTransportError` or `LLMProviderError`.

Rate limit/429, authentication, authorization, balance, response-format,
schema, response-size, generic and interruption failures are not eligible.
Every physical dispatch consumes the unchanged 340-call cap immediately before
it is sent and receives one terminal trace. A redispatch remains within the
same H/C logical turn and contributes no retry fact to H, research history,
Protocol or Decision.

If the cap cannot admit the second dispatch, the existing resource-exhausted
outcome applies. If the second eligible dispatch also fails, the existing
blocked-infrastructure outcome applies. A returned response that fails format
or schema validation is terminal and is not redispatched.

No exactly-once property is claimed. A timed-out first request may remain in
flight upstream, but Scion never observes or uses a later response from it.
This boundary introduces no request identity, lease, issuance, registration,
signature, receipt, request hash or repeated finalization lifecycle.

## Terminal-finalization and carrier boundary

The CLI keeps its SIGTERM, SIGINT and SIGHUP handlers installed through
`finalize_requested_stop`. Repeated handler re-entry is suppressed, so a second
handled signal cannot restore default behavior before the first typed stop is
durable. This does not make `SIGKILL` catchable and does not protect against
machine or user-manager loss.

R3e proved that an ordinary non-TTY unified-exec call is not a stable owner for
a multi-hour campaign: the carrier returned `failed/-1` after `7704.372878714`
seconds and the process tree disappeared without typed finalization. The R3
non-TTY success after `77359.3004` seconds was a precedent, not a guarantee.

R3f therefore uses exactly one local tmux session named
`scion-r3f-normal-k1-sol-20260831-r1`. A provider/solver-free probe verified the
following sequence across independent unified-exec calls:

1. create one detached session with a lazy `sleep infinity` pane;
2. set window-local `remain-on-exit on`;
3. replace the lazy pane once with `respawn-pane -k` and one foreground command;
4. observe that the tmux server is reparented to PID 1 and the session remains
   live after its creating tool call exits;
5. observe exit status or terminal signal in the dead pane without treating it
   as scientific evidence.

The lazy command is replaced before any proxy, provider, solver or campaign
action. It is not a keeper after launch. The final pane command ends in
`exec env`, so the pane foreground process is Scion Python rather than a shell
child. `remain-on-exit` retains only a dead pane for one operational exit
inspection; it grants no authority and never enters H, Protocol, Safe Features
or Decision.

This one local carrier is not a service, deployment, distribution, scheduler,
package, installation or build. It adds no PID registry, Scion object identity,
owner, lease, issuance, registration, signature, receipt, manifest closure or
hash lifecycle. Scientific and terminal truth remains exclusively in ordinary
durable campaign artifacts. The pane, capture output, tmux session, tool result
and exit status cannot authorize promotion, relaunch, backfill or
interpretation.

## Frozen runtime and resources

- model: `gpt-5.6-sol` through the local Codex proxy;
- reasoning effort: `high`;
- H candidate count: K=1;
- H maximum turns per attempt: eight;
- C research maximum turns per attempt: eight, plus one final decision;
- formal evaluated-stage horizon: 20;
- ordinary maximum active branches: three;
- physical provider dispatch cap: 340;
- outer hardwall: 345600 seconds (96 hours);
- provider SDK retries: zero;
- explicit Scion transient redispatches per frozen request: one;
- output root:
  `/home/clawd/research/scion-experiments/v04-cvrp-r3f-normal-k1-sol-20260831-r1`.

The cap remains `20 x (8 H + 8 C + 1 C-finalize) = 340`. A transient
redispatch consumes that fixed allowance and can therefore censor the logical
horizon earlier. Research rejections also consume provider dispatches but not
the evaluated-stage horizon. Exact candidates move only through new live
branch state; no history summary reconstructs one.

## Launch gate and current status

Launch is authorized only after all of the following are true:

1. the R3e root is classified and frozen without retrospective terminalization
   or partial-result projection;
2. the full provider-free, non-campaign regression passes on the exact launch
   tree after the signal/provider repairs;
3. focused CLI signal/finalization, ResourceEnvelope, ProviderCaller,
   transport, history and CVRP formal-readiness tests pass;
4. the five history files load as exactly 26 ordered strict `cvrp` records in
   R3, R3b, R3c, R3d, R3e order;
5. the R3e file contains exactly one complete initial-screen row and no partial
   expanded result;
6. all 37 declared split cases and all 73 required files resolve under the
   frozen data root;
7. the claw Python environment imports the declared runtime dependencies;
8. tmux 3.4 is available, the provider/solver-free carrier probe passes, and
   the exact R3f session name is absent;
9. the fresh R3f output root is absent;
10. the one-shot wrapper below is frozen, shell-syntax valid and uses the exact
    session, window and pane targets;
11. one local proxy/model check confirms `gpt-5.6-sol` without printing the
    key, inside the respawned pane and before root creation.

The production history loader currently observes exactly 26 records with file
counts `[21,1,2,1,1]` and total input size 787897 bytes. Formal-data readiness
is green at 37 cases and 73 required files with zero missing or unsafe files.
The declared R3f root is absent, tmux 3.4 is installed, and the dummy carrier
probe left no session or file behind. The fresh exact-tree provider-free,
non-campaign regression collected `2296` tests and completed `2295 passed, 1
skipped, 0 failed` in 437.80 seconds (438.83 seconds outer elapsed). Focused
Ruff `E9,F,I` and the full-tree `git diff --check` pass. This is a fresh R3f
gate result rather than an inferred reuse of the earlier R3e run.

Items 1-10 are provider-free. Item 11 is the only local network precondition
and runs once inside the exact pane command. If any precondition or proxy gate
fails, the pane remains dead with operational exit evidence, no campaign is
inferred, and this one-shot preregistration does not authorize a second
`respawn-pane`.

## Frozen launch

Run the following block once from
`/home/clawd/research/or-autoresearch-agent/scion`. The wrapper creates only the
named local tmux carrier; the campaign itself remains the single foreground
process in its pane.

```bash
set -Eeuo pipefail

carrier_session='scion-r3f-normal-k1-sol-20260831-r1'
carrier_workdir='/home/clawd/research/or-autoresearch-agent/scion'
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

test ! -e /home/clawd/research/scion-experiments/v04-cvrp-r3f-normal-k1-sol-20260831-r1
test -f /home/clawd/research/scion-experiments/v04-cvrp-r3-normal-k1-sol-20260828-r1/research_history.jsonl
test -f /home/clawd/research/scion-experiments/v04-cvrp-r3b-normal-k1-sol-20260829-r1/research_history.jsonl
test -f /home/clawd/research/scion-experiments/v04-cvrp-r3c-normal-k1-sol-20260830-r1/research_history.jsonl
test -f /home/clawd/research/scion-experiments/v04-cvrp-r3d-normal-k1-sol-20260830-r1/research_history.jsonl
test -f /home/clawd/research/scion-experiments/v04-cvrp-r3e-normal-k1-sol-20260830-r1/research_history.jsonl
test -x /home/clawd/miniconda3/envs/claw/bin/python

proxy_key_value=$(curl -fsS --connect-timeout 5 --max-time 15 \
  http://127.0.0.1:8080/auth/status | \
  jq -er ".proxy_api_key | select(type == \"string\" and length > 0)")

curl -fsS --connect-timeout 5 --max-time 15 \
  -H "Authorization: Bearer $proxy_key_value" \
  http://127.0.0.1:8080/v1/models | \
  jq -e --arg model gpt-5.6-sol \
    "any(.data[]?; .id == \$model)" >/dev/null

cd /home/clawd/research/or-autoresearch-agent/scion
exec env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
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
    --problem /home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp/problem-v1.yaml \
    --research-input /home/clawd/research/or-autoresearch-agent/scion/experiments/cvrp_history_matched_study/research_input.json \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3-normal-k1-sol-20260828-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3b-normal-k1-sol-20260829-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3c-normal-k1-sol-20260830-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3d-normal-k1-sol-20260830-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3e-normal-k1-sol-20260830-r1/research_history.jsonl \
    --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json \
    --protocol /home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp/formal/protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp/formal/split_manifest.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp/formal/seed_ledger.yaml \
    --time-limit-sec 30 \
    --provider-call-cap 340 \
    --provider-transient-retries 1 \
    --outer-hardwall-sec 345600 \
    --rounds 20 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-r3f-normal-k1-sol-20260831-r1'

trap - EXIT
printf 'TMUX_SESSION=%s\n' "$carrier_session"
tmux display-message -p -t "${carrier_session}:run.0" \
  '#{session_name}\t#{pane_dead}\t#{pane_dead_status}\t#{pane_dead_signal}\t#{pane_pid}\t#{pane_current_command}\t#{socket_path}'
```

After that block returns, a separate read-only observation may run:

```bash
carrier_session='scion-r3f-normal-k1-sol-20260831-r1'
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
tmux kill-session -t scion-r3f-normal-k1-sol-20260831-r1
```

If a later user-requested graceful stop is necessary, send exactly one `C-c`
to `scion-r3f-normal-k1-sol-20260831-r1:run.0` and wait for Python's typed
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
regression in a complete Protocol result remains negative algorithm evidence,
not root-level infrastructure. A partial stage has no scientific Decision. A
positive screen is not promotion, postrun analysis cannot override Decision,
and retained-B0 remains unauthorized before promotion.
