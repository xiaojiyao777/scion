# CVRP Route-Merge Transfer Agentic Resume Postrun

Date: 2026-06-18

## Purpose

This run copied the completed `f3d634c` route-merge campaign state and appended
one agentic round from commit `af5b5a2`. The question was whether Scion could
transfer the immediate `active_no_effect` route-merge lesson instead of
repeating the same guarded v2 patch unchanged.

## Run

- Commit: `af5b5a2`
- Branch: `codex/v04-evidence-repair-plan`
- WSL run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-routemerge-transfer-agentic-resume1r-af5b5a2-env-20260618T0130Z`
- Server copy:
  `/home/clawd/research/scion-experiments/v04-cvrp-routemerge-transfer-agentic-resume1r-af5b5a2-env-20260618T0130Z`
- Source campaign copied from:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-routemerge-guarded-agentic-1r-f3d634c-pypath-20260618T004101Z`
- Wrapper status: `valid`, `complete`, `completed_requested_rounds=true`
- Time: `2026-06-18T01:25:35Z` to `2026-06-18T02:00:22Z`
- Model: copied and new LLM traces all used `gpt-5.5`.

The valid run explicitly set:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion
SCION_MODEL=gpt-5.5
SCION_BASE_URL=http://127.0.0.1:8080
SCION_API_KEY=pwd
```

An earlier transfer-check launch omitted the `SCION_*` environment and failed
authentication/fallback behavior before useful solver evidence. Exclude
`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-routemerge-transfer-agentic-resume1r-af5b5a2-20260618T0125Z`
from evidence.

## Transfer Result

Partially accepted.

The new proposal did not repeat the exact no-effect candidate. It stayed on
`policies/baseline_modules/destroy_repair.py` and mechanism
`route_merge_repair`, but changed the implementation into a repair-stage sparse
route absorption pass with a material distance-improvement requirement.

However, target-intent still leaned on the older post-share70 positive evidence
(`10/3/19`, direct effect positive `19/32`) more strongly than the immediate
`f3d634c` no-effect result (`0/0/32`). The hypothesis also carried confusing
branch-lesson language that contrasted against a `scheduler_share_variant`
family even though the active lesson was route-merge. This shows lesson transfer
is present but not yet clean enough to rely on for long CVRP campaigns.

## Candidate Patch

Formal candidate:

`campaign/artifacts/formal_candidates/bee2fece/screening-432c45b9-a089-4989-af5b-cf8d5d8ae82d-29574d897c47d6a8/candidate.patch.json`

Patch digest:
`23bf0718374887ca37fcffc58c15c56f3d2241aa3b84a4df72ac8ec86b8bae7f`

The patch added:

- `_route_merge_repair(solution, context, reserve, max_routes=None)` in
  `policies/baseline_modules/destroy_repair.py`;
- `_best_absorption_insertion(...)`;
- scheduler wiring to call `_route_merge_repair(...)` after each repair
  operator before embedded VNS.

The candidate is materially different from the rejected `f3d634c` no-effect
patch because route merge now runs as a bounded post-repair pass and requires a
positive full-candidate distance delta before committing.

## Screening Result

Rejected as a production solver improvement, but useful as mechanism evidence.

- Stage: `screening`
- Selected surface: `solver_design`
- Valid pairs: `32/32`
- Failed pairs: `0`
- Decision: `expand_screening`
- Reason: `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT`
- Pair W/L/T: `7/7/18`
- Median total-distance delta: `0.0`
- Mean total-distance delta: `-0.28125`
- Runtime ratio median: `1.001322488178139`
- Runtime delta median: `32.0ms`
- Runtime regression rate: `0.625`
- Runtime evidence: `high`, `sufficient`
- Champion remained `v1`; `accepted_experiments=0`.

Telemetry improved over `f3d634c`:

- `route_merge_repair` activation/runtime fields were present and positive in
  `32/32` candidate runs.
- `solver_algorithm_phase_improvement_counts.route_merge_repair` was positive
  in `19/32` and zero in `13/32`.
- `solver_algorithm_phase_best_delta.route_merge_repair` was positive in
  `19/32`, with examples such as `106.0`, `57.0`, and `118.0`.
- Telemetry guard passed with no warnings or failures.

This is not a promotion, but it is a stronger research-loop signal than the
previous route-merge no-effect patch because the mechanism now has direct
measured effect while aggregate quality remains mixed.

## Framework Defect Found

The run exposed a branch-card continuity bug. The final status kept the
screening result in `last_result`, metric files, and formal-candidate artifacts,
but the new clean-fork branch `bee2fece-bfdf-4bb1-8745-350939e098fb` persisted
with:

- `direction=null`;
- `branch_mechanism_ids=[]`;
- `branch_evidence_summary=null`;
- branch card evidence `tier=unknown`;
- phase activation summary `unknown`;
- no not-promoted reason codes.

Root cause: `DecisionFinalizer` synchronized branch evidence for
`ABANDON` and `CONTINUE_EXPLORE`, but not for non-terminal protocol decisions
such as `EXPAND_SCREENING`. That made a valid evaluated branch look like an
empty clean branch to later proposal prompts.

Repair added on 2026-06-18:

- `scion/scion/core/decision_finalizer.py` now syncs retained protocol evidence
  for non-terminal decisions before state transition/persist.
- `scion/scion/tests/unit/core/test_decision_finalizer_lifecycle.py` adds a
  regression test for `EXPAND_SCREENING` branch-card evidence retention.

Acceptance:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/core/test_decision_finalizer_lifecycle.py -q
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_campaign_screening_verification_run.py
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/core/test_branch_hygiene_status.py
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/core
```

Results: `17`, `12`, `20`, `53`, and full `unit/core` `522` tests passed.

## Conclusion

This transfer run is valid and useful, but not sufficient to declare CVRP
effective-research recovery complete.

Accepted:

- Scion can create a materially different same-mechanism route-merge variant
  after a no-effect lesson.
- Screening and telemetry are complete and interpretable.
- The second route-merge variant has direct mechanism effect in `19/32` pairs.
- A real framework continuity defect was found and repaired.

Not accepted:

- The candidate is not a solver improvement (`7/7/18`, median `0.0`, mean
  `-0.28125`, no promotion).
- Lesson transfer still over-weights stale positive provider guidance and
  confuses the active lesson family.
- The repaired branch-card path still needs a fresh short WSL rerun before
  relying on subsequent CVRP continuation prompts.

Next CVRP field check: run one fresh WSL agentic round after the branch-card
evidence-retention repair, with `PYTHONPATH` and `SCION_*` env set. Acceptance
should inspect whether the new prompt sees the retained `marginal`/mixed
route-merge evidence, the `route_merge_repair` mechanism id, and direct effect
telemetry before selecting the next target.
