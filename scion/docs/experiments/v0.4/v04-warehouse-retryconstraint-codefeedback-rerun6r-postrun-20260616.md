# Warehouse Retry-Constraint Code Feedback Rerun Postrun

*Date: 2026-06-16*
*Commit: `3c2b7b5`*
*Status: valid run; retry-constraint repair accepted; research quality failed*

## Artifact Roots

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-retryconstraint-codefeedback-rerun6r-3c2b7b5-20260616T214445Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-retryconstraint-codefeedback-rerun6r-3c2b7b5-20260616T214445Z`
- Campaign:
  `rep01/on_compact/campaign`

## Result

The wrapper exited `0`, and `run_validity.status` is `valid`.

Final accounting:

- `effective_rounds_completed`: `6/6`.
- `proposal_attempts_total`: `15`.
- `quality_blocks`: `9`.
- `quality_block_ledger_count`: `9`.
- `formal_screened_candidates`: `6`.
- Protocol rows: `6` screening, `0` validation, `0` frozen.
- Champion stayed at v1.

Aggregate screening evidence:

- case W/L/T: `6/8/30`, case win rate `0.136`.
- pair W/L/T: `28/30/30`, pair win rate `0.318`.
- decisions: `abandon=3`, `continue_explore=2`, `expand_screening=1`.

Quality block taxonomy:

- `5` hypothesis-stage
  `warehouse_validation_transfer_quality_missing` blocks.
- `4` code-stage
  `warehouse_validation_transfer_patch_quality_missing` blocks.
- No infrastructure failures.
- No verification-consumed failures.
- No fresh-runtime replay drain.

## Accepted Repair

The `3c2b7b5` retry-constraint preservation repair is field-accepted.

The final `status.json` quality-block ledger preserves problem-owned warehouse
retry constraints instead of the previous generic novelty fallback:

- Hypothesis quality block:
  `Rewrite the warehouse operator hypothesis before code: state the screening-to-validation transfer risk, declare expected activation/effect diagnostics, and explain the guard against screening-only improvements.`
- Patch quality block:
  `Revise the warehouse operator patch before protocol: add code-visible activation/effect diagnostic counters or a named instrumentation path, and include a guard that prevents screening-only or lexicographically dominated moves.`

Code prompt traces also preserve the actionable repair material:

- `10` code traces were recorded.
- `8/10` include `Prior Agent Quality Blocks For This Code Patch`.
- `5/10` include the patch-quality gate, warehouse-specific retry constraint,
  and `activation_effect_diagnostic_code`.
- `0/10` include the old generic retry text
  `Acknowledge the existing mechanism...`.

This accepts the field repair for context propagation and problem-owned
constraint preservation. No `DecisionFeatures`, Protocol thresholds, or
warehouse validation/frozen gate semantics changed.

## Rejected Research Quality

The run rejects warehouse research-quality acceptance:

- no validation/frozen/promotion occurred;
- quality blocks consumed `9/15` proposal attempts;
- final screening aggregate was loss-heavy or tie-heavy;
- formal candidate artifacts remained screening-only; and
- the agent repeatedly failed to satisfy the same warehouse transfer/diagnostic
  requirements even after prior blocks were visible in code prompts.

This means the next bottleneck is no longer observability or field propagation.
The next repair should make prior quality blocks hard at hypothesis time, not
only code time, and force repeated warehouse transfer failures into a
structured repair mode before another near-same hypothesis is allowed.

## Follow-up Local Repair

A local follow-up repair adds an explicit
`Prior Agent Quality Blocks For This Hypothesis` section to hypothesis prompts.
It renders `agentic_prior_quality_blocks` and the quality-block rule as a hard
proposal-only research constraint before the analysis steps. The section
requires the next hypothesis to repair cited `failure_code`, gate,
`retry_constraint`, `missing_claims`, or `missing_code_elements` before
proposing a near-same mechanism.

Focused verification:

```bash
PYTHONPATH=scion python -m pytest scion/scion/tests/unit/core/test_proposal_pipeline_quality_blocks.py -q
PYTHONPATH=scion python -m pytest scion/scion/tests/unit/core/test_proposal_pipeline_*.py -q
python -m py_compile scion/scion/proposal/engine/hypothesis_prompts.py
git diff --check
```

Results:

- Proposal quality-block tests: `21 passed`.
- Proposal pipeline tests: `77 passed`.
- `py_compile`: passed.
- `git diff --check`: passed.

## Next Gate

Run a fresh warehouse short field check from the follow-up commit. Acceptance
requires fewer repeated validation-transfer quality blocks or clear evidence
that any remaining blocks are caused by genuine adapter constraints after the
hypothesis prompt visibly received the hard quality-block section.
