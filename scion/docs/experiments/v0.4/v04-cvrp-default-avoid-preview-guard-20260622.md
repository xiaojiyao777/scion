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

The corrected launcher/run-script path was then used for the active forced
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

Current checkpoint:

- The live forced proposal/code path produced
  `bounded_interroute_2opt_bridge` in
  `policies/baseline_modules/local_search.py`.
- Schema preview, target/action preview, and static contract preview passed.
- Code generation completed and the candidate entered Protocol screening.
- Campaign status has reached `effective_rounds_completed=1` and
  `screening_protocol_results=1` with 0 quality blocks.
- The first complete screening row has 32/32 valid pairs, 10 wins, 8 losses,
  14 ties, and net raw delta `-59`.
- Runtime/mechanism evidence is real: the new
  `bounded_interroute_2opt_bridge` phase activated and recorded accepted moves,
  improvement counts, phase runtime, and objective-effect deltas in the
  candidate metrics.

This is an important v0.4 recovery checkpoint: the framework can now steer the
agent away from repeated acceptance-family proposals, generate a bounded
local-search mechanism, code it, and collect case-level screening evidence. The
specific candidate is not promotion-quality on the first row, so the next
decision should come from the complete forced-local postrun review rather than
from another unchanged rank-gap, route-pressure, or generic acceptance relaunch.

Operational caveat: this root was manually SIGTERM-stopped once after an
operator misread of resume artifacts, then restarted. While the restart is
running, the stale top-level `exit.txt` records the earlier SIGTERM; use
`campaign/run_status.json`, `campaign/status.json`, and the metrics artifacts as
the current live state.
