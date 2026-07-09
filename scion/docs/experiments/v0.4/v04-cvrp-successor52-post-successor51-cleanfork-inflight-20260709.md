# CVRP successor52 post-successor51 clean fork in flight - 2026-07-09

## Scope

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor52-post-successor51-cleanfork-server-claw-2r-gpt55-20260709T020546Z-claw`

Successor52 is the first clean-fork launch after successor51 recorded
`bounded_route_arc_lns_rebuild` as valid active-marginal below-MDE and
protected-case unsafe evidence.

## Launch

Launcher commit: `1869299c`.

Command:

```bash
/home/clawd/miniconda3/envs/claw/bin/python \
  scion/tools/launch_cvrp_agentic_campaign.py \
  --rounds 2 \
  --label v04-cvrp-successor52-post-successor51-cleanfork-server-claw \
  --proposal-context-ablation full \
  --force-surface solver_design \
  --completion-preflight \
  --launch
```

PID: `1821540`.

Run command recorded by launcher:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m scion.cli.main run \
  --problem scion/problems/cvrp/problem.yaml \
  --protocol scion/problems/cvrp/formal/protocol.yaml \
  --split scion/problems/cvrp/formal/split_manifest.yaml \
  --seeds scion/problems/cvrp/formal/seed_ledger.yaml \
  --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-successor52-post-successor51-cleanfork-server-claw-2r-gpt55-20260709T020546Z-claw/campaign \
  --rounds 2 \
  --time-limit-sec 30 \
  --agentic-session-timeout-sec 3600 \
  --agentic-tool-max-steps 0 \
  --agentic-tool-max-calls 0 \
  --agentic-code-tool-max-calls 0 \
  --agentic-observation-max-chars 0 \
  --proposal-attempt-limit 0 \
  --proposal-quality-loop-limit 0 \
  --fresh-runtime-replay-drain-limit 0 \
  --stage-transition-drain-limit 4 \
  --measurement-governance on \
  --proposal-context-ablation full \
  --force-surface solver_design \
  --disable-early-stop \
  --agentic-proposal
```

## Readiness Snapshot

- Server-local runner: conda `claw`.
- Model: local `gpt-5.5`, base URL `http://127.0.0.1:8080`.
- Completion preflight: healthy chat completion, HTTP 200, `ok=true`.
- Runtime guard paths were clean before launch.
- Prepared manifest is report-only and excludes research focus from
  `DecisionFeatures`.
- `required_mechanism_ids=[]`.
- `target_intent_required_mechanism_ids=[]`.
- Prepared `reviewed_mechanism_ids` contains
  `bounded_route_arc_lns_rebuild`.
- Prepared default-avoid directions contain an unchanged
  `bounded_route_arc_lns_rebuild` warning.

## Initial Runtime Check

Immediately after launch:

- root `run_status.json`: `status=running`, `prepared_only=false`;
- campaign `status.json`: one explore branch
  `ba84a8af-34b9-45ef-9c7e-4ae34437dfab`;
- proposal attempts observed: `1`;
- initial LLM trace files:
  - `20260709T020550053193_hypothesis_target_intent_c6b9b3489a_9ae8dd70.json`
  - `20260709T020608564362_hypothesis_2ae2d96a5c_7ba64e87.json`

## Acceptance Notes

Interpret successor52 only after postrun acceptance is ready. The important
checks are:

- whether the next mechanism is materially different from
  `bounded_route_arc_lns_rebuild` and other reviewed/default-avoid directions;
- whether prompt manifests keep the successor51 reviewed evidence visible
  without truncating solver-design source;
- whether CMT2/CMT4 priority cases are effective in screening;
- whether direct telemetry is tied to final or post-downstream total-distance
  attribution rather than phase-local deltas only.
