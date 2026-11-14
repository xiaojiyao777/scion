# CVRP successor37 clean-fork material causal path in-flight

Date: 2026-07-05

## Run

Root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor37-cleanfork-material-causal-path-server-2r-gpt55-20260705T133809Z-claw`

Launch status:

- `status=running`
- `pid=1491574`
- `git_commit=289aaa8a`
- `model=gpt-5.5`
- `base_url=http://127.0.0.1:8080`
- `completion_preflight=true`
- `rounds=2`
- `time_limit_sec=30`
- `stage_transition_drain_limit=4`
- `postrun_reports=true`

This is a server-local `claw` run. It is intentionally small enough for the
2-core server; larger parallel follow-ups should use the WSL `scion` runner.

## Design Intent

Successor36b closed the temporary seed-post target-intent binding:
`seed_post_optimization_selector` activated and emitted direct telemetry, but
both rows had zero aggregate medians, no positive row at MDE, and CMT2
regressed. Successor37 therefore does not force `seed_selector.py`,
`force-surface`, `force-action`, or `force-target-file`.

The run relies on the updated CVRP-owned guidance:

- `target_intent_required_mechanism_ids=[]`;
- unchanged seed-post selector variants are reviewed/default-avoid;
- the next proposal should clean-fork to a materially different CVRP-owned
  causal path;
- the hypothesis must provide direct activation-to-objective evidence and
  CMT2/CMT4 protection evidence or an explicit unresolved caveat.

## Launch Command Shape

The generated run command uses:

- `--agentic-proposal`
- `--disable-early-stop`
- `--measurement-governance on`
- `--proposal-context-ablation full`
- no force target arguments.

## Follow-up

After completion, inspect `run_status.json`, `run.log`, and
`postrun_acceptance/research_efficiency.json`. If the run is valid and
complete, classify the selected mechanism by family and update the CVRP
successor evidence catalog only if it reached effective protocol rows.
