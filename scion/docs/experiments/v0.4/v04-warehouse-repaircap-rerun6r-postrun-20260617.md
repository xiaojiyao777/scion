# Warehouse Repair-Cap Rerun 6R Postrun

*Date: 2026-06-17*
*Commit under test: `f81bb73`*
*Status: valid complete field gate; no promotion*

## Purpose

This is the short warehouse production field gate for the follow-up repair after
the `7fe46a7` telemetry-identity run stopped with
`telemetry_repair_attempt_budget_exhausted`.

The repair under test:

- keeps `agent_quality_blocked` failures on repair-focused branches in the
  proposal quality-block path;
- preserves explicit repair-first policy violations as telemetry repair
  attempts;
- downgrades the same branch/mechanism telemetry repair cap from run-level
  termination to the diagnostic status field
  `telemetry_repair_attempt_limit_exhausted_keys`;
- leaves strict telemetry, Contract/Verification/Protocol, validation/frozen,
  and promotion gates unchanged.

## Run

- Root:
  `/home/clawd/research/scion-experiments/v04-warehouse-repaircap-rerun6r-f81bb73-20260617T064032Z`
- Cell:
  `rep01/on_compact`
- Script:
  `/home/clawd/research/scion-experiments/v04-warehouse-repaircap-rerun6r-f81bb73-20260617T064032Z/run_server.sh`
- Commit:
  `f81bb73`
- Model:
  `gpt-5.5`
- Run shape:
  warehouse production protocol/split/seeds, `6` rounds, `30s` time limit,
  measurement governance on, compact-measurement-diagnostics context, early
  stop disabled, agentic proposal.

Startup confirmed the warehouse data root:

```text
INFO: activated problem data root SCION_WAREHOUSE_DATA_ROOT=/home/clawd/research/scion-data
Starting campaign: warehouse_delivery (max_rounds=6, mock_llm=False, disable_early_stop=True)
```

## Result

Wrapper:

```text
status=finished
finished_at_utc=2026-06-17T07:34:13Z
exit_code=0
commit=f81bb73
rounds=6
```

Scientific validity:

```text
run_validity.status=valid
run_validity.reason=valid
effective_rounds_completed=6
protocol_metric_results=7
protocol_stage_counts: screening=3 validation=2 frozen=1
quality_blocks=4
stopped_reason=max_rounds_exhausted
champion_version=1
```

The previous run-level repair cap stop did not recur:

```text
campaign_loop.telemetry_repair_attempts=1
campaign_loop.telemetry_repair_attempt_limit=2
campaign_loop.telemetry_repair_attempt_limit_exhausted_keys=[]
campaign_loop.telemetry_repair_attempts_by_branch_mechanism={
  "4aeeea16-bdab-4ec9-9f7a-784af25034cd:repack_subcategory_group": 1
}
```

## Candidate Trajectory

Early proposal quality remained weak:

- `4` proposal quality blocks;
- `2` hypothesis approval failures missing `validation_transfer_risk`;
- `2` code-generation quality blocks missing
  `screening_or_lexicographic_guard`.

The first formal branch (`4aeeea16`) produced one non-effective
telemetry-repairable screening row and one strict telemetry failure:

- `repack_subcategory_group.py`: case `2/0/8`, pair `9/6/5`, median `0.0`,
  `continue_explore`, telemetry repairable/non-effective;
- follow-up `repack_subcategory_group.py`: case `0/0/6`, pair `0/0/12`,
  median `0.0`, `SCREENING_TELEMETRY_FAILED`, abandoned.

The second branch (`3857ba8e`) recovered the full research path on
`operators/merge_vehicles.py`:

- screening expand row: case `3/0/3`, pair `7/0/5`, median `+950.0`,
  `expand_screening`;
- screening pass row: case `8/0/6`, pair `19/0/9`, median `+950.0`,
  `queue_validate`;
- validation expand row: median `+22400.0`, `expand_validation`;
- validation pass row: median `+22400.0`, `queue_frozen`;
- frozen holdout row: median `-650.0`,
  `FROZEN_PROTOCOL_GATE_NOT_PASS`, abandoned.

## Acceptance

Framework repair is accepted:

- the run completed requested effective rounds;
- same branch/mechanism telemetry repair accounting remained visible;
- the repair cap no longer terminated the campaign invocation;
- strict `SCREENING_TELEMETRY_FAILED` and frozen holdout gates still failed
  closed;
- no Decision, Protocol, validation/frozen, or promotion threshold was relaxed.

Warehouse research quality is only partially restored:

- Scion reached screening expansion, validation expansion, and frozen holdout;
- no champion promotion occurred;
- the best candidate appears to overfit validation or fail generalization to
  frozen holdout.

## Next

Before launching a larger warehouse matrix, analyze the `3857ba8e` branch at
the prompt/code/artifact level:

- why `merge_vehicles.py` produced very large validation gains but negative
  frozen median delta;
- whether frozen failure is a true generalization failure, telemetry/evidence
  artifact, or problem split sensitivity;
- whether branch lessons from the failed frozen candidate are carried into
  later prompts with enough specificity.
