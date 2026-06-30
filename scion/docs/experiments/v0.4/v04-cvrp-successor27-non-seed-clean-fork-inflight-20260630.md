# CVRP Successor27 Non-Seed Clean Fork In-Flight - 2026-06-30

## Status

Successor27 is running.

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor27-non-seed-clean-fork-server-2r-gpt55-20260630T151408Z-claw`
- PID: `1293195`
- Runner: server-local `claw`
- Git commit recorded by launcher: `5241eb22`
- Started UTC: `2026-06-30T15:14:09Z`
- Rounds: `2`
- Model: local `gpt-5.5`
- Base URL: `http://127.0.0.1:8080`
- Completion preflight: healthy, HTTP `200`
- Forced target:
  `solver_design` / `modify` /
  `policies/baseline_modules/destroy_repair.py`
- Plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor27-non-seed-clean-fork-plan-20260630.md`

This is a server-local small run. WSL `scion` remains the intended runner for
large or concurrent batches after fresh completion preflight.

## Initial Health Check

At the first post-launch check:

- wrapper status: `running`
- `proposal_attempts_total`: `1`
- `proposal_quality_blocks`: `0`
- `quality_blocks`: `0`
- `telemetry_failed_experiments`: `0`
- `effective_protocol_rounds`: `0`
- `protocol_metric_results`: `0`
- observed LLM traces: `hypothesis_target_intent`, `hypothesis`,
  `tool_selection`, and `code`
- observed trace model: `gpt-5.5`

No protocol row had completed yet. This document is a launch/in-flight record,
not outcome evidence.

## Monitoring

Useful checks:

```bash
ps -p 1293195 -o pid,ppid,stat,etime,cmd
cat /home/clawd/research/scion-experiments/v04-cvrp-successor27-non-seed-clean-fork-server-2r-gpt55-20260630T151408Z-claw/run_status.json
jq '{effective_rounds_completed,effective_protocol_rounds,protocol_metric_results,screening_protocol_results,proposal_attempts_total,proposal_quality_blocks,quality_blocks,telemetry_failed_experiments,verification_consumed_candidates,llm_model_counts,llm_request_kind_counts,updated_at}' /home/clawd/research/scion-experiments/v04-cvrp-successor27-non-seed-clean-fork-server-2r-gpt55-20260630T151408Z-claw/campaign/status.json
tail -n 120 /home/clawd/research/scion-experiments/v04-cvrp-successor27-non-seed-clean-fork-server-2r-gpt55-20260630T151408Z-claw/run.log
```

After completion, inspect postrun readiness and research efficiency before
changing guidance:

```bash
jq '{status,wrapper_exit_status,run_validity_status,run_completeness_status}' /home/clawd/research/scion-experiments/v04-cvrp-successor27-non-seed-clean-fork-server-2r-gpt55-20260630T151408Z-claw/run_status.json
find /home/clawd/research/scion-experiments/v04-cvrp-successor27-non-seed-clean-fork-server-2r-gpt55-20260630T151408Z-claw/postrun_acceptance -maxdepth 3 -type f | sort
```
