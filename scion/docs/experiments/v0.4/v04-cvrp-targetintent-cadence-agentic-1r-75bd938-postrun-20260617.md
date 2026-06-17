# CVRP Target-Intent Cadence Agentic 1R Postrun

Date: 2026-06-17
Branch: `codex/v04-evidence-repair-plan`
Commit: `75bd938`

## Purpose

Field-check the target-intent prompt repair. The acceptance question was whether
the first live `hypothesis_target_intent` trace could see the CVRP cadence-2
opportunity text before selecting target/action/mechanism.

## Run

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-targetintent-cadence-agentic-1r-75bd938-20260617T195330Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-cvrp-targetintent-cadence-agentic-1r-75bd938-20260617T195330Z`
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
  `tool_selection=4`, `code=2`)
- Formal screening metric:
  `campaign/metrics/ab716e3b-6108-4723-8c19-ab014e4c509d.json`
- Screening pairs: `32/32`, failures `0`
- Evidence status: `screening_evidence_status=complete`,
  `runtime_evidence_status=sufficient`, `runtime_confidence=high`
- Candidate branch: `d29ab511-c88b-4313-b01c-7616e29af2aa`
- Candidate status: `active_marginal`, retained as an active branch

The candidate implemented `cross_route_2opt_reconnect` in
`policies/baseline_modules/local_search.py`. It did not implement or refine the
intended adaptive embedded-VNS cadence-2 trigger.

Authoritative branch-card evidence classified the candidate as marginal:
case-level W/L/T `2/1/5`, median delta `0.0`, CI `[-3.0, 3.0]`, runtime ratio
median `1.0029618045955608`, runtime delta median `+86 ms`, and runtime
regression rate `0.65625`. Case-level positive signals appeared on
`P-n65-k10.vrp` and `CMT2.vrp`; losses appeared on `A-n64-k9.vrp`,
`B-n63-k10.vrp`, and `X-n110-k13.vrp`.

## Prompt Evidence

The target-intent repair worked for visibility. The live
`hypothesis_target_intent` trace contains:

- `Solver-design target-selection guidance`
- `adaptive embedded-VNS cadence-2`
- `Current CVRP no-LLM opportunity`
- `remaining-budget, recent best-update`
- `repaired-candidate-improvement signals`

The same trace selected:

- `target_file=policies/baseline_modules/local_search.py`
- `mechanism_id=cross_route_2opt_reconnect`
- `mechanism_family=vns_local_search`

The final hypothesis stayed bound to that preflight intent. That binding is
correct protocol behavior; the remaining issue is target-intent steering, not
binding or source visibility.

## Interpretation

Accepted:

- The target-intent prompt repair is field-verified: cadence-2 guidance is
  visible before target selection.
- The framework completed the short CVRP run cleanly with complete screening
  evidence, no failed pairs, retained formal candidate artifact, and
  high-confidence runtime evidence.
- Runtime saturation remained proposal-visible and excluded from
  `DecisionFeatures`.

Rejected:

- This is not cadence-2 adaptive embedded-VNS trigger evidence.
- The agent still chose another local-search operator after seeing the
  cadence-2 opportunity. The current CVRP guidance is visible but too weak or
  ambiguous for the active cadence-trigger follow-up.
- This is not CVRP solver improvement evidence. The candidate is marginal and
  slower by runtime diagnostics.

## Follow-Up Repair

Add problem-owned target-intent guidance for CVRP solver-design prompts. It
should make the current target-selection priority explicit: first evaluate the
adaptive embedded-VNS cadence-2 trigger refinement and choose the scheduler
owner unless same-branch constraints or explicit evidence justify a different
mechanism. Any non-cadence target should have to state the deviation reason in
the target-intent notes.

This remains proposal-only guidance. It must not change Decision, Protocol,
lifecycle policy, promotion gates, or `DecisionFeatures`.
