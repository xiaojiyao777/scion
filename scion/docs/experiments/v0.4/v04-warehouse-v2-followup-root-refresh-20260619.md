# v0.4 Warehouse v2 Follow-Up Root Refresh

Date: 2026-06-19

## Purpose

The earlier warehouse champion-v2 follow-up root predated later runtime guard
path changes. Rather than treating a docs-only pointer refresh as current
operational truth, a new prepare-only warehouse root was generated from the
current WSL checkout so static readiness, prepared prompt/context readiness,
and runtime guard identity all agree before launch.

## New Prepared Root

WSL command:

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent
export PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion
export SCION_API_KEY=pwd

/home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/launch_warehouse_agentic_campaign.py \
  --rounds 6 \
  --label v04-warehouse-v2-followup-ready-35dd723 \
  --model gpt-5.5 \
  --base-url http://127.0.0.1:8080 \
  --api-key-env SCION_API_KEY \
  --completion-preflight \
  --time-limit-sec 30 \
  --agentic-session-timeout-sec 900 \
  --measurement-governance on \
  --proposal-context-ablation full \
  --control-pair-key warehouse.v2-followup:rep01 \
  --resume-from-campaign /home/xjy-ubuntu/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z/rep01/full_context/campaign \
  --warehouse-data-root /home/xjy-ubuntu/research/scion-data \
  --experiments-root /home/xjy-ubuntu/research/scion-experiments
```

Prepared root:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-35dd723-6r-gpt55-20260619T001002Z-claw`

Prepared manifest evidence:

- `git.commit=35dd723`
- `control_pair_key=warehouse.v2-followup:rep01`
- `resume_from_campaign=/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z/rep01/full_context/campaign`
- Research focus carries the champion-v2 checkpoint, plateau-vs-continuous
  improvement question, default-avoid directions, required evidence, and
  decision-boundary framing.

Prepared handoff evidence:

- `warehouse_continuous_plateau_question.available=true`
- `warehouse_decision_boundary_handoff.available=true`
- `warehouse_default_avoid_handoff.available=true`
- `warehouse_required_evidence_handoff.available=true`
- `warehouse_v2_checkpoint_handoff.available=true`

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

## Boundary Check

- This refresh is prepare-only.
- It does not start a campaign.
- It does not mutate campaign state, scheduler state, promotion state,
  `DecisionFeatures`, Protocol evidence, or warehouse solver semantics.
- The warehouse champion-v2 follow-up framing remains problem-owned handoff
  evidence for delegated review.

## Acceptance

Accepted as the current warehouse launch-prepared root. Once `gpt-5.5` auth is
restored and strict launch readiness reports `launch_ready=true`, this is the
warehouse root to launch for the simpler continuous-improvement proof.

Later current root:

- The `35dd723`, `67f4da9`, `529b9ef`, and `a57fd07` roots were superseded
  after later runtime guard path changes.
- Current warehouse root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-8c68347-6r-gpt55-20260619T005550Z-claw`.
- Current refresh report:
  `scion/docs/experiments/v0.4/v04-postrun-handoff-review-ready-guard-20260619.md`.
