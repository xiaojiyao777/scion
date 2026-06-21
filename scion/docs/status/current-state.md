# Scion v0.4 Current State

Last updated: 2026-06-21

This file is the operational resume point, not a run log. Replace stale facts
instead of appending history. Put detailed repair evidence in focused
experiment reports, keep sparse milestones in `v0.4-history.md`, and use git
history when exact old chronology is needed.

## Operating Frame

- Branch: `codex/v04-evidence-repair-plan`.
- Boundary authority: `scion/design/scion-architecture-v3.md`.
- v0.4 closes only after Scion demonstrates effective research behavior:
  warehouse should recover useful continuous optimization from champion `v2`,
  and CVRP/VRP should produce evidence-backed solver-design follow-up.
- v0.5 is for broader experiment matrices. Do not defer v0.4 framework
  stability, prompt/context quality, runtime semantics, or effective-agent
  research to v0.5.
- Current posture: avoid broad budgets, generic truncation/compression, and
  decorative gates. Keep CVRP/warehouse semantics problem-owned and keep
  `DecisionFeatures` problem-neutral.

## Current Decision

- Framework/readiness/launcher repairs are accepted enough for focused
  warehouse and CVRP follow-up.
- v0.4 is not closed until a fresh current-run-ready campaign proves effective
  research behavior. Warehouse has now shown effective research movement; CVRP
  still needs a solver-design improvement or evidence-backed follow-up result.
- WSL `gpt-5.5` auth is no longer the active blocker. Strict readiness passed
  for the latest warehouse rerun before launch.
- Latest accepted prompt/source visibility repair: local commit `774c981d` /
  WSL commit `a9a537c4` removes active-subject code-constraint prompt
  truncation, counts cross-branch/branch-lesson sections as
  `cross_branch_lesson` signal, and requires hypothesis target-source
  visibility only when a target-intent preflight or required target source is
  actually present. This stays in proposal/postrun audit paths and does not
  change Decision, scheduler, promotion, or Protocol inputs.
- Existing protected-case and calibration guards remain in force: CVRP
  CMT2/CMT4 review-ready evidence must carry numeric objective/distance deltas,
  and calibration provenance remains proposal-visible summary material, not
  Decision input.

## Active WSL Roots

Use WSL for launches and postrun checks:

- WSL repo: `/home/xjy-ubuntu/research/or-autoresearch-agent`
- WSL Python: `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`
- WSL experiment root: `/home/xjy-ubuntu/research/scion-experiments`

Warehouse evidence root:

- `/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-33f0e976-transfer-6r-gpt55-20260621T183412Z-claw`
- Campaign completed 6 effective rounds from champion `v2`, reached champion
  `v3`, and produced two promotion dossiers. Campaign status is valid and
  stopped by `max_rounds_exhausted`.
- Wrapper/postrun status is intentionally not accepted as current-run-ready:
  the run exposed pre-repair prompt visibility failures
  (`active_subject_code_constraints` truncation and missing cross-branch
  signal accounting). Treat it as positive research evidence, not final v0.4
  postrun-acceptance proof.

Active CVRP root:

- `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-26a03547-calprompt-4r-gpt55-4r-gpt55-20260621T054140Z-claw`
- Launched before the latest prompt/source visibility repair. As of the latest
  check it is still running under WSL, has completed 1 effective round, and is
  screening the second candidate. Use it as useful CVRP research evidence, but
  expect postrun commit/readiness caveats because the WSL checkout has advanced.

Before launching any new prepared root, require strict launch readiness from
the same WSL checkout:

```bash
PY=/home/xjy-ubuntu/miniconda3/envs/scion/bin/python
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  "$PY" /home/xjy-ubuntu/research/or-autoresearch-agent/scion/tools/check_launch_readiness.py \
  <prepared-root> --require-launch-ready --format json
```

After a run, inspect `exit.txt`, `run_status.json`, and
`postrun_acceptance/readiness/`, then mirror the WSL root back to the server:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  python scripts/sync_wsl_run_root.py <wsl-run-root> \
  --execute --format json
```

Prepared-only mirrors skip current-run postrun acceptance and should return the
rsync/local-status result with `postrun_check_skip_reason=prepared_only_not_launched`;
postrun acceptance remains required after an actual launch.

## Preserved Guarantees

Keep this list compact. Detailed field-level evidence lives in `scion/TASK.md`,
the v0.4 planning summary, focused tests, and experiment reports.

- v3 boundary stays hard: LLM output, prompt ratios, branch lessons, repair
  diagnostics, and problem-owned research diagnostics remain proposal/control
  material and excluded from Decision, `DecisionFeatures`, promotion, scheduler
  state, and solver semantics unless explicitly part of Protocol.
- Launch readiness is the operator-facing authority for prepared roots. It
  checks prepared-contract identity, prompt-context bridge, runtime paths,
  model route, completion preflight, private `launch.env` permissions,
  wrapper/campaign marker consistency, and strict postrun rebuild/readiness
  behavior before launch. Low nonzero proposal/APS caps fail readiness; use
  exact `0` when the intended v0.4 behavior is no research-headroom cap. The
  same explicit-disabled convention applies to focused fresh-runtime replay
  drain. Stage-transition drain must also be explicit and positive for the
  current focused launch shape. Prompt-context readiness now exposes compact
  renderer-summary evidence in launch readiness; live provider-prompt evidence
  remains a postlaunch trace requirement.
- Problem-owned diagnostics may guide proposal context, protocol
  configuration, runtime governance, lifecycle policy, and readiness only
  through deterministic, schema-validated fields.
- Measurement readiness records calibration evidence depth as a compact status
  field. Current packaged CVRP and warehouse calibration refs are
  `summary_only`; richer external A/A artifacts must prove replay metadata
  before being labeled `full_replay`.
- Code-phase prompts must retain direct champion/current-branch/target source
  visibility and active problem-owned code constraints. Compression may remove
  boilerplate, not research-object source or active contracts.
- Hypothesis prompts should receive compact mechanism-level branch lessons,
  research-shape diagnostics, and bounded runtime/protocol feedback with
  omission/digest audit markers, not raw long prose or telemetry dumps.
- Active no-effect branch cards, sibling projections, and scheduler policy must
  agree with same-mechanism follow-up policy: ordinary no-effect/tie evidence
  remains schedulable for same-mechanism follow-up and does not emit
  runtime-saturated diversity, clean-fork guidance, or scheduler-origin
  parked-lineage blocks without a Decision-origin park marker. Cross-branch
  repeated-signature pressure preserves current active no-effect diagnostic
  follow-up, portfolio plateau lessons still block unchanged sibling copies,
  and true quality/runtime regression remains fail-closed.
- Runtime semantics must not turn budget-exhausting solver saturation, cached
  ties, comparative runtime-ratio slowdown, or inactive mechanism activation
  into meaningless replay pressure, lifecycle churn, or proposal feedback
  noise. Nominal no-effect/tie runtime summaries remain report-only; generic
  bounded/top-k runtime guidance requires actual comparative slowdown,
  runtime failure, or runtime budget saturation.
- Postrun acceptance must fail closed on missing current-run evidence, stale
  copied resume artifacts, wrapper/postrun status failures, absent source
  visibility, missing interpretation-specific review inputs, or CVRP bounded
  two-opt claims without current-run CMT2/CMT4 protection evidence.
- Screening gate, Decision, proposal feedback, and search memory must agree on
  marginal evidence: high-win-rate, non-negative, sub-practical-delta screening
  evidence is diagnostic follow-up material, not promotable proof. Global
  search-memory AVOID is driven by hard failures, not ordinary repeated
  no-effect/tie diagnostics.

## Problem Frontiers

Warehouse:

- Positive checkpoint: champion `v2` promoted in the validation-transfer rerun.
- Next question: can Scion produce useful follow-up research from `v2`, or
  correctly diagnose a real post-v2 plateau?
- Accept a plateau conclusion only with protocol evidence below MDE,
  review-ready runtime evidence, and substantive continuity evidence without
  fully missed same-mechanism follow-up opportunities.

CVRP/VRP:

- CVRP now has better target intent, branch-lesson transfer, material solver
  code generation, formal screening, mechanism telemetry, and evidence-backed
  rejection of weak/negative hypotheses.
- CVRP is still not v0.4-accepted because no current solver-design branch has
  produced continuous improvement or promotion.
- The active follow-up treats the external large-instance intra-route two-opt
  result only as proposal guidance. Review readiness requires a bounded,
  deadline-aware implementation with current-run positive effect, activation,
  objective-effect, intra-large-two-opt telemetry, and CMT2/CMT4 protection
  evidence. `two_opt_star`, cross-route, VNS, unbounded fallback, and
  continuity-only mentions do not satisfy this direct-evidence rule.
- The active CVRP prepared handoff now also carries proposal-only
  `resume_continuity_requirements`, so the zero-branch-card sparse resume must
  use copied target-intent or hypothesis trace evidence rather than being
  treated as an empty campaign.

## Next Actions

1. Let the active CVRP root finish or reach a clean stopping point, then mirror
   and classify it with the current problem-owned postrun rules.
2. Prepare and launch one fresh warehouse champion-`v2` follow-up from WSL commit
   `a9a537c4` to prove the prompt/source visibility repair under live provider
   prompts and current-run postrun acceptance.
3. If the pre-repair CVRP root is useful but postrun-compromised by checkout
   drift, prepare a fresh CVRP bounded large-two-opt follow-up from the current
   WSL commit.
4. Update this file and `scion/TASK.md` only when operating truth changes; keep
   detailed run evidence in focused experiment reports.

## Pointers

- Task and acceptance source: `scion/TASK.md`.
- Current planning summary:
  `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`.
- Boundary and audit basis:
  `scion/design/scion-architecture-v3.md`,
  `scion/reports/v04-core-framework-review-20260611.md`,
  `scion/reports/v04-core-framework-code-review-20260611.md`, and
  `scion/design/v0.5-evidence-uplift-roadmap.md`.
- Detailed repair/postrun evidence: `scion/docs/experiments/v0.4/`.
- Sparse milestone index: `scion/docs/status/v0.4-history.md`.
- WSL SSH:
  `ssh -i ~/.ssh/id_ed25519_codex_wsl -p 2222 -o BatchMode=yes -o StrictHostKeyChecking=no xjy-ubuntu@127.0.0.1`.
- WSL repo: `/home/xjy-ubuntu/research/or-autoresearch-agent`.
- WSL experiments root: `/home/xjy-ubuntu/research/scion-experiments`.
- WSL Python: `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`.
