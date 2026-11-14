# Warehouse Hypothesis Quality-Block Rerun Postrun

*Date: 2026-06-17*
*Commit under test: `4b2ee29`*
*Status: valid run; prompt visibility accepted; research quality failed*

## Artifact Roots

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-hypothesis-qualityblock-rerun6r-4b2ee29-20260616T222243Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-hypothesis-qualityblock-rerun6r-4b2ee29-20260616T222243Z`

The final run accounting below was inspected from the WSL root. The server sync
root lagged the final WSL state during postrun because the reverse SSH tunnel
accepted TCP connections but timed out during SSH banner exchange. Treat that as
an artifact-sync risk, not as experiment invalidity.

## Run Result

The run completed validly:

- wrapper exit: `0`.
- run validity: `valid`.
- completed at: `2026-06-16T22:41:26Z`.
- effective rounds: `6/6`.
- proposal attempts: `11`.
- proposal quality blocks: `5`.
- quality-block ledger rows: `5`.
- formal screened candidates: `6`.
- protocol metric rows: `6`.
- stage counts: `6` screening, `0` validation, `0` frozen.
- promotions: `0`.
- champion version: v1.

Screening decisions:

- `abandon=1`.
- `expand_screening=3`.
- `continue_explore=2`.
- no validation queue, frozen row, or promotion.

Best retained branch remained marginal:

- branch: `2021b41c-2e65-4baa-8a63-9d4c19943435`.
- status: `explore_expand`.
- current evidence W/L/T: `1/1/12`.
- median delta: `0.0`.
- CI: `[-150.0, 250.0]`.
- runtime evidence confidence: `low_cached_champion`.

## Accepted Repair

Prompt visibility for the hypothesis quality-block repair is accepted.

Final traces contained `12` hypothesis calls. `7/12` hypothesis traces and
`7/12` hypothesis prompt manifests included:

```text
Prior Agent Quality Blocks For This Hypothesis
```

The section carried concrete warehouse-owned repair material:

- `agent_quality_blocked:warehouse_validation_transfer_quality_missing`.
- `warehouse_validation_transfer_quality`.
- `missing_claims=[validation_transfer_risk, screening_only_guard]`.
- the hypothesis retry constraint.
- `agent_quality_blocked:warehouse_validation_transfer_patch_quality_missing`.
- `warehouse_validation_transfer_patch_quality`.
- `missing_code_elements=[activation_effect_diagnostic_code]`.
- later traces also showed
  `missing_code_elements=[activation_effect_diagnostic_code, screening_or_lexicographic_guard]`.

This rules out the earlier prompt/context propagation failure as the primary
remaining cause.

## Rejected Research Quality

Research quality is still rejected:

- no validation/frozen/promotion path was restored;
- all formal candidates stayed screening-only;
- quality blocks decreased from `9/15` in the prior retry-constraint rerun to
  `5/11`, but the same warehouse transfer/diagnostic failure family repeated;
- screening evidence remained marginal or negative; and
- the best retained branch had only `1/1/12` W/L/T with median `0`.

The bottleneck is now the agent's ability to satisfy problem-owned warehouse
research/code-generation constraints after they are visible, not generic
observability, prompt truncation, Decision, Protocol, or measurement failure.

## Next Repair

Add problem-owned repair templates to warehouse quality-block structured
rejections and preserve them through quality feedback. The next prompt should
not merely show `failure_code`, `retry_constraint`, and missing items. It should
also show a concrete adapter-owned checklist for:

- required hypothesis fields and claims;
- required activation/effect diagnostic identifiers;
- required screening-only or lexicographic guard shape; and
- minimal executable code signals that satisfy the patch-quality gate.

This remains proposal-only tainted context. It must not change
`DecisionFeatures`, Protocol thresholds, or warehouse validation/frozen gate
semantics.
