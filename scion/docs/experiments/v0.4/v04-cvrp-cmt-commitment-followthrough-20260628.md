# CVRP CMT Commitment Follow-Through

Date: 2026-06-28

## Purpose

The seed-family review alignment made the proof-status root distinguish
observed large-twoopt activation/objective/phase evidence from the remaining
CMT case-protection gap. The next issue was whether that remaining gap reached
the next code-generation prompt as an actionable problem-owned checklist.

This repair keeps the change in the CVRP opportunity provider:

- Generic opportunity commitment/schema behavior is unchanged.
- `DecisionFeatures`, Protocol, scheduler, lifecycle, runtime pressure, and
  promotion behavior are unchanged.
- CVRP-owned `cmt2_cmt4_case_protection` now states that CMT protection
  requires case-level `total_distance` deltas for CMT2/CMT4, or a formal
  case-selection caveat.
- When postrun requirement status reports missing CMT protection, the code
  commitment required observations now include:
  `current postrun missing: missing_cmt_case_protection_evidence` and
  `case-level total_distance deltas still required for protected cases: CMT2, CMT4`.

## Artifact Recheck

Recomputed locally on the mirrored proof-status root:

`/home/clawd/research/scion-experiments/v04-cvrp-proofstatus-followup-05ade2e0-2r-gpt55-20260625T155106Z-claw`

The rebuilt CVRP opportunity requirement for `cmt2_cmt4_case_protection` now
projects:

- `status`: `current_run_selected_but_required_evidence_missing`
- `reason_codes`: `missing_cmt_case_protection_evidence`
- `protected_cases`: `CMT2`, `CMT4`
- required observations include CMT2/CMT4 case-level `total_distance` deltas
  and the current postrun missing field.

The derived code-phase `Opportunity Evidence Commitment` for
`large_instance_intra_route_two_opt_seed` contains both the observed objective
runtime requirement and the missing CMT protection requirement.

## Validation

Commands run locally with conda `claw`:

```bash
conda run -n claw pytest \
  scion/scion/tests/unit/test_cvrp_opportunity_provider.py \
  scion/scion/tests/unit/test_research_surfaces_cvrp_context.py \
  scion/scion/tests/unit/test_problem_opportunity_prompt_projection.py \
  scion/scion/tests/unit/test_cvrp_opportunity_usage_review.py \
  scion/scion/tests/test_cvrp_postrun_opportunity_brief.py -q
```

Result: `22 passed`.

```bash
conda run -n claw pytest scion/scion/tests/test_check_postrun_acceptance.py -q
```

Result: `85 passed`.

```bash
conda run -n claw python -m py_compile \
  scion/scion/problems/cvrp/opportunity.py \
  scion/scion/tests/unit/test_cvrp_opportunity_provider.py
git diff --check
```

Result: passed.

## Runtime Caveat

No new agentic CVRP run was launched in this slice. The local gpt-5.5 proxy at
`127.0.0.1:8080` is reachable, but `/auth/status` currently has no active
account and chat completion preflight returns `401 invalid_api_key`. Refresh
the local proxy login before launching the prepared server-side CVRP follow-up.
