# CVRP Successor31 Adaptive Embedded VNS Runtime Allocation In-Flight - 2026-07-01

## Status

Successor31 is running.

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor31-adaptive-embedded-vns-runtime-allocation-server-2r-gpt55-20260701T111631Z-claw`
- Wrapper PID: `1335137`
- Runner: server-local `claw`
- Git commit recorded by wrapper: `9cfee8e3`
- Started UTC: `2026-07-01T11:19:34Z`
- Rounds: `2`
- Model: local `gpt-5.5`
- Base URL: `http://127.0.0.1:8080`
- Completion preflight: healthy, HTTP `200`
- Forced target:
  `solver_design` / `modify` /
  `policies/baseline_modules/scheduler.py`
- Design review:
  `scion/docs/experiments/v0.4/v04-cvrp-successor31-design-review-20260701.md`

This is a server-local small run. WSL `scion` remains reserved for large or
concurrent batches.

## Prepared Focus Override

The run was prepared with the standard CVRP launcher, then only this run root's
prepared manifest was patched before launch:

- `research_focus.required_mechanism_ids`:
  `["adaptive_embedded_vns_runtime_allocation"]`
- typed `research_guidance_contract.required_mechanisms`:
  `adaptive_embedded_vns_runtime_allocation`
- override record:
  `prepared_manifest_override.v1.json`

The override also updates the prepared current question and next required
direction away from local-search and destroy/repair operator variants. This is
a single-run proposal-context override. It does not change the CVRP default
guidance provider and does not enter `DecisionFeatures`.

The prepared handoff was rebuilt after the override:

- `analysis_brief=ok`
- `inventory=ok`
- `launch_readiness=ok`
- `prompt_context_readiness=ok`

Strict live launch readiness with completion preflight passed:

```json
{
  "launch_ready": true,
  "ready": true,
  "failed_required_checks": [],
  "launch_blockers": [],
  "completion_classification": "healthy",
  "completion_http_status": 200,
  "runtime_guard_status": "ok"
}
```

`launch_research_guidance_payload(...)` returned:

```json
{
  "required_mechanism_ids": [
    "adaptive_embedded_vns_runtime_allocation"
  ],
  "rendered_paths": [
    "required_mechanisms.adaptive_embedded_vns_runtime_allocation",
    "evidence_requirements.successor31_adaptive_embedded_vns_runtime_allocation",
    "guidance_blocks.successor31_adaptive_embedded_vns_runtime_allocation"
  ]
}
```

## Initial Health Check

At the first post-launch checks:

- wrapper status: `running`
- completion preflight: HTTP `200`, chat completion non-empty
- authenticated local proxy pool: active `1`
- `proposal_attempts_total`: `1`
- `proposal_quality_blocks`: `0`
- `quality_blocks`: `0`
- `telemetry_failed_experiments`: `0`
- `effective_protocol_rounds`: `0`
- `protocol_metric_results`: `0`
- observed LLM traces:
  `hypothesis_target_intent`, `hypothesis`, `tool_selection`, `code`
- `llm_model_counts`: `{"gpt-5.5": 4}`

Target-intent authority applied the prepared required mechanism:

- selected mechanism:
  `adaptive_embedded_vns_runtime_allocation`
- prepared required mechanism ids:
  `["adaptive_embedded_vns_runtime_allocation"]`
- target file:
  `policies/baseline_modules/scheduler.py`
- selected mechanism family:
  `embedded_vns_runtime_allocation`

The first code proposal kept the required mechanism id. Static/smoke preview
passed with a diagnostic advisory, not a blocker: the preview did not observe
positive activation telemetry for
`solver_algorithm_context_records.adaptive_embedded_vns_runtime_allocation_iterations`
and advised using natural-path `context.record_iteration` or
`context.record_phase` activation evidence. Treat this as early telemetry-risk
context; formal screening and postrun telemetry decide whether the mechanism is
valid evidence.

## Monitoring

Useful checks:

```bash
RUN=/home/clawd/research/scion-experiments/v04-cvrp-successor31-adaptive-embedded-vns-runtime-allocation-server-2r-gpt55-20260701T111631Z-claw
ps -p 1335137 -o pid,ppid,stat,etime,cmd
cat "$RUN/run_status.json"
jq '{effective_rounds_completed,effective_protocol_rounds,protocol_metric_results,screening_protocol_results,proposal_attempts_total,proposal_quality_blocks,quality_blocks,telemetry_failed_experiments,verification_consumed_candidates,llm_model_counts,llm_request_kind_counts,updated_at}' "$RUN/campaign/status.json"
tail -n 160 "$RUN/run.log"
```

After completion:

```bash
RUN=/home/clawd/research/scion-experiments/v04-cvrp-successor31-adaptive-embedded-vns-runtime-allocation-server-2r-gpt55-20260701T111631Z-claw
jq '{status,wrapper_exit_status,run_validity_status,run_completeness_status,postrun_acceptance_status,last_stop_reason}' "$RUN/run_status.json"
find "$RUN/postrun_acceptance" -maxdepth 3 -type f | sort
```
