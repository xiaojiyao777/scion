# CVRP Successor29 Route-Pair Overlap Required Follow-Up In-Flight - 2026-07-01

## Status

Successor29 is running.

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor29-route-pair-overlap-required-followup-server-2r-gpt55-20260701T031419Z-claw`
- PID: `1315703`
- Runner: server-local `claw`
- Git commit recorded by wrapper: `9cfee8e3`
- Started UTC: `2026-07-01T03:15:34Z`
- Rounds: `2`
- Model: local `gpt-5.5`
- Base URL: `http://127.0.0.1:8080`
- Completion preflight: healthy
- Forced target:
  `solver_design` / `modify` /
  `policies/baseline_modules/destroy_repair.py`
- Plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor29-route-pair-overlap-required-followup-plan-20260701.md`

This is a server-local small run. WSL `scion` remains reserved for large or
concurrent batches.

## Prepared Focus Override

The run was prepared with the standard CVRP launcher, then only this run root's
prepared manifest was patched before launch:

- `research_focus.required_mechanism_ids`:
  `["route_pair_overlap_removal_protected_followup"]`
- typed `research_guidance_contract.required_mechanisms`:
  `route_pair_overlap_removal_protected_followup`
- override record:
  `prepared_manifest_override.v1.json`

This is a single-run proposal-context override. It does not change the CVRP
default guidance provider and does not enter `DecisionFeatures`.

The prepared handoff was rebuilt after the override:

- `analysis_brief=ok`
- `inventory=ok`
- `launch_readiness=ok`
- `prompt_context_readiness=ok`

`launch_research_guidance_payload(...)` returned:

```json
{
  "payload_required_mechanism_ids": [
    "route_pair_overlap_removal_protected_followup"
  ],
  "typed_required_mechanisms": [
    "route_pair_overlap_removal_protected_followup"
  ],
  "legacy_required_mechanism_ids": [
    "route_pair_overlap_removal_protected_followup"
  ]
}
```

## Initial Health Check

At the first post-launch check:

- wrapper status: `running`
- completion preflight: HTTP 200, chat completion non-empty
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

- authority status: `prepared_focus_already_selected`
- selected mechanism:
  `route_pair_overlap_removal_protected_followup`
- prepared required mechanism ids:
  `["route_pair_overlap_removal_protected_followup"]`

The formal hypothesis also used the required mechanism:

- `mechanism_changes` includes
  `route_pair_overlap_removal_protected_followup`
- target file:
  `policies/baseline_modules/destroy_repair.py`
- schema preview passed
- target permission preview passed

No screening row had completed yet when this in-flight note was written.

## Monitoring

Useful checks:

```bash
ps -p 1315703 -o pid,ppid,stat,etime,cmd
cat /home/clawd/research/scion-experiments/v04-cvrp-successor29-route-pair-overlap-required-followup-server-2r-gpt55-20260701T031419Z-claw/run_status.json
jq '{effective_rounds_completed,effective_protocol_rounds,protocol_metric_results,screening_protocol_results,proposal_attempts_total,proposal_quality_blocks,quality_blocks,telemetry_failed_experiments,verification_consumed_candidates,llm_model_counts,llm_request_kind_counts,updated_at}' /home/clawd/research/scion-experiments/v04-cvrp-successor29-route-pair-overlap-required-followup-server-2r-gpt55-20260701T031419Z-claw/campaign/status.json
tail -n 120 /home/clawd/research/scion-experiments/v04-cvrp-successor29-route-pair-overlap-required-followup-server-2r-gpt55-20260701T031419Z-claw/run.log
```

After completion:

```bash
jq '{status,wrapper_exit_status,run_validity_status,run_completeness_status,postrun_acceptance_status,last_stop_reason}' /home/clawd/research/scion-experiments/v04-cvrp-successor29-route-pair-overlap-required-followup-server-2r-gpt55-20260701T031419Z-claw/run_status.json
find /home/clawd/research/scion-experiments/v04-cvrp-successor29-route-pair-overlap-required-followup-server-2r-gpt55-20260701T031419Z-claw/postrun_acceptance -maxdepth 3 -type f | sort
```
