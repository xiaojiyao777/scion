# CVRP successor34 frozen-safe neighbor-list VNS filter in-flight

Date: 2026-07-01

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor34-frozen-safe-neighbor-list-vns-filter-server-2r-gpt55-20260701T192249Z-claw`

Runner: server-local `claw`

Model: local `gpt-5.5`

Runner commit: `fe7a1a14`

Environment: `http://127.0.0.1:8080`

Design input:
`scion/docs/experiments/v0.4/v04-cvrp-successor34-frozen-safe-neighbor-list-vns-filter-design-20260701.md`

## Question

Can `frozen_safe_neighbor_list_vns_filter` preserve successor33's
customer-adjacency VNS filtering signal while removing frozen candidate-side
timeouts through deadline guards, bounded fallback, direct budget/fallback
telemetry, and a cleaner neighbor-filter boundary?

## Launch command

```bash
/home/clawd/miniconda3/envs/claw/bin/python scion/tools/launch_cvrp_agentic_campaign.py \
  --label v04-cvrp-successor34-frozen-safe-neighbor-list-vns-filter-server \
  --rounds 2 \
  --time-limit-sec 30 \
  --model gpt-5.5 \
  --base-url http://127.0.0.1:8080 \
  --force-surface solver_design \
  --force-action modify \
  --force-target-file policies/baseline_modules/local_search.py \
  --completion-preflight \
  --launch
```

Forced launch controls:

- surface: `solver_design`
- action: `modify`
- target file: `policies/baseline_modules/local_search.py`
- rounds: `2`
- time limit: `30` seconds
- early stop: disabled by the launcher wrapper

Required target-intent mechanism:

`frozen_safe_neighbor_list_vns_filter`

Mechanism family:

`bounded_local_search_variant`

## Initial status

- launcher shell PID: `1384719`
- campaign started at `2026-07-01T19:22:53Z`
- outer `run_status.json`: `status=running`
- campaign `run_status.json`: `status=running`
- completion preflight: `ok=true`
- prepared manifest hard `required_mechanism_ids=[]`
- prepared manifest target-intent binding:
  `target_intent_required_mechanism_ids=["frozen_safe_neighbor_list_vns_filter"]`

## Live binding check

The first live target-intent trace selected:

- `change_locus=solver_design`
- `action=modify`
- `target_file=policies/baseline_modules/local_search.py`
- `mechanism_id=frozen_safe_neighbor_list_vns_filter`
- `mechanism_family=bounded_local_search_variant`
- `confidence=0.99`

The first formal hypotheses stayed on:

- `target_file=policies/baseline_modules/local_search.py`
- `mechanism_id=frozen_safe_neighbor_list_vns_filter`
- `mechanism_family=bounded_local_search_variant`

Both hypotheses describe a frozen-safe repair of successor33's
customer-adjacency filter inside existing VNS neighborhoods, with deadline
guards and bounded fallback. This is the intended successor34 causal path, not
a new move family or a scheduler/destroy-repair/seed/acceptance change.

## Monitor with

```bash
RUN_ROOT=/home/clawd/research/scion-experiments/v04-cvrp-successor34-frozen-safe-neighbor-list-vns-filter-server-2r-gpt55-20260701T192249Z-claw
jq '{status, run_validity_status, run_completeness_status, campaign_exit_status, postrun_acceptance_status}' "$RUN_ROOT/run_status.json"
jq '{status, wrapper_exit_status, wrapper_signal, started_at, ended_at}' "$RUN_ROOT/campaign/run_status.json"
jq '{run_complete, current_round, completed_rounds, branches: (.branches // [] | length), last_decision: .last_decision}' "$RUN_ROOT/campaign/status.json"
tail -80 "$RUN_ROOT/nohup.log"
```

## Analysis boundary

Judge successor34 by whether it preserves the successor33 screening/validation
signal and removes frozen candidate-side timeout failures. A safety-only patch
that disables local-search effect should be parked as no-effect; a positive
validation row must still survive frozen before it can be promotion-grade.

