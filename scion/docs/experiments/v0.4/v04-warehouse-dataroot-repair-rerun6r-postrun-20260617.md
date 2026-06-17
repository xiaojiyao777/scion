# Warehouse Data-Root Repair Rerun Postrun

*Date: 2026-06-17*
*Preflight commit: `ad469f0`*
*Status: data-root repair accepted; research quality rejected*

## Artifacts

- Server root:
  `/home/clawd/research/scion-experiments/v04-warehouse-dataroot-repair-rerun6r-ad469f0-20260617T033450Z`
- Campaign:
  `/home/clawd/research/scion-experiments/v04-warehouse-dataroot-repair-rerun6r-ad469f0-20260617T033450Z/rep01/on_compact/campaign`
- Postrun acceptance reports:
  `/home/clawd/research/scion-experiments/v04-warehouse-dataroot-repair-rerun6r-ad469f0-20260617T033450Z/postrun_acceptance`
- Wrapper status:
  `status=finished`, `exit_code=0`, `rounds=6`
- Model/context:
  local `gpt-5.5`, measurement governance `on`,
  `compact-measurement-diagnostics`

The wrapper preflight enforced `EXPECTED_COMMIT=ad469f0` before campaign
startup. The final `status.txt` reports `commit=88bb264` because the main repo
advanced while the run was active and the wrapper reread `HEAD` during final
status writing.

## Outcome

The copied-config data-root repair is accepted:

- the wrapper exited `0`;
- `run_validity.status=valid`;
- `run_validity.reason=valid`;
- `completed_requested_rounds=true`;
- `effective_rounds_completed=6`;
- `protocol_metric_results=6`;
- `formal_screened_candidates=6`;
- `verification_consumed_candidates=6`;
- `verification_failure_consumed_candidates=0`;
- no `absolute_outside_roots` or canary configuration failure recurred.

This validates the repair that resolves warehouse declared repo-relative data
roots from the protocol/budget source before falling back to copied
experiment-local config paths.

## Research Verdict

The run is rejected as warehouse research-quality evidence:

- `protocol_stage_counts={'screening': 6, 'validation': 0, 'frozen': 0}`;
- no promotion dossier was produced;
- `proposal_attempts_total=10`;
- `quality_blocks=4`;
- `failure_categories={'premise_contradicted': 1, 'agent_grounding_failure': 3}`.

All formal rows stopped at screening. This is now a real research-loop result,
not a data-root/canary setup failure.

## Branch Snapshot

Screening rows from `scion.db`:

```text
branch    decision          win_rate  pair_win_rate  median_delta
6045ddb5  abandon           0.0000    0.1667         0.0
ed329b23  expand_screening  0.2000    0.5000         575.0
ed329b23  continue_explore  0.1875    0.4688         575.0
ed329b23  continue_explore  0.0000    0.0000         0.0
792e6d6e  expand_screening  0.2000    0.5000         575.0
792e6d6e  continue_explore  0.1875    0.4688         575.0
```

Final branch states:

- `6045ddb5`: `abandoned`, discarded after negative screening.
- `ed329b23`: still `explore`, `branch_code_status=active_no_effect`, retained
  best quality checkpoint but latest head has no objective effect and carries
  `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`.
- `792e6d6e`: still `explore`, `branch_code_status=active_marginal`, retained
  marginal signal with `3/1/12` W/L/T, median delta `575.0`, low cached runtime
  confidence, and same-mechanism follow-up policy.

This shows branch-internal continuation exists, but the run still did not
translate marginal screening signal into validation.

## Next

A deeper branch-level analysis is required before another warehouse rerun. The
analysis should inspect agentic session traces, branch lessons, repair-template
usage, and target/current code context for the two retained branches
`ed329b23` and `792e6d6e`. The immediate question is no longer whether the
data-root repair works; it is why marginal case/pair signal and same-mechanism
follow-up still remain screening-only.
