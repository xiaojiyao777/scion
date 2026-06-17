# Warehouse Repair-Template Rerun Launch

*Date: 2026-06-17*
*Commit under test: `4a316e1`*
*Status: running on server*

## Purpose

This field check validates the follow-up repair after the `4b2ee29`
hypothesis quality-block rerun. That run accepted prompt visibility for
`Prior Agent Quality Blocks For This Hypothesis`, but still failed research
quality: `6` screening rows, `0` validation/frozen rows, no promotion, and
`5/11` proposal attempts quality-blocked.

The `4a316e1` repair adds warehouse problem-owned `repair_template` payloads to
quality-block structured rejections and preserves them through later proposal
contexts. The intent is to stop forcing the agent to infer how to satisfy the
warehouse quality gates from only `failure_code`, `retry_constraint`, and
missing item names.

## Launch

- Server root:
  `/home/clawd/research/scion-experiments/v04-warehouse-repairtemplate-rerun6r-4a316e1-20260617T002824Z`
- tmux session:
  `scion_wh_repairtemplate_rerun6r_4a316e1_002824`
- repo:
  `/home/clawd/research/or-autoresearch-agent`
- expected commit:
  `4a316e1`

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

This run is on the server rather than WSL because the WSL reverse SSH endpoint
accepted TCP connections but timed out during SSH banner exchange during
postrun sync.

## Initial Health Check

Initial status:

```text
status=running
commit=4a316e1
rounds=6
measurement_governance=on
context=compact-measurement-diagnostics
purpose=v0.4_warehouse_repairtemplate_rerun_after_4a316e1
```

The campaign started with:

```text
Starting campaign: warehouse_delivery (max_rounds=6, mock_llm=False, disable_early_stop=True)
```

## Early Trace Check

Early traces accept repair-template prompt propagation:

- first hypothesis trace: no prior block, as expected before any quality block;
- second hypothesis trace: includes
  `Prior Agent Quality Blocks For This Hypothesis` and `repair_template`;
- first code trace after the repaired hypothesis: includes
  `Prior Agent Quality Blocks For This Code Patch` and `repair_template`.

Current early accounting:

- `proposal_attempts_total`: `2`;
- `quality_blocks`: `1`;
- `formal_screened_candidates`: `0`;
- protocol stage counts: `0` screening, `0` validation, `0` frozen.

This accepts the propagation part of the `4a316e1` repair. Research-quality
acceptance still requires the full run outcome.

## Acceptance Criteria

Prompt repair-template propagation has been observed in early hypothesis/code
traces.

Research-quality improvement is accepted only if one of these occurs:

- repeated warehouse validation-transfer quality blocks materially decrease
  from the `4b2ee29` level (`5/11`);
- a repeated block is explained by a genuine adapter-owned requirement after
  `repair_template` content is visible; or
- validation/frozen/promotion behavior is restored without regressing
  retry-constraint and prompt-visibility evidence.
