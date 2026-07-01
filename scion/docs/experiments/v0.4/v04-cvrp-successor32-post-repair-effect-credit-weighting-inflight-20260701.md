# CVRP successor32 post-repair effect credit weighting in-flight

Date: 2026-07-01

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor32-post-repair-effect-credit-weighting-server-2r-gpt55-20260701T135711Z-claw`

Commit: `f8ca1bc5`

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

Monitor with:

```bash
RUN_ROOT=/home/clawd/research/scion-experiments/v04-cvrp-successor32-post-repair-effect-credit-weighting-server-2r-gpt55-20260701T135711Z-claw
jq '{status, completed_rounds, stop_reason, proposal_attempts_total, formal_screened_candidates}' "$RUN_ROOT/campaign/status.json"
tail -80 "$RUN_ROOT/run.log"
tail -80 "$RUN_ROOT/nohup.log"
```
