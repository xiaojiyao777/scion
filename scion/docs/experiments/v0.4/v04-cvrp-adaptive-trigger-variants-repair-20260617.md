# CVRP Adaptive Trigger Variants Repair

Date: 2026-06-17

## Verdict

Accepted as a local no-LLM mechanism-probe extension. This change adds two
CVRP-owned embedded-VNS trigger variants for the next compact matrix:

- `adaptive_embedded_vns_cadence2`
- `adaptive_embedded_vns_improve_only`

The change does not alter generic Decision, Protocol, lifecycle, promotion, or
`DecisionFeatures`. Canonical behavior remains unchanged because the default
`EMBEDDED_VNS_CADENCE` is still `1`.

## Rationale

The compact cadence-4 matrix showed that adaptive embedded-VNS scheduling is a
useful mechanism family, but cadence-4 is too aggressive:

- embedded-VNS runtime share dropped from `0.651` to `0.361`;
- mean ALNS iterations increased from `4.0` to `8.35`;
- paired quality was still worse overall (`4/7/9`, mean delta `+6.95`).

The next matrix needs nearby trigger variants before this idea is exposed to an
agentic CVRP campaign.

## Implementation

Files changed:

- `scion/scion/problems/cvrp/policies/baseline_modules/config.py`
- `scion/scion/problems/cvrp/policies/baseline_modules/scheduler.py`
- `scion/scion/problems/cvrp/evidence/mechanism_matrix.py`
- `scion/tools/cvrp_mechanism_matrix.py`
- `scion/scion/tests/unit/evidence/test_cvrp_mechanism_matrix.py`

Config semantics:

- `EMBEDDED_VNS_CADENCE = 1`: canonical, run embedded VNS every ALNS iteration.
- positive `EMBEDDED_VNS_CADENCE`: run every N ALNS iterations, plus repair
  improvement if enabled.
- `EMBEDDED_VNS_CADENCE = 0`: no fixed cadence; embedded VNS runs only when the
  repaired candidate already improves current or best and
  `EMBEDDED_VNS_RUN_ON_REPAIR_IMPROVEMENT` is true.

New matrix mechanisms:

- `adaptive_embedded_vns_cadence2`: a less aggressive skip policy than
  cadence-4.
- `adaptive_embedded_vns_improve_only`: embedded VNS only for repaired
  candidates that already improve current/best before polish.

## Local Acceptance

Commands:

```bash
PYTHONPATH=$PWD/scion python -m py_compile \
  scion/scion/problems/cvrp/policies/baseline_modules/config.py \
  scion/scion/problems/cvrp/policies/baseline_modules/scheduler.py \
  scion/scion/problems/cvrp/evidence/mechanism_matrix.py \
  scion/tools/cvrp_mechanism_matrix.py

PYTHONPATH=$PWD/scion pytest -q \
  scion/scion/tests/unit/evidence/test_cvrp_mechanism_matrix.py \
  scion/scion/tests/test_cvrp_solver_algorithm_runtime.py

PYTHONPATH=$PWD/scion pytest -q \
  scion/scion/tests/test_cvrp_solver_algorithm_runtime.py \
  scion/scion/tests/unit/evidence/test_cvrp_mechanism_matrix.py \
  scion/scion/tests/unit/test_cvrp_active_solver_map_provider.py \
  scion/scion/tests/unit/test_expected_telemetry_activation_contract.py

rm -rf /tmp/scion-cvrp-adaptive-trigger-smoke &&
PYTHONPATH=$PWD/scion python scion/tools/cvrp_mechanism_matrix.py \
  --case-id P-n76-k4 --case-limit 1 --seed 1 \
  --mechanism canonical_alns_vns \
  --mechanism adaptive_embedded_vns_cadence2 \
  --mechanism adaptive_embedded_vns_improve_only \
  --time-budget-sec 1 \
  --output-dir /tmp/scion-cvrp-adaptive-trigger-smoke
```

Results:

- py_compile passed.
- Focused runtime/matrix tests: `20 passed`.
- Broader related suite: `35 passed`.
- `git diff --check` passed.
- Smoke completed `3/3` jobs.

Smoke signal on `P-n76-k4`, seed `1`, `1s`:

| Mechanism | Total distance | ALNS iterations | Embedded VNS fraction |
| --- | ---: | ---: | ---: |
| `canonical_alns_vns` | `650` | `3` | `0.595` |
| `adaptive_embedded_vns_cadence2` | `650` | `4` | `0.380` |
| `adaptive_embedded_vns_improve_only` | `650` | `7` | `0.320` |

The smoke proves both overlays execute and preserve output schema. It is not an
efficacy claim.

## Next Gate

Run a compact WSL no-LLM matrix before any agentic CVRP campaign:

- cases: `P-n76-k4`, `CMT2`, `CMT4`, `M-n151-k12`;
- seeds: `1..5`;
- mechanisms: `canonical_alns_vns`, `adaptive_embedded_vns_cadence2`,
  `adaptive_embedded_vns_improve_only`, and optionally cadence-4 as the prior
  reference;
- time budget: `3s`.

Accept a trigger variant for proposal context only if it reduces embedded-VNS
pressure without a paired-quality regression across the compact case set.
