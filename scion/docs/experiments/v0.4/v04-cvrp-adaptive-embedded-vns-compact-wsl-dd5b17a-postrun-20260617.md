# CVRP Adaptive Embedded VNS Compact WSL Postrun

Date: 2026-06-17

## Verdict

Accepted as a no-LLM mechanism diagnostic, not accepted as a production
candidate. `adaptive_embedded_vns_cadence4` reduces embedded-VNS runtime
pressure and gives ALNS more iterations, but it does not preserve paired
quality strongly enough to feed directly into a long agentic CVRP campaign.

The useful conclusion is narrower: adaptive embedded-VNS scheduling remains a
promising mechanism family, but cadence-4 as implemented is too blunt. The next
slice should tune the trigger or cadence before exposing the idea as a
proposal-context opportunity.

## Run

- Commit: `dd5b17a`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-adaptive-embedded-vns-compact-dd5b17a-20260617T162800Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-cvrp-adaptive-embedded-vns-compact-dd5b17a-20260617T162800Z`
- Shape: no-LLM mechanism matrix, `40` jobs
- Cases: `P-n76-k4`, `CMT2`, `CMT4`, `M-n151-k12`
- Seeds: `1..5`
- Mechanisms:
  - `canonical_alns_vns`
  - `adaptive_embedded_vns_cadence4`
- Time budget: `3s`
- Wrapper status: `finished`
- Exit code: `0`
- Raw result files: `40`

Command shape:

```bash
PYTHONPATH=$PWD/scion python scion/tools/cvrp_mechanism_matrix.py \
  --case-id P-n76-k4 --case-id CMT2 --case-id CMT4 --case-id M-n151-k12 \
  --case-limit 4 \
  --seed 1 --seed 2 --seed 3 --seed 4 --seed 5 \
  --mechanism canonical_alns_vns \
  --mechanism adaptive_embedded_vns_cadence4 \
  --time-budget-sec 3 \
  --output-dir /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-adaptive-embedded-vns-compact-dd5b17a-20260617T162800Z
```

## Artifact Checks

- `status.txt`: `status=finished`, `exit_code=0`.
- `summary.csv`: `40` data rows plus header.
- Raw JSON files: `40`.
- `results.json`: `40/40` jobs completed with return code `0`.
- No route-count or fleet-regression flags were raised.

## Quality Results

Overall comparison versus canonical:

| Mechanism | Rows | W/L/T vs canonical | Median delta | Mean delta | Mean ALNS iterations | Mean embedded VNS fraction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `canonical_alns_vns` | 20 | reference | `0.0` | `0.0` | `4.0` | `0.651` |
| `adaptive_embedded_vns_cadence4` | 20 | `4/7/9` | `0.0` | `+6.95` | `8.35` | `0.361` |

The adaptive embedded-VNS fraction above treats rows with no embedded-VNS run as
`0`, which is the right whole-matrix runtime-pressure view. Across only rows
where embedded VNS actually ran, adaptive mean embedded-VNS fraction was
`0.451` and mean embedded-VNS runtime was `1217.94ms`; canonical mean
embedded-VNS runtime was `1825.7ms`.

Per-case adaptive comparison:

| Case | W/L/T vs canonical | Median delta | Deltas |
| --- | ---: | ---: | --- |
| `CMT2` | `2/3/0` | `+11.0` | `[-8.0, +11.0, -81.0, +90.0, +109.0]` |
| `CMT4` | `0/2/3` | `0.0` | `[0.0, 0.0, +1.0, +31.0, 0.0]` |
| `M-n151-k12` | `0/0/5` | `0.0` | `[0.0, 0.0, 0.0, 0.0, 0.0]` |
| `P-n76-k4` | `2/2/1` | `0.0` | `[0.0, -23.0, +14.0, +5.0, -10.0]` |

## Interpretation

The probe is a partial mechanism success:

- It cuts whole-matrix embedded-VNS runtime share from `0.651` to `0.361`.
- It raises mean ALNS iterations from `4.0` to `8.35`.
- It is much less damaging than broad embedded-VNS removal from the prior
  compact matrix (`+6.95` mean delta here versus `+17.3`).
- It does not preserve quality enough to accept as a default or campaign seed:
  paired quality is still worse overall at `4/7/9`.

Case behavior matters:

- `M-n151-k12` is all ties, so adaptive skipping appears harmless there.
- `CMT4` is mostly tied with two small losses.
- `P-n76-k4` still has mixed local opportunity, but not a stable rule.
- `CMT2` is volatile and currently the main warning against cadence-only
  skipping.

This supports adaptive scheduling as the next CVRP research surface, but the
trigger must become more selective than "every fourth iteration plus
repair-improvement." Do not launch a long LLM campaign from cadence-4 as-is.

## Next Step

Run a small follow-up no-LLM trigger matrix before proposal-context exposure.
Useful variants:

- `cadence2`: less aggressive skipping, expected to reduce quality loss while
  still improving ALNS iteration count.
- `improve_only`: embedded VNS only when the repaired candidate improves
  current or best before polish.
- dynamic cadence by remaining budget or recent best-update density.

Accept a variant for proposal context only if it reduces embedded-VNS pressure
without a paired-quality regression across the compact case set.
