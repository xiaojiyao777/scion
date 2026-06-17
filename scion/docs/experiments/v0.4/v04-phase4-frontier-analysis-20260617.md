# Scion v0.4 Phase 4 Frontier Analysis - 2026-06-17

## Boundary

This is a main-session synthesis of two read-only subagent analyses:

- `Lagrange` inspected the latest warehouse repair-cap field gate:
  `/home/clawd/research/scion-experiments/v04-warehouse-repaircap-rerun6r-f81bb73-20260617T064032Z`
- `Noether` inspected the current CVRP/VRP evidence set across Phase A/B/C,
  fixed-candidate replay, single-round debug, and independent VRP controls.

The v3 boundary remains authoritative. Prompt traces, branch lessons, raw
frozen rows, BKS gaps, runtime curves, and independent-agent logs are
problem-owned diagnostics for proposal/context, human audit, lifecycle planning,
and experiment design only. They are not promotion evidence and must not become
raw `DecisionFeatures`.

## Current Decision

Do not launch a broad warehouse matrix or another long blind CVRP/VRP LLM
campaign as the immediate next step.

The next v0.4 work should be:

1. a narrow warehouse problem-owned guidance/quality repair for split-vs-cost
   effect scope and bounded runtime acceptance, followed by one local short
   `6R` field check; and
2. a CVRP/VRP no-LLM family/slice mechanism diagnostic design before any
   further long LLM campaign.

This preserves the TASK.md resource policy: short single-cell acceptance checks
can run on the 2-core server, while larger matrices should wait for a clean WSL
runner worktree and a pre-registered design.

## Warehouse f81bb73 Field Gate

The `f81bb73` repair-cap field gate is accepted as framework evidence:

- wrapper `exit_code=0`;
- `run_validity.status=valid`;
- `effective_rounds_completed=6`;
- stage counts `screening=3`, `validation=2`, `frozen=1`;
- `telemetry_repair_attempt_budget_exhausted` did not recur;
- strict telemetry and frozen gates still failed closed.

It is not promotion evidence. Champion stayed v1.

### Candidate Trajectory

Branch `4aeeea16-bdab-4ec9-9f7a-784af25034cd`:

- candidate `88a8b52dfcba86d4`, target
  `operators/repack_subcategory_group.py`;
- screening metric
  `metrics/0e6a3282-bcee-4527-9be4-4c76c59c2425.json`;
- case `2/0/8`, pair `9/6/5`, median `0.0`;
- decision `continue_explore` because telemetry was repairable but no effect
  counter moved.

The same branch then attempted a repair:

- hypothesis `9e518413-72ab-4e9f-b113-0c096ea630e1`;
- metrics `metrics/6d76ac04-4393-4e74-b976-cca0eb29a16c.json`;
- case `0/0/6`, pair `0/0/12`, median `0.0`;
- stopped with `SCREENING_TELEMETRY_FAILED`.

Branch `3857ba8e-63c8-4e1f-bb5d-7ed88cf7cea7`:

- candidate `eb52b33be051a5ab`, target `operators/merge_vehicles.py`;
- screening expand:
  `metrics/7b3557f5-cba2-4ffa-8657-55f0788f01a2.json`, case `3/0/3`,
  pair `7/0/5`, median `+950`;
- screening pass:
  `metrics/dbe53716-a552-4886-aed3-24329b90fe5f.json`, case `8/0/6`,
  pair `19/0/9`, median `+950`;
- validation expand:
  `metrics/e0cbb53c-c541-4d0d-aa11-75b29640d928.json`, median `+22400`;
- validation pass:
  `metrics/4dd05430-f06b-4d45-80de-3db0c543c5cb.json`, median `+22400`,
  CI low `+1200`;
- frozen fail:
  `metrics/7df01a8e-da57-4eb2-953a-8932b5ec02c0.json`, median `-650`,
  CI low `-10100`, decision `abandon`.

### Warehouse Interpretation

The best `merge_vehicles` candidate mostly improved lower-priority cost while
preserving the higher-priority split metric. Screening and validation looked
strong because cost deltas were positive on seen distributions, but
`split_delta_sum` was zero across nearly all pairs. Frozen exposed real
distribution sensitivity:

- `instance_prod_fro_x01`: all three seeds won;
- `instance_prod_fro_x04`: all three seeds won;
- `instance_prod_day2`: mixed;
- `instance_prod_fro_xx03`: all three seeds lost.

Frozen split deltas were all `0.0`, so losses were total-cost regressions under
preserved split count. Frozen runtime also regressed; candidate runtime ratio
median was about `1.123`, with regression rate `1.0`. This is a real holdout
generalization and runtime-risk failure, not an infra or Decision failure.

Branch depth did occur in `4aeeea16`, and later prompts did receive screening
lessons. There was no later prompt after the `merge_vehicles` frozen failure
inside this run, so frozen lessons could not influence a follow-up branch.

Prompt/context quality improved but is not yet sufficient. The latest
trajectory manifest reports `research_signal` token share around `0.113`, while
`general` plus `tool_selection` dominate. Code-stage source visibility held in
the sampled `merge_vehicles` trace, but the model still underestimated
cost-only overfit and runtime risk.

## CVRP/VRP Frontier

CVRP/VRP is now research-capable but not research-effective.

Completed and accepted:

- Phase 1 measurement calibration: CVRP formal MDE `9.9`, Phase A ALNS+VNS
  MDE `9.6`, ALNS-only MDE `4.65`.
- Phase 2/3 framework repairs: practical deltas, budget-exhausting runtime,
  trajectory-divergent low-SNR expansion, lifecycle/context/source visibility,
  and measurement readiness.
- Phase C long run: validation/frozen reach happened, especially on the copied
  ALNS-only research surface.
- Single-round debug after repair: path health was restored through Protocol.
- Independent VRP-only controls produced auditable process records and narrow
  hypothesis seeds.

Not yet proven:

- formal CVRP promotion;
- canonical ALNS+VNS improvement above its MDE;
- ALNS-only validation positives that generalize through frozen/large-X;
- branch lessons that causally improve later mechanism choices;
- robust broad VRP mechanism improvement from the independent control lane.

ALNS+VNS remains the canonical baseline and is too strong/noisy for blind
small-effect search. ALNS-only is a copied diagnostic research surface with
more measurable headroom, not a production replacement.

The immediate VRP bottleneck is mechanism quality and mechanism diagnosis, not
just runtime budget. Large-X runtime curves and candidate-specific replays show
that simply extending solver time did not create broad best-update leverage.
The independent `regret4_repair` lane also failed broad validation with W/T/L
`21/31/28`, median `0.0`, and repeated regressions in `E`, `M`, and `P`.

## Next Gates

### Warehouse

Before a larger warehouse matrix, repair problem-owned proposal/code guidance:

- require merge-style candidates to distinguish true split-positive improvement
  from split-preserving cost compression;
- require cost-only candidates to state frozen/generalization risk and runtime
  boundedness;
- add a lightweight patch-quality check against unbounded exhaustive
  vehicle-pair/order-pair scans unless an executable cap/top-k/early-exit policy
  is present.

Acceptance should be one local server `6R` check from the repair commit. It is
accepted only if the run reaches Protocol without the old repair-cap failure and
candidate proposals either target split-positive effects or explicitly bounded
cost-only effects. WSL long matrix waits until this short check passes.

### CVRP/VRP

Before another long LLM campaign, design a no-LLM family/slice mechanism
diagnostic:

- compare ALNS+VNS and ALNS-only separately;
- cover A/B/E/P/M/X families and selected size tiers;
- record construction cost, post-local-search cost, ALNS iterations,
  destroy/repair selection, accepted moves, best-update count, route-count,
  phase runtime, final gap, and timeout/completeness;
- include short budget tiers and one longer tier;
- keep BKS/gap, VNS telemetry, family labels, and mechanism rankings as
  problem-owned diagnostics outside `DecisionFeatures`.

If that diagnostic finds a narrow measurable mechanism, then run a `4R-6R`
Scion behavior debug to check whether the diagnostic becomes useful hypothesis,
code, and evidence. Only after that should a WSL `12R/16R` matrix be considered.

