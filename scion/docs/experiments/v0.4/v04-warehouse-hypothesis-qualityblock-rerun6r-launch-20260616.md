# Warehouse Hypothesis Quality-Block Rerun Launch

*Date: 2026-06-16*
*Commit under test: `4b2ee29`*
*Status: running on WSL*

## Purpose

This is the field check for the follow-up repair after the `3c2b7b5`
retry-constraint rerun. That run accepted retry-constraint propagation but
rejected warehouse research quality: all formal candidates stayed in screening
and `9/15` proposal attempts were quality-blocked.

The new repair renders prior branch-local quality blocks directly in
hypothesis prompts as `Prior Agent Quality Blocks For This Hypothesis`. The
section is proposal-only context and not Decision input. Its purpose is to make
the next hypothesis explicitly address cited `failure_code`, gate,
`retry_constraint`, `missing_claims`, or `missing_code_elements` before
proposing another near-same mechanism.

## Launch

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-hypothesis-qualityblock-rerun6r-4b2ee29-20260616T222243Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-hypothesis-qualityblock-rerun6r-4b2ee29-20260616T222243Z`
- tmux session:
  `scion_wh_hypqblock_rerun6r_4b2ee29_222243`
- WSL repo:
  `/home/xjy-ubuntu/research/or-autoresearch-agent`
- Expected commit:
  `4b2ee29`

The run reuses the prior short warehouse production field-check shape:

- problem: warehouse delivery production config copied to WSL-local paths;
- protocol: `scion/problems/warehouse_delivery/protocol_prod.yaml`;
- split: production split manifest copied to WSL-local paths;
- seeds: `scion/problems/warehouse_delivery/seed_ledger.yaml`;
- rounds: `6`;
- time limit: `30s`;
- measurement governance: `on`;
- proposal context ablation: `compact-measurement-diagnostics`;
- early stop: disabled;
- proposal mode: agentic;
- agentic session timeout: `900s`;
- model endpoint: local `gpt-5.5`.

## Initial Health Check

Initial synced status:

```text
status=running
commit=4b2ee29
rounds=6
measurement_governance=on
context=compact-measurement-diagnostics
purpose=v0.4_warehouse_hypothesis_qualityblock_rerun_after_4b2ee29
```

The first branch hit the expected warehouse validation-transfer quality gate:

```text
agent_quality_blocked:warehouse_validation_transfer_quality_missing:premise_contradicted
missing=validation_transfer_risk,screening_only_guard
```

This is not a launch failure. It is the intended first signal for this repair:
the next hypothesis call on that branch should receive the prior block as a
hard proposal-only research constraint.

## Acceptance Criteria

Accept the prompt repair only if later hypothesis traces/manifests show the
`Prior Agent Quality Blocks For This Hypothesis` section after a quality block
has occurred.

Accept research-quality improvement only if one of these is true:

- repeated warehouse validation-transfer quality blocks materially drop;
- a repeated block is explained by a genuine adapter-owned requirement after
  the hard hypothesis section was visible; or
- the run restores validation/frozen/promotion behavior without regressing
  prompt visibility or retry-constraint preservation.

Do not treat screening-only rows or promotion alone as sufficient without the
prompt-trace evidence above.
