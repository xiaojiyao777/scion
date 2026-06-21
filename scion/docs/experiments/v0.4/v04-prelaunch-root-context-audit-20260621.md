# v0.4 Prelaunch Root Context Audit

Date: 2026-06-21

Scope: current WSL prepared roots generated after scheduler-depth repair at WSL
runtime commit `896b9c06`. This is a launch-before-auth audit, not a postrun
result and not a Decision input.

## Boundary

The v3 boundary is preserved: prepared research focus, problem-owned
measurement diagnostics, branch-shape signals, source constraints, and prompt
bridge checks are proposal/control-plane material only. The audited reports
mark `report_only=true`, `quality_judgment=false`, and
`decision_features_excluded=true`; they do not mutate campaign, scheduler, or
promotion state.

## Roots

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-896b9c06-scheddepth-6r-gpt55-6r-gpt55-20260621T020223Z-claw`

Local mirror:

`/home/clawd/research/scion-experiments/v04-wh-v2-896b9c06-scheddepth-6r-gpt55-6r-gpt55-20260621T020223Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-896b9c06-scheddepth-resume-4r-gpt55-4r-gpt55-20260621T020237Z-claw`

Local mirror:

`/home/clawd/research/scion-experiments/v04-cvrp-twoopt-896b9c06-scheddepth-resume-4r-gpt55-4r-gpt55-20260621T020237Z-claw`

Both strict launch-readiness snapshots report `static_ready=true`,
`launch_ready=false`, `failed_static_required_checks=[]`, and only one required
failure: `completion_preflight`. The completion preflight returns HTTP `401`,
`classification=not_authenticated`, `code=invalid_api_key`, with auth pool
`active=0`, `expired=1`, `total=1`.

The headroom guard is clean for both roots. Exact `0` values for
`agentic_tool_max_steps`, `agentic_tool_max_calls`,
`agentic_code_tool_max_calls`, `agentic_observation_max_chars`,
`proposal_attempt_limit`, and `proposal_quality_loop_limit` are recorded as
explicitly disabled, not low nonzero caps.

## Warehouse Readiness

Prepared manifest:

`prepared_run_manifest.v1.json`

Key evidence:

- Model route: `gpt-5.5` via `http://127.0.0.1:8080`, completion preflight
  required.
- Resume source:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z/rep01/full_context/campaign`.
- Campaign command: 6 rounds, `--time-limit-sec 10`, `--disable-early-stop`,
  measurement governance on, full proposal context.
- Copied campaign summary reports `champion_version=2`, one copied branch
  snapshot, and `active_slots.used=0`, `active_slots.available=3`.
- The copied branch is already `parked_lineage` with quality-regression
  evidence, so the next live campaign should start a new champion-v2 follow-up
  rather than continue that lineage.

Prompt/context readiness:

`prepared_handoff/prompt_context_readiness/warehouse_on_full.prepared_prompt_context_readiness.v1.json`

Key evidence:

- `readiness.status=ready`, `missing_required=[]`.
- `prepared_research_focus_projection` has 8 manifest fields and no missing
  projected keys or paths.
- `prepared_research_focus_prompt_bridge` renders all required warehouse paths:
  `warehouse_v2_followup_present=true`,
  `warehouse_measurement_followup_opportunity_present=true`,
  `warehouse_measurement_plateau_guard_present=true`,
  `warehouse_measurement_required_diagnostics_present=true`,
  `warehouse_measurement_transfer_risk_present=true`,
  `warehouse_required_evidence_rendered_count=5`.
- Warehouse measurement/runtime handoff is available with
  `measurement_readiness_status=ready`, `runtime_model=comparative`,
  `pairing_validity=trajectory_divergent`, and screening MDE `577.5`.
- Active subject code constraints render the warehouse validation-transfer
  payload with `constraint_count=5`, `forbidden_pattern_count=5`,
  `warehouse_lexicographic_guard_present=true`, and
  `warehouse_validation_transfer_diagnostics_present=true`.

Conclusion: the warehouse root has enough launch-before-auth evidence to test
continuous improvement from champion `v2`. The main remaining warehouse risk is
empirical, not static: after auth is restored, the first live postrun must prove
whether Scion uses the v2 follow-up guidance to create a bounded operator with
activation/effect diagnostics, instead of misclassifying quality-blocked or
screening-only behavior as plateau evidence.

## CVRP Readiness

Prepared manifest:

`prepared_run_manifest.v1.json`

Key evidence:

- Model route: `gpt-5.5` via `http://127.0.0.1:8080`, completion preflight
  required.
- Resume source:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-guidance-agentic-1r-acc21ba-20260618T064210Z/campaign`.
- Campaign command: 4 rounds, `--time-limit-sec 30`,
  `--stage-transition-drain-limit 4`, `--disable-early-stop`, measurement
  governance on, full proposal context.
- Copied campaign summary reports `champion_version=1`, no branch cards, and
  `active_slots.used=0`, `active_slots.available=3`.

Prompt/context readiness:

`prepared_handoff/prompt_context_readiness/cvrp_on_full.prepared_prompt_context_readiness.v1.json`

Key evidence:

- `readiness.status=ready`, `missing_required=[]`.
- `prepared_research_focus_projection` has 11 manifest fields and no missing
  projected keys or paths.
- `prepared_research_focus_prompt_bridge` renders all required CVRP paths:
  `cvrp_bounded_twoopt_present=true`,
  `cvrp_case_protection_present=true`,
  `cvrp_case_protection_required_evidence_rendered_count=3`,
  `cvrp_case_protection_rule_rendered_count=4`,
  `cvrp_large_twoopt_implementation_constraint_rendered_count=5`,
  `cvrp_large_twoopt_required_pair_evidence_rendered_count=5`,
  `cvrp_measurement_mechanism_ranking_present=true`, and
  `cvrp_measurement_screening_headroom_present=true`.
- Case protection requirements explicitly name `CMT2` and `CMT4`.
- Large-instance two-opt constraints reject unbounded fallback and require a
  deadline-aware bounded implementation with pair-level objective,
  feasibility, route-count, and wall-clock evidence.
- Active source constraints render
  `cvrp_solver_design_code_constraints.v1` with `api_contract_count=2`,
  `constraint_count=2`, `object_model_hint_count=3`,
  `large_twoopt_runtime_guard_present=true`, and
  `unbounded_twoopt_reject_present=true`.
- Problem-owned measurement diagnostics expose 5 measurable opportunity
  classes, 5 opportunity diagnostics, 4 mechanism ranks, and mark the
  large-instance intra-route two-opt seed as the highest current follow-up.

Conclusion: the CVRP root has enough launch-before-auth evidence to test the
bounded large-instance intra-route two-opt follow-up. The main remaining CVRP
static caveat is that the copied resume campaign has no branch cards, so the
first live prompt relies on prepared research focus, prior target-intent trace
artifacts, and problem-owned diagnostics rather than a rich copied branch
lesson. If the live run still scatters into shallow variants, the next repair
should strengthen branch-continuity seeding for sparse-resume CVRP roots.

## Remaining Launch Risks

1. Completion auth is the only hard launch blocker. Do not launch either root
   until strict readiness reports `launch_ready=true`.
2. `raw_provider_prompt_rendered=false` in both prepared prompt/context reports.
   The readiness audit verifies prompt bridge rendering through deterministic
   summaries, but the first actual provider prompt still needs postlaunch
   inspection through scratch prompt manifests and LLM traces.
3. CVRP has no copied branch snapshot in the prepared root. This is not a
   static readiness failure, but it weakens branch-continuity evidence before
   the first live round.
4. Scheduler/runtime-pressure policy still permits a material clean fork after
   a same-branch diagnostic sample when repeated low-confidence/no-effect
   runtime pressure reaches the plateau gate. This is covered by existing tests
   as proposal-only/material-difference behavior, but it should be reviewed
   against live branch-depth evidence if the next runs remain shallow.

## Post-Auth Acceptance Focus

Warehouse live run:

- Confirm the first proposal starts from champion `v2`.
- Confirm prompt manifests include v2 follow-up, plateau guard, warehouse
  required evidence, and validation-transfer code constraints.
- Accept plateau only with protocol evidence below MDE, review-ready runtime
  evidence, and no fully missed same-mechanism follow-up opportunity.

CVRP live run:

- Confirm target-intent or hypothesis text names bounded/deadline-aware
  intra-route two-opt or a materially different solver-design mechanism.
- Confirm CMT2/CMT4 protection requirements appear before spending another
  branch slot.
- Require pair-level total-distance, feasibility, route-count, wall-clock, and
  CMT2/CMT4 evidence before treating a bounded two-opt claim as review-ready.

