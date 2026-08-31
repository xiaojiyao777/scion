# CVRP R3e adaptive-history K1 preregistration

Date: 2026-08-30 UTC

## Question

After correcting the typed terminal-finalization race and changing launch from
start-then-attach to attach-before-start, can a fresh ordinary Scion campaign
start from CVRP B0, voluntarily use the complete R3, R3b, R3c and R3d ordinary
histories, and produce an exact candidate that drains screening, validation and
frozen testing into deterministic promotion?

R3e is a new experiment after an operational run-lifetime repair. It is not a
resume, retry, extension or fixed-candidate replay of R3d. It receives a fresh
output root, B0 workspace, branch state and provider session. It loads no R3d
candidate source, workspace, SQLite file, status file, metric file, process
state, provider response or expanded counter. Any similar proposal must be
independently selected and generated in R3e.

The interrupted R3d root remains untouched.

## Frozen history policy

Four external H-only files are loaded in this exact order:

1. R3 `research_history.jsonl`: 21 complete ordinary records;
2. R3b `research_history.jsonl`: one complete initial-screen record;
3. R3c `research_history.jsonl`: two complete typed records, one evaluated
   initial screen followed by one proposal-hypothesis infrastructure block;
4. R3d `research_history.jsonl`: one complete evaluated initial-screen record.

The production loader accepts the concatenation as exactly 25 ordered strict
`cvrp` records (`21 + 1 + 2 + 1`). The common research input contains eight
ordinary prior observations, so R3d's complete row is exposed last as
`history-0033`.

R3d's history file contains only the completed `32/32` initial screen with
`EVALUATION_COMPLETED` and Decision `expand_screening`. It was written before
the later expanded-screen heartbeats. The unfinalized `35` attempted, `34`
completed/valid of `96` planned expansion is absent from the history file and
is excluded from R3e. No host-authored interruption row is added.

External history remains agent-optional. The host exposes the complete ordered
index but does not rank a reference, select a mechanism, copy a patch or require
an external read. Mandatory used/rejected disposition applies only to explicit
failures at the latest ordinary live `current` and `sibling` relation rounds,
independently. Used evidence must be read and cited; rejected evidence needs a
bounded agent-authored reason.

Search, read, citation, selected-basis explanation and frontier disposition are
reported separately. Uptake requires an actual read and citation. This single
adaptive campaign cannot identify the causal benefit of history.

## Scientific inputs and interpretation

The formal problem and science inputs are unchanged from R3d:

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

No file under the B0 algorithm policy package is replaced by an earlier
candidate. The terminal-finalization repair is framework runtime work and does
not alter the CVRP algorithm, Protocol, split, seed ledger, research input or
code-research limits.

The split remains 12 screening, 12 validation and 12 frozen cases plus one
canary. The production formal-data check resolves all 37 declared cases and 73
required files under the data root, with zero missing cases, missing companions
or unsafe files. Screening remains the outcome-known adaptive development
population used by R3, R3b, R3c and R3d; it is not independent generalization
evidence. Validation and frozen inputs remain prospective for an exact R3e
candidate. Retained-B0 evaluation remains blocked until promotion.

Existing activation falsifiers and public synthetic deadline checks remain
tainted development diagnostics outside Safe Features and Decision. Missing
activation evidence cannot reverse Protocol or promotion; it is reported as an
audit gap.

## Frozen provider boundary

Provider SDK retries remain zero. R3e explicitly sets
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

## Terminal-finalization and foreground boundary

The CLI now keeps the existing SIGTERM, SIGINT and SIGHUP handlers installed
through `finalize_requested_stop`. Repeated handler re-entry is suppressed, so
a second handled terminal signal cannot restore default behavior before the
first typed stop has been made durable. This does not make `SIGKILL` catchable
and does not replace a stable foreground terminal owner.

The preregistered attach-before-start gate was attempted twice across turns
without starting R3e. Both empty-shell exposure requests remained `queued`, and
the later terminal observations showed that neither exact shell was attached.
The earlier empty shell was closed. Neither attempt ran the proxy/model check,
created the campaign root or invoked the CLI, and the R3e root remains absent.
The marker roundtrip is therefore unavailable and no third PTY attempt is
authorized.

This prelaunch amendment changes only the operational foreground carrier. R3's
ordinary non-TTY unified-exec foreground invocation completed with exit `0`
after `77359.3004` seconds. In contrast, the R3b and R3d PTY-backed foreground
invocations disappeared after `4957.185` and `5039.302` seconds respectively.
Those observations do not prove a process-lifetime guarantee, but they support
one narrower result-blind fallback: a single ordinary non-TTY `exec_command`
unified-exec call, in the foreground and without detachment.

The call is frozen with `workdir=/home/clawd/research/or-autoresearch-agent/scion`,
`tty=false`, `login=false` and `yield_time_ms=1000`; its `cmd` is exactly the bash
block below. Output-budget plumbing is not a scientific input. No interactive
session, backgrounding, service, scheduler, distribution, deployment,
packaging, build, PID registry, identity, lease, receipt or hash lifecycle is
introduced. The call result, console output and any tool-session handle are not
liveness or scientific evidence and cannot authorize intervention, relaunch or
interpretation. Only the ordinary durable campaign artifacts may establish the
terminal and scientific result. The frozen block ends with `exec env`, so the
fail-closed shell is replaced by Python rather than retaining a shell child
layer.

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
  `/home/clawd/research/scion-experiments/v04-cvrp-r3e-normal-k1-sol-20260830-r1`.

The cap remains `20 x (8 H + 8 C + 1 C-finalize) = 340`. A transient
redispatch consumes that fixed allowance and can therefore censor the logical
horizon earlier. Research rejections also consume provider dispatches but not
the evaluated-stage horizon. Exact candidates move only through new live branch
state; no history summary reconstructs one.

## Launch gate and current status

Launch is authorized only after all of the following are true:

1. focused tests cover first-signal typed finalization, repeated-signal
   suppression, SIGHUP, outer hardwall and ordinary command exit behavior;
2. the full provider-free, non-campaign regression passes after the repair;
3. focused ResourceEnvelope, ProviderCaller, transport, history and CVRP
   formal-readiness tests pass;
4. the four history files load as exactly 25 ordered strict `cvrp` records in
   R3, R3b, R3c, R3d order;
5. all 37 declared split cases and all 73 required files resolve under the
   frozen data root;
6. the claw Python environment imports the declared runtime dependencies;
7. the fresh R3e output root is absent;
8. both empty-PTY attachment attempts have failed closed without a root, and
   the earlier empty shell is closed;
9. the one-shot unified-exec call uses the exact non-TTY foreground parameters
   and bash payload frozen here;
10. one local proxy/model check confirms `gpt-5.6-sol` without printing the key.

Current provider-free evidence records `1197` passing unit tests and `45`
passing focused signal/finalization tests. The fresh full non-campaign
regression collected `2296` tests and completed with `2295 passed, 1 skipped,
0 failed` in 443.05 seconds (444.10 seconds outer elapsed). History loading,
formal-data resolution, the Python dependency check and fresh-root check also
pass. This result belongs to the repaired tree; no earlier full-suite count is
reused.

Two cross-turn empty-terminal attempts returned and remained `queued` without
attachment. No proxy/model check, CLI invocation or campaign-root creation
followed either attempt; the earlier shell is closed and the declared root is
still absent. This exhausts the PTY route rather than relaxing its marker gate.

Items 1-7 freeze source, public tests, Protocol, split, seeds, limits, ordered
histories, this preregistration and the launch payload. Item 8 records the
failed-closed PTY boundary. Item 9 freezes the only replacement invocation.
Item 10 is the sole local network precondition and runs once inside that exact
block. If any block precondition fails, no campaign root is created, the
command exits nonzero and the one-shot is not retried.

## Frozen launch

```bash
set -uo pipefail

SOURCE=/home/clawd/research/or-autoresearch-agent/scion
DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp
R3_HISTORY=/home/clawd/research/scion-experiments/v04-cvrp-r3-normal-k1-sol-20260828-r1/research_history.jsonl
R3B_HISTORY=/home/clawd/research/scion-experiments/v04-cvrp-r3b-normal-k1-sol-20260829-r1/research_history.jsonl
R3C_HISTORY=/home/clawd/research/scion-experiments/v04-cvrp-r3c-normal-k1-sol-20260830-r1/research_history.jsonl
R3D_HISTORY=/home/clawd/research/scion-experiments/v04-cvrp-r3d-normal-k1-sol-20260830-r1/research_history.jsonl
CAMPAIGN_ROOT=/home/clawd/research/scion-experiments/v04-cvrp-r3e-normal-k1-sol-20260830-r1
PYTHON=/home/clawd/miniconda3/envs/claw/bin/python
proxy_key_value=

if test ! -e "$CAMPAIGN_ROOT" &&
  test -f "$R3_HISTORY" &&
  test -f "$R3B_HISTORY" &&
  test -f "$R3C_HISTORY" &&
  test -f "$R3D_HISTORY" &&
  test -x "$PYTHON" &&
  proxy_key_value=$(curl -fsS --connect-timeout 5 --max-time 15 \
    http://127.0.0.1:8080/auth/status | \
    jq -er '.proxy_api_key | select(type == "string" and length > 0)') &&
  curl -fsS --connect-timeout 5 --max-time 15 \
    -H "Authorization: Bearer $proxy_key_value" \
    http://127.0.0.1:8080/v1/models | \
    jq -e --arg model gpt-5.6-sol \
      'any(.data[]?; .id == $model)' >/dev/null &&
  cd "$SOURCE"
then
  exec env \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="$SOURCE" \
  SCION_PROBLEM_DATA_ROOT="$DATA_ROOT" \
  SCION_MODEL=gpt-5.6-sol \
  SCION_REASONING_EFFORT=high \
  SCION_BASE_URL=http://127.0.0.1:8080 \
  SCION_API_KEY="$proxy_key_value" \
  SCION_LLM_TIMEOUT_SEC=120 \
  SCION_LLM_HYPOTHESIS_RESEARCH_TURN_TIMEOUT_SEC=120 \
  SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC=240 \
  SCION_LLM_CODE_RESEARCH_FINALIZE_TIMEOUT_SEC=240 \
  "$PYTHON" -B -m scion.cli.main run \
    --problem "$SOURCE/scion/problems/cvrp/problem-v1.yaml" \
    --research-input "$SOURCE/experiments/cvrp_history_matched_study/research_input.json" \
    --research-history "$R3_HISTORY" \
    --research-history "$R3B_HISTORY" \
    --research-history "$R3C_HISTORY" \
    --research-history "$R3D_HISTORY" \
    --code-research-limits "$SOURCE/docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json" \
    --protocol "$SOURCE/scion/problems/cvrp/formal/protocol.yaml" \
    --split "$SOURCE/scion/problems/cvrp/formal/split_manifest.yaml" \
    --seeds "$SOURCE/scion/problems/cvrp/formal/seed_ledger.yaml" \
    --time-limit-sec 30 \
    --provider-call-cap 340 \
    --provider-transient-retries 1 \
    --outer-hardwall-sec 345600 \
    --rounds 20 \
    --campaign-dir "$CAMPAIGN_ROOT"
  launch_status=$?
  unset proxy_key_value
  printf 'R3e exec failed before launch (exit=%s)\n' "$launch_status" >&2
  exit "$launch_status"
else
  gate_status=$?
  unset proxy_key_value
  printf 'R3e launch gate failed (exit=%s); campaign not started\n' \
    "$gate_status" >&2
  exit "$gate_status"
fi
```

The non-TTY unified-exec carrier is operational only, not a scientific
authority or result channel. Campaign status, ordinary metrics, research
history and Decision remain the runtime/scientific records.

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
