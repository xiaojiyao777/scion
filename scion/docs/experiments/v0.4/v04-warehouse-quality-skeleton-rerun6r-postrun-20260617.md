# Warehouse Quality-Skeleton Rerun 6R Postrun

*Date: 2026-06-17*
*Commit under test: `9853dd4`*
*Run status: interrupted by API balance exhaustion*

## Run

- Root:
  `/home/clawd/research/scion-experiments/v04-warehouse-quality-skeleton-rerun6r-9853dd4-20260617T120052Z`
- Cell: `rep01/on_compact`
- Protocol: warehouse production protocol/split/seeds copied into the run root
- Rounds requested: `6`
- Time limit: `30s`
- Measurement governance: `on`
- Proposal context: `compact-measurement-diagnostics`
- Agentic proposal model endpoint: local `gpt-5.5`
- Wrapper exit: `20`
- Stopped reason: `api_balance_exhausted`

The campaign stopped with:

```text
API balance exhausted: Error code: 403 - Your account balance is insufficient.
```

No server or WSL Scion experiment process remained active after the stop.

## Counter Reconciliation

The run is valid only as partial interrupted evidence:

- `run_validity.status=valid`
- `run_validity.reason=valid_partial_interrupted`
- `complete=false`
- `requested_rounds=6`
- `effective_rounds_completed=1`
- `proposal_attempts_total=13`
- `proposal_attempts=11`
- `proposal_quality_blocks=9`
- `protocol_metric_results=2`
- `screening_protocol_results=2`
- `validation_protocol_results=0`
- `frozen_protocol_results=0`
- `formal_candidate_artifact_count=3`
- `champion_version=1`

The run is not a completed field gate and is not warehouse efficacy evidence.

## Branch Evidence

Branch `c9e3ca68` created `operators/subcategory_merge.py` and reached
screening twice:

- First screening row: case W/L/T `4/0/6`, pair W/L/T `11/3/6`, median delta
  `425.0`, telemetry guard failed, decision `continue_explore`.
- Follow-up telemetry repair row: case W/L/T `0/0/6`, pair W/L/T `0/0/12`,
  median delta `0.0`, telemetry guard failed, decision `abandon`.
- Final branch state: `abandoned`, `branch_code_status=discarded`,
  `last_screening_feedback_tier=weak_positive`, and
  `last_telemetry_outcome=activation_missing_or_wiring_suspect`.

Branch `66cd0d18` remained in `explore` and did not reach Protocol before API
exhaustion. Its failure codes were proposal quality, telemetry identity, and
patch quality blocks:

- missing `validation_transfer_risk` / `screening_only_guard`
- `warehouse_operator_telemetry_identity_mismatch`
- schema output failures
- two `warehouse_validation_transfer_patch_quality_missing` blocks on
  `operators/change_vehicle_type.py`

## Quality-Block Classification

Subagent Curie audited the two late `change_vehicle_type.py` code-stage blocks
from the LLM traces.

`a1931a64-aa3a-4704-9b0e-846994ed0cb7` was a true block:

- It added diagnostics and ranked candidates, but did not compute executable
  base/candidate split and cost comparisons.
- It asserted split preservation in comments and hard-coded
  `split_delta_sum += 0`.
- The adapter correctly returned `screening_or_lexicographic_guard`.

`c0e6a00c-0b86-42bb-b8c5-2e9a07d395be` was a detector false negative:

- The prompt visibly included the strengthened `repair_template`,
  `lexicographic_guard_skeleton`, and `change_vehicle_type_downsize` guidance.
- The generated patch computed base and candidate splits/costs, then used
  sequential executable filters:
  `if split_delta < 0: continue` and `if cost_delta <= 0: continue`.
- It fell back to `return solution` when no candidate passed.
- The existing warehouse recognizer only accepted a single guard expression
  containing both split and cost, or a derived guard variable from such an
  expression. It missed the equivalent sequential candidate-loop form.

## Repair

The follow-up repair remains warehouse-owned in
`scion/scion/problems/warehouse_delivery/adapter.py`.

It now accepts candidate-loop transfer guards when the same loop contains both
an executable split filter and an executable cost filter that skip dominated
candidates with `continue`, and the function falls back to the original
solution when no candidate is accepted.

The repair keeps the gate strict:

- split-only candidate filters still fail;
- cost-only downsize filters still fail;
- string-only and comment-only guards still fail;
- local-only diagnostics still fail;
- generic Decision, Protocol thresholds, and `DecisionFeatures` are unchanged.

## Validation

Commands:

```bash
PYTHONPATH=scion python -m pytest -q scion/scion/tests/unit/test_warehouse_target_preview.py
PYTHONPATH=scion python -m pytest -q scion/scion/tests/unit/core/test_proposal_pipeline_quality_blocks.py scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py
PYTHONPATH=scion python -m py_compile scion/scion/problems/warehouse_delivery/adapter.py scion/scion/tests/unit/test_warehouse_target_preview.py
git diff --check
```

Results:

- Warehouse target preview: `42 passed`
- Proposal quality block and recorder status tests: `74 passed`
- `py_compile`: passed
- `git diff --check`: passed

## Acceptance

The `9853dd4` field gate is not complete and cannot field-accept the full
quality-skeleton repair because the LLM API balance stopped the run after only
one effective round.

The partial evidence is still useful:

- the strengthened skeleton reached the code prompt;
- one remaining block was legitimate;
- one remaining block was an adapter detector false negative;
- the detector false negative has a narrow warehouse-owned repair and focused
  tests.

Next LLM experiment gate: after API balance is restored, rerun one short local
warehouse `6R` acceptance check from the repaired commit. Keep this as a
single-cell or two-cell server task; reserve WSL for larger synchronized
parallel matrices.
