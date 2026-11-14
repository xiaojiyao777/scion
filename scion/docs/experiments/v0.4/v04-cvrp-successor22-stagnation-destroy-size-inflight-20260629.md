# CVRP Successor22 Stagnation Destroy-Size In-Flight - 2026-06-29

## Status

Successor22a was launched on WSL and intentionally stopped before formal
screening because the live hypothesis drifted to the wrong mechanism. That run
is a wrong-mechanism diagnostic, not solver evidence.

Successor22b completed on WSL and is postrun-ready. It was relaunched from a
synced runner commit that hard-requires
`stagnation_adaptive_destroy_size_schedule` in both legacy research focus and
the typed research-guidance contract.

- Active WSL run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor22b-stagnation-required-2r-gpt55-20260629T193044Z-claw`
- Runner commit used by `run.sh`: `14a7f78c`
- Wrapper pid: `54395`
- Scion campaign pid: `54410`
- Started UTC: `2026-06-29T19:31:49Z`
- Model route: `gpt-5.5` via `http://127.0.0.1:8080`
- Launch readiness: `launch_ready=true`
- Completion preflight: `ok`, HTTP 200, authenticated local proxy
- Early model traces: `hypothesis_target_intent`, `hypothesis`,
  `tool_selection`, and `code` all used `gpt-5.5`
- Early mechanism status: live hypothesis and completed proposal output name
  `stagnation_adaptive_destroy_size_schedule`
- Final status: `finished`, `valid`, `complete`, `postrun_acceptance_status=ready`
- Final interpretation: target mechanism and telemetry were present, but the
  aligned ALNS q trace had zero q difference versus champion and both
  screening rows had median delta `0.0`
- Postrun report:
  `scion/docs/experiments/v0.4/v04-cvrp-successor22b-stagnation-required-postrun-20260630.md`

Stopped diagnostic run:

- WSL run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor22-stagnation-destroy-size-2r-gpt55-20260629T192118Z-claw`
- WSL runner repo:
  `/home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629`
- Runner commit used by `run.sh`: `5db1ea54`
- Wrapper pid: `53026` (exited)
- Scion campaign pid: `53043` (SIGTERM)
- Started UTC: `2026-06-29T19:21:50Z`
- Model route: `gpt-5.5` via `http://127.0.0.1:8080`
- Launch readiness: `launch_ready=true`
- Completion preflight: `ok`, HTTP 200, authenticated local proxy
- Stop reason: wrong-mechanism drift before formal screening
- Wrong mechanism observed: `bounded_repair_retry_on_reject`

## Purpose

Run a 2-round CVRP solver-design clean fork for
`stagnation_adaptive_destroy_size_schedule`.

The intended mechanism is a CVRP-owned scheduler policy that changes ALNS
destroy magnitude `q` from stagnation/search-progress state before existing
destroy/repair operators run. It must not repeat successor21's
`operator_pair_destroy_size_bands`, which only clamped q by destroy/repair
operator pair and measured below MDE.

## Prepared Context

Before launch, problem-owned CVRP guidance was updated so prepared context
matches current evidence:

- `bounded_route_segment_exchange` is reviewed successor20 active
  zero-effect below-MDE evidence.
- `operator_pair_destroy_size_bands` is reviewed successor21 active
  scheduler destroy-size evidence below MDE, with a loss-heavy follow-up row.
- `seed_post_optimization_selector` remains a deferred activation diagnostic.
- The current slot is still `stagnation_adaptive_destroy_size_schedule`, but
  only as a materially different stagnation-state q schedule.
- Measurement diagnostics keep `scheduler_destroy_size_policy` first while
  default-avoiding unchanged operator-pair q bands.

The WSL runner copy first used local experiment commit `5db1ea54` for
successor22a. After wrong-mechanism drift, the runner was resynced and committed
as `14a7f78c` so successor22b's prepared manifest hard-requires
`stagnation_adaptive_destroy_size_schedule`. Local source changes remain
uncommitted in the main checkout.

## Launch Command

Prepare command used from the WSL runner repo for successor22b:

```bash
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/launch_cvrp_agentic_campaign.py \
  --rounds 2 \
  --label v04-cvrp-successor22b-stagnation-required \
  --model gpt-5.5 \
  --time-limit-sec 30 \
  --measurement-governance on \
  --completion-preflight \
  --force-surface solver_design \
  --force-action modify \
  --force-target-file policies/baseline_modules/scheduler.py \
  --experiments-root /home/xjy-ubuntu/research/scion-experiments
```

Launch readiness command:

```bash
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/check_launch_readiness.py \
  /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor22b-stagnation-required-2r-gpt55-20260629T193044Z-claw \
  --completion-preflight \
  --require-launch-ready
```

Background launch command:

```bash
cd /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor22b-stagnation-required-2r-gpt55-20260629T193044Z-claw
nohup bash run.sh > nohup.log 2>&1 < /dev/null &
```

## Acceptance Focus

Postrun analysis must check:

- live hypothesis names `stagnation_adaptive_destroy_size_schedule`;
- proposal is not another operator-pair q-band, acceptance, weight, or
  local-search repeat;
- candidate changes actual destroy-size `q` before existing destroy/repair
  operators run;
- q depends on stagnation/search-progress state;
- activation/decision telemetry is present under the declared mechanism id;
- q distribution or ALNS trace evidence differs from both baseline and
  successor21 operator-pair bands;
- formal rows are complete and interpreted against MDE;
- CMT2/CMT4 case-level deltas are visible;
- postrun acceptance readiness is ready.

If the run completes but no row reaches MDE, classify it as evidence-complete
below-MDE or quality regression rather than solver-positive. Successor22b also
requires a stricter caveat: if the aligned q trajectory is unchanged versus
champion, classify it as an inactive-q-trajectory no-op rather than a
meaningful scheduler policy test.
