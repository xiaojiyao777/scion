# CVRP Size70 Direct-Evidence Guard

Date: 2026-06-20

## Result

CVRP bounded large two-opt review readiness now rejects the existing
`size70_two_opt_*` fallback telemetry path. `size70` scope alone no longer
counts as bounded/deadline evidence; a current-run ready summary still requires
a qualifying bounded or deadline-aware large two-opt family plus co-located
positive effect, mechanism activation, objective-effect telemetry, and
non-fallback large two-opt phase telemetry on the same top effect row.

This preserves the v3 boundary: the change is problem-owned postrun
interpretation only. It does not add CVRP semantics to `DecisionFeatures`,
promotion, scheduler state, or generic core decision inputs.

## Verification

Local:

```bash
pytest scion/scion/tests/test_postrun_analysis_brief.py scion/scion/tests/test_check_postrun_acceptance.py
pytest scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_rebuild_prepared_handoff.py
```

Result after the hypothesis prompt-context evidence refresh:
`103 passed`; `96 passed`.

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py
```

Result after the hypothesis prompt-context evidence refresh: `199 passed`.

Additional runtime replay semantics check after the budget-exhausting stale
marker suppression: local and WSL adjacent runtime/finalizer/scheduler suites
each report `224 passed`.

Additional low-SNR runtime-ratio check after the budget-exhausting follow-up
suppression: local and WSL decision/protocol/lifecycle suites each report
`130 passed`.

## Prepared Roots

Regenerated on WSL at runtime commit `5ae79470`.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-size70hypctx-5ae79470-preflight-6r-gpt55-20260620T084135Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-size70hypctx-5ae79470-preflight-4r-gpt55-20260620T084150Z-claw`

Strict launch readiness for both roots:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- completion preflight HTTP `401`, `classification=not_authenticated`,
  `code=invalid_api_key`, auth pool `active=0`, `total=1`

No campaign was launched.

The refreshed roots also include the postrun prompt-context guard that tracks
hypothesis-generation block-family totals and signal density separately from
aggregate prompt context. Current-run warehouse/CVRP research-context readiness
cannot be proven by code-only, target-intent, or aggregate-only prompt traces
when continuity signals require research or cross-branch lesson signal to reach
the formal hypothesis prompt.

They also include budget-exhausting runtime replay suppression: stale
fresh-runtime markers, materialization, and pressure reports no longer force a
runtime replay path under a budget-exhausting measurement model.

Budget-exhausting runtime ratios also no longer block trajectory-divergent
low-SNR expansion or same-branch low-SNR follow-up; comparative runtime slowdown
remains actionable.
