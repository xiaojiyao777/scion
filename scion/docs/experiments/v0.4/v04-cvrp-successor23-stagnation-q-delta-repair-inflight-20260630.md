# CVRP Successor23 Stagnation q-Delta Repair In-Flight - 2026-06-30

## Status

Successor23 completed on WSL and is postrun-ready.

- Completed WSL run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor23-stagnation-q-delta-repair-2r-gpt55-20260630T020559Z-claw`
- WSL runner repo:
  `/home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629`
- Runner commit used by `run.sh`: `b0adf692`
- Wrapper pid: `63815`
- Scion campaign pid: `63837`
- Started UTC: `2026-06-30T02:06:31Z`
- Model route: `gpt-5.5` via `http://127.0.0.1:8080`
- Pre-campaign completion preflight: `ok`, HTTP 200, authenticated local proxy
- Initial campaign phase: `proposal_hypothesis`
- Final status: valid, complete, postrun-ready
- Stop reason: `max_rounds_exhausted`
- Final interpretation: q trajectory changed versus champion, but objective
  evidence stayed below MDE and the branch parked as quality regression
- Postrun report:
  `scion/docs/experiments/v0.4/v04-cvrp-successor23-stagnation-q-delta-repair-postrun-20260630.md`
- Requested rounds: `2`
- Forced target:
  `solver_design` / `modify` / `policies/baseline_modules/scheduler.py`

Superseded launch-path transient:

- Prepared root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor23-stagnation-q-delta-repair-2r-gpt55-20260630T014819Z-claw`
- Status: failed before campaign start
- Failure: pre-campaign completion preflight HTTP 502,
  `tls handshake eof`
- Interpretation: proxy/upstream launch transient, not experiment evidence

## Purpose

Run a two-round CVRP solver-design activation repair for
`stagnation_adaptive_destroy_size_schedule`.

This successor must test whether the scheduler policy can create observable
destroy-size q deltas under formal screening before objective effect is
interpreted.

## Acceptance Focus

Postrun analysis must check:

- live hypothesis and completed proposal name
  `stagnation_adaptive_destroy_size_schedule`;
- patch stays local to `policies/baseline_modules/scheduler.py`;
- telemetry records `baseline_q`, `adapted_q`, and `q_delta`;
- aligned candidate/champion ALNS traces contain nonzero q deltas;
- q deltas come from stagnation/search-progress state, not case id, BKS,
  split membership, protected cases, or seed-specific shortcuts;
- formal rows are complete and interpreted against CVRP A/A MDE;
- CMT2/CMT4 case-level deltas are visible;
- postrun acceptance readiness is ready.

If q deltas remain zero, classify successor23 as
`inactive-q-trajectory-repeat` and park the scheduler destroy-size branch.
If q deltas are present but rows remain below MDE, classify it as
`activation-repaired-but-below-MDE`, not solver-positive.

Observed classification:

- `activation-repaired-but-below-MDE`;
- `quality-regression-parked`;
- `explicit-q-delta-telemetry-missing`.
