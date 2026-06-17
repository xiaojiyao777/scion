# Warehouse Repair-Template Rerun Postrun

*Date: 2026-06-17*
*Run commit: `4a316e1`*
*Postrun repair commit: pending*
*Status: invalid as research evidence*

## Artifacts

- Server root:
  `/home/clawd/research/scion-experiments/v04-warehouse-repairtemplate-rerun6r-4a316e1-20260617T002824Z`
- Campaign:
  `/home/clawd/research/scion-experiments/v04-warehouse-repairtemplate-rerun6r-4a316e1-20260617T002824Z/rep01/on_compact/campaign`
- Wrapper status:
  `status=finished`, `exit_code=0`, `rounds=6`
- Model/context:
  local `gpt-5.5`, measurement governance `on`,
  `compact-measurement-diagnostics`

## Outcome

The wrapper completed, but the campaign is not valid protocol evidence:

- `run_validity.status=invalid`
- `run_validity.reason=invalid_no_protocol_rows`
- `effective_rounds_completed=6`
- `proposal_attempts_total=17`
- `quality_blocks=10`
- `formal_screened_candidates=0`
- `protocol_stage_counts={'screening': 0, 'validation': 0, 'frozen': 0}`

The run should not be interpreted as a warehouse research-quality result or as
evidence that the `repair_template` change harmed candidate quality.

## Diagnosis

The formal candidates were vetoed before protocol rows because strict canary
case-path resolution used an unsafe data root.

The experiment copied `split_manifest_prod.yaml` into the run-local config
directory. That manifest contains:

```yaml
safe_data_roots:
  - ../../../../scion-data
```

When the manifest lives at its repo path, this resolves to
`/home/clawd/research/scion-data`. When copied to the experiment config
directory, it resolves to `/home/clawd/scion-data`. The production canary cases
are absolute paths under `/home/clawd/research/scion-data`, so strict protocol
reported:

```text
Unsafe case path in strict ExperimentProtocol:
'artifact:instance_prod_can_s01.json#64a747f955e8'
status=absolute_outside_roots
reason=absolute case path is outside workspace and safe_data_roots
```

The campaign summary preserved the structured canary payloads with this reason.
The DB lineage payloads only showed the high-level `CANARY_FAILED` decision
reason, so campaign summary/status must be inspected for canary-detail
diagnosis.

## Prompt Finding

The prompt-propagation part of `4a316e1` is still accepted:

- later hypothesis traces include
  `Prior Agent Quality Blocks For This Hypothesis` and `repair_template`;
- later code traces include
  `Prior Agent Quality Blocks For This Code Patch` and `repair_template`.

Because no formal protocol row was produced, this run cannot validate whether
the templates improve warehouse research behavior.

## Repair

The follow-up local repair keeps the v3 boundary intact:

- adds `scion/problems/warehouse_delivery/budgets.json` declaring
  `SCION_WAREHOUSE_DATA_ROOT` with repo-relative root `../scion-data`;
- updates `activate_declared_problem_data_root()` to resolve the declared
  repo-relative root from the protocol/budget source first, then fall back to
  the copied `problem.yaml` location.

This keeps warehouse path semantics problem-owned and does not add raw
diagnostics or problem data to `DecisionFeatures`.

## Verification

Commands:

```bash
PYTHONPATH=scion python -m pytest \
  scion/scion/tests/unit/test_cli_data_roots.py \
  scion/scion/tests/unit/protocol/test_case_path_safety.py \
  scion/scion/tests/unit/core/test_evaluation_pipeline.py -q
python -m py_compile scion/scion/cli/commands/data_roots.py
git diff --check
```

Result:

```text
27 passed
```

Manual copied-config replay confirmed both production canary cases resolve as
`resolved_safe_data_root` under `/home/clawd/research/scion-data`.

## Next

Run a small server-side warehouse acceptance rerun after committing this repair.
This is a 1-cell validation, so it belongs on the 2-core server rather than WSL.
