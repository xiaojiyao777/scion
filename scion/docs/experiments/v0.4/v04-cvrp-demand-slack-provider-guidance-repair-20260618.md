# CVRP Demand-Slack Provider Guidance Repair - 2026-06-18

## Purpose

The latest CVRP current state rejects unchanged
`demand_slack_regret_insertion`, but the live CVRP solver-design provider still
only carried the older share70 and route-merge lessons. A fresh agentic run
could therefore repeat the just-rejected demand-slack branch despite the status
documents saying not to.

## Repair

- Added the demand-slack negative lesson to CVRP-owned hypothesis guidance.
- Added the same lesson to target-intent guidance, because target-intent runs
  before final hypothesis binding.
- The guidance is proposal-only and explicitly outside `DecisionFeatures`.
- The guidance says unchanged demand-slack/regret insertion should not be
  continued by default; any new destroy/repair hypothesis must preserve earlier
  A/E positives while explicitly addressing CMT2/CMT4, otherwise pivot to a
  materially different solver-design owner.
- The text directs follow-up case coverage to Protocol selection rather than
  case-id, BKS, seed, split-membership, Decision, gate, or budget hardcoding.

## Acceptance

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/unit/test_cvrp_solver_design_provider.py \
  scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py \
  scion/scion/tests/unit/test_hypothesis_context_profiles.py
```

Result: `61 passed`.

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion python -m py_compile \
  scion/scion/problems/cvrp/solver_design_provider.py \
  scion/scion/tests/unit/test_cvrp_solver_design_provider.py \
  scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py
```

Result: passed.

## Next

Run the next WSL CVRP agentic slice from a clean synchronized commit with
`gpt-5.5`. Acceptance should inspect live target-intent and hypothesis traces to
confirm the demand-slack lesson is present before interpreting the candidate.
