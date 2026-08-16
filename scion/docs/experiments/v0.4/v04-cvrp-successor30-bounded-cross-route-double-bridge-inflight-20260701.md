# CVRP Successor30 Bounded Cross-Route Double-Bridge In-Flight - 2026-07-01

## Status

Successor30 is running.

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor30-bounded-cross-route-double-bridge-server-2r-gpt55-20260701T052131Z-claw`
- Wrapper PID: `1323395`
- Campaign PID at launch check: `1323426`
- Runner: server-local `claw`
- Git commit recorded by wrapper: `9cfee8e3`
- Started UTC: `2026-07-01T05:24:18Z`
- Rounds: `2`
- Model: local `gpt-5.5`
- Base URL: `http://127.0.0.1:8080`
- Completion preflight: healthy
- Forced target:
  `solver_design` / `modify` /
  `policies/baseline_modules/local_search.py`
- Plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor30-bounded-cross-route-double-bridge-plan-20260701.md`

This is a server-local small run. WSL `scion` remains reserved for large or
concurrent batches.

## Prepared Focus Override

The run was prepared with the standard CVRP launcher, then only this run root's
prepared manifest was patched before launch:

- `research_focus.required_mechanism_ids`:
  `["bounded_cross_route_double_bridge_polish"]`
- typed `research_guidance_contract.required_mechanisms`:
  `bounded_cross_route_double_bridge_polish`
- override record:
  `prepared_manifest_override.v1.json`

The override also updates the prepared current question and next required
direction away from the stale route-pair-overlap question. This is a single-run
proposal-context override. It does not change the CVRP default guidance
provider and does not enter `DecisionFeatures`.

The prepared handoff was rebuilt after the override:

- `analysis_brief=ok`
- `inventory=ok`
- `launch_readiness=ok`
- `prompt_context_readiness=ok`

Launch readiness after the override:

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
  "payload_required_mechanism_ids": [
    "bounded_cross_route_double_bridge_polish"
  ],
  "rendered_paths": [
    "required_mechanisms.bounded_cross_route_double_bridge_polish"
  ]
}
```

## Initial Health Check

At the first post-launch checks:

- wrapper status: `running`
- completion preflight: HTTP 200, chat completion non-empty
- authenticated local proxy pool: active `1`
- `proposal_attempts_total`: `2`
- `proposal_quality_blocks`: `1`
- `quality_blocks`: `1`
- `telemetry_failed_experiments`: `0`
- `effective_protocol_rounds`: `0`
- `protocol_metric_results`: `0`
- observed LLM traces:
  `hypothesis_target_intent`, `hypothesis`, `tool_selection`, `code`
- `llm_model_counts`: `{"gpt-5.5": 8}`

Target-intent authority applied the prepared required mechanism:

- selected mechanism:
  `bounded_cross_route_double_bridge_polish`
- prepared required mechanism ids:
  `["bounded_cross_route_double_bridge_polish"]`
- target file:
  `policies/baseline_modules/local_search.py`

The first proposal was blocked before screening by static solver-design
quality:

```text
solver_design static smoke rejected hypothesis/code semantic drift: the
approved hypothesis claims a cross-route or up-to-four-routes double-bridge
perturbation, but the patch implementation appears to operate on a single
route only.
```

This is a useful fail-closed guard, not solver evidence. The second proposal
kept the required mechanism and was in code phase when this in-flight note was
written.

## Monitoring

Useful checks:

```bash
RUN=/home/clawd/research/scion-experiments/v04-cvrp-successor30-bounded-cross-route-double-bridge-server-2r-gpt55-20260701T052131Z-claw
ps -p 1323395 -o pid,ppid,stat,etime,cmd
cat "$RUN/run_status.json"
jq '{effective_rounds_completed,effective_protocol_rounds,protocol_metric_results,screening_protocol_results,proposal_attempts_total,proposal_quality_blocks,quality_blocks,telemetry_failed_experiments,verification_consumed_candidates,llm_model_counts,llm_request_kind_counts,updated_at}' "$RUN/campaign/status.json"
tail -n 120 "$RUN/run.log"
```

After completion:

```bash
RUN=/home/clawd/research/scion-experiments/v04-cvrp-successor30-bounded-cross-route-double-bridge-server-2r-gpt55-20260701T052131Z-claw
jq '{status,wrapper_exit_status,run_validity_status,run_completeness_status,postrun_acceptance_status,last_stop_reason}' "$RUN/run_status.json"
find "$RUN/postrun_acceptance" -maxdepth 3 -type f | sort
```
