# CVRP Scheduler Instrumentation Compact WSL Postrun

Date: 2026-06-17

## Verdict

Accepted as a no-LLM instrumentation validation matrix. The scheduler-local
telemetry repair works end to end: raw artifacts, `results.json`, and
`summary.csv` preserve ALNS iteration traces, `alns_core` timing, initial VNS
timing, and embedded VNS timing.

The mechanism result rejects a simple embedded-VNS removal path. Disabling
embedded VNS gives ALNS many more iterations, but quality is still worse or tied
against canonical ALNS+VNS. Pure ALNS/no-polish is worse again. The next CVRP
research mechanism should therefore be adaptive embedded-VNS scheduling or
triggering, not broad VNS removal and not another blind LLM campaign.

## Run

- Commit: `875dc83`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-scheduler-instrumentation-compact-875dc83-20260617T161500Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-cvrp-scheduler-instrumentation-compact-875dc83-20260617T161500Z`
- Shape: no-LLM mechanism matrix, `60` jobs
- Cases: `P-n76-k4`, `CMT2`, `CMT4`, `M-n151-k12`
- Seeds: `1..5`
- Mechanisms:
  - `canonical_alns_vns`
  - `embedded_vns_disabled`
  - `pure_alns_no_polish`
- Time budget: `3s`
- Wrapper status: `finished`
- Exit code: `0`
- Raw result files: `60`

Command shape:

```bash
PYTHONPATH=$PWD/scion python scion/tools/cvrp_mechanism_matrix.py \
  --case-id P-n76-k4 --case-id CMT2 --case-id CMT4 --case-id M-n151-k12 \
  --case-limit 4 \
  --seed 1 --seed 2 --seed 3 --seed 4 --seed 5 \
  --mechanism canonical_alns_vns \
  --mechanism embedded_vns_disabled \
  --mechanism pure_alns_no_polish \
  --time-budget-sec 3 \
  --output-dir /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-scheduler-instrumentation-compact-875dc83-20260617T161500Z
```

## Telemetry Acceptance

- `results.json`: `60/60` jobs completed, return code `0`.
- `summary.csv`: `60` data rows plus header.
- Raw JSON files: `60`.
- `alns_iterations`: present for `60/60` rows.
- `alns_iteration_trace_count`: present for `60/60` rows; trace count range
  `1..32`.
- `alns_core_runtime_ms`: present for `60/60` rows.
- `vns_initial_runtime_ms`: present for `40/60` rows, exactly the canonical and
  embedded-VNS-disabled mechanisms.
- `vns_embedded_runtime_ms` and `vns_embedded_runtime_fraction`: present for
  `20/60` rows, exactly canonical ALNS+VNS.

This validates the intended instrumentation semantics:

- construction timing no longer includes initial VNS;
- `alns_core` captures destroy/repair/acceptance time outside VNS;
- canonical rows expose both initial and embedded VNS;
- embedded-VNS-disabled rows expose initial VNS but no embedded VNS;
- pure ALNS/no-polish rows expose neither VNS phase.

## Quality Results

Overall comparison versus canonical:

| Mechanism | Rows | W/L/T vs canonical | Median delta | Mean delta | Mean ALNS iterations | Mean `alns_core_ms` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `embedded_vns_disabled` | 20 | `2/8/10` | `0.0` | `+17.3` | `22.4` | `2183.25` |
| `pure_alns_no_polish` | 20 | `2/18/0` | `+8.0` | `+35.6` | `29.35` | `2507.3` |

Canonical reference:

- Rows: `20`
- Median BKS gap: `11.676%`
- Mean ALNS iterations: `4.0`
- Mean `alns_core_ms`: `487.0`
- Mean `vns_initial_ms`: `478.0`
- Mean `vns_embedded_ms`: `1839.3`
- Mean `vns_embedded_runtime_fraction`: `0.651`

Per-case comparison:

| Case | `embedded_vns_disabled` W/L/T | Embedded median delta | `pure_alns_no_polish` W/L/T | Pure median delta |
| --- | ---: | ---: | ---: | ---: |
| `CMT2` | `0/4/1` | `+69.0` | `0/5/0` | `+98.0` |
| `CMT4` | `0/2/3` | `0.0` | `0/5/0` | `+2.0` |
| `M-n151-k12` | `0/0/5` | `0.0` | `0/5/0` | `+8.0` |
| `P-n76-k4` | `2/2/1` | `0.0` | `2/3/0` | `+3.0` |

No mechanism produced route/fleet regressions in this compact run.

## Interpretation

The run separates runtime pressure from mechanism value:

- Canonical spends most of its time in embedded VNS: mean embedded VNS fraction
  `0.651`.
- Disabling embedded VNS increases ALNS iteration count from `4.0` to `22.4`,
  but does not create stable quality improvement.
- Pure ALNS/no-polish increases iteration count further to `29.35`, but quality
  degrades on `18/20` rows.
- `P-n76-k4` remains the only case with occasional local wins, but it is not
  stable enough to justify a case-specific rule.
- `CMT2` is the strongest warning against broad embedded-VNS removal:
  embedded-disabled loses `4/5`, median `+69.0`; pure ALNS loses `5/5`, median
  `+98.0`.

The likely opportunity is not "remove VNS." It is to preserve VNS where it
produces quality while reducing low-value embedded VNS calls. Candidate
mechanism families for the next no-LLM slice:

- adaptive embedded-VNS cadence, such as every `k` accepted ALNS moves or after
  a meaningful post-repair delta;
- embedded-VNS trigger based on remaining budget and candidate distance before
  polish;
- lighter embedded polish for non-improving or annealing-only accepted moves;
- explicit proposal diagnostics that tell CVRP agents the budget-pressure
  shape without exposing raw BKS/case-specific shortcuts to `DecisionFeatures`.

## Next Step

Do not launch a long agentic CVRP campaign from this result alone. First add or
test a narrow adaptive embedded-VNS scheduling probe, then feed the accepted
problem-owned opportunity summary into CVRP proposal context so an agent has a
real mechanism target rather than a vague "improve ALNS" prompt.
