# CVRP Proof-Status Follow-Up Postrun

Date: 2026-06-25

## Purpose

This run resumed the fresh Design Q/R CVRP root after the local
proof-status follow-through repair. Its purpose was to validate that
`cvrp_large_twoopt_summary` emits problem-owned
`evidence_requirement_statuses`, that `cvrp_opportunity_usage_summary`
projects those statuses as `required_evidence_proof`, and that the proof
remains separate from positive-at-MDE solver outcome.

This is not a solver-improvement acceptance run.

## Artifacts

- WSL run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-proofstatus-followup-05ade2e0-2r-gpt55-20260625T155106Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-proofstatus-followup-05ade2e0-2r-gpt55-20260625T155106Z-claw`
- WSL runtime commit at launch: `05ade2e0`
- Local commit basis: `e72a0b0e`
- Resume source:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-designqr-codeprompt-fresh-23f24bca-data-2r-gpt55-20260625T140430Z-claw/campaign`
- Model: `gpt-5.5`
- Requested continuation budget: `2`
- Agentic caps: tool steps/calls/code calls/observation chars all disabled
  with `0`; solver time limit remained `30s`.

The local mirror was produced with
`scripts/sync_wsl_run_root.py --execute --skip-postrun-check --format json`.
For this WSL-origin root, WSL postrun acceptance is authoritative.

## Lifecycle

- Completion preflight: healthy before launch.
- Wrapper exit/status: `0` / `finished`
- Validity/completeness: `valid` / `complete`
- Stop reason: `max_rounds_exhausted`
- Requested/effective rounds: `2` / `2`
- Screening Protocol rows: `2`
- Formal screened/evaluated candidates: `2` / `2`
- Proposal attempts total: `2`
- Proposal quality blocks: `0`
- Active-slot blocked attempts: `0`
- WSL postrun readiness: `current_run_analysis_ready=true`,
  `delegation_ready=true`
- Required readiness failures: none
- Optional readiness failures: `postrun_report_status_marker`

## Solver And Research Signal

The run remains solver-negative:

- Champion stayed `v1`
- Promotions: `0`
- Positive rows: `0`
- Rows at or above MDE: `0`
- Rows with CI high below MDE: `2`
- Max median delta: `0.0`
- Max effect-to-MDE ratio: `0.0`
- Measurement interpretation: `all_available_ci_high_below_mde`
- Same-mechanism follow-up: `2/2`
- Active research shape: `mixed_depth`

Both screening rows selected
`large_instance_intra_route_two_opt_seed` and recorded phase runtime buckets
for that mechanism, but the objective effect was zero.

## Proof-Status Evidence

The new schema path is present in the real postrun artifacts:

- `cvrp_large_twoopt_summary.evidence.evidence_requirement_statuses`
- `cvrp_opportunity_usage_summary.required_evidence_proof`

Current status:

- `cvrp_large_twoopt_summary.interpretation`:
  `protocol_evaluated_without_large_twoopt_signal`
- `evidence_requirement_statuses.status`: `incomplete`
- `required_evidence_proof.checklist_status`: `not_ready`
- `required_evidence_proof.outcome_direct_evidence_ready`: `false`
- `cvrp_opportunity_usage_summary.usage_status`: `checklist_unproven`
- `opportunity_evidence_checklist_unproven`: `4`

The missing checklist fields were:

- `missing_large_twoopt_mechanism_family`
- `missing_activation_observed`
- `missing_objective_effect_telemetry`
- `missing_phase_telemetry`
- `missing_cmt_case_protection_evidence`

## Interpretation

Accepted v0.4 interpretation:

- The proof-status carrier works on a live CVRP root and remains report-only,
  problem-owned, and excluded from `DecisionFeatures`.
- The run does not close the CVRP solver gap: rows were below MDE, champion
  stayed `v1`, and no promotion occurred.
- The important new finding is a CVRP problem-owned review mismatch:
  measurement rows and proposal fingerprints use the prepared opportunity id
  `large_instance_intra_route_two_opt_seed`, while the current large-twoopt
  review still fails the required checklist as missing large-twoopt mechanism
  family/direct evidence. The next repair should align the CVRP opportunity
  requirement proof with structured large-instance two-opt activation,
  objective, phase-runtime, and CMT2/CMT4 evidence without treating zero or
  below-MDE objective effects as solver success.

## Boundary

This report is postrun and planning evidence. It does not change Decision,
`DecisionFeatures`, Protocol gates, scheduler policy, promotion policy,
runtime-pressure semantics, or generic Scion core. CVRP/BKS/CMT/ALNS/VNS/two-opt
semantics remain problem-owned.
