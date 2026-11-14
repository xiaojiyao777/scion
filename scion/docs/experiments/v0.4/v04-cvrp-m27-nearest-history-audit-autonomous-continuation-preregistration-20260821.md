# CVRP M27 nearest-history-audit autonomous-continuation preregistration

**State:** `TERMINAL_COMPLETED_VALID / EXPANDED_SCREENING_ABANDON`

**Label:**
`v04-cvrp-m27-nearest-history-audit-autonomous-continuation-20260821`

**Fresh campaign root:**
`/home/clawd/research/scion-experiments/v04-cvrp-m27-nearest-history-audit-autonomous-continuation-20260821`

**Framework preparation base:** `c65c1438f2efcc488b0be8cf58e5d82515367077`

**Preparation and live carrier:** `4f4a8de9ae4504f0c22de0b315a92fa74aab4203`

The implementation revision and carrier are ordinary source references, not
authorization, identity, digest or proof objects. This preregistration and all
named inputs were committed before launch.

## Terminal result

The authorized command ran exactly once and is terminal
`completed / valid / requested_rounds_completed`. One accepted H produced one
candidate that completed initial and expanded screening. The two requested
formal rounds were therefore two screening stages for the same candidate;
validation and frozen evaluation were zero. The fresh root is preserved and
consumed, with no retry, resume, root reuse or automatic M28.

The live nearest-history audit was completely observable. The first H prompt
contained 43 entries: six problem observations and 37 native ordinary records,
of which the 37 headline-bearing native records were ranking-eligible. The
single H session used four provider turns in order: read current source,
attempt finalize and receive the fixed audit trigger for `history-0030`, read
that ref, then finalize an accepted H. Thus accepted-H coverage was 1/1 and
incomplete-H coverage was zero. The accepted basis contained `history-0030` in
both `read_refs` and `nearest_prior_refs`; the read was audit-triggered rather
than preemptive.

The structured candidate changed after the trigger, but independent
recomputation on the complete current index kept its eligible top-1 at
`history-0030`. H did not explicitly characterize its `material_delta` as a
pivot or refinement, so the frozen self-label audit is `not_observable`.
Direct equality against all 37 supplied ordinary records found zero exact
structured-H replays and zero exact complete ordered-patch replays. Qualitative
post-hoc direction review describes the accepted work as a same-mechanism
refinement or reimplementation, not a pivot or a novelty result.

The observable C path was `revise -> test_patch -> ready -> finalize_patch`.
The `test_patch` action supplied a 1,199-character falsifier source; the next
durable C prompt projected probe information only as
`falsifier_outcome=passed`, while its ordinary host outcome was `passed` with
all five checks passing. C made no post-probe revision. The source body remains
only in the tainted raw provider trace and is not copied here or into ordinary
history. Probe adoption and its enum are descriptive, non-evidentiary facts
and support no causal probe claim.

Resource accounting reconciled exactly. The campaign used 8/34 provider calls:
four H turns, three C turns and one C final decision. It ran 42 solver
subprocesses with maximum concurrency one: two in Verification, four across
the two canaries and 36 in formal Protocol work. The recorded interval from
run-root birth to the root-directory mtime immediately following terminal-
summary publication was `1545.200343s`; it is not a measurement of the full
shell lifetime. The `14000s` hardwall was not reached.

Initial screening completed 6/6 valid pairs with zero failures. Case
win/loss/tie counts were `1/0/2`, pair counts were `1/0/5`, and median
total-distance delta was `0.0` with CI `[0.0, 28.5]`. Median candidate/champion
runtime ratio was `0.99951391`, with median runtime delta `-9.5ms`. Protocol
returned `expand / SCREENING_EXPAND_INITIAL_QUALITY`; Decision returned
`expand_screening`.

Expanded screening attempted all 12 pairs, completed 10 valid pairs and
recorded two candidate-only timeouts. The host guard fired at the declared
`90s + 15s`; recorded end-to-end elapsed values were `105112ms` and
`105116ms`, including bounded post-kill drain/accounting. Both paired champion
runs completed. Across six cases, case counts were `1/1/4`,
pair counts were `1/2/9`, and median total-distance delta was `0.0` with CI
`[-0.5, 0.5]`. Median runtime ratio was `1.00062879`, with median runtime delta
`+17ms`. Protocol returned `fail / SCREENING_FAIL_CASE_QUALITY`; Decision
returned `abandon / CANDIDATE_RUNTIME_FAILURE`.

Exactly two ordinary JSONL records were appended in stage order. Their
structured H values and complete ordered patches are respectively equal,
recording the same candidate's initial and expanded evidence rather than a
second H. Family telemetry was `unavailable_current_source` and remains
association-only; it cannot establish exact activation or causality. No
validation, frozen, promotion, retained or champion-change evidence exists.

Post-terminal cleanup found zero scoped campaign/child/solver/bubblewrap/
prlimit processes and zero active slots. The checked run-root `workspaces`,
`candidate_workspaces` and `archive` directories had zero children, and no
M27-era `/tmp/scion_run_*` match remained. The durable campaign root is
expected preserved evidence, not resumable state.

The three claim layers therefore remain separate:

1. **Framework.** The four-turn audit trigger/read/citation path, candidate
   recomputation, bounded C probe projection, host checks and formal execution
   were observable and behaved as designed. This does not establish a causal
   audit or probe effect.
2. **Research direction.** The accepted direction was testable but is best
   described as same-mechanism refinement/reimplementation. Zero exact replay
   is only a direct-equality fact, not proof of semantic novelty.
3. **Algorithm.** Initial expansion followed by expanded-screening failure and
   runtime abandon is negative/mixed development evidence on the already
   outcome-exposed bank. It establishes no fresh-population, confirmation,
   generalization, validation, frozen, promotion, retained, production-readiness
   or v0.4-complete claim.

At preparation time the root was required to be absent and the frozen command
below could be invoked exactly once only after the carrier was committed and
the provider-/solver-free and independent review gates passed. Those conditions
were satisfied before the now-consumed invocation.

## Scientific question

Can generic Scion's bounded H/C path autonomously select, implement and
evaluate another CVRP solver candidate while ensuring that every accepted H has
read and cited the lexical top-1 ordinary prior for that exact candidate among
the usable headline-bearing entries found by scanning the complete history
index visible on that H turn?

The host specifies no algorithm mechanism, first-candidate direction, target
file, action, patch, repair or falsifier. It routes one ordinary evidence ref;
it does not decide novelty or candidate quality. C remains bound to the exact
accepted H. Contract, Verification and the unchanged problem-owned
Protocol -> Safe Features -> Decision chain retain all formal authority.

The framework estimand is whether the nearest-history audit is completely
observable and satisfied for each accepted H, including a preemptive exact-ref
read, an audit-triggered read, or a candidate change that causes recomputation.
The research-direction audit reports whether H self-describes a pivot or
refinement and whether the accepted H or finalized patch exactly replays an
ordinary prior. The algorithm estimand remains candidate versus champion in
completed paired Protocol stages on the declared seen development bank.

M26 and M27 are sequential, adaptive and non-randomized. Their framework,
direction or algorithm results cannot be interpreted as a causal effect of the
nearest-history audit.

## Why this is a new experiment

M26 is terminal and preserved at its consumed root. Both of its autonomous
candidates passed bounded development, Contract, Verification and canary and
completed valid paired initial screens, but both Protocol results failed case
quality. H1 reimplemented an ordinary historical direction. H2 used the first
same-campaign result and pivoted, yet its finalized patch exactly replayed an
unread failed ordinary prior. The optional C probes were adopted, but they were
non-evidentiary and establish no causal effect.

M27 is not a retry, resume, repair or renamed M26. It has a new label, fresh
root, one strict aggregate M26 terminal observation and the two canonical M26
ordinary history records. It also uses the new problem-neutral nearest-history
audit. M27 deliberately reuses the M25/M26 outcome-exposed development bank;
that preserves a descriptive continuation population instead of spending an
untouched later-stage population on a non-randomized framework change.

There is no automatic M28 regardless of outcome.

## Generic nearest-history audit

The audit reuses the existing `finalize_hypothesis` action. It creates no new
provider action, config, database field, history record type, object identity,
hash, authority or lifecycle.

For every otherwise valid finalize attempt:

1. The host parses the candidate and validates its already bounded
   `research_basis` before ranking. An invalid candidate or basis cannot use the
   ranker as an oracle.
2. The host scans the complete current `history_index`, including ordinary
   problem observations, explicit native history and any ordinary current-
   campaign entries already present for that later H. It ranks only entries
   with a usable whitelisted hypothesis headline; entries without such a
   headline are safely skipped rather than treated as zero-score candidates.
3. Ranking reads index headlines only. It never reads a history body, patch,
   Protocol metrics or Decision evidence. Text tokens come only from `text`,
   `hypothesis_text`, `target_weakness` and `expected_effect`; structured exact
   comparisons use `target_file`, `change_locus`, `action` and
   `predicted_direction`.
4. Text is Unicode-NFKC-normalized and case-folded. The pure deterministic
   ordering is token Jaccard, then the four ordered structured exact matches,
   then unique-token overlap count, then later append ordinal. A usable corpus
   always produces one top-1 ref. Equal headlines therefore resolve to the
   later ordinary append position. If no entry has a usable headline, no top-1
   ref is produced and the existing any-history grounding rule applies.
5. If that ref is not visible, the finalize consumes its normal H turn and the
   host returns exactly:

   ```json
   {
     "action": "finalize_hypothesis",
     "ok": false,
     "reason": "nearest_history_audit_required",
     "required_history_ref": "<one existing history ref>"
   }
   ```

   It returns no candidate text, matched headline, score, body, patch, metric,
   novelty judgment or recommended algorithm change.
6. H must use the existing `read_history` action for that exact ref and include
   it in both `research_basis.read_refs` and
   `research_basis.nearest_prior_refs` before acceptance. Reading or citing an
   arbitrary different history does not satisfy the audit.
7. The host recomputes top-1 on every finalize. If H changes the candidate after
   an audit trigger, the old routed ref has no special status and the new
   candidate may require another ref. If H preemptively reads and cites the
   eventual candidate's top-1, acceptance needs no audit-trigger feedback.

The ranker routes evidence; it does not enforce novelty, material difference,
mechanism diversity or predicted quality. `material_delta`, alternatives,
prediction and falsification condition remain tainted H context. The audit does
not enter C, Contract, Verification, Protocol, Safe Features or Decision. The
direct one-shot H path when bounded research limits are absent is unchanged.
When a history inventory has no usable headline, the prior any-history
grounding behavior remains unchanged.

The audit adds no maximum provider call. A normal audit-triggered path can use
four H turns: read source, attempt finalize, read the routed history, then
finalize. A preemptive source/read-history/finalize path can still use three.
Both remain inside the existing eight-turn H limit and shared campaign cap.

## Ordinary research context

The sole problem-owned research input is
`inputs/v04-cvrp-m27-m26-terminal-research-input.json`. Its first five
observations are the exact ordered M26 input prefix: M7, M18, M23, M24 and M25.
The sixth strict M26 terminal observation contains only public aggregate facts:

- two completed initial screens, each 6/6 valid with no subject or fleet
  failure;
- ordered case win/loss/tie values `0/1/2` and `0/1/2`, median deltas `0.0`,
  and CIs `[-61.5, 0.0]` and `[-90.5, 0.0]`;
- 15/34 provider calls split into seven H research, six C research and two C
  final-decision calls, with provider retry zero;
- two valid H values, two C candidates, successful public development,
  Verification and canary, 32 serial solver calls, two formal stages and two
  `continue_explore` Decisions; and
- no validation, frozen, promotion or retained stage.

The observation's legacy input fields named `validation_stage_metrics`,
`validation_safe_features` and `validation_decision` are `true` because the
production adapter projects those names to generic `terminal_stage_metrics`,
`terminal_safe_features` and `terminal_decision`. They represent M26's completed
screening metrics/Safe Features/Decision, not a validation-stage claim. The
completed-stage list and explicit diagnostics keep `validation_reached=false`.

`exact_candidate_outcome_overlap_count=1` records that one M26 exact candidate
already had an ordinary prior candidate outcome. It is not a case-population
overlap count and does not identify the prior candidate in this sanitized
observation. Population selection was outcome-exposed, incremental effect was
not isolated and global case unseen is false.

The sixth observation contains no H `research_basis`, provider response or raw
trace, probe source or body, editable source, mechanism, target, action, patch,
actual case identity, actual seed identity, or validation/frozen reserved
identity or raw datum.

M27 supplies fourteen ordered native history files. The first thirteen are the
35-record set consumed by M26. The fourteenth,
`inputs/v04-cvrp-m27-m26-research-history.jsonl`, is the consumed M26
`research_history.jsonl` copied byte for byte in original candidate order. It
contains two canonical ordinary records; both have a failed screening Protocol
and `continue_explore` Decision. The live preflight compares the tracked copy
directly with the preserved M26 root. No digest is introduced.

The first H therefore sees exactly six problem observations followed by 37
native records: 43 ordered history entries. All 43 are traversed as the complete
inventory. The six observations lack a hypothesis headline and remain visible
ordinary evidence but are not ranking-eligible; the top-1 denominator is the 37
usable headline-bearing native entries. A later H may additionally see a
bounded ordinary same-campaign entry. M26 H bases, raw provider/probe traces and
raw solver output are not imported. Historical H and patch bodies in the two
canonical ordinary records have the same bounded evidence role as all other
native history; they are observations, not replay instructions.

## Outcome-exposed adaptive development population

M27 reuses the exact M25/M26 reached development bank and seeds byte for byte.
Its outcomes are known. This population is **outcome-exposed**, not fresh,
outcome-blind, independent confirmation or generalization.

Initial screening is exactly:

- `cvrplib/B/B-n57-k7.vrp`
- `cvrplib/P/P-n60-k15.vrp`
- `cvrplib/X/X-n261-k13.vrp`

Expanded screening strictly contains initial and adds exactly:

- `cvrplib/A/A-n53-k7.vrp`
- `cvrplib/X/X-n167-k10.vrp`
- `cvrplib/X/X-n411-k19.vrp`

Screening seeds remain exactly `4358` and `1868`. The existing M24 protocol,
split and seed files and M11 research-limits file are reused at their existing
paths, byte for byte. Their internal M24 version string is an ordinary reusable
control version, not an M27 identity or an M24 resume marker.

The split declares validation and frozen controls, but `--rounds 2` makes them
unreachable. M25 and M26 did not touch those populations. M27 does not open,
inspect, evaluate or use their raw data; they remain reserved for a separately
designed future experiment.

The reused controls are:

- `inputs/v04-cvrp-m24-autonomous-direction-research-development-protocol.yaml`
- `inputs/v04-cvrp-m24-autonomous-direction-research-development-split.yaml`
- `inputs/v04-cvrp-m24-autonomous-direction-research-development-seeds.yaml`
- `inputs/v04-cvrp-m11-code-research-limits.json`

## Optional embedded falsifier

The M26 falsifier semantics remain unchanged and non-evidentiary:

- only C may supply at most one optional `falsifier_source` on each existing
  `test_patch`; a C session still has zero through three count-consuming
  `test_patch` attempts;
- each source is at most 20,000 characters and each probe process at most ten
  seconds, further bounded by the remaining shared development deadline;
- the probe shares the existing development call, time, file, byte, transcript
  and campaign budgets; it adds no provider call or formal stage;
- ordinary development safety preflight occurs before the probe;
- the narrow bubblewrap/prlimit sandbox receives only the draft workspace and
  explicit problem runtime closure, with no host Scion/public suite/formal data
  access and no network;
- its fixed scratch file is deleted before public host suites are copied or run;
- the provider-supplied source remains only in its tainted raw provider response
  trace; probe-child stdout and stderr are discarded; no source, path or failure
  text is replayed or projected into H, later C context, ordinary history,
  Protocol, Decision or a scientific claim; and
- the only safe projection is `passed`, `failed`, `inconclusive`, `timeout` or
  `unavailable`. That enum never directly controls readiness. The ordinary host
  `test_patch.outcome == passed` does, while probe and host work share the same
  deadline.

The terminal audit enumerates every visible `test_patch` response action across
all completed C sessions in chronological order. It reports session/action
ordinal, whether the field was supplied and, optionally, source character
count, but never source text. A safe enum is reported only if a later provider
prompt trace durably exposes that tool result. Otherwise the value is exactly
`projection_unobserved`; no null, inferred or substituted enum is allowed. A
pre-dispatch tool error remains a visible action but is not recast as a
count-consuming attempt.

`adoption_inconclusive_unused` is allowed only if the complete observable C
trajectory and terminal counts establish that no action supplied the field. If
coverage is incomplete, or any supplied field has `projection_unobserved`, the
campaign state is `adoption_observation_incomplete`. Neither state is enum
`inconclusive`. The audit reports the whole ordered sequence and never selects
only a favorable enum. No probe result supports a causal or formal claim.

## Stages and legal trajectories

`--rounds 2` counts completed formal Protocol stages, not H/C attempts.

- If candidate 1 requests expansion, stage 2 reuses that exact verified branch
  on the six-case expanded screen. It does not invoke another H or C.
- If candidate 1 returns to exploration after an evaluated initial stage, a
  later H may receive its bounded ordinary same-campaign observation. Its
  current full index, including that entry, is independently ranked for its
  own candidate.
- Contract, Verification or research rejection does not count as a formal
  stage. Every actual provider dispatch consumes the shared cap.

A `revise` in one C session remains one H/C attempt. Scheduler-forward after
`RESEARCH_REJECTED` may start a fresh H/C attempt inside this invocation and
remaining shared envelope. It is not SDK retry, campaign retry or root reuse.

No path reaches validation, frozen evaluation, promotion or retained replay.
Population replacement, candidate repair after terminalization, relaunch,
resume and root reuse are prohibited.

## Frozen resources and typed stops

The unchanged research limits permit at most eight H turns, eight C research
turns, one independent C final decision per H/C attempt and zero through three
`test_patch` actions per C session. Provider SDK retry is zero. The campaign-
wide provider cap is 34. Nearest-history routing consumes an ordinary H finalize
turn and adds no call allowance.

The independently recomputed conservative envelope remains:

- provider calls `<=34`; H timeout `120s`, C turn/final timeout `240s`;
- structured-provider timeout `<=7080s` (the provider-cap-constrained worst mix
  remains nine minimum H calls plus 25 C/final calls);
- public development work, including every optional probe, `<=450s`;
- Verification pytest `<=480s`;
- formal Protocol/Safe-Feature/Decision stages `<=2`;
- serial solver subprocesses `<=48`: Verification `8`, canary `4`, formal
  screening `36`;
- solver nominal/guarded subject-seconds `<=1900 / 2620`;
- all known guarded work `<=10630s` (`7080 + 450 + 480 + 2620`);
- outer hardwall `14000s`; solver concurrency `1`.

The audit does not increase any maximum. The optional probe consumes the
existing `450s` development and `10630s` known-work envelopes.

Provider-cap exhaustion is typed `resource_exhausted /
PROVIDER_CALL_CAP_EXHAUSTED` with no further dispatch. H transcript, turn or
result-cap exhaustion maps to `RESOURCE_EXHAUSTED` and stops the invocation.
Provider-balance exhaustion is also a resource stop.

C test-call or shared test-time exhaustion returns bounded tool feedback; a
dispatched host timeout is an ordinary bounded host outcome. C transcript,
turn or result-cap exhaustion becomes `RESEARCH_REJECTED`, so the scheduler may
move forward to a fresh H if resources remain. Provider/transport errors, other
`NOT_EVALUATED`, interrupt, unknown, comparator-incomplete or evaluated-without-
formal outcomes stop. Outer hardwall exit 124 terminates children. Shell exit
zero alone is not scientific success; interpretation uses terminal status,
validity, evaluated rounds, last outcome and stop reason.

## Frozen terminal audit and claim boundary

For every observable H session, the terminal audit reports actions in
chronological order. Accepted and incomplete sessions have different evidence
boundaries.

For an accepted H, the durable final response and basis establish the accepted
candidate, actually read refs and cited refs. The audit recomputes that exact
candidate's eligible top-1 from the complete index in the prompt that preceded
the accepted response and verifies read/citation satisfaction. For accepted H
values it reports:

- full index size and eligible-headline count for each otherwise valid finalize,
  plus whether a nearest-history audit triggered;
- each routed required ref, whether it was later read, and whether the accepted
  basis cited it in both required arrays;
- whether the accepted candidate's ref was read preemptively before its first
  valid finalize;
- whether the structured candidate remained equal or changed after an audit
  trigger, and whether recomputation changed the required ref;
- H's own bounded `material_delta` characterization as pivot, refinement or
  other only when that characterization is actually explicit; otherwise
  `not_observable`; and
- direct field equality of the accepted structured H against every supplied
  ordinary prior H, and direct equality of the finalized patch's complete
  ordered change list, including source bytes, against each supplied ordinary
  prior patch. Equality is reported as exact replay; absence of exact equality
  is not a semantic novelty claim.

For an H that does not reach an accepted final response, the audit reports only
actions actually present in durable response traces and tool results actually
present in a later durable prompt trace. If a visible finalize action has no
later prompt that projects the host result, its feedback and routed ref are
exactly `projection_unobserved`, and the session state is
`audit_observation_incomplete`. Offline recomputation may not be substituted for
that missing trace observation, and the audit does not infer a trigger, read,
citation or satisfaction. Such an incomplete H is not included in the
accepted-H read/citation estimand denominator. The report never fills a missing
feedback projection with a guessed ref or a source-derived value.

The preregistration does not name a live top-1 ref, candidate mechanism, target
or patch. Those values exist only after H authors a candidate. The ranker never
upgrades exact or non-exact replay into a host novelty gate. A qualitative
post-hoc direction audit may distinguish a plausible pivot from a refinement,
but it cannot alter the formal result.

The three claim layers are:

1. **Framework.** Provider-/solver-free replay can establish ordering, fixed
   feedback, read/citation enforcement, recomputation, preemptive-read behavior,
   boundedness and non-leakage. A live run may establish its actual observable
   H/C trajectory. Neither proves research-quality improvement.
2. **Research direction.** The accepted H basis, its cited prior, C alignment
   and exact-replay audit support descriptive, tainted direction analysis only.
   M26-to-M27 is non-randomized and non-causal.
3. **Algorithm.** Only complete paired Protocol comparisons support candidate-
   versus-champion claims, and only on this already seen bank. No fresh-
   population, confirmation, generalization, validation, frozen, promotion,
   retained, production-readiness or v0.4-complete claim follows.

Problem-owned family telemetry remains association-only. It cannot prove exact
activation or causality and does not reach Safe Features or Decision. The probe
enum and nearest-history audit likewise never become Protocol evidence.

## Frozen one-shot command

Preparation requires a clean tracked worktree and index, all named inputs and
tests tracked, the fresh M27 root absent, the preserved M26 root readable,
functional bubblewrap and prlimit, provider metadata available, and no
concurrent Scion/candidate run. The replay and sandbox tests below are provider-
and solver-free and confer mechanical evidence only.

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
  docs/experiments/v0.4/inputs/v04-cvrp-m27-m26-terminal-research-input.json \
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
  docs/experiments/v0.4/inputs/v04-cvrp-m27-m26-research-history.jsonl \
  scion/tests/fixtures/m27_nearest_history_audit_replay.json \
  scion/tests/unit/core/test_m27_nearest_history_audit_replay.py \
  docs/experiments/v0.4/v04-cvrp-m27-nearest-history-audit-autonomous-continuation-preregistration-20260821.md
do
  git ls-files --error-unmatch "$INPUT" >/dev/null
done

M26_HISTORY=/home/clawd/research/scion-experiments/v04-cvrp-m26-embedded-falsifier-autonomous-continuation-20260821/research_history.jsonl
M27_HISTORY=docs/experiments/v0.4/inputs/v04-cvrp-m27-m26-research-history.jsonl
test -f "$M26_HISTORY"
cmp -s "$M26_HISTORY" "$M27_HISTORY"
test "$(wc -l < "$M27_HISTORY")" -eq 2
test "$(wc -c < "$M27_HISTORY")" -eq 51034

M27_CAMPAIGN_DIR=/home/clawd/research/scion-experiments/v04-cvrp-m27-nearest-history-audit-autonomous-continuation-20260821
test ! -e "$M27_CAMPAIGN_DIR"
test -x /usr/bin/bwrap
test -x /usr/bin/prlimit

env -i \
  HOME=/home/clawd \
  PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages \
  /home/clawd/miniconda3/envs/claw/bin/python -S -B - <<'PY'
from pathlib import Path

import scion
import scion.cli.commands.init_run as init_run
import scion.config.problem as config_problem
import scion.core.research_history as research_history
import scion.proposal.hypothesis_research_session as hypothesis_session
import scion.protocol.experiment as protocol_experiment
from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.code_research_limits import load_code_research_limits
from scion.core.resource_envelope import ResourceEnvelope
from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)

project = Path("/home/clawd/research/or-autoresearch-agent/scion")
package = (project / "scion").resolve()
assert {Path(origin).resolve() for origin in scion.__path__} == {package}
for module in (
    init_run,
    config_problem,
    research_history,
    hypothesis_session,
    protocol_experiment,
):
    origin = Path(module.__file__).resolve()
    assert origin.is_relative_to(package), (module.__name__, origin)

inputs = project / "docs/experiments/v0.4/inputs"
history_names = (
    "v04-cvrp-m10-m9-research-history.jsonl",
    "v04-cvrp-m11-m10-research-history.jsonl",
    "v04-cvrp-m12-m11-research-history.jsonl",
    "v04-cvrp-m13-m12-research-history.jsonl",
    "v04-cvrp-m14-m13-research-history.jsonl",
    "v04-cvrp-m15-m14-research-history.jsonl",
    "v04-cvrp-m16-m15-research-history.jsonl",
    "v04-cvrp-m19-m16-research-history.jsonl",
    "v04-cvrp-m20-m19-research-history.jsonl",
    "v04-cvrp-m21-m20-research-history.jsonl",
    "v04-cvrp-m22-m21-research-history.jsonl",
    "v04-cvrp-m24-m22-research-history.jsonl",
    "v04-cvrp-m26-m25-research-history.jsonl",
    "v04-cvrp-m27-m26-research-history.jsonl",
)
research_input = init_run._load_research_input(
    inputs / "v04-cvrp-m27-m26-terminal-research-input.json"
)
legacy_problem = config_problem.ProblemSpec.from_yaml(
    str(project / "scion/problems/cvrp/problem.yaml")
)
problem_v1 = load_problem_spec_v1_from_yaml(project / "scion/problems/cvrp/problem-v1.yaml")
problem_spec = legacy_problem_spec_from_v1(problem_v1)
histories = init_run._load_research_histories(
    [inputs / name for name in history_names],
    problem_spec=problem_spec,
)
limits = load_code_research_limits(inputs / "v04-cvrp-m11-code-research-limits.json")
protocol = ProtocolConfig.from_yaml(
    inputs / "v04-cvrp-m24-autonomous-direction-research-development-protocol.yaml"
)
split = SplitManifest.from_yaml(
    inputs / "v04-cvrp-m24-autonomous-direction-research-development-split.yaml"
)
seeds = SeedLedgerConfig.from_yaml(
    inputs / "v04-cvrp-m24-autonomous-direction-research-development-seeds.yaml"
)
envelope = ResourceEnvelope(provider_call_cap=34, outer_hardwall_sec=14000)

assert len(research_input["observations"]) == 6
assert legacy_problem.name == "cvrp"
assert len(history_names) == 14
assert len(histories) == 37
assert len(research_input["observations"]) + len(histories) == 43
assert protocol.screening.n_cases_modify == 3
assert protocol.screening.expand_to_modify == 6
assert protocol.screening.n_seeds == 2
assert protocol.screening.effective_expand_n_seeds == 2
assert len(split.screening) == 6
assert tuple(split.screening[:3]) == protocol.screening.priority_case_ids
assert seeds.screening == [4358, 1868]
assert limits.max_turns == 8 and limits.max_read_calls == 4
assert protocol.screening.require_expanded_for_pass is True
assert envelope.to_primitive() == {
    "provider_call_cap": 34,
    "outer_hardwall_sec": 14000,
}
PY

env -i \
  HOME=/home/clawd \
  PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages \
  /home/clawd/miniconda3/envs/claw/bin/python -B -m pytest -q \
  -p no:cacheprovider \
  scion/tests/unit/core/test_m27_nearest_history_audit_replay.py \
  scion/tests/unit/proposal/test_hypothesis_research_session.py::test_nearest_history_headline_uses_only_index_headline_fields \
  scion/tests/unit/proposal/test_hypothesis_research_session.py::test_invalid_first_basis_cannot_oracle_the_ranked_history_ref \
  scion/tests/unit/proposal/test_hypothesis_research_session.py::test_m24_unseen_nearest_ref_can_be_grounded_and_revised \
  scion/tests/unit/proposal/test_hypothesis_research_session.py::test_arbitrary_history_read_does_not_satisfy_ranked_audit \
  scion/tests/unit/proposal/test_hypothesis_research_session.py::test_ranked_history_must_be_in_both_basis_ref_arrays \
  scion/tests/unit/proposal/test_hypothesis_research_session.py::test_last_shared_read_call_is_reserved_for_unread_history \
  scion/tests/unit/core/test_resource_envelope_boundary.py \
  scion/tests/unit/core/test_resource_envelope.py::test_resource_exhaustion_has_a_nonzero_cli_completion_status \
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
  --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m27-m26-terminal-research-input.json \
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
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m27-m26-research-history.jsonl \
  --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m24-autonomous-direction-research-development-protocol.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m24-autonomous-direction-research-development-split.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m24-autonomous-direction-research-development-seeds.yaml \
  --time-limit-sec 30 \
  --provider-call-cap 34 \
  --outer-hardwall-sec 14000 \
  --rounds 2 \
  --campaign-dir "$M27_CAMPAIGN_DIR"
```

The user's standing authorization permitted this exact live command once only
after the preparation carrier was committed, the provider-/solver-free
preflight and two independent scientific/runtime reviews passed, the tracked
tree remained clean and the output root remained absent. Those gates passed
before the single now-terminal invocation. Creation of the root consumed the
one-shot; there is no retry, resume, repair launch or root reuse.

No distribution, packaging, build, deployment, root/systemd, Trust/Hash
authority, object identity, lease, signing, registration, duplicate-control or
automatic next experiment is part of M27. Any M28 requires a separately
reviewed design and new authorization.
