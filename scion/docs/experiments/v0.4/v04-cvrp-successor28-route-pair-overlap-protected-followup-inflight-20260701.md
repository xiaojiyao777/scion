# CVRP Successor28 Route-Pair Overlap Protected Follow-Up In-Flight - 2026-07-01

## Status

Successor28 is running.

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor28-route-pair-overlap-protected-followup-server-2r-gpt55-20260701T001959Z-claw`
- PID: `1305865`
- Runner: server-local `claw`
- Git commit recorded by launcher: `ed051d93`
- Started UTC: `2026-07-01T00:20:00Z`
- Rounds: `2`
- Model: local `gpt-5.5`
- Base URL: `http://127.0.0.1:8080`
- Completion preflight: healthy
- Forced target:
  `solver_design` / `modify` /
  `policies/baseline_modules/destroy_repair.py`
- Plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor28-route-pair-overlap-protected-followup-plan-20260701.md`

This is a server-local small run. WSL `scion` remains the intended runner for
large or concurrent batches after a fresh completion preflight.

## Initial Health Check

At the first post-launch check:

- wrapper status: `running`
- `proposal_attempts_total`: `1`
- `proposal_quality_blocks`: `0`
- `quality_blocks`: `0`
- `telemetry_failed_experiments`: `0`
- `effective_protocol_rounds`: `0`
- `protocol_metric_results`: `0`
- observed LLM traces: `hypothesis_target_intent`, `hypothesis`
- prepared manifest top ranking:
  `same_mechanism_cmt_guard_followup_candidate`
- prepared manifest reason codes:
  `SUCCESSOR27_WEAK_POSITIVE_BELOW_MDE`,
  `CMT2_CMT4_P_LOSS_GUARD_REQUIRED`,
  `DIRECT_OBJECTIVE_EFFECT_REQUIRED`

No protocol row had completed yet. This document is a launch/in-flight record,
not outcome evidence.

## Monitoring

Useful checks:

```bash
ps -p 1305865 -o pid,ppid,stat,etime,cmd
cat /home/clawd/research/scion-experiments/v04-cvrp-successor28-route-pair-overlap-protected-followup-server-2r-gpt55-20260701T001959Z-claw/run_status.json
jq '{effective_rounds_completed,effective_protocol_rounds,protocol_metric_results,screening_protocol_results,proposal_attempts_total,proposal_quality_blocks,quality_blocks,telemetry_failed_experiments,verification_consumed_candidates,llm_model_counts,llm_request_kind_counts,updated_at}' /home/clawd/research/scion-experiments/v04-cvrp-successor28-route-pair-overlap-protected-followup-server-2r-gpt55-20260701T001959Z-claw/campaign/status.json
tail -n 120 /home/clawd/research/scion-experiments/v04-cvrp-successor28-route-pair-overlap-protected-followup-server-2r-gpt55-20260701T001959Z-claw/run.log
```

After completion, inspect postrun readiness and research efficiency before
changing guidance:

```bash
jq '{status,wrapper_exit_status,run_validity_status,run_completeness_status,postrun_acceptance_status,last_stop_reason}' /home/clawd/research/scion-experiments/v04-cvrp-successor28-route-pair-overlap-protected-followup-server-2r-gpt55-20260701T001959Z-claw/run_status.json
find /home/clawd/research/scion-experiments/v04-cvrp-successor28-route-pair-overlap-protected-followup-server-2r-gpt55-20260701T001959Z-claw/postrun_acceptance -maxdepth 3 -type f | sort
```
