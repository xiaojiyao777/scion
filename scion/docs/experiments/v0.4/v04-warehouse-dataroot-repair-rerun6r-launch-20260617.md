# Warehouse Data-Root Repair Rerun Launch

*Date: 2026-06-17*
*Commit under test: `ad469f0`*
*Status: running on server*

## Purpose

This single-cell server rerun validates the data-root repair after the
`4a316e1` warehouse repair-template field check produced
`invalid_no_protocol_rows`.

The prior run was not research evidence. It copied `split_manifest_prod.yaml`
into an experiment-local config directory, so relative `safe_data_roots:
../../../../scion-data` resolved to `/home/clawd/scion-data` instead of
`/home/clawd/research/scion-data`; strict canary path resolution then vetoed
formal candidates before screening.

Commit `7c35363` added a warehouse data-root declaration and changed data-root
activation to resolve repo-relative data roots from the protocol/budget source
before falling back to copied `problem.yaml`. Commit `ad469f0` only records the
postrun repair commit in docs.

## Launch

- Corrected server root:
  `/home/clawd/research/scion-experiments/v04-warehouse-dataroot-repair-rerun6r-ad469f0-20260617T033450Z`
- tmux session:
  `scion_wh_dataroot_repair_rerun6r_ad469f0_033450`
- repo:
  `/home/clawd/research/or-autoresearch-agent`
- commit:
  `ad469f0`

The run uses the same short warehouse production field-check shape:

- problem: warehouse delivery production config copied into the experiment root;
- protocol: `scion/problems/warehouse_delivery/protocol_prod.yaml`;
- split: production split manifest copied into the experiment root;
- seeds: `scion/problems/warehouse_delivery/seed_ledger.yaml`;
- rounds: `6`;
- time limit: `30s`;
- measurement governance: `on`;
- proposal context ablation: `compact-measurement-diagnostics`;
- early stop: disabled;
- proposal mode: agentic;
- agentic session timeout: `900s`;
- model endpoint: local `gpt-5.5`.

This is a single cell and therefore runs on the 2-core server. Larger parallel
matrices should use WSL.

## Preflight

The wrapper performs a strict copied-config data-root preflight before starting
the campaign. Manual preflight before launch confirmed:

```text
DataRootActivation(env_name='SCION_WAREHOUSE_DATA_ROOT',
data_root=PosixPath('/home/clawd/research/scion-data'),
source=PosixPath('/home/clawd/research/or-autoresearch-agent/scion/problems/warehouse_delivery/budgets.json'),
activated=True)
/home/clawd/research/scion-data/production/generated/instance_prod_can_s01.json resolved_safe_data_root /home/clawd/research/scion-data
/home/clawd/research/scion-data/production/generated/instance_prod_can_s02.json resolved_safe_data_root /home/clawd/research/scion-data
```

The campaign log also confirms:

```text
INFO: activated problem data root SCION_WAREHOUSE_DATA_ROOT=/home/clawd/research/scion-data
Starting campaign: warehouse_delivery (max_rounds=6, mock_llm=False, disable_early_stop=True)
```

## Failed Wrapper Attempt

An earlier launch directory exited before campaign startup because the wrapper
included an unsupported CLI option `--problem-v1`:

`/home/clawd/research/scion-experiments/v04-warehouse-dataroot-repair-rerun6r-ad469f0-20260617T011900Z`

That attempt has `exit_code=2`, consumed no LLM/campaign work, and should be
ignored except as a wrapper typo record.

## Acceptance Criteria

The rerun first needs to prove that copied production split cases reach canary
and screening without `absolute_outside_roots`.

Accept the data-root repair if:

- `run_validity.status=valid`;
- at least one formal protocol row is produced;
- no candidate is abandoned solely because production canary case paths resolve
  outside `safe_data_roots`.

Only after that should the run be used to judge whether warehouse
`repair_template` guidance improves research quality.
