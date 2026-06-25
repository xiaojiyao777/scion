# CVRP Design Q/R Code-Prompt Commitment Postrun

Date: 2026-06-25

## Purpose

This fresh no-resume run validates the Design Q/R code-prompt opportunity
commitment relay after the local no-resume prepared-launch readiness fix. It
tests whether a selected problem-owned CVRP opportunity requirement is rendered
into code-generation prompts as `Opportunity Evidence Commitment` and then
audited by postrun visibility reports without parsing raw prompts or feeding
CVRP semantics into `DecisionFeatures`.

This is a relay and visibility validation run, not a solver-improvement
acceptance run.

## Artifacts

- WSL run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-designqr-codeprompt-fresh-23f24bca-data-2r-gpt55-20260625T140430Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-designqr-codeprompt-fresh-23f24bca-data-2r-gpt55-20260625T140430Z-claw`
- WSL isolated worktree:
  `/home/xjy-ubuntu/research/or-autoresearch-agent-a957fresh`
- WSL runtime commit at launch: `23f24bca`
- Local repair commit basis: `a957737f`
- Model: `gpt-5.5`
- Requested budget: `2` rounds
- Resume source: none
- Forced surface/action/target:
  `solver_design` / `modify` / `policies/baseline_modules/local_search.py`
- Prepared opportunity family:
  `large_instance_intra_route_two_opt_seed`

The local mirror was produced with
`scripts/sync_wsl_run_root.py --execute --skip-postrun-check --format json`.
For this WSL-origin root, the WSL postrun acceptance output is authoritative:
stored artifacts contain WSL absolute run identity paths, so the server-side
mirror is for audit reads, not for replacing WSL acceptance.

## Lifecycle

- Strict launch readiness: passed before launch, including `gpt-5.5`
  completion preflight and runtime guard.
- Wrapper exit/status: `0` / `finished`
- Campaign wrapper exit/status: `0` / `finished`
- Validity/completeness: `valid` / `complete`
- Stop reason: `max_rounds_exhausted`
- Requested/effective rounds: `2` / `2`
- Screening Protocol rows: `2`
- Validation/frozen rows: `0` / `0`
- Formal screened/evaluated candidates: `2` / `2`
- Proposal attempts total/consumed: `2` / `2`
- Proposal quality blocks: `0`
- Active-slot blocked attempts: `0`
- WSL postrun readiness: `current_run_analysis_ready=true`,
  `delegation_ready=true`
- Required readiness failures: none
- Optional readiness failures: `postrun_report_status_marker`

## Design Q/R Evidence

The code-generation prompt manifest contains the rendered commitment section
and the manifest-safe summary:

- Prompt manifest:
  `campaign/agentic_sessions/3cf8382c-85af-4647-9eb0-af5a27ad1be0/scratch/api_visible_prompt_manifest_0002_code.json`
- `call_kind`: `code`
- Rendered section: `opportunity_evidence_commitment`
- Section heading: `Opportunity Evidence Commitment`
- Commitment digest: `a70515cce42ea190`
- Source summary digest: `a87c477b333e0c2d`
- Selected mechanism ids:
  `large_instance_intra_route_two_opt_seed`
- Requirement ids:
  `large_instance_two_opt_objective_runtime_requirement`,
  `cmt2_cmt4_case_protection`
- Boundary flags:
  `proposal_visibility_only=true`, `report_only=true`,
  `decision_features_excluded=true`

Postrun prompt visibility confirms the relay was visible and not dropped:

- `trace_count=4`
- `commitment_summary_trace_count=1`
- `section_present_trace_count=1`
- `section_visible_trace_count=1`
- `full_section_visible_trace_count=1`
- `code_trace_count=1`
- `code_section_present_trace_count=1`
- `code_section_visible_trace_count=1`
- `commitment_summary_without_section_count=0`
- `code_commitment_summary_without_section_count=0`
- `truncated_section_trace_count=0`

The auxiliary resume root
`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-opportunity-commitment-relay-7394757b-2r-gpt55-20260625T132405Z-claw`
also finished postrun-ready and showed the same commitment digest with
code-section visible count `1` and summary-without-section count `0`. Because
that root resumed copied campaign state, this report treats it as supplemental
evidence only; the fresh no-resume root above is the clean validation.

## Research And Solver Signal

The run validates the relay, but it is still solver-negative and shallow by
design:

- Champion stayed `v1`
- Promotions: `0`
- Positive rows: `0`
- Rows at or above MDE: `0`
- Rows with CI high below MDE: `2`
- Max effect-to-MDE ratio: `0.0`
- MDE at 80 percent power: `9.9`
- Measurement interpretation: `all_available_ci_high_below_mde`
- CVRP large-twoopt interpretation:
  `protocol_evaluated_without_large_twoopt_signal`
- Max branch depth: `2`
- Same-mechanism follow-up: `1/1`
- Research-context actionability gaps: none
- Runtime budget diagnostics: `SCREENING_RUNTIME_BUDGET_SATURATION` on both
  screening rows, informational/report-only under the repaired
  budget-exhausting runtime semantics.

CVRP opportunity usage shows that the agent selected the prepared opportunity
family but did not prove the required evidence checklist:

- `opportunity_summary_visible=true`
- `usage_status=checklist_unproven`
- `used_opportunity=0`
- `contrasted_opportunity=0`
- `ignored_or_unproven=0`
- `default_avoid_repeat=0`
- `opportunity_evidence_checklist_unproven=2`
- Evidence gap:
  `proposal_selected_opportunity_without_required_evidence_checklist`

## Interpretation

Accepted v0.4 interpretation:

- Designs Q/R are live-validated for the code-prompt commitment relay on a
  fresh no-resume CVRP launch: selected problem-owned opportunity requirements
  reached the code prompt, were manifest-visible as `research_signal`, and were
  audited postrun with zero summary-without-section drops.
- The result does not show CVRP solver progress: both Protocol rows were below
  MDE, champion stayed `v1`, and large-twoopt review remained
  `protocol_evaluated_without_large_twoopt_signal`.
- The next CVRP/VRP work is problem-owned opportunity evidence quality: make
  the required objective/runtime and CMT2/CMT4 checklist directly actionable
  for the agent and auditable from structured proposal fingerprints. Do not add
  CVRP-specific scheduler, Protocol, runtime-pressure, or promotion gates to
  generic core for this failure shape.

## Boundary

This report is postrun and planning evidence. It does not change Decision,
`DecisionFeatures`, Protocol gates, scheduler policy, promotion policy,
runtime-pressure semantics, or generic Scion core. CVRP/BKS/CMT/ALNS/VNS/two-opt
semantics remain problem-owned.
