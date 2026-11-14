# CVRP Default-Avoid Preview Guard

Date: 2026-06-22

This report records the first post route-pressure CVRP relaunch attempt after
the launcher marked rank-gap and route-pressure acceptance variants as
default-avoid directions. The attempt was intentionally stopped before Protocol
evaluation because the live proposal still selected an acceptance-family target.

## Run

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-nonaccept-443b1a51-postroutepressure-4r-gpt55-20260622T073501Z-claw`
- WSL commit: `443b1a51`
- Resume source:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-nextmech-1aae436c-postrankgap-4r-gpt55-20260622T041502Z-claw/campaign`
- Strict launch readiness passed before launch.
- The run was manually stopped after the first proposal attempt and before any
  protocol rows were produced.
- Campaign status after stop: `last_stop_reason=signal:SIGTERM`,
  `run_validity_status=invalid_no_experiments`,
  `run_completeness_status=interrupted_incomplete`, 0 effective rounds, and 0
  protocol-evaluated rows.

## Finding

Prompt-only default-avoid guidance was not enough. The prepared handoff told the
agent not to spend the next branch slot on rank-gap, route-pressure, or generic
acceptance/adaptive-weighting variants unless it supplied a new non-acceptance
causal path and direct objective-effect telemetry. The live proposal still
started an acceptance-family candidate:

- Target file: `policies/baseline_modules/acceptance.py`
- Mechanism id: `distance_scaled_sa_reheat`
- Hypothesis shape: distance-scaled simulated-annealing reheating.

The root is not evidence about CVRP solver quality. It is evidence about
proposal control: `launch_research_focus.default_avoid_directions` must be
enforced in the proposal preview/quality path, not only rendered in the prompt.

## Repair

The follow-up repair keeps the v3 boundary intact:

- `launch_research_focus` remains proposal-only context.
- `DecisionFeatures`, Protocol, scheduler state, promotion, and solver
  semantics do not consume the prepared focus payload.
- `proposal.schema_preview` now returns a structured
  `launch_research_focus_default_avoid_guard` result and fails the hypothesis
  preview when the candidate matches a prepared default-avoid direction.

Focused tests cover both the blocked acceptance-family case and a nonmatching
bounded local-search case.

## Guarded Launch Probe

After synchronizing the first guard repair to WSL, a fresh root was prepared
and launched:

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-nonaccept-guard-24b609de-postroutepressure-4r-gpt55-20260622T075205Z-claw`
- WSL commit: `24b609de`
- Strict launch readiness: `launch_ready=true`, completion preflight healthy,
  runtime guard clean.
- Final status: wrapper effective exit `64`, postrun acceptance `failed`,
  `last_stop_reason=circuit_breaker`,
  `run_validity_status=invalid_no_effective_rounds`, 0 effective rounds, 0
  protocol rows, 3 proposal quality blocks.

The guard correctly stopped default-avoid hypotheses before Protocol rows, but
the first implementation matched some acceptance-family candidates to earlier
avoid strings such as `route-limit seed diversification` and
`simple initial-VNS disablement`. The cause was phrase matching over narrative
text. The follow-up repair tightens matching so multi-token avoid phrases must
also hit candidate identity fields (`target_file`, `change_locus`, or
`mechanism_changes`), while strong identity tokens such as `acceptance` still
block acceptance-family targets. A regression test now puts route-limit and VNS
avoid directions before the acceptance avoid direction and requires the
acceptance candidate to match the acceptance avoid entry.

## Next

After synchronizing the tightened guard to WSL, prepare a fresh CVRP root from
the new commit and monitor the first hypothesis:

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-nonaccept-tightguard-93a3b3c8-postroutepressure-4r-gpt55-20260622T080005Z-claw`
- WSL commit: `93a3b3c8`
- Strict launch readiness: `launch_ready=true`, completion preflight healthy,
  runtime guard clean.
- Final status: wrapper effective exit `64`, postrun acceptance `failed`,
  `last_stop_reason=repeated_quality_block_signature`,
  `run_validity_status=invalid_no_effective_rounds`, 0 effective rounds, 0
  protocol rows, 3 proposal quality blocks.

The tightened guard attributed the blocks to acceptance-family default-avoid
items instead of unrelated route-limit/VNS strings, so the matcher repair
worked. The live agent still selected acceptance-family targets three times
(`distance_scaled_acceptance`, `distance_rank_acceptance`, and another
acceptance variant) and never reached bounded local search. The remaining issue
is therefore not Protocol screening waste; it is target selection. The next
CVRP launch should use the existing `scion run` forced-surface diagnostic path,
exposed through the CVRP launcher, to force `solver_design` / `modify` /
`policies/baseline_modules/local_search.py` for a bounded-local-search probe.

An intermediate forced-local prepared root was intentionally discarded after
launch inspection showed that `command.txt` and the COMMAND marker contained the
force arguments but the generated `run.sh` execution block did not. The launcher
template now builds a `FORCE_ARGS` bash array and passes it to the actual
`scion.cli.main run` invocation; tests assert both command metadata and the real
run script execution block.

## Forced Local-Search Checkpoint

The corrected launcher/run-script path was then used for the forced
local-search root:

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-forced-local-eb2627e5-postroutepressure-4r-gpt55-20260622T081704Z-claw`
- WSL commit: `eb2627e5`
- Forced target:
  `--force-surface solver_design --force-action modify --force-target-file policies/baseline_modules/local_search.py`
- Resume source:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-nextmech-1aae436c-postrankgap-4r-gpt55-20260622T041502Z-claw/campaign`

Interpretation caveat: because this root resumes the route-pressure campaign,
the `agentic_session_index.json` contains older construction and
acceptance-family sessions from the resume source. They are not current forced
target failures. The current forced-local path starts at the local-search
sessions in this root.

Final checkpoint:

- The root finished current-run-ready with wrapper exit `0`, postrun readiness
  exit `0`, postrun acceptance `ready`, validity `valid`, completeness
  `complete`, and `last_stop_reason=max_rounds_exhausted`.
- Campaign status reached 4 effective screening rows, 0 quality blocks, 0
  proposal quality blocks, 0 promotions, and champion still `v1`.
- The forced proposal/code path produced local-search mechanisms in
  `policies/baseline_modules/local_search.py`, and mechanism telemetry shows
  activation and objective-effect events.
- The solver evidence is negative: `bounded_interroute_2opt_bridge` produced
  two marginal/negative rows, its refinement regressed, and
  `cmt_slack_aware_segment_swap` was abandoned. All rows were below MDE and
  had CI high below MDE.

This remains an important v0.4 recovery result: the framework can steer the
agent away from repeated acceptance-family proposals, generate local-search
mechanisms, code them, collect case-level screening evidence, and reject weak or
negative mechanisms. The specific mechanisms are not promotion-quality, so the
next CVRP decision should come from the completed forced-local postrun report
rather than from another unchanged rank-gap, route-pressure, generic acceptance,
or unchanged local-search relaunch:
`scion/docs/experiments/v0.4/v04-cvrp-forced-local-postroutepressure-postrun-20260622.md`.

The launcher prepared focus now includes the failed local-search mechanisms
(`bounded_interroute_2opt_bridge`, its high-asymmetric-promise refinement, and
`cmt_slack_aware_segment_swap`) as proposal-visible default-avoid directions.
Focused tests cover propagation into prepared manifests/handoffs and
schema-preview blocking for repeated `bounded_interroute_2opt_bridge`
hypotheses.
