# CVRP Large Two-Opt Launch Focus Repair - 2026-06-18

## Purpose

Move the new large-instance intra-route two-opt evidence from a passive report
into the next CVRP prepared-run research focus, while keeping it proposal-only
and outside Scion decision machinery.

The unbounded `vrp/src/solver.py` diff remains unaccepted. The prepared focus
asks the agent to pursue the seed only as a deadline-aware bounded local-search
mechanism with pair-level objective, feasibility, route-count, and wall-clock
evidence.

## Code Change

- `scion/tools/launch_cvrp_agentic_campaign.py`
  - Adds the seed report path:
    `scion/docs/experiments/v0.4/v04-vrp-large-instance-two-opt-seed-evidence-20260618.md`
  - Changes the current CVRP question to prioritize the
    large-instance intra-route two-opt seed only as a deadline-aware bounded
    local-search mechanism.
  - Adds the unbounded large-instance two-opt fallback to default-avoid.
  - Adds the seed to `measurable_opportunity_classes`.
  - Adds an acceptance-focus reminder that this seed needs deadline-aware
    implementation and wall-clock evidence.
- `scion/scion/tests/test_cvrp_agentic_launcher.py`
  - Locks the seed, default-avoid, report path, and acceptance-focus text into
    the prepared manifest, manifest Markdown, and prepared analysis brief.

This is launch/handoff guidance only. It does not change `DecisionFeatures`,
Protocol gates, scheduler scoring, promotion, or the CVRP baseline solver.

## Verification

Local focused tests:

```bash
PYTHONPATH=scion pytest -q scion/scion/tests/test_cvrp_agentic_launcher.py
# 15 passed

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py
# 16 passed

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py
# 17 passed
```

Local prepare smoke confirmed the prepared manifest includes:

- current question mentioning the large-instance intra-route two-opt seed;
- default-avoid entry for unbounded large-instance two-opt fallback;
- measurable opportunity entry `large_instance_intra_route_two_opt_seed`;
- prompt-context readiness signals
  `prepared_research_focus_prompt_bridge=true`,
  `cvrp_measurable_opportunity_classes=true`, and
  `cvrp_default_avoid_directions=true`.

## New Prepared Root

After committing the launcher focus change at `ece0256`, the WSL checkout was
fast-forwarded and a new CVRP prepare-only root was generated:

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent
export PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion
export SCION_API_KEY=pwd

/home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/launch_cvrp_agentic_campaign.py \
  --rounds 1 \
  --label v04-cvrp-large-twoopt-seed-ready-ece0256 \
  --model gpt-5.5 \
  --base-url http://127.0.0.1:8080 \
  --api-key-env SCION_API_KEY \
  --completion-preflight \
  --time-limit-sec 30 \
  --agentic-session-timeout-sec 900 \
  --stage-transition-drain-limit 4 \
  --control-pair-key cvrp.large-twoopt-seed:rep01 \
  --resume-from-campaign /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-guidance-agentic-1r-acc21ba-20260618T064210Z/campaign \
  --experiments-root /home/xjy-ubuntu/research/scion-experiments
```

Prepared root:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-seed-ready-ece0256-1r-gpt55-20260618T231842Z-claw`

Static readiness:

```json
{
  "static_ready": true,
  "ready": true,
  "prompt": "ok",
  "contract": "ok",
  "git": "ok",
  "detail": "checkout matches manifest commit"
}
```

Strict launch readiness still fails only at the real completion preflight:

```json
{
  "exit_code": 64,
  "static_ready": true,
  "launch_ready": false,
  "completion": "failed",
  "chat": {
    "http_status": 401,
    "classification": "not_authenticated",
    "code": "invalid_api_key"
  },
  "auth_pool": {
    "active": 0,
    "expired": 1,
    "refreshing": 0,
    "total": 1
  }
}
```

The existing warehouse prepared root remains statically ready under checkout
`ece0256`; its git consistency detail is `checkout differs, but runtime guard
paths are unchanged`.

## Next Gate

Do not launch until

```bash
scion/tools/check_launch_readiness.py <prepared-root> \
  --require-launch-ready --format json
```

reports `launch_ready=true`.

When `gpt-5.5` auth is restored, launch the new CVRP large-twoopt-seed root
first. Postrun analysis must inspect whether the agent turns the seed into a
deadline-aware bounded mechanism, whether it avoids simply applying the
unbounded solver diff, and whether pair-level evidence clears the CVRP
MDE/runtime interpretation requirements.
