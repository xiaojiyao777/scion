# Warehouse swap_orders Audit and CVRP Focused Diagnostic Prep

Date: 2026-06-17

## Scope

This note records the focused postrun audit after the copied-config data-root
fallback field gate and the next no-LLM CVRP diagnostic preparation.

Inputs:

- Warehouse run:
  `/home/clawd/research/scion-experiments/v04-warehouse-datarootfallback-full-rerun6r-5630697-20260617T132912Z`
- Warehouse postrun:
  `scion/docs/experiments/v0.4/v04-warehouse-datarootfallback-full-rerun6r-postrun-20260617.md`
- CVRP matrix postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-mechanism-matrix-wsl-224ca7f-postrun-20260617.md`
- WSL handoff/connection docs:
  `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/WSL_EXECUTION.md`
  and
  `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/RSYNC_PATHS.md`

## Warehouse Audit

The `swap_orders` validation failure is accepted as a real mechanism failure,
not a Contract, Verification, path-safety, or telemetry false-negative failure.
The run reached formal validation, and the validation gate failed normally with
`VALIDATION_PROTOCOL_GATE_FAIL` plus the auxiliary
`VALIDATION_FAIL_NO_HIERARCHICAL_GAIN` pattern.

Key shape:

- screening reached `queue_validate` through expanded borderline pair signal,
  not a strong case-level gate;
- validation had W/T/L `8/1/6` at pair level but failed aggregate quality;
- validation median delta was `-200`;
- `split_delta_sum` was `0` across validation transfer diagnostics;
- median runtime ratio was about `1.025`;
- cost-only wins did not establish case-general hierarchical improvement.

The follow-up repair is therefore problem-owned proposal/context feedback, not
a generic Decision or Protocol threshold change. The warehouse adapter now
exposes this latest aggregate failure pattern in proposal-visible diagnostics
while keeping it excluded from `DecisionFeatures`.

Quality blocks are mostly true blocks:

- three hypothesis-stage blocks missed `validation_transfer_risk`;
- one patch-stage block missed bounded candidate policy;
- session `549918fe-964b-46b7-b2ed-05bb041cea73` cannot be called a detector
  miss from available artifacts because its patch body is omitted; text claims
  are not enough to prove executable split/cost guard code.

Known observability gap:

- `experiment_events.decision_reason` can be empty even when
  `audit_payload_json.lineage_metadata.decision_reason_codes` contains the
  authoritative reason codes. This is a next P1 observability repair candidate
  and should not be mixed with gate semantics.

## CVRP Prep

The first WSL matrix rejects `alns_only` and `size70_two_opt_candidate` as broad
canonical replacements. The next CVRP diagnostic should be exact-case and
fixed-mechanism, not another long LLM campaign.

Implemented preparation:

- `scion/tools/cvrp_mechanism_matrix.py` now accepts repeatable `--case-id`;
- `load_case_entries(...)` filters exact case ids before applying
  `--case-limit`;
- this enables direct focused runs for `P-n76-k4`, `P-n101-k4`, `P-n65-k10`,
  `M-n151-k12`, `CMT2`, and `CMT4`.

Because the matrix tool keeps a conservative default `--case-limit=1`, focused
multi-case runs must set `--case-limit` to at least the number of requested
exact case ids.

Example next WSL command shape:

```bash
OUT=/home/xjy-ubuntu/research/scion-experiments/cvrp-focused-mechanism-$(date -u +%Y%m%dT%H%M%SZ)

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
/home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/cvrp_mechanism_matrix.py \
  --workspace scion/scion/problems/cvrp \
  --repo-root . \
  --data-root /home/xjy-ubuntu/research/or-autoresearch-agent/vrp \
  --case-manifest scion/scion/problems/cvrp/formal/manifests/screening.json \
  --output-dir "$OUT" \
  --case-id P-n76-k4 \
  --case-id P-n101-k4 \
  --case-id M-n151-k12 \
  --case-id CMT4 \
  --case-limit 4 \
  --seed 11 --seed 23 --seed 37 --seed 47 \
  --time-budget-sec 3 \
  --timeout-padding-sec 60
```

Acceptance for moving into a short agentic CVRP campaign:

- local candidate wins remain across added seeds, not only the original two
  seeds;
- median candidate-vs-canonical delta clears the CVRP A/A noise floor;
- no route/fleet regression;
- high-gap cases show a concrete mechanism clue such as best-update starvation,
  accepted-move starvation, phase budget imbalance, or local-search mismatch.

## Local Acceptance

Commands:

```bash
PYTHONPATH=$PWD/scion pytest -q \
  scion/scion/tests/unit/test_warehouse_target_preview.py \
  scion/scion/tests/unit/evidence/test_cvrp_mechanism_matrix.py

python -m py_compile \
  scion/scion/problems/warehouse_delivery/adapter.py \
  scion/scion/problems/cvrp/evidence/mechanism_matrix.py \
  scion/tools/cvrp_mechanism_matrix.py
```

Result: `48 passed`; py_compile passed.
