# CVRP successor38 proposal-quality contract in-flight

Date: 2026-07-05

## Purpose

Successor38 is the first CVRP clean-fork slot after the successor37 root-cause
audit. It intentionally repairs proposal control before asking the agent to
generate another solver candidate.

The design source is
`scion/docs/experiments/v0.4/v04-cvrp-successor38-proposal-quality-contract-design-20260705.md`.

## Repair

Accepted repair commits:

- `ad014be2` adds the CVRP causal-path hypothesis-quality contract as a
  problem-owned package under `scion/problems/cvrp/proposal_quality/` and keeps
  `CvrpAdapter.validate_hypothesis_quality()` as a delegation point.
- `23e23a1d` clarifies the retry feedback shape so a blocked agent receives the
  exact structured CMT2/CMT4 fields it must provide before code generation.

The repair is intentionally not implemented as generic scheduler/proposal
logic and does not add CVRP semantics to `DecisionFeatures`.

Validation before launch:

- `python -m py_compile` on the new proposal-quality package and adapter.
- `pytest scion/scion/tests/test_cvrp_adapter_core.py ... test_v3_problem_boundary...`
  returned `77 passed`.

## Launches

First launch:

- Root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor38-proposal-quality-contract-cleanfork-server-2r-gpt55-20260705T153433Z-claw`
- Commit: `ad014be2`
- Model/base URL: `gpt-5.5` at `http://127.0.0.1:8080`
- Outcome: stopped before screening. Four proposals were blocked because the
  model kept omitting structured CMT2/CMT4 protection fields. This is feedback
  shape evidence, not solver evidence.

Retry launch:

- Root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor38-proposal-quality-contract-cleanfork-server-retry-2r-gpt55-20260705T153833Z-claw`
- Commit: `23e23a1d`
- PID: `1511455`
- Model/base URL: `gpt-5.5` at `http://127.0.0.1:8080`
- Completion preflight: passed.
- Current state at 2026-07-05 15:49 UTC: running screening. The quality gate
  blocked the first incomplete hypothesis, then accepted
  `radial_2opt_star_relink` after the retry included `material_difference`,
  direct effect telemetry, and structured CMT2/CMT4 protection. Aggregate
  screening had written 6 of 32 requested pairs; no conclusion should be drawn
  until the run completes.

## Next Check

When the retry root finishes:

1. Inspect run validity/completeness/postrun readiness.
2. Compare objective evidence against CVRP MDE and case variance.
3. Inspect mechanism actionability. Early pairs show the new
   `radial_2opt_star_relink` phase was attempted, so the analysis must verify
   whether it ever accepts moves or produces direct objective effect beyond
   prompt-level compliance.
4. If the run is solver-negative, decide whether the remaining issue is
   proposal-side mechanism quality, generated-code mechanism realization, or
   the underlying CVRP search surface.
