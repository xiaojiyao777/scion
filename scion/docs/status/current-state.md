# Scion Current State

*Current as of: 2026-11-15*

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
bounded H→C handoff, resources/failures and prospective authority changes.
Its companion acceptance design separates engineering, real research process,
controlled mechanism effect and independent algorithm benefit. A/B/C distinguish
observation from cross-attempt material continuity. These are reviewable design
drafts, not implemented capabilities, empirical acceptance or launch instructions.
The latest user request authorizes publishing the `v0.4` stage tag, integrating
into the default branch and entering `codex/v0.5-dev`. The verified remote default
is `master`, not `main`/`mian`. The runtime remains v0.4 direct-v3; detailed contract
adoption and V3/addendum alignment precede implementation. The old June Evidence
Uplift roadmap is explicitly superseded by this direction.

## Checkout and R26 terminal

- Publication entry: branch `v0.4-dev`, `c82b77ef`, equal to freshly fetched
  `origin/v0.4-dev`, with sixteen preceding documentation edits preserved.
  Remote `master` is `bafb74a0`, an ancestor of the development line; no divergent
  mainline changes or existing `v0.4` tag were found. Commit/tag/merge/push are
  explicitly authorized by the latest request. Recheck Git/tmux at the next entry.
- All listed experiment tmux panes are dead. R26's pane has a blank exit-status
  field; JSON/metrics establish scientific completion independently.
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
- H has no pre-hypothesis empirical observation tool. C's isolated falsifier
  returns bounded test outcomes rather than general measurement data. Research
  scripts, observations and unresolved questions have weaker continuity than
  source. These are the main proposed v0.5 topics.
- R26 reports about 21.47 million cumulative provider input tokens. Its H index
  carries full hypothesis prose and is repeatedly transmitted. This supports
  studying lossless context representation, not causal attribution of failure
  or permission for top-k, truncation or summary substitution.
- `OperatorConfig`, `ChampionState.operator_pool` and legacy configuration remain
  separate debt; do not extend their algorithm-shaped schema. Historical full
  source retention is limited. Future parent comparisons need actual ordinary
  source preservation, without identities or executable reconstruction.

## Verification and next work

November 14 ran read-only artifact/source calculations and documentation checks;
November 15 adds accepted stage closure, detailed v0.5 design/acceptance,
source/boundary review and link/diff validation.
Neither ran a provider, solver, regression suite or new scientific experiment.
Last recorded shared-runtime full suite: P16, **2678 passed / 1 skipped**,
runtime `6380a59e`. R26 prelaunch recorded 142 focused regressions and optional
example checks. These are historical validation, not new results.

Use `env PYTHONPATH=scion:. /home/clawd/miniconda3/envs/claw/bin/python`
from the repository root for future tests. Shared-boundary changes require
appropriate focused/full checks and a prospectively specified cross-problem
control; ordinary CVRP work does not always require Warehouse first.

Next work is review/adoption of the detailed contracts, followed by separate O
(observation) and M (materials) slices and a fully specified comparison, as
tracked in [`TASK.md`](../../TASK.md). This documentation task has not implemented
or launched them. Earlier P0–P23 chronology
remains in Git at `c82b77ef` and the [experiment index](../experiments/v0.4/README.md).
This snapshot replaces accumulated launch logs, not scientific evidence.
Distribution, deployment, packaging, build, services, Trust/Hash authority,
identity, leases, signing, registration, receipts, duplicate closure,
host-selected mechanisms and new quality gates remain excluded.
