# CVRP Share70 Agentic 1R Postrun

Date: 2026-06-17
Branch: `codex/v04-evidence-repair-plan`
Commit: `7e312a7`
Run: `/home/clawd/research/scion-experiments/v04-cvrp-share70-agentic-1r-7e312a7-20260617T214532Z`

## Purpose

This was the short agentic check after the fixed
`adaptive_embedded_vns_share70_cadence2` no-LLM diagnostic. The goal was to
verify that Scion can steer the CVRP agent to the intended scheduler-owned
share-70 refinement and then interpret the candidate evidence without treating
runtime savings as a promotion signal by itself.

## Launch

The run executed in WSL through the reverse SSH channel, then was synced back
to the server experiment root.

Command shape:

```bash
python -m scion.cli.main run \
  --problem .../cvrp/problem.yaml \
  --protocol .../cvrp/formal/protocol.yaml \
  --split .../cvrp/formal/split_manifest.yaml \
  --seeds .../cvrp/formal/seed_ledger.yaml \
  --campaign-dir "$ROOT/campaign" \
  --rounds 1 \
  --time-limit-sec 30 \
  --agentic-session-timeout-sec 900 \
  --measurement-governance on \
  --proposal-context-ablation compact-measurement-diagnostics \
  --disable-early-stop \
  --agentic-proposal
```

Model/proxy settings:

- `SCION_MODEL=gpt-5.5`
- `SCION_BASE_URL=http://127.0.0.1:8080`
- `SCION_LLM_TIMEOUT_SEC=120`
- `SCION_LLM_CODE_TIMEOUT_SEC=240`

## Run Outcome

- Wrapper exit: `0`.
- Run validity: `valid`.
- Requested rounds completed: `true`.
- Effective rounds completed: `1/1`.
- Formal screened candidates: `1`.
- Formal candidate artifacts: `1`.
- Screening pairs: `32/32` attempted and valid, `0` failed.
- LLM calls: `hypothesis_target_intent=1`, `hypothesis=1`,
  `tool_selection=4`, `code=1`, all `gpt-5.5`.
- Candidate decision: `expand_screening`.
- Decision reason: `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT`.

Artifact:

`campaign/artifacts/formal_candidates/8a00b04c/screening-80b2e55d-b52a-41cb-8e1b-9ac11d1b042a-18f2bbed0bd29611/`

## Steering Evidence

The steering repair held in the field.

The target-intent trace selected:

- `change_locus`: `solver_design`
- `action`: `modify`
- `target_file`: `policies/baseline_modules/scheduler.py`
- `mechanism_id`: `adaptive_embedded_vns_share70_trigger`

The final hypothesis stayed on the same scheduler-owned mechanism. It proposed
first-call protection, cumulative embedded-VNS runtime share, remaining-budget
gating, and repaired-candidate improvement signals. Keyword checks found the
share70/scheduler/adaptive-VNS guidance in target-intent, hypothesis,
tool-selection, and code traces.

## Candidate Patch

The patch touched only `policies/baseline_modules/scheduler.py`.

It:

- passed `reserve` into `_should_run_embedded_vns`;
- added a first eligible embedded-VNS call guard;
- treated embedded VNS runtime share `>= 0.70` as a hard skip;
- allowed objective-improving repaired candidates under the share cap;
- retained cadence activation below the share cap;
- recorded activation/runtime telemetry for
  `adaptive_embedded_vns_share70_trigger`.

This is a real refinement of the intended share70 scheduler mechanism, not a
local-search detour or prompt visibility failure.

## Screening Results

Lower candidate-minus-champion delta is better.

Overall:

| Pairs | W/L/T | Mean Delta | Median Delta | Runtime Ratio Median | Runtime Delta Median |
| ---: | ---: | ---: | ---: | ---: | ---: |
| `32` | `16/11/5` | `+2.0` | `-0.5` | `0.9993` | `-16 ms` |

Case level:

| Case | W/L/T | Mean | Median | Deltas |
| --- | ---: | ---: | ---: | --- |
| `A-n64-k9` | `3/1/0` | `-8.0` | `-12.5` | `[9, -11, -16, -14]` |
| `B-n63-k10` | `3/1/0` | `+3.5` | `-6.0` | `[38, -1, -11, -12]` |
| `CMT2` | `2/2/0` | `+6.0` | `+1.0` | `[32, 11, -9, -10]` |
| `CMT4` | `3/1/0` | `-11.25` | `-13.0` | `[-23, 4, -23, -3]` |
| `E-n101-k14` | `3/1/0` | `-4.75` | `-8.5` | `[-13, -14, 12, -4]` |
| `M-n200-k17` | `0/0/4` | `0.0` | `0.0` | `[0, 0, 0, 0]` |
| `P-n65-k10` | `1/3/0` | `-0.25` | `+1.5` | `[2, -7, 1, 3]` |
| `X-n110-k13` | `1/2/1` | `+30.75` | `+6.0` | `[12, -5, 116, 0]` |

Interpretation:

- The candidate fixed the prior CMT4 failure mode: CMT4 became a case-level
  win instead of a hard-case loss.
- M-n200 stayed neutral on all four seeds.
- X-n110 still has a large negative tail (`+116`), so the candidate is not a
  production solver improvement.
- Runtime is high-confidence but only a supporting signal under the current
  runtime evidence policy. Median runtime was essentially neutral.

## Telemetry

Activation/runtime telemetry for the new trigger was observed on all `32`
candidate runs:

- `solver_algorithm_context_records.adaptive_embedded_vns_share70_trigger_iterations`
- `solver_algorithm_phase_runtime_ms.adaptive_embedded_vns_share70_trigger`

The candidate embedded-VNS share averaged about `0.708`, close to the intended
share ceiling. The telemetry guard passed, but emitted repairable
effect-attribution diagnostics because the candidate did not record
mechanism-specific direct effect fields such as
`solver_algorithm_phase_improvement_counts.adaptive_embedded_vns_share70_trigger`
or `solver_algorithm_phase_best_delta.adaptive_embedded_vns_share70_trigger`.

This should not become a stricter gate. It is a proposal/code guidance repair:
future share70-trigger candidates should record direct effect telemetry with
`context.record_move('<mechanism>', attempted=1, accepted=..., delta=...,
best_improved=...)` when the triggered embedded VNS actually improves the
candidate.

## Decision

Accept this run as positive CVRP research-loop evidence:

- Scion selected the intended scheduler target.
- It generated a real mechanism-family refinement.
- It completed formal screening without infrastructure failures.
- It preserved and improved some hard-case behavior compared with the previous
  failed cadence trigger.
- It correctly avoided promotion and chose low-SNR expansion rather than
  over-reading runtime.

Do not accept the generated hard share70 cap as a default solver change. The
next CVRP work should continue the same scheduler mechanism family, with
special attention to the X-n110 tail loss and missing effect attribution.
