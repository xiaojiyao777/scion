# CVRP Priority Cadence Agentic 1R Postrun

Date: 2026-06-17
Branch: `codex/v04-evidence-repair-plan`
Commit: `0ac863a`

## Purpose

Field-check the CVRP target-selection-priority repair. The acceptance question
was whether the live `hypothesis_target_intent` call would select the intended
scheduler-owned adaptive embedded-VNS cadence-2 trigger refinement instead of
another local-search mechanism.

## Run

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-priority-cadence-agentic-1r-0ac863a-20260617T203421Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-cvrp-priority-cadence-agentic-1r-0ac863a-20260617T203421Z`
- Model: `gpt-5.5`
- Command shape: CVRP formal protocol, `--rounds 1`, `--time-limit-sec 30`,
  `--agentic-session-timeout-sec 900`, `--measurement-governance on`,
  `--proposal-context-ablation compact-measurement-diagnostics`,
  `--disable-early-stop`, `--agentic-proposal`
- Wrapper exit: `0`

## Outcome

- Run completeness: `complete`
- Run validity: `valid`
- Effective rounds: `1`
- Formal candidate artifacts: `1`
- Protocol rows: `1`
- LLM traces: `8` (`hypothesis_target_intent=1`, `hypothesis=1`,
  `tool_selection=5`, `code=1`)
- Formal screening metric:
  `campaign/metrics/6741100e-04d2-4b19-8f78-5c7376302768.json`
- Screening pairs: `32/32`, failures `0`
- Evidence status: `screening_evidence_status=complete`,
  `runtime_evidence_status=sufficient`, `runtime_confidence=high`
- Candidate branch: `9e31b328-c068-46e3-b1e3-ada8cc8b8468`
- Candidate status: `discarded`; no active branches remain

The target-intent acceptance check passed. The live target-intent artifact
selected:

- `target_file=policies/baseline_modules/scheduler.py`
- `mechanism_id=adaptive_embedded_vns_cadence2_trigger`
- `mechanism_family=embedded_vns_cadence2_trigger`

The notes explicitly cited the repaired priority guidance and scheduler
ownership of `_should_run_embedded_vns` plus the ALNS/VNS integration loop.

## Candidate

The generated patch modified `policies/baseline_modules/scheduler.py`.
It added an adaptive cadence-2 embedded-VNS gate:

- require even ALNS iteration
- require repaired-candidate distance
- require `remaining_time() > reserve * 2.0`
- block VNS when a recent best improvement happened within a bounded window
- run VNS only when repaired candidate is near current or best cost
- record activation and runtime under
  `adaptive_embedded_vns_cadence2_trigger`

This is the intended research family and owner target. It is not another
local-search detour.

## Evidence

The candidate failed objective screening and was discarded:

- Generic tier: `regression`
- Case-level W/L/T: `2/1/5`
- Median delta: `-0.25`
- CI: `[-6.0, 3.5]`
- Why abandoned: `SCREENING_FAIL_WIN_RATE`,
  `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`,
  `SCREENING_SOFT_ABANDON_NEGATIVE_DELTA`
- Positive cases: `A-n64-k9.vrp` delta `+7.0`, `P-n65-k10.vrp` delta `+3.5`
- Negative cases: `CMT4.vrp` delta `-22.0`, `X-n110-k13.vrp` delta `-6.0`

Runtime evidence was positive but supporting only:

- Runtime ratio median: `0.993630901607996`
- Runtime delta median: `-155.5 ms`
- Runtime regression rate: `0.09375`
- Runtime pairs: `32`

The runtime signal stayed proposal-visible and excluded from `DecisionFeatures`;
it did not override the objective fail.

## Interpretation

Accepted:

- The CVRP target-selection-priority repair works in the field. The agent
  selected scheduler-owned cadence-trigger refinement before code generation.
- The framework produced a real, targeted CVRP solver-design candidate, ran a
  complete formal screening matrix, recorded replayable formal candidate
  artifacts, and discarded the branch for objective evidence rather than
  infrastructure noise.
- The candidate is scientifically useful negative evidence: it saves runtime,
  but the current trigger over-prunes useful VNS on `CMT4` and `X-n110-k13`.

Rejected:

- The generated trigger is not a solver improvement.
- The branch should not be resumed without new evidence because it was
  objective-negative despite runtime savings.
- Runtime speedup alone is not sufficient for promotion or continuation.

## Next Research Direction

This should now move from framework repair to mechanism analysis. The useful
next CVRP work is to inspect the scheduler patch and case deltas, then design a
new trigger that keeps the runtime savings while avoiding `CMT4` and
`X-n110-k13` quality losses. Candidate directions include less aggressive
recent-best blocking, a narrower near-incumbent threshold, or repaired-candidate
improvement gating that preserves VNS on medium/large cases where pruning
caused objective loss.

This remains problem-owned solver-design research. No Decision, Protocol,
lifecycle, promotion, or `DecisionFeatures` change is justified by this run.
