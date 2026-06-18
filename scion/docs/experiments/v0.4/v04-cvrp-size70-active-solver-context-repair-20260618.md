# CVRP Size70 Active Solver Context Repair

Date: 2026-06-18

## Purpose

Make the CVRP active solver map and active algorithm fact packet match the
current scheduler. The scheduler already has a `size70_two_opt_initial` /
`size70_two_opt_embedded` fallback path that calls `_two_opt_intra_polish` when
full VNS is skipped or disabled for instances at or above
`SIZE70_TWO_OPT_MIN_CUSTOMERS`. Before this repair, problem-owned context
mostly described the VNS threshold as a skip, so a solver-design agent could
mistake the fallback as absent or propose it as a new mechanism.

This is problem-owned proposal/context evidence only. It does not change
Scion core, `DecisionFeatures`, protocol gates, lifecycle, scheduler policy, or
CVRP solver behavior.

## Changes

- `active_solver_map_provider.py`
  - marks `_two_opt_intra` as also connected to the size70 fallback polish path;
  - exposes `size70_two_opt_initial` and `size70_two_opt_embedded` telemetry in
    scheduler integrations;
  - adds `cvrp.slice.scheduler.size70_two_opt_polish` so agents can read the
    fallback integration directly;
  - reads up to the provider-owned 24k source window before extracting scheduler
    class-method slices, then still returns bounded content.
- `active_solver_facts.py`
  - adds call-graph edges from scheduler initial/embedded paths to
    `_run_size70_two_opt_polish`;
  - adds fact id `cvrp.local_search.size70_two_opt_fallback` with variant
    guidance.
- Tests assert that active solver map payloads, slice reads, fact packets, and
  call graphs expose the fallback.

## VRP Standalone Candidate Audit

The local worktree also had an uncommitted `vrp/src/solver.py` candidate that
adds a lightweight `two_opt_intra` fallback when standalone `vrp` skips full
VNS. That file is not imported by active Scion CVRP solver-design runs; Scion
uses the copied problem package under
`scion/scion/problems/cvrp/policies/baseline_modules/`.

WSL A/B was run on 17 historical high-gap X instances using the historical
full-experiment-style parameters:

```text
time_limit=1.0
seed=0
cw_threshold=1000
vns_threshold=200
alns_threshold=1000
max_destroy_customers=80
vns_max_no_improve=50
```

Result:

```text
BASE:      n=17 mean_gap=8.356955 median_gap=8.673544 max_gap=12.854841 route_bad=3 total_wall=21.947
CANDIDATE: n=17 mean_gap=7.671253 median_gap=8.234197 max_gap=11.668939 route_bad=3 total_wall=22.759
```

The standalone candidate improved every sampled instance and did not increase
the number of cases exceeding the reference route count. It was not included in
this repair because the current objective is to align Scion's active context
with the already-present problem-package fallback. A separate staging-baseline
parity commit can accept `vrp/src/solver.py` later if desired.

## Verification

Local:

```text
python -m py_compile scion/scion/problems/cvrp/active_solver_map_provider.py scion/scion/problems/cvrp/active_solver_facts.py scion/scion/tests/unit/test_cvrp_active_solver_map_provider.py scion/scion/tests/unit/test_agentic_solver_design_active_tools.py
pytest -q scion/scion/tests/unit/test_cvrp_active_solver_map_provider.py scion/scion/tests/unit/test_agentic_solver_design_active_tools.py
```

Observed:

```text
18 passed
```

Focused broader local and WSL validation:

```text
pytest -q scion/scion/tests/unit/test_cvrp_active_solver_map_provider.py scion/scion/tests/unit/test_agentic_solver_design_active_tools.py scion/scion/tests/unit/test_cvrp_solver_design_provider.py scion/scion/tests/test_cvrp_solver_algorithm_runtime.py scion/scion/tests/unit/test_research_surfaces_cvrp_context.py scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py
```

Observed locally and on WSL:

```text
79 passed
```

## Prepared Root Refresh

Because this repair changes a `scion/scion` provider path that participates in
runtime guard checks, both current launch-prepared roots were refreshed
prepare-only from synchronized WSL checkout `8130c09`.

CVRP:

```text
/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-size70ctx-8130c09-1r-gpt55-1r-gpt55-20260618T215237Z-claw
```

Warehouse:

```text
/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-size70ctx-8130c09-6r-gpt55-6r-gpt55-20260618T215433Z-claw
```

WSL readiness summary for both roots:

```text
static_ready=true
ready_without_preflight=true
git_runtime_consistent=ok, checkout matches manifest commit
prepared_handoff/prompt_context_readiness/*.json:
  ready_for_launch_prompt_audit=true
  missing_required=[]
strict launch readiness:
  exit=64
  launch_ready=false
  HTTP 401
  classification=not_authenticated
  auth pool active=0 / refreshing=1 / total=1
```

No campaign was launched. Live launch remains blocked until the real
`gpt-5.5` chat completion preflight returns HTTP 200 with non-empty output.
