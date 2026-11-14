# Warehouse Research-Loop Repair Short 6R Postrun - 2026-06-16

## Verdict

The run is valid execution evidence but failed the research-quality acceptance
gate. It proves the prior prompt/no-hard-truncation repair did not by itself
restore v0.3-style warehouse research continuity. The next repair must target
proposal quality and cheap problem-owned prevention of structurally unsafe
warehouse operator edits.

This is not a promotion/efficacy result and not a warehouse longrun.

## Run

- Branch: `codex/v04-evidence-repair-plan`
- Commit: `0bb99ec` (`fix: steer warehouse research followups`)
- Launch report:
  [`v04-warehouse-research-loop-repair-short-6r-launch-20260616.md`](v04-warehouse-research-loop-repair-short-6r-launch-20260616.md)
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-research-loop-repair-short-6r-20260616T165145Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-research-loop-repair-short-6r-20260616T165145Z`
- Campaign root:
  `/home/clawd/research/scion-experiments/v04-warehouse-research-loop-repair-short-6r-20260616T165145Z/rep01/on_compact/campaign`
- Model: local `gpt-5.5`
- Shape: warehouse production protocol/split/seeds, `6` rounds, disabled early
  stop, `measurement_governance=on`, `compact-measurement-diagnostics`,
  `time_limit_sec=30`.

## Run Validity

`campaign/status.json` reports:

- `run_validity.status=valid`
- `run_completeness_status=complete`
- `completed_requested_rounds=true`
- `effective_rounds_completed=6`
- `total_rounds=7`
- `proposal_attempts_total=7`
- `quality_blocks=1`
- `quality_block_ledger_count=1`
- `verification_failure_consumed_candidates=2`
- `protocol_metric_results=4`
- `protocol_metric_stage_counts={screening:4, validation:0, frozen:0}`
- `fresh_runtime_replay_protocol_results=0`
- `last_stop_reason=max_rounds_exhausted`

`campaign/campaign_summary.json` reports `failure_categories={verification:2,
proposal:1}` and `fresh_champion_required_count=1`.

The formal candidate index contains `4` screening candidates, all with complete
replay identity metadata. No validation, frozen, or promotion occurred.

## Acceptance Check

The launch acceptance criteria were research-quality focused:

- complete wrapper/run validity;
- all traces use `gpt-5.5`;
- candidate/protocol/quality-block counters reconcile;
- fewer or better-repaired branch-lesson quality blocks;
- no repeat unsafe warehouse operator structural failure;
- retained marginal branches receive same-mechanism causal follow-up.

Only the execution/reconciliation part passed. The research-quality part did
not pass.

Observed failures:

- One proposal quality block remained:
  `branch_lesson_usage_semantic_mismatch`.
- Two consumed candidates failed verification before formal screening on branch
  `c64e6804-9ac9-40a3-aba1-5aafe2fcc536`.
- Four formal candidates reached screening, but all stayed in screening. Two
  were `active_marginal`; two were `active_no_effect`.
- Same-branch follow-up did start on branch
  `48cdfe69-591a-42af-8c33-57770a9188f9`, but the branch still did not close a
  useful validation path.
- A final follow-up on the same branch produced all ties and
  `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`; no replay protocol row was scheduled
  before max rounds.

The prompt/context repair therefore passed as visibility infrastructure, but
the research loop still produced too much fragile code and too little
evidence-backed mechanism refinement.

## Branch-Level Read

The useful branch signal was not zero. The scheduler created repeated work on
two branches:

- `c7772566-2898-4eed-a0e8-195f0e306002` explored
  `operators/consolidate_subcategory_bucket.py` twice and produced one
  marginal and one no-effect screening row.
- `48cdfe69-591a-42af-8c33-57770a9188f9` explored
  `operators/split_neutral_cost_compact.py`, produced a marginal first
  candidate, hit a branch-lesson semantic block on an intermediate retry, then
  produced a no-effect follow-up screening row.
- `c64e6804-9ac9-40a3-aba1-5aafe2fcc536` attempted existing operator edits
  (`operators/move_order.py` and `operators/swap_orders.py`) that consumed
  verification failures.

This partially validates the branch-depth mechanism: the campaign did not only
make one-off branches. But the follow-ups did not yet convert branch lessons
into better warehouse mechanisms.

## Repair Accepted After This Run

After this failed acceptance, the next repair is targeted and boundary-limited:

1. Generic proposal path:
   - Add deterministic canonical repair for concrete `branch_lesson_usage`
     values that already name/apply a branch lesson but miss machine-readable
     linkage fields.
   - The repair uses the existing skeleton, records repair attribution, and is
     proposal-only. It does not create lesson usage from empty or metadata-only
     values.
   - `DecisionFeatures`, Protocol, promotion gates, and raw lesson text remain
     unchanged.

2. Warehouse problem package:
   - Add a problem-owned cheap preview hook for warehouse operator patches.
   - Reject deletion of existing imported operator modules before heavy
     verification.
   - Statically catch local nested dict state-key references not declared in
     the candidate's own dict literal, a direct class of fragile operator edit
     that should not wait for `V5_solution_consistency`.

Focused acceptance for this repair passed:

- `test_branch_lesson_usage.py`: `29 passed`
- `test_warehouse_target_preview.py`: `6 passed`
- proposal/context regression subset: `62 passed`
- agentic schema/session subset: `34 passed`
- trajectory/artifact subset: `30 passed`
- pipeline/research-surface/AST contract subset: `57 passed`
- Python compile on touched files: passed

The repair is accepted as code-quality mitigation, not as field-proven research
efficacy. The next live warehouse check must rerun a short field gate from the
new repair commit and accept only if semantic quality blocks and unsafe
verification failures actually fall while same-branch causal follow-up improves.

## Status Impact

This run keeps the v0.4 Phase 4 warehouse state open:

- v0.4 warehouse is execution-capable and prompt/source visibility is no longer
  the immediate blocker.
- v0.4 warehouse is not yet research-quality restored relative to the v0.3
  continuous-promotion behavior.
- The next work is not broad observability and not a longrun by default. It is
  targeted research-loop repair, followed by another short live acceptance
  check.
