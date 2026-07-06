# CVRP Successor43b Destroy Shadow Protected Follow-Up Postrun

Date: 2026-07-06

## Status

- Fresh run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor43b-destroy-shadow-protected-followup-fresh-server-claw-2r-gpt55-2r-gpt55-20260706T133531Z-claw`
- Invalid resume root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor43b-destroy-shadow-protected-followup-server-claw-2r-gpt55-2r-gpt55-20260706T133342Z-claw`
- Launcher commit: `f8383943`
- Runner: server-local `claw`, local `gpt-5.5`
- Outcome: valid, complete, postrun-ready.
- Effective protocol rows: 2.
- Model calls: 11 total: target-intent 2, hypothesis 2, code 2,
  tool-selection 5.
- Quality/model/telemetry/verification/postrun failures: 0.

The resume root is not solver evidence. It inherited three active slots from
the copied campaign state and stopped with `scheduler_active_slot_blocked`
before any experiments.

## Mechanism

Mechanism id:
`bounded_destroy_operator_shadow_selector_protected_followup`

Owner boundary:

- `policies/baseline_modules/destroy_operator_selector.py`
- minimal wiring in `policies/baseline_modules/scheduler.py`

This was the only allowed protected same-line follow-up to successor43. It was
allowed to repair RNG isolation, selected destroy-operator attribution, and
default/alternate diagnostics. It was not allowed to add a new removal rule,
repair selector, route memory, route skeleton, local-search move, seed selector,
acceptance rule, or embedded-VNS runtime-allocation change.

## Screening Evidence

| row | decision signal | formal case W/L/T | pair W/L/T | median delta | CI | pair delta sum | runtime note |
|---|---:|---:|---:|---:|---:|---:|---|
| 1 | abandon | 2/4/6 | 19/27/2 | -1.0 | [-6.0, 1.5] | -135 | sufficient |
| 2 | expand/low-signal | 5/3/4 | 23/22/3 | 2.0 | [-3.25, 5.5] | 49 | low cached champion |

Combined raw pair evidence across both rows was 42/49/5 with median delta
about -1.0 and delta sum -86. Both rows were below the 9.9 MDE and no row was
positive-at-MDE.

Protected and loss-prone surfaces:

- CMT2: negative in both rows; combined seed votes 1/7/0, delta sum -74.
- CMT4: negative by median in both rows; combined seed votes 2/6/0, delta sum
  -110.
- B-n67-k10: negative in both rows; combined seed votes 2/6/0, delta sum -75.
- P-family: mostly neutral to weak-negative, not a broad positive surface.

Positive signal was concentrated in A/M/tai and some CMT3/E cases. That is not
broad enough to offset the protected-case and B-family losses.

## Trace And Code Audit

The live target-intent, hypothesis, and code traces bound to
`bounded_destroy_operator_shadow_selector_protected_followup`. Code-stage prompt
manifest inspection showed no code prompt truncation; the target files were
visible. The hypothesis stage had one preflight truncation, but the generated
hypothesis retained the mechanism id, target file, CMT2/CMT4 protection, RNG
isolation, and attribution obligations. There is no evidence that context loss
or model routing caused this result.

Implementation review found the main successor43 contract repairs mostly landed:

- the alternate shadow trial saves/restores RNG state;
- the selector returns the selected candidate, destroy index, destroy name, and
  reason;
- scheduler attribution uses the returned selected destroy index/name for
  adaptive weights and ALNS trace destroy labels.

Remaining diagnostics are incomplete:

- `selector_reason` is not surfaced in the ALNS iteration trace;
- default/alternate distance, route count, feasibility, reject reason, selected
  flag, and budget-skip diagnostics are not recorded as explicit trace fields;
- pre-VNS local selector delta was recorded as mechanism best-improvement
  evidence, which can overstate final trajectory effect.

These are telemetry-hygiene issues. They do not explain away the main solver
result because both rows still lost CMT2/CMT4/B and the local selector gains did
not preserve final solution quality.

## Noise Judgment

This is still a two-round screening result. Do not use it to estimate a precise
effect size or to conclude that the protected follow-up is strongly negative.

The reliable conclusions are narrower:

- the run is valid and complete;
- the mechanism activated and produced local pre-VNS selector movement;
- both rows were below MDE;
- CMT2/CMT4/B remained unsafe;
- the second row's weak-positive case-gate signal is low-SNR and below MDE;
- unchanged successor43b is not a promotion or long-run candidate.

## Decision

Park the destroy-shadow selector line for v0.4.

Do not long-run, threshold-tune, or run another same-mechanism follow-up for
`bounded_destroy_operator_shadow_selector` or
`bounded_destroy_operator_shadow_selector_protected_followup`.

The next CVRP solver slot should clean-fork to a materially different
CVRP-owned causal path while preserving the current exact
`material_difference.changed_dimensions` / `contrast` / `evidence` schema,
CMT2/CMT4 priority coverage, and design-first module boundary discipline.

Telemetry lessons to carry forward:

- selected operator attribution must match scheduler weights and traces;
- pre-VNS candidate-filter deltas are not final trajectory proof;
- default/alternate diagnostics should be explicit when a selector mechanism is
  proposed.
