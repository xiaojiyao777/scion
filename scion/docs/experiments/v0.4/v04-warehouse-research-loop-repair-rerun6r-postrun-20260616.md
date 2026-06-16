# Warehouse Research-Loop Repair Rerun 6R Postrun - 2026-06-16

## Verdict

The `d666311` rerun is field-accepted for the targeted repair-slice gate, but
not accepted as warehouse efficacy evidence or restored v0.3-style continuous
promotion.

The strict distinction matters: this run is more than valid execution. It
directly improved the failure modes from the failed `0bb99ec` 6R gate:

- proposal quality blocks fell from `1` to `0`;
- verification-consumed unsafe warehouse operator failures fell from `2` to
  `0`;
- formal screening rows rose from `4` to `6`;
- formal candidate replay identities reconciled exactly;
- retained marginal work received same-mechanism follow-up on one branch for
  four screening attempts.

However, every formal row remained screening-only. No validation, frozen
holdout, promotion, or efficacy claim is supported. Treat this as acceptance of
the branch-lesson canonicalization and warehouse preview/repair slice, not as a
warehouse research-quality closeout.

The v3 architecture boundary held. LLM outputs in this analysis are tainted
proposal material; Decision consumed deterministic protocol/DecisionFeatures
outputs only; warehouse-specific interpretation stays in this problem-owned
postrun report and related adapter/spec/report artifacts, not in generic
DecisionFeatures.

## Run

- Branch: `codex/v04-evidence-repair-plan`
- Expected commit: `d666311`
- Launch report:
  [`v04-warehouse-research-loop-repair-rerun6r-launch-20260616.md`](v04-warehouse-research-loop-repair-rerun6r-launch-20260616.md)
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-research-loop-repair-rerun6r-20260616T173136Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-research-loop-repair-rerun6r-20260616T173136Z`
- Campaign root:
  `/home/clawd/research/scion-experiments/v04-warehouse-research-loop-repair-rerun6r-20260616T173136Z/rep01/on_compact/campaign`
- WSL tmux: `scion_wh_repair_rerun6r_173136`
- Model: local `gpt-5.5`
- Shape: warehouse production protocol/split/seeds, `6` rounds, disabled early
  stop, `measurement_governance=on`,
  `compact-measurement-diagnostics`, `time_limit_sec=30`.

The WSL wrapper finished at `2026-06-16T17:48:10Z` with exit code `0`. The
campaign `run_status.json` reports `WRAPPER_EXIT_STATUS:0`,
`CAMPAIGN_EXIT_STATUS:complete`, `RUN_VALIDITY_STATUS:valid`,
`COMPLETED_REQUESTED_ROUNDS:True`, and
`LAST_STOP_REASON:max_rounds_exhausted`.

## Run Validity And Accounting

Final `campaign/status.json` and postrun reports reconcile:

- `run_validity.status=valid`
- `run_completeness_status=complete`
- `completed_requested_rounds=true`
- `requested_rounds=6`
- `effective_rounds_completed=6`
- `total_rounds=6`
- `proposal_attempts_total=6`
- `quality_blocks=0`
- `quality_block_ledger_count=0`
- `verification_failure_consumed_candidates=0`
- `verification_consumed_candidates=6`
- `protocol_metric_results=6`
- `protocol_metric_stage_counts={screening:6, validation:0, frozen:0}`
- `fresh_runtime_replay_protocol_results=0`
- `formal_candidate_artifact_count=6`
- formal candidate index entries `6`
- DB screening rows `6`
- formal-candidate reconciliation differences `[]`
- `last_stop_reason=max_rounds_exhausted`

`postrun_acceptance/failures/rep01_on_compact.failures.json` reports
`total_failures=0`. `research_efficiency` reports no code-generation,
tool-timeout, stale-source, old-string, or heavy-verification failures. A
non-counted stage-transition drain was attempted once and skipped because there
was no pending fresh-runtime replay candidate; this did not consume the max
round budget and produced no replay row.

## Protocol Outcomes

All six formal candidates passed contract and verification and reached
screening. All six screening rows failed the screening win-rate gate and
received `continue_explore`.

| Branch | Hypothesis | Target | Action | Case W/L/T | Pair W/L/T | Median | CI | Decision |
|---|---|---|---|---:|---:|---:|---:|---|
| `68c4f8c8` | `52d4fff7` | `operators/consolidate_subcategory.py` | create | `3/3/4` | `8/8/4` | `150.0` | `[-900.0, 600.0]` | continue |
| `68c4f8c8` | `d08f27ce` | `operators/consolidate_subcategory.py` | modify | `0/0/6` | `0/0/12` | `0.0` | `[0.0, 0.0]` | continue |
| `0229b440` | `2a727f8d` | `operators/move_order.py` | modify | `2/1/3` | `5/3/4` | `300.0` | `[-1225.0, 975.0]` | continue |
| `0229b440` | `020b2589` | `operators/move_order.py` | modify | `2/1/3` | `5/3/4` | `400.0` | `[-1550.0, 1875.0]` | continue |
| `0229b440` | `d6a05837` | `operators/move_order.py` | modify | `2/0/4` | `6/2/4` | `0.0` | `[-1725.0, 1350.0]` | continue |
| `0229b440` | `6387880a` | `operators/move_order.py` | modify | `2/0/4` | `6/2/4` | `0.0` | `[-1725.0, 1350.0]` | continue |

Aggregate screening evidence:

- case W/L/T: `11/5/24`
- case win rate: `0.275`
- pair W/L/T: `30/18/32`
- pair win rate: `0.375`
- champion promotions: `0`
- latest champion version: `1`

The best branch evidence remained marginal. The final `move_order.py`
checkpoint had case-level positive signals on `instance_prod_scr_s03.json`
and `instance_prod_scr_m03.json`, but the median was `0.0`, CI crossed zero,
and validation was never reached. This is not a promotion-quality result.

## Comparison To Failed `0bb99ec` Gate

The failed `0bb99ec` run was valid execution evidence but failed the
research-quality acceptance gate:

- `6/6` effective rounds;
- `7` proposal attempts;
- `1` proposal quality block:
  `branch_lesson_usage_semantic_mismatch`;
- `2` verification-consumed failures from fragile existing-operator edits;
- `4` screening rows;
- no validation/frozen/promotion;
- branch follow-up existed but did not repair the fragile-code path.

This rerun improves the targeted blockers:

- `0` branch-lesson semantic quality blocks. The trajectory manifest reports
  branch-lesson usage present in all `12` sessions, semantic projection present
  in all `12`, `usage_missing_count=0`, and
  `unrecognized_usage_present_count=0`.
- `0` verification-consumed unsafe operator failures. Existing `move_order.py`
  edits passed contract and verification rather than failing V5 after consuming
  the budget.
- `6` screening candidates, all replayable, with no reconciliation differences.
- Branch follow-up became more concentrated and interpretable: one
  `consolidate_subcategory` branch received a create plus refine attempt; one
  `fill_slack_order_move` branch received four same-mechanism modifications.

The remaining weakness is research efficacy. Compared with `0bb99ec`, the
repair reduced bad failures, but it did not make warehouse candidates advance
past screening.

## Branch Trajectories

`68c4f8c8-b85f-4a84-a3ab-5b4a37ed85d2` explored
`consolidate_subcategory`:

- first candidate created `operators/consolidate_subcategory.py` and registered
  it;
- second candidate refined the same file with stricter projected-cost and
  affected-vehicle checks;
- the branch ended `active_no_effect`;
- best checkpoint was marginal (`3/3/4`, median `150.0`), but current head was
  all ties (`0/0/6`);
- branch policy now allows only a clean fork for new mechanisms.

`0229b440-fd63-4563-9f40-6301b6030ea1` explored
`fill_slack_order_move` in `operators/move_order.py`:

- all four formal candidates were same-branch, same-mechanism modifications;
- hypotheses narrowed from slack filling to full source-vehicle drain, then to
  assignment synchronization and exact split-count certification;
- final branch status was `active_marginal`;
- current head had `2/0/4` case W/L/T and `6/2/4` pair W/L/T, but median
  remained `0.0` with CI `[-1725.0, 1350.0]`;
- runtime aggregate evidence was excluded as low-confidence cached champion
  evidence, preserving the intended caution around runtime interpretation.

This is better branch continuity than the previous run. It shows causal
same-mechanism follow-up, but the mechanism did not convert marginal
case-level wins into validation reach.

## Prompt And Trace Audit

The LLM trace index contains `12` sessions and `29` traces:

- `11` hypothesis calls;
- `12` tool-selection calls;
- `6` code calls;
- all recorded traces use `gpt-5.5`;
- no trace-level error type was recorded;
- no auth/API failure appears in the failure taxonomy or run status.

The proposal trajectory manifest loaded all `29` prompt manifests and joined all
`6` formal candidate code sessions by branch-code sequence. It is report-only:
raw prompts, raw responses, patch bodies, and `DecisionFeatures` are excluded;
campaign, scheduler, and promotion state are not mutated.

Prompt/source visibility was interpretable:

- all `29` prompt manifests reported zero truncated sections and zero omitted
  sections;
- hypothesis manifests used compact measurement diagnostics, not a standalone
  measurement block;
- representative hypothesis prompts showed substantial research signal plus
  branch lessons, branch history, cross-branch map, objective feedback, runtime
  feedback, and same-mechanism constraints;
- code-phase manifests for existing `operators/move_order.py` edits recorded
  full current source visible in the rendered prompt with literal source digest;
- the create-new `operators/consolidate_subcategory.py` code prompt correctly
  used create-mode target visibility rather than pretending prior source
  existed.

Representative trace inspection showed the final hypothesis explicitly
responded to branch evidence: it preserved the `fill_slack_order_move`
mechanism, added assignment synchronization, and added an exact split-count
certification guard to address marginal wins with losses/ties. The paired code
trace used `operators/move_order.py` source digest
`cc1dfb941de47b0e14134f8b9133aedf10d69da234a45fdf6f852ad3f4654969` and
submitted typed exact replacements. This is an interpretable proposal-layer
repair behavior path, even though screening evidence stayed insufficient.

## Acceptance Decision

Accept the `d666311` repair as field-proven for the targeted blocker slice:

- branch-lesson usage repair worked in the field;
- unsafe operator-edit failure mode did not recur;
- existing operator modifications passed contract and verification;
- candidate artifact indexing and replay identity remained healthy;
- same-branch follow-up was concrete and same-mechanism constrained;
- v3 boundaries remained intact.

Do not accept it as warehouse efficacy evidence:

- no validation row;
- no frozen row;
- no promotion;
- all decisions were `continue_explore` after screening fail;
- aggregate pair/case evidence is below promotion quality;
- runtime evidence remained partly low-confidence and should remain advisory.

## Commands And Checks Run

- Read required architecture/task/experiment docs:
  `sed -n` over `scion/design/scion-architecture-v3.md`, `scion/TASK.md`,
  `v04-warehouse-research-loop-repair-short-6r-postrun-20260616.md`, and
  `v04-warehouse-research-loop-repair-rerun6r-launch-20260616.md`.
- Monitored WSL:
  `ssh -i /home/clawd/.ssh/id_ed25519_codex_wsl -p 2222 ... tmux has-session`
  and repeated `status.json`/`status.txt` polling.
- Synced final artifacts:
  `rsync -a --delete -e 'ssh -i /home/clawd/.ssh/id_ed25519_codex_wsl -p 2222 ...'`.
- Audited final run files:
  `status.txt`, `campaign/run_status.json`, `campaign/status.json`,
  `campaign/campaign_summary.json`, `postrun_acceptance/*`,
  `artifacts/formal_candidates/index.jsonl`, candidate patch artifacts,
  `agentic_sessions/agentic_session_trace_index.json`, prompt manifests, LLM
  traces, and `scion.db`.
- Queried SQLite `experiment_events`, `hypotheses`, `branches`, and
  `champions`.
- Checked the report target did not already exist and verified no forbidden
  status files were modified.

## Residual Risks

- Screening-only evidence cannot distinguish plateau from a mechanism that
  needs more budget or a stronger validation path.
- The final marginal `fill_slack_order_move` branch has positive cases but no
  median lift; it may be overfitting narrow screening cases.
- Candidate complexity increased in `move_order.py`; no heavy verification
  failure appeared, but longer-run maintainability remains a risk.
- The trajectory manifest still has hypothesis-only sessions without formal
  candidate joins, expected for non-code sessions, but direct causal
  prompt-to-candidate linkage remains stronger for code sessions than for all
  proposal deliberation.
- This run had only one 6R cell. It proves the targeted blocker repair in a
  short field gate, not repeatability across seeds/repeats.
