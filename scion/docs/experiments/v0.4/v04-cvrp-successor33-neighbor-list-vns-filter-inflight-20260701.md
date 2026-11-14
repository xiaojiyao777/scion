# CVRP successor33 neighbor-list VNS filter in-flight

Date: 2026-07-01

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor33-neighbor-list-vns-filter-server-2r-gpt55-20260701T160210Z-claw`

Runner: server-local `claw`

Model: local `gpt-5.5`

Runner commit: `b579797d`

Environment: `http://127.0.0.1:8080`

Design input:
`scion/docs/experiments/v0.4/v04-cvrp-successor33-neighbor-list-vns-filter-design-20260701.md`

## Question

Can `neighbor_list_vns_filter` improve CVRP `total_distance` by filtering or
ordering candidate enumeration inside existing VNS neighborhoods, while keeping
the move families, acceptance policy, destroy/repair policy, construction
seeds, scheduler q policy, operator credit, embedded-VNS runtime allocation,
and generic core unchanged?

## Launch command

```bash
/home/clawd/miniconda3/envs/claw/bin/python scion/tools/launch_cvrp_agentic_campaign.py \
  --label v04-cvrp-successor33-neighbor-list-vns-filter-server \
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

`neighbor_list_vns_filter`

Mechanism family:

`bounded_local_search_variant`

## Initial status

- launcher shell PID: `1370329`
- campaign run PID: `1370361`
- outer `run_status.json`: `status=running`
- campaign `run_status.json`: `status=running`
- completion preflight: `ok=true`, chat healthy, HTTP 200, authenticated
- prepared manifest hard `required_mechanism_ids=[]`
- prepared manifest target-intent binding:
  `target_intent_required_mechanism_ids=["neighbor_list_vns_filter"]`

The run was launched after the guidance commit that moved the top CVRP
opportunity from successor32 operator credit to successor33 local-search
candidate filtering. Do not compare this root against the earlier successor32
roots as a same-mechanism continuation.

## Live binding check

The first live target-intent trace selected:

- `change_locus=solver_design`
- `action=modify`
- `target_file=policies/baseline_modules/local_search.py`
- `mechanism_id=neighbor_list_vns_filter`

The first formal hypothesis stayed on:

- `target_file=policies/baseline_modules/local_search.py`
- `mechanism_id=neighbor_list_vns_filter`
- `mechanism_family=bounded_local_search_variant`

The hypothesis proposes nearest-neighbor or route-neighbor candidate ordering
inside existing VNS neighborhoods such as relocate, Or-opt, swap, and
two-opt-star. This is the intended successor33 causal path, not a replay of
successor32 scheduler/operator-credit behavior.

## Monitor with

```bash
RUN_ROOT=/home/clawd/research/scion-experiments/v04-cvrp-successor33-neighbor-list-vns-filter-server-2r-gpt55-20260701T160210Z-claw
jq '{status, run_validity_status, run_completeness_status, campaign_exit_status, postrun_acceptance_status}' "$RUN_ROOT/run_status.json"
jq '{status, wrapper_exit_status, wrapper_signal, ended_at}' "$RUN_ROOT/campaign/run_status.json"
jq '{run_complete, current_round, completed_rounds, branches: (.branches // [] | length), last_decision: .last_decision}' "$RUN_ROOT/campaign/status.json"
tail -80 "$RUN_ROOT/run.log"
tail -80 "$RUN_ROOT/nohup.log"
```

## Analysis boundary

When this completes, judge it by objective effect against CVRP A/A MDE and
protected CMT2/CMT4/P-family behavior. Treat runtime movement, extra local
search iterations, or mechanism activation as necessary but not promotion
evidence. If both rows are exact zero-effect or below MDE, park unchanged
`neighbor_list_vns_filter` as reviewed/default-avoid before selecting the next
CVRP causal path.
