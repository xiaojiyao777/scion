# Scion Current State

*Current as of: 2026-11-21*

Enter through [`../../../AGENTS.md`](../../../AGENTS.md), then read
[`../AGENT_ONBOARDING.md`](../AGENT_ONBOARDING.md), this snapshot,
[`../../TASK.md`](../../TASK.md), and the selected reading profile in that order.
The sole architecture authority is
[Architecture V3](../../design/scion-architecture-v3.md);
the [direct-runtime addendum](../../design/scion-architecture-v3-v0.4-direct-runtime-addendum.md)
describes the current v0.4 implementation.

## Current direction

The November 14 user request changes the immediate priority from repeated
support repair / fresh campaign cycles to a stage retrospective and deep review
of Scion's research mechanism. The
[stage review and v0.5 proposal](../planning/v0.4/v04-stage-review-and-v05-research-mechanism-proposal-20261114.md)
is complete. On November 15 the user explicitly accepts the main direction:
**让 agent 围绕一个持续的算法问题，自主观察、实验、修正解释，再提交正式 H/C。**
The subsequent November 15 request explicitly accepts the M1–M5 stage-closeout
standard and asks to close v0.4 while carrying the CVRP scientific objective
forward. **v0.4 mechanism stage is now closed; original scientific success
acceptance is partially met.** Warehouse retained improvement is accepted;
CVRP retained improvement remains unconfirmed. No R27 is needed for this project
stage decision, and no old scientific result or success criterion is rewritten.

The [v0.5 detailed design](../../design/v0.5/README.md) now covers sustained
questions, separated subject/analysis observations, ordinary research materials,
bounded H→C handoff, resources/failures and explicit authority changes.
Its companion acceptance design separates engineering, real research process,
controlled mechanism effect and independent algorithm benefit. A/B/C distinguish
observation from cross-attempt material continuity. V3 now adopts the explicit
public-research extension. P1/P2 provide execution; P3 now integrates O into the
existing H/C sessions behind explicit opt-in. P4 adds M material continuity;
P5a adds diagnostic tasks, bounded study design and offline assessment tooling.
The preceding November 15 request explicitly authorizes the fixed P5b real-provider
matrix. It is now terminal; its actual evidence does not satisfy E2, and independent
second reviews remain pending. E3/E4 were not run.
[P5c](../../design/v0.5/v0.5-p5c-question-session-and-materials.md) A/B implemented
test readback, actual source retention and continuity. The preceding November 21 request
advanced C: V3 first adopted explicit investigation lifecycle semantics, then code
added continuing-question context and an H-only typed conclusion. Zero-formal
investigation is allowed; a conclusion never creates H/C, Protocol or Decision.
Q11–Q15 focused validation covers both real problem runtimes, fault precedence and
old-mode compatibility. Full-suite results and all earlier failures are below.
The November 21 P5d provider batch closed on the first H request. The frozen
proxy returned HTTP 401 in cvrp-01. The CLI recorded blocked infrastructure and
exited 20. The remaining seven slots are individually recorded as not_run under
the preregistered authentication rule. There was one dispatch, zero successful
model turns, zero H/C exports and zero formal stages. Neither 01→03 import nor
either open investigation ran. Two independently prepared AI reviews agree on
all five rated dimensions. Their 91 citations were checked against the originals.
E2 and voluntary no-candidate termination lack behavioral evidence in this batch. [Postrun and review records](../experiments/v0.5/v05-p5d-e2-postrun-20261121.md)

**v0.5 is now the active design/development stage on `codex/v0.5-dev`.** The
`v0.4` stage tag and integration into the remote default `master` have been
published as explicitly requested. The default remains the existing direct-v3 path. Explicit `public_research`
configuration enables independent O/M capabilities in bounded sessions; both default off.
The old June
Evidence Uplift roadmap is explicitly superseded by this direction.

## Checkout and R26 terminal

- Published closeout: annotated `v0.4` points to `eb339d32`; `v0.4-dev` stops at
  that documentation closeout. `master` merge `6befa390` has the exact tag tree.
  The two branches and tag were pushed atomically to origin. The actual remote
  default is `master`; no `main`/`mian` branch was created or renamed.
- Active branch: `codex/v0.5-dev`, created from `6befa390`; its initial change
  records the v0.5 development handoff. The worktree now includes P0/P1 design
  and the P1/P2 execution backend, P3/P4 session/material integration, P5a offline
  task/assessment tools and P5c A/B/C materials and explicit investigation; disabled
  campaign behavior remains the audited direct-v3 path. Recheck live Git/tmux
  at the next entry rather than treating this document as live process state.
- Historical experiment tmux panes and all eight P5b panes are dead; P5b results
  are recorded below. The latest live check shows R26 exit 0; JSON/metrics
  establish scientific completion independently.
- [R26 terminal audit](../experiments/v0.4/v04-cvrp-r26-scope-and-net-benefit-autonomous-postrun-20261114.md):
  completed / valid / requested_rounds_completed at **October 29 14:30:25
  Beijing** (06:30:25 UTC). Twelve screening stages, nine evaluated candidates,
  three expansions and one additional Code abandonment; 324 valid pair rows /
  648 sides. No validation, frozen or promotion; champion v1 unchanged.
- All 162 provider calls succeed on attempt 0; 438/600 calls remain. No recorded
  quota, provider, global-resource, solver, feasibility or fleet failure.
  All twelve aggregate case-median effects are zero; three initial signals fail
  expanded screening. Negative/uncertain evidence is preserved.
- A1 has a real nonempty cache publication/reuse probe. Final A4 has a real
  changed-path two-opt gain and final-retention witness on a synthetic instance.
  These are actual research progress, not proof of net timed advantage over the
  inherited algorithm. Missing real-path probes no longer adequately explain R26.
- Initial 100 files, 395 non-null editable C source bodies and three surviving
  complete final heads match. Six superseded evaluated heads have ordinary
  in-memory patch fallback only. All 648 progress rows and 1,023 recorded best
  updates retain their gains; no best-return repair is supported.
- Audit scope includes pair grids/objective differences/medians and recorded
  stage results, not a new bootstrap/Contract/Verification execution or a full
  public/private projection audit. Exact limitations and raw refs are in the postrun.

Exact R26 root:
`/home/clawd/research/scion-experiments/v04-cvrp-r26-scope-and-net-benefit-autonomous-20261028`.
Read its [status](/home/clawd/research/scion-experiments/v04-cvrp-r26-scope-and-net-benefit-autonomous-20261028/status.json)
and [summary](/home/clawd/research/scion-experiments/v04-cvrp-r26-scope-and-net-benefit-autonomous-20261028/campaign_summary.json),
then only the metrics/traces/sources needed for the bounded task.
The [preregistration](../experiments/v0.4/v04-cvrp-r26-scope-and-net-benefit-autonomous-preregistration-20261028.md)
preserves its `1d9845db` plus uncommitted-at-launch provenance and subsequent
publication as `c82b77ef`. Original inputs, labels and artifacts remain unchanged.

## Scientific checkpoint

Warehouse's previously accepted evidence remains:
[synthetic continuous campaign](../experiments/v0.4/v0.4-warehouse-v3-continuity-synthetic-36stage-r8-postrun-20260808.md),
[independent replay](../experiments/v0.4/v0.4-warehouse-v3-continuity-r8-heldout-replay-postrun-20260809.md),
[production transfer](../experiments/v0.4/v0.4-warehouse-v3-production-transfer-prod12-24stage-r1-postrun-20260809.md),
and [production replay](../experiments/v0.4/v0.4-warehouse-prod12-independent-heldout-v1-postrun-20260809.md).
Synthetic v1→v2→v3 and production-style v1→v2 retained improvement are accepted.
Those historical raw runs were not reaudited this turn.

CVRP remains open:

- [R3i](../experiments/v0.4/v04-cvrp-r3i-long-run-adaptive-history-postrun-20260904.md)
  promoted a cumulative bundle; the
  [R4 independent B0 check](../experiments/v0.4/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-postrun-20260905.md)
  did not confirm retained superiority. Promotion and retention are distinct.
- [R20](../experiments/v0.4/v04-cvrp-r20-r19-final-b0-fixed-postrun-20261009.md)
  passed screening against B0-fixed but had uncertain validation. B0-fixed
  includes the separately labeled constructor engineering repair; it is not
  unchanged original B0.
- [R22](../experiments/v0.4/v04-cvrp-r22-retained-path-autonomous-postrun-20261018.md)
  C3 and [R23 local confirmation](../experiments/v0.4/v04-cvrp-r23-r22-final-local-fixed-postrun-20261024.md)
  showed positive case signals but adverse/uncertain full-population effects.
- [R24](../experiments/v0.4/v04-cvrp-r24-stable-advantage-autonomous-postrun-20261026.md),
  [R25](../experiments/v0.4/v04-cvrp-r25-counterfactual-evidence-autonomous-postrun-20261028.md)
  and R26 use unchanged complete R22 C3 as local comparator. R24 A2 passes
  expanded screening but not validation; R25/R26 have zero aggregate effects
  at every stage. These are not original-B0 contrasts.

The complete C3 baseline is preserved at
`/home/clawd/research/scion-experiments/v04-cvrp-r23-r22-final-local-fixed-20261018/input_snapshots/candidate`.
Using it as a fresh baseline confers no promotion or retained-improvement status.
Known screening populations are adaptive; expansions rerun initial cells and
ordinary autonomous order is champion-first. Do not pool those rows or equate
fresh seeds with unseen cases. Private later-stage results stay out of H/C.

## Current runtime and research gaps

- Core is problem-neutral; problem packages own algorithms, objectives,
  feasibility, research surfaces, public support and telemetry meanings.
- Complete verified branch trees support successive attempts, including after
  scientific screening fail. Incorrect code cannot become an executable head.
  Stale reconciliation uses the existing tree, not patch replay or merging.
  Held-out stages reuse the exact candidate.
- H can read/search safe source and history. C can read/search/revise/test/ready
  after H approval. One attempt exports at most one H and one bound C;
  successful ready exports immediately. Open drafts may be revised; exported
  proposals and terminal campaigns cannot be repaired or resumed.
- SDK retry is zero. Explicit charged redispatch handles typed transient errors;
  usage-quota exhaustion stops in the resource lane. Attempt-local research
  rejection does not count as a formal evaluated round. Transcript total size
  has no default lifetime cap; explicit limits cannot rank mechanisms or
  silently truncate context.
- Contract, Verification, Protocol, held-out isolation and deterministic Decision
  remain necessary. Diagnostic prose and research quality add no promotion gates.
- With explicit O enabled, H can observe current source before export; C can
  observe its approved base/draft and read selected H handoff plus its own materials.
  Observation cannot establish readiness or clear the exact-falsifier veto.
  With M, subsequent H can read the full closed-session public corpus and explicit
  imports; C still has no general history access.
- R26 reports about 21.47 million cumulative provider input tokens. Its H index
  carries full hypothesis prose and is repeatedly transmitted. This supports
  studying lossless context representation, not causal attribution of failure
  or permission for top-k, truncation or summary substitution.
- `OperatorConfig`, `ChampionState.operator_pool` and legacy configuration remain
  separate debt; do not extend their algorithm-shaped schema. Historical pre-P4 full
  source retention is limited. P4 now saves actual complete trees before cleanup;
  it does not reconstruct the missing historical R26 trees.

## Verification and next work

The subsequent v0.5 design review at clean `6ef924e6` checks the full V3 blueprint
and addendum against the mechanism and acceptance drafts. The research direction
is aligned, while H execution and C material exposure require explicit contract
extensions. The [module plan](../../design/v0.5/v0.5-v3-alignment-and-module-plan.md)
defines P0–P7 design exits, dependencies and validation evidence; progress stays in
TASK. The subsequent [P0](../../design/v0.5/v0.5-p0-interface-and-boundary-contract.md)
and [P1](../../design/v0.5/v0.5-p1-public-problem-execution.md) designs now specify
action/provider/runner/checker interfaces, permissions, failure routing and
numbered cases. Formal evaluation parameters remain unfinished. Acceptance includes capability-off compatibility, source changes,
bounded open-solver research and the correct bundled O-effect interpretation.
The preceding requests adopted V3 and P1b/P2/P3/P4; the current request advances P5.
V3 now contains the scoped public-research extension; the addendum retains its
v0.4 scope. The [P2 contract](../../design/v0.5/v0.5-p2-isolated-observation-execution.md)
specifies source/config copying, exact mounts, independent runner/checker/analysis,
output handling, accounting, material access and S01–S12 cases.

Implemented backend: pure provider contracts and strict input validation; actual
CVRP/Warehouse entries; source/config snapshots; separate frozen checkers;
bubblewrap/seccomp isolation; single-process wall/CPU/AS/output/scratch limits;
shared resource accounting; ordinary persisted outputs and exact byte paging/
literal search. CVRP failure does not fall back; Warehouse binds the selected
registry/config. The 12/14 distance and 800-cost references now have isolated
execution evidence. These are engineering examples, not algorithm improvements.

Real tests exposed default bubblewrap wait4 CPU undercounting; `--as-pid-1`
fixes this for the explicitly single-process backend, verified with a busy loop.
AS is not RSS; peak rusage includes the launcher, and tmpfs has no independent
inode/kernel-memory quota. The P2 contract records these actual limits.
P3 now wires the backend through Campaign composition → ProposalPipeline → the
existing bounded H/C sessions. Its [contract](../../design/v0.5/v0.5-p3-session-permissions-and-handoff.md)
was written before implementation and indexed from V3. Permissions select H current
or C base/draft; draft safety and approved-H action/target/surface checks run before
execution. Existing workspace configuration synchronization is reused. Protocol
exclusions include the actual SplitManager, supplied manifest, public/source roots,
canary and explicitly supplied configuration files; every copied closure is checked.
Only safe metadata/indexes and scoped byte reads enter provider projections. H
freezes explicitly selected files before export; ExploreStep passes them to C only
after H Contract acceptance. New tool bodies stay in a separate user data block.
Local/global resource, infrastructure, internal and interruption routes remain typed.
No new Decision writer or readiness rule is added; positive observation cannot clear
failed falsifier evidence. With M disabled, session closure preserves files but grants no next-attempt
visibility. The same backend counters span all H/C sessions of a fresh campaign.
CLI `--public-research` accepts strict config/budget JSON alongside explicit
`--code-research-limits`; omitted/disabled configuration resolves no provider and
adds no proposal fields. Source/config
copies, configuration.json, per-stage records and session index/usage samples are
ordinary audit files, not identities or permission receipts.
P4's [contract](../../design/v0.5/v0.5-p4-material-continuity.md) and V3 extension
were written before implementation. `ResearchContinuity` publishes closed H/C
files into an ordinary complete public index; later H reads them, C remains scoped.
Fresh imports copy only explicitly indexed public bytes with separate namespaces,
retaining original references and explicit missing dependencies. Imports do not
restore source, branch, provider, budgets or stage state. M-only supports material
write/read/search while observe remains disabled; either capability needs explicit
resources and problem-owned public declarations.

Actual complete trees are saved privately before old-head cleanup. Only declared
source projections are indexed for H, with distinct retained/projection-only/
unavailable labels. Workspace retention failures preserve old bytes and completed
Decision, record a material fault and block later research dispatch. Failed drafts
stay evidence; notes and imported promotion claims cannot select an executable head.
All material work shares existing wall/CPU/storage budgets. Full initial/parent
copies can need larger explicit source/file/storage limits than O-only observations.
No historical source is reconstructed from patches.

All preceding worktree changes at `6ef924e6` were preserved. This step uses the
Code Repair Or Feature Work profile plus full V3/addendum, active mechanism and
acceptance contracts, and current observation/proposal/workspace/Decision sources.
No historical experiment roots were loaded.

Use `env PYTHONPATH=scion:. /home/clawd/miniconda3/envs/claw/bin/python`
from the repository root for future tests. Shared-boundary changes require
appropriate focused/full checks and a prospectively specified cross-problem
control; ordinary CVRP work does not always require Warehouse first.

P4 non-slow regression: **2941 passed / 1 skipped** (611.74 s), using
`-m 'not slow' scion/scion/tests`. Final focused regression: **253 passed**
(11.30 s), covering all 34 material-continuity cases, P3 permissions/materials,
H/C sessions and direct proposal transitions. The final focused run covers the
last imported-script UTF-8 refinement made after full-suite collection: invalid
script bytes now produce INPUT_INVALID feedback without a process launch or
session termination; original bytes remain readable. This refinement and its
new test are not claimed as part of the preceding full-suite collection.

Both real problem outer chains pass with O-only and O+M, including explicit fresh
imports, H Contract rejection and unchanged formal counting. Fixture scripts select
only current-H files for handoff; an earlier full run correctly rejected scripts
that selected imported old notes, and the three corrected cases passed separately
(67.74 s) before the successful full run. Actual Decision/Workspace tests confirm
that material faults preserve the Decision, accepted head and old source bytes.
Documentation checks: 16 changed Markdown files, 153 local links with no broken
targets; `git diff --check` passed. Historical P3 non-slow validation was 2905
passed / 1 skipped (545.22 s); it is superseded by the P4 evidence above.
These are engineering fixtures/scripted providers, not E2 real-agent research,
E3 mechanism effects or E4 independent retained algorithm gains.

P5a's [design](../../design/v0.5/v0.5-p5-process-assessment.md) preceded implementation.
The [task package](../../experiments/v0.5/p5/README.md) contains six diagnoses across
CVRP/Warehouse, separate evaluator answers, two open-solver slots and complete
development resource configurations. Local benefit, no benefit and invalid transfer
are distinguished from full-solver evidence. Eight slots allow at most 672 physical
calls / 7 hours outer wall / 3480 seconds public-research CPU / 7 GiB research
materials, with no budget transfers or external confirmation looks. These are
feasibility caps, not E3 power/sample-size claims; actual launch records are now
frozen separately for P5b. Public task export keeps synthetic examples in ordinary question text,
not the existing problem-specific prior-observation schema.

`scion/tools/p5_assessment.py` is operator-side only: public-only export, empty
eight-slot review template, strict coverage/cost/reference validation, and preserved
independent ratings/disagreements. It cannot establish evidence meaning, provenance
or chronology and never produces an automatic E2 pass or runtime Decision.
P5 focused validation: **74 passed** (2.05 s): 61 new P5 cases plus 13 existing
research-input cases. All 12 reference solutions use actual isolated frozen checkers;
two actual solver/runner checks execute the public inputs. No core, adapter,
scientific gate or session runtime code changed in P5; this does not replace or
claim a new full-suite result beyond the historical P4 regression above.
CLI diagnostic/open export, template and review checks also pass; an empty template
retains all eight not_run slots. P5a's documentation checks covered eighteen Markdown
files and 169 valid local links, with `git diff --check` passing. P5a used Code Repair Or Feature Work,
full V3/addendum, active v0.5 contracts and the experiment runbook; no historical
raw experiment roots were loaded.

P5b ran under explicit authorization from a frozen ordinary source copy;
see the [preregistration](../experiments/v0.5/v05-p5b-process-study-preregistration-20261115.md).
Study root: `/home/clawd/research/scion-experiments/v05-p5b-process-study-20261115`.
`run-plan.json` fixes all eight argv/env/input records and `preflight-results.json`
confirms CLI parsing, formal file availability and public-closure exclusions.
All eight slots are terminal as of 06:08:04 UTC: seven completed their formal targets;
warehouse-02 exhausted its 48-call cap before evaluation. All 298 calls returned on
attempt 0; no provider errors, replacement runs or scientific interventions. Eleven
formal stages retain 214 valid pair rows and zero failed pairs; expanded rows overlap.
All champions remain v1. open-cvrp failed expanded screening and its next candidate's
screening; open-warehouse passed screening/validation but failed frozen with unclear
evidence. The
[process/results record](../experiments/v0.5/v05-p5b-process-study-postrun-20261115.md)
preserves the full matrix, positive/negative evidence and single-review limitations.
All slots use `gpt-6.1-sol/high`, no redispatch, default source snapshots and the P5a
caps. Existing CVRP staged time overrides were explicitly replaced in this study's
Protocol copies with 1/5-second budgets; algorithm/gates remain unchanged.
No observe action occurred. No imported/prior-attempt material was read; current
source projections, current inputs and own-session notes are not continuity witnesses.
CVRP's second H correctly used legacy formal history and checked the fresh branch's
actual source. Warehouse abandonment exercised complete source retention before cleanup.
These positive findings do not establish the new O/M research loop. P5b's frozen
test_patch did not return its script as readable research material; a real trace
reports that gap after a failed probe. Wrong self-authored reference assertions
also occurred. P5c A's later change does not retrospectively repair those traces.

Eight-row configuration/data/source audit and 60 original-byte citations passed offline
checks. Formal data resolves through frozen data roots or byte-equal workspace/retained
copies; generated cache files are disclosed. There is one non-blinded review per slot,
not two independent reviews. P5b changed no production code and did not rerun the P4
suite. E2 is not met; E3/E4 and CVRP retained gains remain unconfirmed.
P5c A now integrates `observation/development_materials.py` with the existing C
session. Before a test it saves exact UTF-8 script bytes, every requested draft
file and ordinary request metadata; after the original bounded feedback and veto/
ready calculation it saves the finite result. Both refs are readable by existing
tools. Raw callback logs, host paths and private suites are not exposed. O/M off
retains the old path; M-only does not launch observe. Own-C / later-H permissions
and ordinary import follow P4. Request-only source projections cannot change head.

Preflight reserves requests, bounded results and two index writes. Automatic
material writes charge host CPU/wall/storage without another provider/public
action. Callback wall remains in the existing test budget; child CPU is null with
an explicit not-measured reason. Request-write failure prevents execution;
result-write failure prevents further dispatch/ready. Callback errors/interruption
retain the request and available bounded record, with primary failures preserved.

Q01–Q07 mapping is in the [P5c contract](../../design/v0.5/v0.5-p5c-question-session-and-materials.md).
Focused verification: **203 passed** (15.27 s), covering the 34 new material cases,
P3 permissions, P4 continuity and existing CodeResearchSession behavior. This
includes one real isolated failed probe; the rest use controlled callbacks or
scripted providers as appropriate. Full non-slow regression: **3036 passed /
1 skipped / 1 failed** (640.58 s), using
`env PYTHONPATH=scion:. /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q -m 'not slow' scion/scion/tests`.
Both real problem outer chains pass, including reading actual development feedback
before ready, H Contract rejection and unchanged formal counts.

The failure is
`unit/test_development_probe_diagnostic.py::test_public_cvrp_example_runs_real_source_without_framework`:
the unchanged public CVRP example's probe line 341 requires a real VNS call within
its .35/1.4-second instrumented fixture budgets. This path directly invokes the
existing sandbox/example and does not use P5c A material capture. Its isolated
rerun passed (**1 passed**, 9.23 s). Timing sensitivity is a plausible explanation,
not a confirmed root cause; the full-suite failure is retained, not relabeled as
an all-green run. The example, solver and assertion were not changed. The bounded
follow-up covering `unit/test_development_probe_diagnostic.py`,
`unit/test_code_development.py`, `unit/test_code_development_redteam.py` and
`test_development_test_materials.py` passed: **128 passed** (33.02 s), including
that same example. No further repeat was needed to validate the affected boundary.

P5c B now wires the actual evaluator scratch into a host-only capture callback
after safety preflight, before the probe and before host checks. The latter stage
includes the copied suites only in a private audit tree. Public entries expose
only the existing C algorithm inventory and declared public dependencies, with
original formal paths remapped into scratch before no-link projection. Missing
files are not reconstructed from patches or another observation tree. Capture
failure prevents that stage from executing; completed earlier stages remain.
Result `tested_source_refs` points to at most two stage records with
`source_kind=development_draft`, `capture_scope=public_test_source` and
`captured_before_execution` (not a claim that a process started). Request originals
and historical A records stay request_only. Neither projection is a full ordinary
algorithm workspace or a verified head. P4 publishes source dependencies to later
H/fresh imports; missing imports are unavailable, never executable source fallback.
Material CPU/wall/storage are charged; capture time is also inside the unchanged
test deadline, so the two wall figures overlap and must not be summed. Child CPU
remains explicitly not measured. Existing veto/ready ordering is unchanged.

B validation: `test_development_source_materials.py` has **17 passed** (8.86 s),
covering Q08–Q10. The expanded focused run had **319 passed / 1 failed** (182.55 s):
the new preflight fixture used an invalid reason enum, which the existing safe
feedback validator correctly rejected. Changing the fixture to `source_frozen`
produced the 17-pass result above; no production whitelist was widened. Those 319
passes include A, permissions, continuity, C sessions, development/red-team/probe
diagnostics and both real problem outer chains (Q15). An earlier incremental run
had **64 passed / 4 failed** (150.92 s): already-loaded outer assertions still
expected request_only after B produced public_test_source; the updated Q15
assertions also compare actual saved patch bytes and passed in the expanded run.
An additional Q10 readback check explicitly verifies the original script, bounded
result and source-condition bytes in both later H and fresh import: **1 passed**
(1.68 s). Seven touched Python files parse without trailing whitespace; all 102
local links in the six updated Markdown documents resolve; `git diff --check` passes.
Full non-slow B regression: **3054 passed / 1 skipped** (641.30 s), using the same
`env PYTHONPATH=scion:. /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q -m 'not slow' scion/scion/tests`
command. The unchanged CVRP timed public example passed in this run. This does
not erase A's earlier failure or establish its root cause. No solver/probe assertion,
timeout or production feedback/veto rule was relaxed to obtain this result.

P5c C (November 21) implements the V3-adopted optional `run_intent=investigation`
with a nonnegative `formal_stage_limit`, ordinary current-question context and
shared provider/wall/observation/material limits. Default formal_target retains its
round target and rejection loop. Zero formal capacity hides and rejects H export;
an open H may return a bounded reason and only its own note refs through
`conclude_research`. No mandatory observe/note/frontier review is added to that
non-proposal action; actual H export keeps its existing checks. C cannot conclude,
and ready still returns immediately with the original exact-falsifier veto.

The reason and note dependencies are ordinary material. The body address survives
index/publication failure; normal completion requires successful closure and no
higher-priority fault. `RESEARCH_CONCLUDED` has no H, failure fields, Contract,
Verification, Protocol or Decision. The loop counts zero formal delta, preserves
existing Decisions and complete heads, reports pending work as not_executed and
uses the existing terminal drain. Signal/exception finalization retains saved
conclusion refs even between closure and typed return. One CampaignRunResult drives
status and summary. Completed invocation is not scientific completion: zero formal
stages still report invalid_no_evaluated_outcome. No terminal resume is added;
fresh import treats a conclusion as ordinary notes only. CLI keeps its existing
signal hardwall; direct Python API checks deadlines at dispatch/loop/finish and
cannot preempt an in-flight host call.

C validation: the final bounded H/public-session/core set has **202 passed /
4 deselected** (18.71 s; the four expensive formal-chain cases are separate).
The supplementary CLI/signal/proposal-route set has **96 passed / 4 deselected**
(15.30 s). The final write/index/close/resource/stop and post-close interruption
checks have **9 passed / 41 deselected** (7.44 s). Both CVRP and warehouse also
passed each actual H/C→Verification→Protocol→Decision→formal-cap/conclusion chain
in the expanded focused run below. These use scripted providers and real problem
runners, not autonomous E2. The final test file has 52 cases, including O-only,
M-only and O+M zero-formal runs and the real CLI path.

Development failures remain explicit: initial focused checks had **149 passed /
2 failed** (5.58 s), exposing the intentionally changed run signature and an
unwanted zero conclusion key in old-mode reports; the latter was fixed to retain
old report shape. The first new bounded run had **19 passed / 15 failed /
2 deselected** (9.50 s): test refs/feedback locations were wrong, and the new
StepRecord omitted required fields. After those changes, **183 passed / 4 failed**
(85.64 s), plus an isolated **1 failed / 32 deselected** (1.11 s), exposed the old
record invariant that treated every no-H result as failure. The typed conclusion
exception now explicitly forbids H/scientific results/failure fields; other
failure constraints remain intact. The next expanded set had **189 passed /
5 failed** (156.33 s), including the four real formal-chain passes: four new
fixtures imported a wrong helper, tried reading a closed session or expected
quota to be infra instead of resource; the generic enum roundtrip also needed a
no-H conclusion fixture. A bounded follow-up had **38 passed / 5 failed /
4 deselected** (14.50 s), including those fixture issues and a new ready fixture
without a test callback. The fixture errors were corrected, no production quota,
closed-session, veto/ready or scientific rule was weakened. Final checks above
cover the corrections; A/B failure records remain unchanged.

A read-through of terminal serialization found that the old proposal-redaction
helper would label a valid no-H conclusion as a failure in summary step rows.
The first full-suite run was deliberately interrupted after **276 passed**
(98.22 s; no failed test) to fix that reporting path before final regression.
The six two-problem O/M zero-formal cases now explicitly check null failure fields
and the saved conclusion ref in summary steps: **6 passed / 44 deselected**
(3.69 s). This is a reporting correction, not a change to failed proposal redaction.

A subsequent lifecycle read-through found that the new single-step terminal guard
needed to preserve the loop's existing nonterminal stale/reconcile exceptions.
The next full run was stopped deliberately after **277 passed** (177.11 s; no
failed test). The guard now shares the existing housekeeping predicates instead
of treating those NOT_EVALUATED records as terminal. Two new cases exercise real
investigation after each housekeeping result; the final bounded lifecycle/core
set has **114 passed / 4 deselected** (17.40 s). No scheduler priority, stale
reconciliation or source-selection rule changed.

C full non-slow regression: **3114 passed / 1 skipped** (784.60 s), using
`env PYTHONPATH=scion:. /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q -m 'not slow' scion/scion/tests`.
This final run includes all 52 C cases, both real problem formal chains, the
stale/reconcile compatibility checks, summary-step projection and related A/B,
source, permission, veto/ready, CLI and formal-boundary regressions. The unchanged
timed CVRP example passed this run; that does not erase A's earlier failure or
establish its cause. All 18 touched Python files parse, all 160 local links in the
11 updated documents resolve, and `git diff --check` passes.

The independent second review of P5b remains pending. E2, E3/E4 and the CVRP
scientific objective stay open. This step followed Code Repair Or Feature Work, full V3/addendum and the
P5c contract before edits. No raw historical experiment roots, live provider calls
or new scientific campaigns were added. Existing P0–P5 changes remain intact;
publication of the completed implementation and P5d record followed in the
v0.5 development branch. The P5d freeze and terminal batch are reported above.
No automatic rerun or larger P6 study follows. Earlier P0–P23 chronology
remains in Git at `c82b77ef` and the [experiment index](../experiments/v0.4/README.md).
This snapshot replaces accumulated launch logs, not scientific evidence.
Distribution, deployment, packaging, build, services, Trust/Hash authority,
identity, leases, signing, registration, receipts, duplicate closure,
host-selected mechanisms and new quality gates remain excluded.
