# CVRP Opportunity-Recipe Postrun

Date: 2026-06-25

## Purpose

This run resumed the clean current-sync CVRP campaign after the Design P
problem-owned opportunity summary was added. Its purpose was to test whether
CVRP opportunity diagnostics reach later proposal contexts and steer the agent
toward the prepared large-instance intra-route two-opt seed opportunity.

This is not a Design Q/R validation run. The WSL root launched before the local
code-prompt `Opportunity Evidence Commitment` relay and postrun commitment
visibility slices were implemented, so code prompts in this root are not
expected to contain that section.

## Artifacts

- WSL run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-opportunity-recipe-resume-633d1d25-4r-gpt55-20260625T110617Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-opportunity-recipe-resume-633d1d25-4r-gpt55-20260625T110617Z-claw`
- WSL runtime commit at launch: `633d1d25`
- Resume source:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-current-sync-d3efc3cb-postsolverdepth-6r-gpt55-20260623T182433Z-claw`
- Model: `gpt-5.5`
- Requested continuation budget: `4`
- Prepared opportunity family:
  `large_instance_intra_route_two_opt_seed`

The local mirror was produced with
`scripts/sync_wsl_run_root.py --execute --skip-postrun-check --format json`.
For this WSL-origin root, the WSL postrun acceptance output is authoritative:
stored artifacts contain WSL absolute run identity paths, so a server-side
mirror is for audit reads, not for replacing the WSL acceptance result.

## Lifecycle

- Wrapper exit/status: `0` / `finished`
- Validity/completeness: `valid` / `complete`
- Stop reason: `max_rounds_exhausted`
- Requested/effective rounds: `4` / `4`
- Screening Protocol rows: `4`
- Validation/frozen rows: `0` / `0`
- Formal screened/evaluated candidates: `4` / `4`
- Proposal attempts total/consumed: `4` / `4`
- Proposal quality blocks: `0`
- Champion version: `1`
- Promotions: `0`
- WSL postrun readiness: `current_run_analysis_ready=true`,
  `delegation_ready=true`
- Required readiness failures: none
- Optional readiness failures: `postrun_report_status_marker`

## Measurement Signal

This is not solver progress.

- Measurement readiness: `ready`
- Protocol rows: `4`
- Positive rows: `0`
- Rows at or above MDE: `0`
- Rows with CI high below MDE: `4`
- Max effect-to-MDE ratio: `0.0`
- Measurement interpretation: `all_available_ci_high_below_mde`
- CVRP large-twoopt interpretation:
  `protocol_evaluated_without_large_twoopt_signal`

The four current screening rows were weak pair-level signals, not MDE-level
effects:

| Metric | Pairs | Pair W/L/T | Net distance delta | Large-twoopt observed/nonzero | Weighted ms |
|---|---:|---:|---:|---:|---:|
| `a5c67853-99f3-414a-a580-f7a0c3bd55f4` | 48 | 0/1/47 | -4 | none | none |
| `af247710-0ad4-4003-a85d-63c324737f4a` | 32 | 3/1/28 | +14 | 20/20 | 268 |
| `300f0849-f404-4475-b4d5-aa329b0877d6` | 48 | 4/1/43 | +20 | 40/40 | 412 |
| `48734ebe-0d33-4edf-88fa-bdacaefccf96` | 32 | 4/1/27 | +20 | 20/20 | 197 |

CMT2/CMT4 protected-case deltas remained mixed or flat. The recurring CMT2
pattern was `[-9, +8, +11, +7]` on the later rows, while CMT4 was all zero.
That is useful diagnostic evidence, but not a review-ready solver improvement.

## Opportunity Visibility

The run validates the Design P visibility path:

- `Problem Opportunity Summary` was present and visible in hypothesis prompts.
- Postrun prompt-context visibility reported
  `hypothesis_generation_section_visible_trace_count=2`.
- CVRP opportunity usage summary was `mixed`.
- Usage counts: `used_opportunity=4`, `contrasted_opportunity=56`,
  `default_avoid_repeat=2`, `ignored_or_unproven=0`,
  `opportunity_evidence_checklist_unproven=0`, `uninterpretable=1`.
- Evidence gap: `proposal_repeats_default_avoid_family`.

The important positive result is not promotion. It is that the problem-owned
opportunity summary reached proposal context and later proposal traces can be
audited without parsing raw prompts or feeding CVRP semantics into
`DecisionFeatures`.

The code-phase opportunity commitment visibility aggregate is empty for this
root by design. The root launched before Design Q/R, so absence of
`Opportunity Evidence Commitment` is not a failure for this experiment.

## Interpretation

Accepted v0.4 interpretation:

- Design P is validated for CVRP proposal visibility: the prepared opportunity
  diagnostics were visible to hypothesis generation and postrun reports can
  audit usage at the proposal level.
- The run remains solver-negative: champion stayed `v1`, promotions were `0`,
  all four measurement rows were below MDE, and large-twoopt review stayed
  `protocol_evaluated_without_large_twoopt_signal`.
- The framework no longer fails mainly by shallow control-flow blockers in this
  root: four effective rounds completed with no proposal quality blocks and no
  active-slot blockage.
- The remaining CVRP/VRP gap is problem-owned solver opportunity quality and
  code-phase implementation/evidence follow-through, not a reason to add
  CVRP-specific gates or ALNS/VNS/two-opt semantics to generic core.

## Next Step

The next launch should sync the post-Design-Q/R local code to WSL only after no
active WSL run is using that checkout. It should validate that selected
opportunity requirements appear in code prompts as
`Opportunity Evidence Commitment`, and that postrun reports show either visible
commitment sections or the new summary-without-section audit counts.

## Boundary

This report is postrun and planning evidence. It does not change Decision,
`DecisionFeatures`, Protocol gates, scheduler policy, promotion policy,
runtime-pressure semantics, or generic Scion core. CVRP/BKS/CMT/ALNS/VNS/two-opt
semantics remain problem-owned.
