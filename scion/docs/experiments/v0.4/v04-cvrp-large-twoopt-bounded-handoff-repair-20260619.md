# v0.4 CVRP Large Two-Opt Bounded Handoff Repair

Date: 2026-06-19

## Purpose

The large-instance intra-route two-opt seed was already visible in the CVRP
prepared `research_focus`, but the key safety requirement was mostly prose:
future agents had to infer what "deadline-aware bounded" meant. That was too
weak for v0.4 effective-research acceptance because an agent could still repeat
the rejected unbounded `vrp/src/solver.py` fallback and produce evidence that is
not auditable against runtime semantics.

This repair makes the seed actionable and checkable without changing the CVRP
solver.

## Change

- Added structured `large_instance_two_opt_constraints` to the CVRP prepared
  `research_focus`.
- Projected that field into proposal-only `launch_research_focus` context so
  the hypothesis prompt can see it.
- Added prepared prompt-context readiness signal
  `cvrp_large_twoopt_bounded_constraints`.
- Added prepared contract and Phase 4 problem-specific coverage item
  `cvrp_large_twoopt_bounded_constraints_handoff`.
- Generated a new CVRP prepare-only root from WSL checkout `dc83d83`.

The structured constraints require future agents to:

- derive an explicit monotonic-clock deadline or remaining-time guard from the
  solver time limit;
- check wall-clock budget before each route, sweep, and accepted improvement;
- bound route/sweep/improvement effort and skip oversized work when remaining
  budget is too small;
- avoid unbounded `two_opt_intra` or VNS above the VNS threshold;
- preserve feasibility, remove empty routes, and report route-count changes;
- provide pair-level total-distance, feasibility, route-count, and wall-clock
  evidence.

## Boundary Check

- This is proposal/handoff/report coverage only.
- It does not change `DecisionFeatures`, Protocol gates, scheduler scoring,
  promotion input, or CVRP solver behavior.
- The large-instance two-opt seed remains problem-owned proposal guidance, not
  accepted Scion evidence or an accepted solver update.

## New Prepared Root

WSL command:

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent
export PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion
export SCION_API_KEY=pwd

/home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/launch_cvrp_agentic_campaign.py \
  --rounds 1 \
  --label v04-cvrp-large-twoopt-bounded-ready-dc83d83 \
  --model gpt-5.5 \
  --base-url http://127.0.0.1:8080 \
  --api-key-env SCION_API_KEY \
  --completion-preflight \
  --time-limit-sec 30 \
  --agentic-session-timeout-sec 900 \
  --stage-transition-drain-limit 4 \
  --control-pair-key cvrp.large-twoopt-bounded:rep01 \
  --resume-from-campaign /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-guidance-agentic-1r-acc21ba-20260618T064210Z/campaign \
  --experiments-root /home/xjy-ubuntu/research/scion-experiments
```

Prepared root:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-dc83d83-1r-gpt55-20260619T000530Z-claw`

Prepared manifest evidence:

- `git.commit=dc83d83`
- `control_pair_key=cvrp.large-twoopt-bounded:rep01`
- `large_instance_two_opt_constraints.schema_version=scion.cvrp_large_instance_two_opt_constraints.v1`
- `proposal_visibility_only=true`
- `decision_features_excluded=true`

Prepared handoff evidence:

- `cvrp_large_twoopt_bounded_constraints_handoff.available=true`
- `cvrp_large_twoopt_seed_handoff.available=true`
- `cvrp_large_twoopt_unbounded_default_avoid_handoff.available=true`
- `prompt_context_readiness.ready_for_launch_prompt_audit=true`
- `signals.cvrp_large_twoopt_bounded_constraints.available=true`

Strict launch readiness remains externally blocked:

```json
{
  "static_ready": true,
  "launch_ready": false,
  "completion": "failed",
  "http_status": 401,
  "classification": "not_authenticated",
  "error_code": "invalid_api_key",
  "auth_pool": {
    "active": 0,
    "expired": 1,
    "total": 1
  },
  "prompt": "ok",
  "git": "ok",
  "detail": "checkout matches manifest commit"
}
```

## Verification

Local:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/unit/test_research_surfaces_cvrp_context.py
# 45 passed
```

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/unit/test_research_surfaces_cvrp_context.py
# 45 passed
```

## Acceptance

Accepted as a CVRP launch-handoff repair. Once `gpt-5.5` auth is restored, the
current CVRP root can ask the agent to pursue the large-instance two-opt seed
without relying on an ambiguous prose-only "bounded" instruction and without
accepting the unbounded fallback diff.

Later current root:

- The `dc83d83`, `67f4da9`, and `529b9ef` roots were superseded after later
  runtime guard path changes.
- Current CVRP root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-a57fd07-1r-gpt55-20260619T004725Z-claw`.
- Current refresh report:
  `scion/docs/experiments/v0.4/v04-launch-readiness-problem-specific-handoff-visibility-20260619.md`.
