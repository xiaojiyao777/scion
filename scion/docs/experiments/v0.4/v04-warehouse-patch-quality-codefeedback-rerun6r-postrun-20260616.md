# Warehouse Patch-Quality Code Feedback Rerun Postrun

*Date: 2026-06-16*
*Commit: `5f2d418`*
*Status: valid run; research path restored; retry-constraint preservation not accepted*

## Artifact Roots

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-patch-quality-codefeedback-rerun6r-5f2d418-20260616T210541Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-patch-quality-codefeedback-rerun6r-5f2d418-20260616T210541Z`
- Campaign:
  `rep01/on_compact/campaign`

## Run Shape

- Warehouse production protocol/split/seeds.
- `6` requested rounds.
- `--measurement-governance on`.
- `--proposal-context-ablation compact-measurement-diagnostics`.
- `--agentic-proposal`.
- `--disable-early-stop`.
- Local model: `gpt-5.5`.

## Result

The wrapper exited `0`, and `run_validity.status` is `valid`.

Final accounting:

- `effective_rounds_completed`: `6/6`.
- `proposal_attempts_total`: `14`.
- `quality_blocks`: `8`.
- `quality_block_ledger_count`: `8`.
- `formal_screened_candidates`: `5`.
- Protocol rows: `5` screening, `1` validation, `1` frozen.
- Champion advanced from v1 to v2.

Promotion dossier:

`artifacts/promotions/champion_v2_promotion_dossier.json`

Promoted branch and hypothesis:

- Branch: `9a9dbe90-b999-4828-9938-b162d180e7cf`.
- Hypothesis: `9ca3d2a2-81e8-4905-8690-b29099ba9618`.
- Target: `operators/move_order.py`.
- Mechanism: bounded slack-fill cost-elimination order move with explicit
  split/cost guard and activation/effect counters.

Stage chain from the promotion dossier:

- Screening expanded: case W/L/T `6/1/7`, median delta `300.0`, CI
  `[0.0, 725.0]`, `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT`, then
  `queue_validate`.
- Validation: W/L/T `5/0/0`, median delta `4400.0`, CI
  `[2800.0, 10500.0]`, `VALIDATION_PASS_HIERARCHICAL`.
- Frozen: W/L/T `4/0/0`, median delta `6900.0`, CI
  `[4700.0, 18600.0]`, `FROZEN_PASS_HIERARCHICAL`, then `promote`.

## Acceptance Interpretation

This run accepts the main `5f2d418` visibility repair:

- Code prompt manifests include the dynamic
  `Prior Agent Quality Blocks For This Code Patch` section.
- Later code attempts can see prior warehouse patch-quality failures.
- The warehouse research path recovered to screening -> validation -> frozen ->
  promotion within a short `6R` field check.

This run does not accept the full quality-feedback repair:

- The run still produced `8` proposal quality blocks:
  `4` hypothesis-stage validation-transfer blocks and `4` code-stage
  patch-quality blocks.
- `campaign_summary.json` and quality-block ledger material still show generic
  retry text:
  `Acknowledge the existing mechanism and state the material trigger...`
- That generic fallback overwrote the warehouse problem-owned retry constraint,
  so the agent did not receive the most actionable adapter-owned wording in the
  durable quality feedback path.

Therefore `5f2d418` is positive research-path evidence but not final
quality-feedback acceptance.

## Next Gate

Commit `3c2b7b5` preserves `structured_rejection.retry_constraint` and carries
`missing_claims` / `missing_code_elements` forward into quality feedback.

A fresh rerun from `3c2b7b5` must prove:

- final WSL and server artifacts are synced and complete;
- quality-block ledgers preserve warehouse problem-owned retry text instead of
  generic novelty fallback text;
- code traces expose `failure_code`, `quality_gate_name`, missing fields, and
  the warehouse-specific retry constraint;
- any remaining quality blocks are real proposal/adapter limitations, not
  context propagation loss; and
- no warehouse semantics enter `DecisionFeatures`.
