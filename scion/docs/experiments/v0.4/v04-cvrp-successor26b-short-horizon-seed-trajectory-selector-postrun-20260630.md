# CVRP Successor26b Short-Horizon Seed Trajectory Selector Postrun - 2026-06-30

## Status

Successor26b produced valid solver-negative evidence.

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor26b-short-horizon-seed-trajectory-selector-static-recognizer-server-2r-gpt55-20260630T134339Z-claw`
- Runner: server-local `claw`
- Model: local `gpt-5.5`
- Wrapper status: `finished`
- Wrapper exit status: `0`
- Run completeness: `complete`
- Run validity: `valid`
- Effective protocol rounds: `2`
- Protocol metric results: `2`
- Screening protocol results: `2`
- Proposal attempts total: `2`
- Proposal quality blocks: `0`
- Verification consumed candidates: `2`
- Postrun readiness: ready
- Postrun failures: `0`

This closes the successor26 invalid-run follow-up. The static-quality
recognizer repair worked: both proposals reached formal screening and no model,
quality, telemetry, or postrun-readiness failure explains the result.

## Environment And Model Calls

The server-local `claw` runner was appropriate for this small two-round
follow-up. The campaign made 9 LLM calls, all to local `gpt-5.5`. The earlier
WSL TLS preflight failure remains environment evidence only and is not part of
this campaign result.

Use WSL `scion` for large or concurrent experiment batches; a single two-round
server-local validation remains acceptable when the local `gpt-5.5` endpoint is
healthy.

## Result Summary

- Total experiments: `2`
- Champion promotions: `0`
- Decisions: `{"abandon": 2}`
- Screening pass rate: `0.0`
- Screening case W/L/T: `2 / 4 / 10`
- Screening pair W/L/T: `15 / 17 / 32`
- MDE at 80% power: `9.9`
- Research-efficiency interpretation:
  `all_available_ci_high_below_mde`
- Rows at or above MDE: `0`
- Positive rows: `0`
- Max median delta: `0.0`

Row 1, `short_horizon_seed_trajectory_selector`:

- Median delta: `0.0`
- CI: `[0.0, 0.0]`
- Win rate: `0.0`
- Rows at or above MDE: `0`
- Key case medians: `CMT2=0.0`, `CMT4=0.0`, `P=-1.0`

Row 2, `short_horizon_seed_trajectory_selector_v2`:

- Median delta: `-5.0`
- CI: `[-8.0, 9.0]`
- Effect/MDE ratio: `-0.505051`
- Win rate: `0.25`
- Rows at or above MDE: `0`
- Key case medians: `A=11.5`, `CMT2=-8.0`, `CMT4=-19.0`,
  `X=9.0`

## Interpretation

This is not an infrastructure, model, telemetry, or static-quality-gate
failure. It is valid below-MDE solver evidence for the short-horizon
construction seed trajectory path.

Treat unchanged `short_horizon_seed_trajectory_selector` and
`short_horizon_seed_trajectory_selector_v2` as reviewed/default-avoid for v0.4.
The first row tied almost everywhere and failed on win rate. The v2 row created
some A/X gains but lost on protected CMT2/CMT4 cases and stayed below MDE.

The CVRP guidance should continue to emit no hard `required_mechanism_ids`.
The next solver slot should clean-fork away from construction seed trajectory
selection and name a materially different CVRP-owned causal path before code
work starts.

## Follow-Up

- Record both short-horizon seed trajectory selector ids as reviewed
  no-positive-at-MDE evidence in the CVRP successor catalog.
- Add the v2 mechanism alias to the construction seed family map.
- Update proposal guidance and measurement diagnostics so the top opportunity
  is a non-seed clean fork, with construction seed trajectory selection parked
  as reviewed/default-avoid.
- Launch the next two-round server-local experiment only after the updated
  guidance tests pass. The intended successor27 direction is a materially
  different non-seed path, preferably destroy/repair or bounded local search,
  not another construction seed trajectory selector.
