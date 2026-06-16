# Warehouse Loss-Heavy Lifecycle Rerun 6R Postrun - 2026-06-16

Scope:

- Launch report:
  `scion/docs/experiments/v0.4/v04-warehouse-lossheavy-lifecycle-rerun6r-launch-20260616.md`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-lossheavy-lifecycle-rerun6r-20260616T184031Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-lossheavy-lifecycle-rerun6r-20260616T184031Z`
- Campaign dir:
  `/home/clawd/research/scion-experiments/v04-warehouse-lossheavy-lifecycle-rerun6r-20260616T184031Z/rep01/on_compact/campaign`
- Commit tested: `6e3988c`

## Executive Finding

The field gate is valid but does not close warehouse research quality.

- Wrapper exit: `0`
- Run validity: `valid`
- Effective rounds: `6/6`
- Protocol rows: `6 screening`, `0 validation`, `0 frozen`
- Proposal quality blocks: `0`
- Verification failures: `0`
- Fresh-runtime replay protocol rows: `0`
- Champion promotions: `0`
- Latest champion version: `1`

This run did not reproduce the prior loss-dominated marginal loop. Therefore the
new lifecycle brake was not field-triggered by the target `1/2/3` case and
`3/4/5` pair shape. It did, however, preserve useful positive/borderline branch
depth: the later `move_order.py` branch continued on non-loss-dominated evidence
instead of being parked by the new rule.

Research quality still fails: the run remained screening-only and did not reach
validation, frozen, or promotion. The next repair should focus on the
warehouse-owned protocol route for expanded-exhausted positive low-SNR evidence,
not on generic observability.

## Candidate Decisions

| Round | Branch | Target | Case W/L/T | Pair W/L/T | Median | CI | Decision | Main Reason |
|---:|---|---|---:|---:|---:|---|---|---|
| 1 | `3aa56f3d...` | `operators/consolidate_subcategory.py` | 3/1/6 | 10/6/4 | 150 | [-1175, 750] | `expand_screening` | `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT` |
| 2 | `3aa56f3d...` | `operators/consolidate_subcategory.py` | 4/2/10 | 14/12/6 | -50 | [-625, 450] | `abandon` | `SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_DELTA`, fail-closed lifecycle archive |
| 3 | `62876db5...` | `operators/move_order.py` | 2/1/3 | 5/3/4 | 375 | [-1950, 1750] | `expand_screening` | `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT` |
| 4 | `62876db5...` | `operators/move_order.py` | 3/1/10 | 13/6/9 | 300 | [0, 875] | `continue_explore` | `SCREENING_LOW_SNR_EXPAND_EXHAUSTED_CONTINUE`, `SCREENING_WEAK_SIGNAL_CONTINUE` |
| 5 | `62876db5...` | `operators/move_order.py` | 2/1/3 | 5/3/4 | 0 | [-1775, 1700] | `expand_screening` | `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT` |
| 6 | `62876db5...` | `operators/move_order.py` | 2/2/10 | 11/10/7 | 75 | [0, 600] | `continue_explore` | `SCREENING_LOW_SNR_EXPAND_EXHAUSTED_CONTINUE`, `SCREENING_MARGINAL_SIGNAL_CONTINUE` |

## Lifecycle Repair Acceptance

Accepted narrowly:

- The new lifecycle rule did not archive or park the positive `move_order.py`
  branch.
- There was no repeat of the previous four-row loss-dominated marginal loop.
- Candidate/runtime failures stayed at zero.
- Negative expanded-exhausted evidence still failed closed.

Not accepted as complete:

- The target loss-heavy shape did not occur in this field run, so this is a
  no-regression field check rather than direct field proof of the brake.
- No validation/frozen/promotion occurred.
- Branch depth remained short and did not produce a confirmed improvement.

## Protocol Finding

The run exposed a sharper protocol issue. Round 4 produced expanded-exhausted
positive evidence:

- case W/L/T `3/1/10`
- pair W/L/T `13/6/9`
- median delta `300`
- CI low `0`
- pair win-loss margin `+7`
- pair loss rate `6/28 = 0.214`
- non-tie pair win rate `13/19 = 0.684`

This is not loss-heavy and is not negative-median. It still did not queue
validation because the repaired pair-level diagnostic route is stricter than
this field-positive shape: total pair win rate counts ties (`13/28 = 0.464`)
and non-tie win rate is just below the configured `0.70` threshold.

The next repair should stay problem-owned and config-driven: warehouse
production protocol should allow expanded-exhausted, non-regressive,
positive-CI evidence like this to enter diagnostic validation, while preserving
fail-closed behavior for negative-median and loss-heavy shapes.

## Prompt / Context Check

The proposal trajectory manifest loaded `14` prompt manifests and `14` traces.
Branch lesson usage was present in `6/6` sessions, with `0` missing and `0`
unrecognized usage records. The code-phase visibility ledger showed full target
source visibility for existing `operators/move_order.py` edits, and champion
research code was included as `current_champion_research_code`.

One accounting caveat remains: the prompt family aggregate records only
`source_context` for patch-source digests, while `current_champion_research_code`
is counted under `general`. Therefore the low aggregate `source_context` share
is not by itself evidence that code was hidden from the model; code-phase
visibility ledgers must be inspected directly.

## Next Gate

Before another warehouse longrun, repair the warehouse protocol route for the
round-4 expanded-exhausted positive shape and add deterministic tests:

- `3/1/10` case, `13/6/9` pair, median `300`, CI low `0` should queue
  diagnostic validation after screening expand is exhausted.
- `4/2/10` case, `14/12/6` pair, median `-50` should still fail closed.
- `1/2/3` case, `3/4/5` pair, median `0` should still not validate.
- Existing `2/0/4` case, `6/2/4` pair behavior should remain validation-eligible.
