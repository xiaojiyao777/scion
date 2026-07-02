# CVRP successor35 capacity-tightness removal in-flight

Date: 2026-07-02

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor35-capacity-tightness-removal-server-2r-gpt55-20260702T004158Z-claw`

Runner: server-local `claw`

Model: local `gpt-5.5`

Runner commit: `81d97474`

PID at launch: `1396023`

## Launch

Successor35 was launched as a single server-local two-round CVRP run with:

- `--force-surface solver_design`
- `--force-action modify`
- `--force-target-file policies/baseline_modules/destroy_repair.py`
- `--completion-preflight`
- `--model gpt-5.5`
- `--base-url http://127.0.0.1:8080`

The launch command recorded `git_commit=81d97474` and `status=running` in
`run_status.json`.

## Health Check

Completion preflight passed before campaign execution:

- auth status: authenticated;
- chat completion status: HTTP `200`;
- chat classification: `healthy`;
- completion content: non-empty.

The first target-intent artifact selected `capacity_tightness_removal` with
target file `policies/baseline_modules/destroy_repair.py`. The formal
hypothesis binding is `bound` and the formal hypothesis target stayed on:

- action: `modify`;
- change locus/surface: `solver_design`;
- mechanism id: `capacity_tightness_removal`;
- target file: `policies/baseline_modules/destroy_repair.py`.

The first formal hypothesis proposes a non-seed destroy/removal operator that
removes customers from low-slack/high-load routes and keeps construction, VNS,
scheduler q, acceptance, and runtime allocation unchanged.

## Follow-Up

After completion, analyze the run as successor35 evidence:

- verify root status, campaign completeness, postrun readiness, and wrapper
  exit status;
- verify live candidates stayed on `capacity_tightness_removal`;
- inspect direct removal-choice telemetry: source route load/slack, removed
  count, fallback/no-op count, repair operator, `record_move` delta, phase
  runtime, feasibility, route count, and total distance;
- report CMT2/CMT4 case evidence explicitly;
- compare median/CI against the current CVRP screening MDE `9.9`;
- decide whether this mechanism should be expanded, repaired with a focused
  follow-up, or parked.
