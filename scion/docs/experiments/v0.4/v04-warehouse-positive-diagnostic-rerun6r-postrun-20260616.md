# Warehouse Positive Diagnostic Rerun 6R Postrun - 2026-06-16

Scope:

- Launch report:
  `scion/docs/experiments/v0.4/v04-warehouse-positive-diagnostic-rerun6r-launch-20260616.md`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-positive-diagnostic-rerun6r-20260616T190605Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-positive-diagnostic-rerun6r-20260616T190605Z`
- Campaign dir:
  `/home/clawd/research/scion-experiments/v04-warehouse-positive-diagnostic-rerun6r-20260616T190605Z/rep01/on_compact/campaign`
- Commit tested: `41d02d1`

## Executive Finding

The run is valid and proves the repaired warehouse research loop can reach
validation again, but it still does not establish warehouse research quality.

- Wrapper exit: `0`
- Run validity: `valid`
- Effective rounds: `6/6`
- Protocol rows: `5 screening`, `1 validation`, `0 frozen`
- Proposal quality blocks: `0`
- Verification failures: `0`
- Fresh-runtime replay protocol rows: `0`
- Champion promotions: `0`
- Latest champion version: `1`

Accepted:

- The run is no longer screening-only. One candidate reached validation.
- The loss-dominated marginal lifecycle brake field-triggered and parked a
  repeated `move_order.py` branch with
  `BRANCH_LIFECYCLE_PARK_LINEAGE` and
  `SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP`.
- Negative or weak marginal evidence did not reach validation.

Not accepted:

- No frozen row or promotion occurred.
- The single validation candidate failed with `VALIDATION_PROTOCOL_GATE_FAIL`
  and `VALIDATION_FAIL_NO_HIERARCHICAL_GAIN`.
- The positive-diagnostic threshold repair was accepted deterministically, but
  this live run did not specifically exercise the exact `3/1/10` case,
  `13/6/9` pair, median `300`, CI low `0` diagnostic path. The live validation
  route was an ordinary screening pass.

## Candidate Decisions

| Step | Branch | Target | Stage | Case W/L/T | Pair W/L/T | Median | CI | Decision | Main Reason |
|---:|---|---|---|---:|---:|---:|---|---|---|
| 1 | `87e1209f...` | `operators/same_subcategory_consolidate.py` | screening | 6/1/3 | 13/3/4 | 475 | [0, 2100] | `queue_validate` | `SCREENING_PASS` |
| 2 | `87e1209f...` | `operators/same_subcategory_consolidate.py` | validation | 2/3/0 | 6/9/0 | 0 | [0, 1] | `abandon` | `VALIDATION_PROTOCOL_GATE_FAIL`, `VALIDATION_FAIL_NO_HIERARCHICAL_GAIN` |
| 3 | `96816377...` | `operators/move_order.py` | screening | 1/2/3 | 3/5/4 | 0 | [-1925, 1050] | `continue_explore` | `SCREENING_FAIL_WIN_RATE`, `SCREENING_MARGINAL_SIGNAL_CONTINUE` |
| 4 | `96816377...` | `operators/move_order.py` | screening | 1/2/3 | 3/4/5 | 0 | [-1925, 1500] | `continue_explore` with lifecycle park | `SCREENING_FAIL_WIN_RATE`, `BRANCH_LIFECYCLE_PARK_LINEAGE`, `SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP` |
| 5 | `ec140590...` | `operators/tail_cluster_repack.py` | screening | 2/0/8 | 9/6/5 | 0 | [-200, 325] | `expand_screening` | `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT` |
| 6 | `ec140590...` | `operators/tail_cluster_repack.py` | screening | 2/1/13 | 11/11/10 | 0 | [-350, 150] | `continue_explore` | `SCREENING_LOW_SNR_EXPAND_EXHAUSTED_CONTINUE`, `SCREENING_MARGINAL_SIGNAL_CONTINUE` |

## Validation Finding

The validation candidate was `same_subcategory_consolidate`. It looked strong
at screening:

- case W/L/T `6/1/3`
- pair W/L/T `13/3/4`
- median delta `475`
- CI low `0`

Validation rejected it:

- validation case W/L/T `2/3/0`
- validation pair W/L/T `6/9/0`
- median delta `0`
- `VALIDATION_FAIL_NO_HIERARCHICAL_GAIN`

Interpretation:

- The gate behavior is correct: screening-positive candidates can now reach
  validation, and validation can reject them.
- The agent still has not produced a robust warehouse improvement.
- The next repair should not loosen validation. It should improve proposal and
  problem-owned diagnostic quality so screening-positive ideas explain why they
  should survive validation, especially across larger validation cases.

## Lifecycle Finding

The loss-heavy lifecycle repair is field-accepted for the target shape. The
second `move_order.py` candidate repeated the prior failure shape:

- case W/L/T `1/2/3`
- pair W/L/T `3/4/5`
- median delta `0`
- prior evidence tier `marginal`

It was parked with:

- `BRANCH_LIFECYCLE_PARK_LINEAGE`
- `SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP`

This directly fixes the earlier four-row same-branch loss-dominated marginal
loop.

## Prompt / Context Notes

The proposal trajectory manifest loaded `17` prompt manifests and `17` traces.
Branch lesson usage was present in `8/8` sessions with `0` missing and `0`
unrecognized usages. Prompt family accounting still places most source code
under `general` rather than `source_context`, so source visibility must be read
from code-phase ledgers rather than the aggregate family share.

## Next Gate

Do not loosen validation or frozen gates. The next repair should target
warehouse proposal quality and problem-owned diagnostics:

- Require screening-positive warehouse hypotheses to name the validation-case
  transfer risk they address.
- Add or surface problem-owned operator activation/effect counters for the
  warehouse operators that repeatedly produce screening-only or validation-fail
  behavior.
- Treat validation failure on `same_subcategory_consolidate` as a problem-domain
  research finding, not as a framework gate failure.

After that, rerun a short warehouse field gate. A full warehouse longrun should
wait until short runs show at least validation-stable evidence or a clear,
accepted research insight.
