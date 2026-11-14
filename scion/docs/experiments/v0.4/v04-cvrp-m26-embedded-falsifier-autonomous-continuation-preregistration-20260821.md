# CVRP M26 embedded-falsifier autonomous-continuation preregistration

**State:** `TERMINAL_COMPLETED_VALID / TWO_INITIAL_SCREENS_NEGATIVE`

**Label:**
`v04-cvrp-m26-embedded-falsifier-autonomous-continuation-20260821`

**Fresh campaign root:**
`/home/clawd/research/scion-experiments/v04-cvrp-m26-embedded-falsifier-autonomous-continuation-20260821`

**Preparation base:** `83d9ab74674b851de4ae0621ddf08c2578b70c30`

**Live carrier:** `320a42c5477cdbefdce6d76336ffee412929d481`

## Terminal result

The authorized command ran exactly once and is terminal
`completed / valid / requested_rounds_completed`. It completed two distinct
candidate initial screens and consumed the fresh root. The root is preserved;
there is no M26 retry, resume, root reuse, repair launch or automatic M27.

Framework execution was complete. The campaign used 15/34 provider calls:
seven H research turns, six C research turns and two independent C final
decisions. Both candidates passed Contract, Verification and the two-call
canary before reaching the unchanged Protocol -> Safe Features -> Decision
chain. Exactly 32 solver subprocesses ran serially with maximum concurrency
one: four in Verification, four in the two canaries and 24 in the two formal
screens. The recorded interval from first-branch creation to the terminal
status update was `1053.552895s`, well within the `14000s` hardwall; this is not
a measurement of the full CLI process lifetime.

The complete observable C trajectory adopted the embedded falsifier twice, in
order. The first supplied source had 3,272 characters and projected `failed`;
the ordinary host checks nevertheless passed 5/5. The second supplied source
had 326 characters and projected `passed`; its ordinary host checks also
passed 5/5. Each C session proceeded directly to `ready` after that host pass,
with no post-probe revision, and then finalized independently. Thus adoption
is complete, but both enums remain tainted, provider-authored development
hints. The source bodies remain only in the raw provider response trace and
are not copied here, replayed into later context or written to ordinary
history. The ordered failed/passed observations neither gate readiness nor
support a causal claim about either candidate or research trajectory.

Candidate 1 completed all 6/6 initial-screen pairs without a runtime or
feasibility failure. Its case win/loss/tie counts were `0/1/2`, its pair counts
were `1/1/4`, and its median total-distance delta was `0.0` with CI
`[-61.5, 0.0]`. Protocol returned
`fail / SCREENING_FAIL_CASE_QUALITY`; Decision returned `continue_explore`.
Candidate 2 also completed 6/6 valid pairs without failure. Its case counts
were `0/1/2`, pair counts were `0/2/4`, and median delta was `0.0` with CI
`[-90.5, 0.0]`. It received the same Protocol failure and Decision continuation.
The requested second formal round was therefore a second candidate's initial
screen, not an expansion of candidate 1.

Direction quality was poor despite complete bounded execution. H1
reimplemented a mechanism already represented in ordinary historical evidence.
H2 did read the same-campaign `history-0041` observation and completed a pivot,
but its candidate was byte-identical to the failed historical
`history-0034`, which that H session had not read. Exactly two ordinary JSONL
records were appended to `research_history.jsonl`, in candidate order. Family
telemetry remained `unavailable_legacy` / association-only; it does not prove
exact mechanism activation or causality.

No expanded screen, validation, frozen evaluation, promotion or retained
comparison ran, and champion v1 did not change. At post-terminal audit, no live
campaign, child, solver, bubblewrap, prlimit or M26-named process remained;
branch workspaces and probe residue were zero. The checked run-root temporary
patterns and launch-era `/tmp/scion_run_*` patterns showed no M26-scoped
residue. The two durable candidate workspaces are expected retained campaign
evidence, not cleanup leaks. Before these terminal documentation edits, the
tracked worktree and index were clean.

The three claim layers therefore separate cleanly:

1. **Framework.** The bounded H/C path, optional embedded probe, ordinary host
   checks and unchanged formal gates all executed as designed, including probe
   isolation from readiness authority and a forward same-campaign H step.
2. **Research direction.** Probe adoption is observed, but this one
   non-randomized run provides no causal probe-effect evidence. H2 used the
   current-campaign observation, yet the historical reimplementation and
   unread byte-identical failed patch are negative evidence about direction
   novelty and history selection.
3. **Algorithm.** Both complete paired initial screens are negative development
   evidence on the already outcome-exposed bank. They establish neither an
   improvement nor fresh-population, confirmation, generalization, validation,
   frozen, promotion, retained or v0.4-complete evidence.

At preparation time the root was required to be absent and the frozen command
below could be invoked exactly once only after the preparation carrier was
committed and independently reviewed. Those conditions were satisfied before
the now-consumed invocation.

## Scientific question

Can the generic Scion H/C path autonomously select and implement a new CVRP
solver candidate from current source and ordinary history, while giving C the
option to attach a bounded self-authored falsifier to any existing
`test_patch` call without transferring evidence or decision authority away
from the ordinary host development checks and the unchanged
Contract -> Verification -> Protocol -> Safe Features -> Decision chain?

The host specifies no algorithm mechanism, target file, patch, repair or
falsifier. H must still ground its proposal in current source and a read nearest
ordinary prior. C may omit the falsifier or author one during `test_patch`.
The formal algorithm estimand remains candidate versus champion on the declared
screening bank. The probe is a bounded development hint, not part of that
estimand.

## Why this is a new experiment

M25 is terminal and preserved at its consumed root. It showed that evidence-
grounded H and bounded C could produce a verified candidate and reach two
formal screening stages, but its expanded result was negative/mixed and ended
in `abandon / CANDIDATE_RUNTIME_FAILURE`. M26 is not a retry of that candidate:
it has a new label, root, research question, ordinary M25 terminal observation,
two new ordinary M25 history records and an optional generic C falsifier
capability.

The embedded falsifier was added to the existing `test_patch` action rather
than becoming a new authority or lifecycle. It runs only after the ordinary
development safety preflight, inside the same bounded development budget and a
narrow bubblewrap/prlimit sandbox. Only its sandbox scratch file is ephemeral:
the provider-authored source remains in the existing tainted raw provider
response trace, but is never replayed into a later prompt, ordinary history or
claim. Its only safe next-context projection is an enum. The ordinary host test
result alone controls whether C may become ready, although probe and host work
consume the same existing development deadline. The probe enum never directly
controls readiness. Contract, Verification, Protocol, Safe Features and
Decision are unchanged and do not consume the probe result.

This one live campaign is not a randomized probe/no-probe comparison. It can
describe adoption and trajectory but cannot causally attribute research quality
or algorithm outcome to the probe.

## Ordinary research context

The sole problem-owned research input is
`inputs/v04-cvrp-m26-m25-terminal-research-input.json`. Its first four
observations are the exact ordered M25 input prefix: the M7, M18, M23 and M24
ordinary observations. A fifth sanitized M25 terminal observation records:

- the completed initial and expanded screening aggregates;
- the candidate-only runtime failure and terminal abandon;
- bounded framework counts and whether public development, Verification and
  canary passed; and
- zero validation, frozen, promotion and retained output.

The fifth observation contains no provider response, raw trace, H
`research_basis`, falsifier source, editable source, actual aggregate failure
case/seed identity, or validation/frozen identity or raw datum.

M26 supplies thirteen explicitly ordered native history files. The first
twelve are the unchanged 33-record history through M22 used by M25. The final
file, `inputs/v04-cvrp-m26-m25-research-history.jsonl`, is the canonical M25
`research_history.jsonl` copied byte for byte in original line order: initial
`expand`, then expanded `fail / abandon`. It has two ordinary records.

Therefore the H research corpus has five problem observations followed by 35
native records, for exactly 40 ordered history entries. M25 H basis text,
provider raw responses and traces are not imported. The two canonical ordinary
records may expose the evaluated H, patch, screening evidence, Protocol and
Decision in the same way as every other native history record; they are
observations rather than instructions to replay.

## Outcome-exposed adaptive development population

M26 deliberately reuses the exact M25 reached development bank and seeds. Its
outcomes are known from M25, so this bank is **outcome-exposed**, not unopened,
outcome-blind, fresh, independent confirmation or generalization. Reuse keeps
the development environment stable for a descriptive continuation and avoids
spending an untouched population on a single non-randomized framework probe.
It does not make a causal M25-versus-M26 comparison.

Initial screening is exactly:

- `cvrplib/B/B-n57-k7.vrp`
- `cvrplib/P/P-n60-k15.vrp`
- `cvrplib/X/X-n261-k13.vrp`

Expanded screening strictly contains initial and adds exactly:

- `cvrplib/A/A-n53-k7.vrp`
- `cvrplib/X/X-n167-k10.vrp`
- `cvrplib/X/X-n411-k19.vrp`

Screening seeds remain exactly `4358` and `1868`. The existing M25/M24
protocol, split and seed files are reused at their existing paths, byte for
byte. Their internal M24 version string is an ordinary control version, not a
campaign identity or resume marker.

The split still declares later-stage controls, but `--rounds 2` makes
validation and frozen evaluation unreachable in M26. M25 did not touch those
populations; M26 does not open, inspect, evaluate or use their raw data. They
remain protected for a separately designed future experiment.

The reused ordinary controls are:

- `inputs/v04-cvrp-m24-autonomous-direction-research-development-protocol.yaml`
- `inputs/v04-cvrp-m24-autonomous-direction-research-development-split.yaml`
- `inputs/v04-cvrp-m24-autonomous-direction-research-development-seeds.yaml`
- `inputs/v04-cvrp-m11-code-research-limits.json`

## Embedded falsifier semantics

The optional falsifier is frozen as follows:

- only C may author it, as at most one optional `falsifier_source` field on
  each existing `test_patch` call;
- one C session has zero through three ordered, count-consuming `test_patch`
  attempts under the unchanged limit; a campaign may contain multiple fresh C
  sessions if ordinary research rejection sends the scheduler forward;
- each supplied source is fixed at 20,000 characters or fewer and each probe
  process at 10 seconds or fewer, further bounded by the remaining shared
  development deadline;
- it shares the ordinary development call, total-time, file, byte and
  transcript caps; no extra campaign resource is added;
- the ordinary development safety preflight occurs before any probe process;
- its sandbox cannot read public host suites or the host Scion framework, has
  no network, and receives only the draft workspace plus the explicit problem
  runtime closure;
- its fixed ephemeral file is deleted before public host suites are copied and
  host checks run;
- its source remains only in the already tainted raw provider response trace;
  it is never projected into a later C turn, H context, ordinary research
  history, Protocol, Decision or scientific claim;
- stdout, stderr, paths and failure text are likewise not projected;
- the only projected value is one of `passed`, `failed`, `inconclusive`,
  `timeout` or `unavailable`; and
- the falsifier enum never directly controls readiness or finalization; host
  `test_patch.outcome == passed` does, while probe and host work share the
  existing development deadline.

The terminal audit is trace-observable rather than omniscient. It lists every
`test_patch` action present in every completed provider response trace, in
cross-session chronological order, and reports only the C-session/action
ordinal and whether `falsifier_source` was supplied; it never copies the source
(an optional bounded character count may be reported). The safe
`falsifier_outcome` exists only in the in-memory tool result and becomes durable
if a later provider prompt trace contains that tool result. When such a later
trace exists, the audit reports the projected enum, including `unavailable`.
If the action trace exists but no later trace makes the projection observable,
the audit records exactly `projection_unobserved`; it must not substitute null,
`inconclusive`, `unavailable` or an inference from the raw source. A
pre-dispatch tool-error remains a visible C action when traced but is not
recast as a count-consuming test attempt.

The audit reconciles visible response traces with durable provider-call and
terminal counts. It may use `adoption_inconclusive_unused` only when the
complete observable C trajectory and terminal evidence establish that no
`test_patch` action in the entire campaign supplied the field. If trace or
terminal coverage cannot establish that fact, the state is exactly
`adoption_observation_incomplete`. Any supplied field whose projection is
`projection_unobserved` also makes the campaign adoption state
`adoption_observation_incomplete`, even though supply itself was observed.
Neither adoption state is enum `inconclusive`. The audit must not select,
average or present only a favorable enum. A `passed` or `failed` probe remains
a provider-authored, tainted development hint, not scientific or formal
evidence. `inconclusive`, `timeout` and `unavailable` are likewise non-
evidentiary and do not short-circuit host tests unless the already shared total
development deadline itself is exhausted.

## Stages and legal trajectories

`--rounds 2` counts completed formal Protocol stages, not H/C attempts.

- If candidate 1 requests expansion, stage 2 reuses that exact verified branch
  on the six-case expanded screen. It is not a second H, C or candidate.
- If candidate 1 returns to exploration after an evaluated initial stage, a
  later H may read its bounded ordinary same-campaign observation and
  autonomously pivot or refine before a distinct candidate-2 initial screen.
- Contract, Verification or research rejection does not count as a formal
  stage, but every actual provider dispatch consumes the shared cap.

A `revise` inside one C session remains the same H/C attempt. A scheduler step
after `RESEARCH_REJECTED` starts a fresh H and, if H succeeds, at most one fresh
C inside the same campaign root and shared 34-call envelope. That forward
adaptive step is not provider retry. Campaign retry or resume means relaunching
the terminal invocation or reusing its created root; both are prohibited.

No path reaches validation, frozen, promotion or retained replay. Population
replacement, candidate repair after terminalization, retry and resume are not
legal trajectories.

## Frozen resources and typed stops

The existing research limits remain unchanged: at most eight H turns, eight C
research turns, one independent C final decision per H/C attempt and zero
through three ordered `test_patch` attempts per C session. Provider SDK retry
is zero. The campaign-wide provider cap is 34.

The conservative envelope is frozen as:

- provider calls `<=34`; structured-provider timeout `<=7080s`;
- public development work, including every optional probe, `<=450s`;
- Verification pytest `<=480s`;
- formal Protocol/Safe-Feature/Decision stages `<=2`;
- serial solver subprocesses `<=48`: Verification `8`, canary `4`, formal
  screening `36`;
- solver nominal/guarded subject-seconds `<=1900 / 2620`;
- all known guarded work `<=10630s`;
- campaign outer hardwall `14000s`; solver concurrency `1`.

The probe consumes the existing `450s` development and `10630s` known-work
envelopes; it does not add time to either.

Provider-cap exhaustion is typed `resource_exhausted /
PROVIDER_CALL_CAP_EXHAUSTED` with no further dispatch; provider-balance
exhaustion is likewise a resource stop. H transcript, turn or result-cap
exhaustion is specially mapped to `RESOURCE_EXHAUSTED` and stops the
invocation.

The C boundary is different. C test-call or shared test-time exhaustion returns
bounded tool feedback, and a dispatched host timeout is a bounded host outcome;
none automatically stops the campaign. It can prevent that draft from becoming
ready. C transcript, turn or result-cap exhaustion becomes
`RESEARCH_REJECTED`, as do other ordinary H/C research rejections; the campaign
scheduler may move forward to a fresh H/C attempt inside the same invocation
and remaining shared 34-call cap. This is adaptive continuation, not SDK retry,
campaign retry or root reuse.

Provider/transport infrastructure errors, other `NOT_EVALUATED`, interrupt,
unknown, comparator-incomplete or evaluated-without-formal outcomes stop the
invocation. Outer hardwall exit 124 terminates children. Shell exit zero alone
is not scientific success; terminal interpretation uses status, validity,
evaluated rounds, last outcome and stop reason.

## Three-layer claim boundary

1. **Mechanical layer.** Provider- and solver-free regression may establish
   only bounded schema, isolation, cleanup, source non-replay and the fact that
   host readiness ignores the probe enum.
2. **Live descriptive layer.** M26 reports the ordered trace-observable
   `test_patch` actions across all C sessions, field-supplied status, and only
   enums visible in later prompt traces, without favorable selection. A
   missing next projection is `projection_unobserved`. Unused adoption is
   asserted only from a complete observable trajectory; otherwise it is
   `adoption_observation_incomplete`. One run cannot show that the probe caused
   a better hypothesis, patch, test, runtime or outcome.
3. **Formal algorithm layer.** The ordinary host outcome controls development
   admissibility; only completed paired Protocol comparisons support candidate-
   versus-champion algorithm claims. Results are adaptive development evidence
   on the already seen bank. They do not support fresh-population, confirmation,
   generalization, exact probe-mechanism, validation, frozen, promotion,
   retained, production-readiness or v0.4-complete claims.

Problem-owned family telemetry is always association-only. A completed paired
Protocol comparison supports only its independent candidate-versus-champion
algorithm claim; it cannot upgrade family telemetry into exact activation or a
causal mechanism claim. The probe enum is never Protocol or Decision evidence.

## Frozen one-shot command

Preparation requires a clean tracked worktree and index, all named inputs and
this preregistration tracked, the fresh root absent, functional bubblewrap and
prlimit, provider metadata available, and no concurrent Scion/candidate run.
The exact replay and real sandbox checks below are provider- and solver-free.
These checks confer mechanical evidence only.

```bash
set -euo pipefail
cd /home/clawd/research/or-autoresearch-agent/scion
git diff --quiet
git diff --cached --quiet
test "$(git rev-parse --show-toplevel)" = /home/clawd/research/or-autoresearch-agent

for INPUT in \
  docs/experiments/v0.4/inputs/v04-cvrp-m24-autonomous-direction-research-development-protocol.yaml \
  docs/experiments/v0.4/inputs/v04-cvrp-m24-autonomous-direction-research-development-split.yaml \
  docs/experiments/v0.4/inputs/v04-cvrp-m24-autonomous-direction-research-development-seeds.yaml \
  docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json \
  docs/experiments/v0.4/inputs/v04-cvrp-m26-m25-terminal-research-input.json \
  docs/experiments/v0.4/inputs/v04-cvrp-m10-m9-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m11-m10-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m12-m11-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m13-m12-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m14-m13-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m15-m14-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m16-m15-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m19-m16-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m20-m19-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m21-m20-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m22-m21-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m24-m22-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m26-m25-research-history.jsonl \
  scion/tests/fixtures/m26_embedded_falsifier_replay.json \
  scion/tests/unit/core/test_m26_embedded_falsifier_replay.py \
  docs/experiments/v0.4/v04-cvrp-m26-embedded-falsifier-autonomous-continuation-preregistration-20260821.md
do
  git ls-files --error-unmatch "$INPUT" >/dev/null
done

CAMPAIGN_DIR=/home/clawd/research/scion-experiments/v04-cvrp-m26-embedded-falsifier-autonomous-continuation-20260821
test ! -e "$CAMPAIGN_DIR"
test -x /usr/bin/bwrap
test -x /usr/bin/prlimit

env -i \
  HOME=/home/clawd \
  PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages \
  /home/clawd/miniconda3/envs/claw/bin/python -B -m pytest -q \
  -p no:cacheprovider \
  scion/tests/unit/core/test_m26_embedded_falsifier_replay.py \
  scion/tests/unit/test_code_development.py::test_test_patch_falsifier_hides_framework_and_leaves_no_host_residue \
  scion/tests/unit/test_code_development.py::test_invalid_falsifier_is_inconclusive_but_host_checks_still_run \
  scion/tests/unit/test_code_development_redteam.py::test_c9_bypass_cannot_read_host_or_masked_framework_or_write_work

test -z "$(ps -eo comm=,args= | awk '
  $1 ~ /^python/ &&
  ($0 ~ /-m scion[.]cli[.]main run/ || $0 ~ /run_.*candidate.*[.]py/) {
    print
    exit
  }
')"

PROXY_KEY_VALUE="$(curl -fsS --connect-timeout 5 --max-time 15 \
  http://127.0.0.1:8080/auth/status | \
  jq -er '.proxy_api_key | select(type == "string" and length > 0)')"
trap 'unset PROXY_KEY_VALUE' EXIT
curl -fsS --connect-timeout 5 --max-time 15 \
  -H "Authorization: Bearer $PROXY_KEY_VALUE" \
  http://127.0.0.1:8080/v1/models | \
  jq -e --arg model gpt-5.6-terra \
    'any(.data[]?; .id == $model)' >/dev/null

env -i \
  HOME=/home/clawd \
  PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONHASHSEED=0 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp \
  SCION_MODEL=gpt-5.6-terra SCION_REASONING_EFFORT=high \
  SCION_BASE_URL=http://127.0.0.1:8080 SCION_API_KEY="$PROXY_KEY_VALUE" \
  SCION_LLM_TIMEOUT_SEC=120 \
  SCION_LLM_HYPOTHESIS_RESEARCH_TURN_TIMEOUT_SEC=120 \
  SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC=240 \
  SCION_LLM_CODE_RESEARCH_FINALIZE_TIMEOUT_SEC=240 \
  /home/clawd/miniconda3/envs/claw/bin/python -S -B -m scion.cli.main run \
  --problem /home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp/problem.yaml \
  --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m26-m25-terminal-research-input.json \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m10-m9-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-m10-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m12-m11-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m13-m12-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m14-m13-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m15-m14-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m16-m15-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m19-m16-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m20-m19-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m21-m20-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m22-m21-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m24-m22-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m26-m25-research-history.jsonl \
  --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m24-autonomous-direction-research-development-protocol.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m24-autonomous-direction-research-development-split.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m24-autonomous-direction-research-development-seeds.yaml \
  --time-limit-sec 30 \
  --provider-call-cap 34 \
  --outer-hardwall-sec 14000 \
  --rounds 2 \
  --campaign-dir "$CAMPAIGN_DIR"
```

The user's standing authorization permitted this exact live command once only
after the preparation carrier was committed, the provider- and solver-free
preflight and two independent scientific/runtime reviews passed, and the
output root remained absent. That invocation is now consumed. It authorizes
neither deletion or reuse of the created root nor a second launch.

No distribution, packaging, build, deployment, root/systemd, Trust/Hash
authority, object identity, lease, signing, registration or duplicate-control
work is part of M26.
