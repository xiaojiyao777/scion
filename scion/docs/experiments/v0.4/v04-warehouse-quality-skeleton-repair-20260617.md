# Warehouse Quality Skeleton Repair - 2026-06-17

## Context

Latest accepted field gate before this repair:

- Run root:
  `/home/clawd/research/scion-experiments/v04-warehouse-effectzero-guidance-rerun6r-8688ac9-20260617T105940Z`
- Commit: `8688ac9`
- Result: valid complete `6/6`, `7` protocol rows (`6` screening,
  `1` validation), no frozen row, no promotion, and `6` proposal quality
  blocks.

The targeted telemetry effect-zero behavior was field-accepted, but research
quality remained rejected. The next gate in `scion/TASK.md` was to classify the
blocked `change_vehicle_type.py` exact-replace session
`f7851de0-0fee-4420-b20d-3c27df9bfd73` and repair warehouse problem-owned
proposal-quality feedback/skeletons before any broad WSL matrix.

## Block Classification

The blocked `change_vehicle_type.py` session is a true block, not a detector
false negative.

The final composed patch was recoverable from the code trace
`llm_traces/20260617T112011954390_code_e4dc1cfc83_99c97138.json`. It filtered
on `cost_delta <= 0`, but it did not compute `split_delta`, `base_splits`,
`candidate_splits`, or an equivalent lexicographic objective comparison before
acceptance. `split_delta_sum` only appeared as a diagnostics key, not as an
enforced guard.

The warehouse detector correctly requires executable split and cost signals in
the guard shape. The Decision layer and generic protocol remain unchanged.

## Repair

Changed files:

- `scion/scion/problems/warehouse_delivery/adapter.py`
- `scion/scion/tests/unit/test_warehouse_target_preview.py`

The repair strengthens warehouse problem-owned feedback only:

- The retry constraint now asks for computed base/candidate subcategory splits
  and total cost, then an executable guard:
  `split_delta > 0 or (split_delta == 0 and cost_delta > 0)`.
- The repair template now includes a code-shaped lexicographic guard skeleton.
- The template warns that `change_vehicle_type` / downsize patches still need
  computed or proven split preservation; a cost-only filter is not enough.
- The bounded-candidate template now requires a real pre-evaluation cap for
  pair scans and calls out late `candidates[:32][0]` selection as insufficient.

This remains problem-owned proposal/code quality feedback. It does not relax
`_patch_has_screening_or_lexicographic_guard`, does not change
`DecisionFeatures`, and does not route raw warehouse diagnostics into Decision.

## Validation

Commands:

```bash
PYTHONPATH=scion python -m pytest -q scion/scion/tests/unit/test_warehouse_target_preview.py
PYTHONPATH=scion python -m pytest -q scion/scion/tests/unit/core/test_proposal_pipeline_quality_blocks.py scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py
PYTHONPATH=scion python -m py_compile scion/scion/problems/warehouse_delivery/adapter.py scion/scion/tests/unit/test_warehouse_target_preview.py
git diff --check -- scion/scion/problems/warehouse_delivery/adapter.py scion/scion/tests/unit/test_warehouse_target_preview.py
```

Results:

- Warehouse target preview: `41 passed`
- Proposal quality block and recorder status tests: `74 passed`
- `py_compile`: passed
- `git diff --check`: passed

## Resource Status

Server experiment check on 2026-06-17 found no active Scion experiment process.
The latest local warehouse field gates are finished with `exit_code=0`.

WSL SSH was verified through:

```bash
ssh -i /home/clawd/.ssh/id_ed25519_codex_wsl -p 2222 xjy-ubuntu@127.0.0.1
```

WSL host `xjy-workspace` has `10` logical CPUs and about `27Gi` memory
available, but the WSL checkout was still at `4b2ee29` while the server branch
was at `1f7f5b1` before this repair. Future WSL experiments must fast-forward
the WSL runner worktree first.

## Next Gate

After commit, run one short local warehouse production field gate on the
2-core server. Do not start a broad WSL matrix until this repair is field
accepted. Use WSL for larger multi-cell or long parallel matrices after the
runner checkout is synchronized.
