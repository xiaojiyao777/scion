# CVRP successor32 post-repair effect credit weighting in-flight

Date: 2026-07-01

Initial run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor32-post-repair-effect-credit-weighting-server-2r-gpt55-20260701T135711Z-claw`

Guarded-live run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor32-post-repair-effect-credit-weighting-server-guarded-live-2r-gpt55-20260701T141225Z-claw`

Commits:

- `f8ca1bc5`: exposed CVRP top opportunity in launcher payload
- `eda5e0c0`: added CVRP `cvrp_successor32_focus` formal-hypothesis guard
- current repair: generic `target_intent_required_mechanism_ids` binding before
  relaunch

Environment: server-local `claw`, local `gpt-5.5`,
`http://127.0.0.1:8080`.

Launch readiness:

- `launch_ready=true`
- completion preflight: healthy, `completion_code=ok`
- runtime guard: clean and commit-matched
- prepared contract/readiness: no required blockers

Forced launch controls:

- surface: `solver_design`
- action: `modify`
- target file: `policies/baseline_modules/scheduler.py`
- rounds: `2`
- time limit: `30` seconds
- early stop: disabled

Required mechanism:

`post_repair_effect_credit_weighting`

Mechanism family:

`acceptance_or_adaptive_weighting`

Design/report input:

`scion/docs/experiments/v0.4/v04-cvrp-successor32-post-repair-effect-credit-weighting-design-20260701.md`

The prepared manifest now carries `top_opportunity_recipe.mechanism_id` =
`post_repair_effect_credit_weighting`, with `target_files` =
`["policies/baseline_modules/scheduler.py"]`.
The current repair additionally carries
`target_intent_required_mechanism_ids=["post_repair_effect_credit_weighting"]`
while keeping hard `required_mechanism_ids=[]`.

Initial status:

- launched with `nohup setsid bash run.sh > nohup.log 2>&1 &`
- shell PID reported: `1348649`
- `run_status.json` moved from prepared-only to `status=running`
- `run.log` reached `Starting campaign: cvrp ... force_surface=solver_design`
- early campaign status showed `proposal_attempts_total=1` and
  `formal_screened_candidates=0`

Aborted first launch:

- stopped with SIGTERM at 2026-07-01T14:02Z before any effective round
- `effective_rounds_completed=0`
- `formal_screened_candidates=0`
- `protocol_evaluated_candidates=0`
- live hypothesis drifted to `pair_failure_cooldown_selection`, not the
  required `post_repair_effect_credit_weighting`
- do not treat this root as successor32 solver evidence

Follow-up guard before relaunch:

- add CVRP problem-owned `cvrp_successor32_focus` hypothesis quality gate
- block scheduler.py successor32 proposals unless the formal hypothesis names
  `post_repair_effect_credit_weighting`
- update target-intent guidance away from stale share70 scheduler text toward
  the successor32 operator-credit causal path
- add generic proposal-only target-intent binding so live target selection is
  rewritten to `post_repair_effect_credit_weighting` before formal hypothesis
  generation, without disabling prepared-successor conflict arbitration

Guarded-live status after formal guard:

- stopped with SIGTERM after three quality blocks and before screening
- `effective_rounds_completed=0`
- `formal_screened_candidates=0`
- blocked mechanisms: `elite_current_restart`,
  `repair_failure_pair_filter`, `runtime_normalized_pair_credit`
- interpretation: fail-closed formal guard evidence, not successor32 solver
  evidence

Monitor with:

```bash
RUN_ROOT=/home/clawd/research/scion-experiments/v04-cvrp-successor32-post-repair-effect-credit-weighting-server-2r-gpt55-20260701T135711Z-claw
jq '{status, completed_rounds, stop_reason, proposal_attempts_total, formal_screened_candidates}' "$RUN_ROOT/campaign/status.json"
tail -80 "$RUN_ROOT/run.log"
tail -80 "$RUN_ROOT/nohup.log"
```

Next relaunch command:

```bash
/home/clawd/miniconda3/envs/claw/bin/python scion/tools/launch_cvrp_agentic_campaign.py \
  --label v04-cvrp-successor32-post-repair-effect-credit-weighting-server-target-bound \
  --rounds 2 \
  --time-limit-sec 30 \
  --model gpt-5.5 \
  --base-url http://127.0.0.1:8080 \
  --force-surface solver_design \
  --force-action modify \
  --force-target-file policies/baseline_modules/scheduler.py \
  --completion-preflight \
  --launch
```
