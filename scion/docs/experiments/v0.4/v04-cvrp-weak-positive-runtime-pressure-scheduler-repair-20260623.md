# CVRP Weak-Positive Runtime-Pressure Scheduler Repair

Date: 2026-06-23

## Evidence Source

- Clean scheduler-status validation root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-schedstatus-d0dded44-clean-missingprimary-4r-gpt55-20260623T025241Z-claw`
- Local replay database:
  `/tmp/scion-clean-cvrp-schedstatus.db`
- Purpose: diagnose why the accepted active-slot validation root still showed
  weak same-mechanism continuity. This is scheduler-policy evidence, not a new
  CVRP solver-mechanism result.

## Finding

The clean root accepted the generic active-slot repair: 4 of 4 effective rounds,
`last_stop_reason=max_rounds_exhausted`, 0 scheduler active-slot blocks, 0
quality blocks, and 0 promotions. All available protocol effects were below MDE
and non-positive, so it is not solver progress.

Postrun research continuity exposed a separate actionability gap:

- `research_continuity.same_mechanism_followup.observed=4`
- `research_continuity.same_mechanism_followup.selected=1`
- `research_continuity.same_mechanism_followup.not_selected=3`
- `same_mechanism_followup.selection_rate=0.25`

The remaining active weak-positive branches had generic evidence summaries with
no case-level loss and pair-level positive signal:

- `bba3d45f-a7d7-4485-905b-cb3777976c1e`: `wins=0`, `losses=0`,
  `pair_wins=2`, `runtime_evidence_pressure_count=3`
- `ec052599-281d-40fc-9d8f-639b452904b3`: `wins=0`, `losses=0`,
  `pair_wins=2`, `runtime_evidence_pressure_count=2`

Before the repair, runtime-evidence completeness pressure preferred a clean fork
for this shape, so current weak-positive/no-case-loss research could be skipped
even after the active-slot blocker was fixed.

## Design Repair

The scheduler now treats runtime-evidence completeness pressure as a generic
resource-policy signal that yields to current weak-positive follow-up when no
case-level loss is present.

Rules:

- Weak-positive lineage with any case-level loss still prefers clean fork under
  runtime-evidence pressure.
- Weak-positive lineage with no case-level loss and current weak-positive
  signal remains schedulable as `weak_positive_signal_followup`, even when
  runtime confidence is low, incomplete, or aggregate-excluded.
- Pair-level wins may justify bounded follow-up, but they remain proposal/audit
  material and do not enter `DecisionFeatures`.
- Audit metadata records
  `runtime_evidence_clean_fork_suppression=weak_positive_exception`, pressure
  count, case wins/losses, pair wins, evidence tier, and runtime pressure
  triggers.

Boundary check: this repair reads only problem-neutral branch/evidence fields
such as `wins`, `losses`, `pair_wins`, `tier`, `branch_code_status`, and
`runtime_evidence_*`. It does not mention CVRP cases, CMT, BKS, two-opt,
warehouse terms, or mechanism ids.

## Replay Result

Replay command:

```bash
PYTHONPATH=scion python - <<'PY'
from scion.lineage.registry import LineageRegistry
from scion.lineage.branch_store import BranchStore
from scion.core.scheduler import Scheduler
from scion.core.scheduling.runtime_pressure import (
    branch_runtime_evidence_clean_fork_pressure_summary,
)

registry = LineageRegistry('/tmp/scion-clean-cvrp-schedstatus.db')
branches = BranchStore(registry).load_all_active()
for branch in branches:
    if branch.branch_id.startswith(('bba3d45f', 'ec052599')):
        print(
            'branch',
            branch.branch_id,
            branch.branch_code_status,
            branch.last_screening_feedback_tier,
            branch.branch_evidence_summary.get('wins'),
            branch.branch_evidence_summary.get('losses'),
            branch.branch_evidence_summary.get('pair_wins'),
            branch_runtime_evidence_clean_fork_pressure_summary(branch),
        )
action = Scheduler(max_active_branches=3).select_next(branches)
print(
    'selected',
    action.action,
    action.branch.branch_id if action.branch else None,
    action.reason,
    action.slot,
    action.audit_metadata,
)
PY
```

Result:

- `bba3d45f` and `ec052599` no longer emit a clean-fork pressure summary.
- Scheduler selected
  `run_existing bba3d45f-a7d7-4485-905b-cb3777976c1e weak_positive_signal_followup exploit_weak_positive`.
- Audit metadata recorded
  `runtime_evidence_clean_fork_suppression=weak_positive_exception`,
  `case_wins=0`, `case_losses=0`, `pair_wins=2`,
  `evidence_tier=weak_positive`, and the low/incomplete runtime pressure
  triggers.

## Verification

Local focused tests after the repair:

```bash
PYTHONPATH=scion pytest \
  scion/scion/tests/unit/core/test_scheduler_runtime_evidence_pressure.py \
  scion/scion/tests/test_scheduler.py -q
```

Result: `73 passed`.

```bash
PYTHONPATH=scion pytest \
  scion/scion/tests/unit/core/test_proposal_pipeline_agentic_routing_signal.py \
  scion/scion/tests/unit/core/test_proposal_pipeline_failure_paths.py \
  scion/scion/tests/unit/core/test_proposal_pipeline_quality_blocks.py \
  scion/scion/tests/unit/core/test_failure_lifecycle.py \
  scion/scion/tests/unit/core/test_retry_round_accounting.py -q
```

Result: `68 passed`.

Clean-worktree local launch readiness:

```bash
PYTHONPATH=scion pytest scion/scion/tests/test_launch_readiness.py -q
```

Result: `115 passed`.

The repair was synced to WSL as head `09094b5c` from local commit `10707890`.
WSL conda `scion` verification passed:

- scheduler runtime-pressure tests: `73 passed`
- proposal-boundary/lifecycle tests: `68 passed`
- launch readiness: `115 passed`

The proposal-boundary routing check was tightened during review: typed agentic
failure detail is now report material. Timeout/transient routing uses typed
termination/category fields, and framework-boundary circuit suppression requires
an exact structured machine payload or exact policy-check payload. A typed
failure whose prose merely mentions framework-boundary keywords remains a
proposal/circuit failure.

## Next Use

The next CVRP run should test research continuity under the repaired scheduler,
not relaunch the old active-slot validation shape. Interpret any solver evidence
against MDE and keep CVRP mechanism guidance in problem-owned providers.
