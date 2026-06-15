# Warehouse Short Debug 4R Guidance Postrun - 2026-06-15

## Boundary

I read `scion/design/scion-architecture-v3.md` first. This report preserves
the v3 boundary by treating LLM outputs, prompt manifests, branch-lesson
usage, cross-branch maps, runtime diagnostics, and proposal transcripts as
proposal/report material only. They can explain search behavior and guide the
next repair, but they are not Decision input. The Decision boundary remains:
Proposal -> Contract -> Verification -> Protocol -> Safe Feature Extractor ->
Decision, with Decision reading deterministic `DecisionFeatures` only.

## Artifacts

- Run root:
  `/home/clawd/research/scion-experiments/v04-warehouse-short-debug-4r-guidance-20260615T205022Z`
- Campaign dir:
  `/home/clawd/research/scion-experiments/v04-warehouse-short-debug-4r-guidance-20260615T205022Z/rep01/on_compact/campaign`
- Launch doc:
  `scion/docs/experiments/v0.4/v04-warehouse-short-debug-4r-guidance-launch-20260615.md`
- Prior 3R postrun:
  `scion/docs/experiments/v0.4/v04-warehouse-short-debug-3r-postrun-20260615.md`
- Wrapper audit:
  `rep01/on_compact/campaign/run_status.json`
- Campaign summary/state:
  `rep01/on_compact/campaign/campaign_summary.json`,
  `rep01/on_compact/campaign/status.json`,
  `rep01/on_compact/campaign/scion.db`
- Postrun acceptance artifacts:
  `postrun_acceptance/summaries/rep01_on_compact.summary.json`,
  `postrun_acceptance/failures/rep01_on_compact.failures.json`,
  `postrun_acceptance/research_efficiency/rep01_on_compact.research_efficiency.v1.json`,
  `postrun_acceptance/manifests/rep01_on_compact.proposal_trajectory_manifest.v1.json`
- Candidate artifacts:
  `rep01/on_compact/campaign/artifacts/formal_candidates/index.jsonl`
- LLM/prompt artifacts:
  `rep01/on_compact/campaign/agentic_sessions/*/output.json`,
  `rep01/on_compact/campaign/agentic_sessions/*/transcript.json`,
  `rep01/on_compact/campaign/agentic_sessions/*/scratch/api_visible_prompt_manifest_*.json`

## Commands Used

Representative read-only commands:

```bash
sed -n '1,520p' scion/design/scion-architecture-v3.md
sed -n '1,260p' scion/docs/experiments/v0.4/v04-warehouse-short-debug-4r-guidance-launch-20260615.md
sed -n '1,320p' scion/docs/experiments/v0.4/v04-warehouse-short-debug-3r-postrun-20260615.md
jq . /home/clawd/research/scion-experiments/v04-warehouse-short-debug-4r-guidance-20260615T205022Z/rep01/on_compact/campaign/run_status.json
jq '{run_validity, accounting_reconciliation, cache_stats, cross_branch_research_observability}' /home/clawd/research/scion-experiments/v04-warehouse-short-debug-4r-guidance-20260615T205022Z/rep01/on_compact/campaign/campaign_summary.json
sqlite3 /home/clawd/research/scion-experiments/v04-warehouse-short-debug-4r-guidance-20260615T205022Z/rep01/on_compact/campaign/scion.db '.tables'
sqlite3 -header -column /home/clawd/research/scion-experiments/v04-warehouse-short-debug-4r-guidance-20260615T205022Z/rep01/on_compact/campaign/scion.db "select ... from hypotheses order by created_at;"
sqlite3 -header -column /home/clawd/research/scion-experiments/v04-warehouse-short-debug-4r-guidance-20260615T205022Z/rep01/on_compact/campaign/scion.db "select ... from experiment_events order by timestamp;"
wc -l /home/clawd/research/scion-experiments/v04-warehouse-short-debug-4r-guidance-20260615T205022Z/rep01/on_compact/campaign/artifacts/formal_candidates/index.jsonl
rg -n "branch_lesson_usage|avoided_lessons|contrasted_lessons|move_order|pack" /home/clawd/research/scion-experiments/v04-warehouse-short-debug-4r-guidance-20260615T205022Z/rep01/on_compact/campaign/agentic_sessions
python - <<'PY'
# small JSON summarizers for per-step metrics, branch_lesson_usage semantics,
# prompt block family shares, and code-stage source visibility guarantees.
PY
```

No solver reruns were executed. The campaign artifacts were only read.

## Key Metrics

| Item | Value |
|---|---:|
| Wrapper exit | `0` |
| Wrapper status | `finished` |
| Run validity | `valid` |
| Started / ended | `2026-06-15T20:51:19Z` / `2026-06-15T21:04:29Z` |
| Requested rounds | `4` |
| Effective rounds completed | `4` |
| Proposal attempts total / consumed | `4` / `4` |
| Verification-consumed candidates | `4` |
| Verification failures | `0` |
| Counted screening Protocol rows | `4` |
| Completed Protocol metric rows | `5` screening rows, including one non-counted fresh-runtime replay |
| Validation / frozen rows | `0` / `0` |
| Formal candidate artifacts | `4` |
| Promotions | `0` |
| Postrun failure count | `0` |
| Agentic sessions / traces | `8` / `21` |
| LLM calls | `hypothesis=7`, `tool_selection=9`, `code=5` |
| LLM tokens | `input=298360`, `output=22818`, `total=321178` |

Caveat: `campaign_summary.run_validity.protocol_metric_results` still reports
`4`, while `status.json`, accounting reconciliation, and the research
efficiency report report `5`. The reconciled interpretation is `4` counted
screening rounds plus `1` non-counted fresh-runtime replay row.

## Attempt Reconciliation

All 4 requested rounds reached Contract, Verification, canary, and screening
Protocol. There were no pre-Protocol failures, no proposal quality blocks, and
no verification-heavy failures.

The apparent `4` requested rounds versus `5` Protocol metric rows is explained
by one non-counted fresh-runtime replay:

- Counted rows: rounds 1-4, all `attempt_kind=screening`,
  `counts_toward_max_rounds=true`.
- Non-counted row: round 5, `attempt_kind=fresh_runtime_replay`,
  `counts_toward_max_rounds=false`, replaying the round-3
  `subcategory_pack_upgrade.py` candidate with fresh runtime evidence.
- Validation and frozen did not occur. No candidate was promoted.

This is better than the prior 3R run on accounting: the 3R run consumed one
requested round with a `V9_perf_guard` Verification failure before Protocol;
this 4R run has no such missing row.

## Candidate Trajectory

| Row | Counted | Branch | Action / target | Mechanism family | Screening evidence | Runtime evidence | Result |
|---:|:---:|---|---|---|---|---|---|
| 1 | yes | `a217ffed` | create `operators/subcategory_pack_upgrade.py` | `subcategory_pack_upgrade` / vehicle-level consolidation | case `3/1/6`, pair `10/6/4`, median delta `100`, CI `[-350,400]` | median ratio `1.044`, high confidence | `continue_explore`, marginal |
| 2 | yes | `a217ffed` | modify `operators/subcategory_pack_upgrade.py` | cost-dominant same mechanism | case `0/0/6`, pair `0/0/12`, median delta `0` | median ratio `1.008`, low cached champion | `continue_explore`, neutral/no-effect |
| 3 | yes | `a217ffed` | modify `operators/subcategory_pack_upgrade.py` | split-first same mechanism repair | case `0/0/6`, pair `0/0/12`, median delta `0` | runtime aggregate excluded, fresh champion required | `continue_explore`, runtime-tie diagnostic |
| 4 | yes | `41a71975` | modify `operators/move_order.py` | `split_neutral_cost_compaction` / order-level compaction | case `1/2/3`, pair `3/5/4`, median delta `0`, CI `[-3050,1650]` | median ratio `0.814`, high confidence | `continue_explore`, marginal |
| 5 | no | `a217ffed` | replay round 3 | same as row 3 | case `0/0/6`, pair `0/0/12`, median delta `0` | median ratio `0.996`, high confidence | branch parked/no-effect exhausted |

Trajectory assessment:

- The first three counted candidates are still low-value nearby variants of
  the same vehicle-level subcategory pack-upgrade idea. They add contrast
  fields, but materially they remain create/modify/refine attempts on the same
  target file and same mechanism.
- The fourth counted candidate is a real clean fork: order-level
  `move_order.py`, split-neutral cost compaction, different target file,
  different intervention surface, and bounded runtime plan.
- Compared with the prior 3R run, the repair did produce material contrast
  eventually and avoided the earlier order-level Verification loss. It did not
  prevent an extra same-branch, no-effect pack-upgrade iteration before the
  clean fork.

## Branch-Lesson Usage

The raw presence counters improved but overstate semantic quality:

- Manifest accounting: `usage_present_count=8`, `usage_missing_count=0`,
  `semantic_projection_present_count=8`.
- Campaign cross-branch observability: `branch_lesson_usage_present_count=4`,
  `branch_lesson_usage_satisfied_count=1`,
  `branch_lesson_usage_present_not_semantic_count=3`,
  `branch_lesson_usage_semantic_mismatch_count=1`,
  `clean_fork_contrast_satisfied_count=1`.

Semantic sampling:

- Round 1 / create `subcategory_pack_upgrade.py`: names a bounded split
  consolidation idea, but its avoided lesson has `old_* = unknown`. This is
  weak as a lesson contrast and mostly establishes a first branch.
- Round 2 / cost-dominant modify: meaningfully preserves the same branch and
  contrasts action/trigger/threshold/runtime budget against the weak-positive
  first row. This is a reasonable same-branch refinement.
- Round 3 / split-first modify: names and contrasts the previous cost-threshold
  failure, but it remains a third same-file/same-mechanism candidate after
  no-effect evidence. It is semantically understandable but not a strong
  diversity response.
- Round 4 / `move_order.py`: meaningfully avoids repeating
  `subcategory_pack_upgrade.py`, explicitly names the old target/mechanism,
  changes target file, locus, mechanism family, effect path, and runtime budget
  strategy, and rejects weak/unknown prior signal as not Decision input. This
  is the best branch-lesson success in the run.

Conclusion: branch lessons are visible and sometimes semantically used, but the
repair has not made semantic satisfaction reliable. The key remaining issue is
not absence of the field; it is that the scheduler/context stack still allows
multiple low-value nearby same-mechanism variants before a clean fork.

## Prompt And Source Visibility

Prompt manifest coverage:

- `21` prompt manifests loaded: `hypothesis=4`,
  `hypothesis_preview_retry=3`, `tool_selection=9`, `code=5`.
- Aggregate prompt-family estimate:
  `general=43.7%`, `tool_selection=27.3%`,
  `research_signal=13.0%`, `tool_observation=8.1%`,
  `governance=4.3%`, `feedback=3.5%`, `source_context=0.1%`.
- All hypothesis and hypothesis-preview manifests still report one truncated
  section: `compact_research_signals`.
- Tool-selection prompts remain dominated by tool-selection scaffolding
  at about `96.8-97.1%` of the prompt-family estimate.
- Code prompts are not truncated, but are dominated by general scaffolding
  at about `76-91%`.

This means compact branch-lesson context moved earlier and was present in the
hypothesis outputs, but branch-lesson truncation / cross-branch map economy /
tool-selection bloat are still real problems. The run quantifies the truncation
rather than clearing it.

Code-stage source visibility is acceptable:

- Code manifests for required modifies show `required_source_satisfied=true`
  and `full_content_visible_in_rendered_prompt=true` for
  `operators/subcategory_pack_upgrade.py` and `operators/move_order.py`.
- Create-new retry manifests mark the target file as not required for full
  current-content visibility, which is acceptable because the file is being
  created.
- There is no evidence that champion/current branch/target source was hidden
  by compression for code generation.

## Runtime And Order-Level Behavior

The repair improved the order-level/runtime failure mode:

- No `V9_perf_guard` occurred.
- The order-level `move_order.py` candidate reached screening.
- Its runtime evidence was favorable: median runtime ratio `0.814`, median
  delta `-126.5 ms`, high confidence.

The objective signal was still weak:

- `move_order.py` produced case `1/2/3`, pair `3/5/4`,
  median delta `0`, CI `[-3050,1650]`.
- It is not promotion evidence and not validation-ready.

Runtime diagnostics still have some warehouse-semantic noise:

- Row 3 emitted `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED` for a no-effect,
  budget-exhausting warehouse candidate.
- A non-counted fresh-runtime replay then confirmed no objective effect and
  parked the lineage.
- This is safer than treating runtime as a standalone optimization signal, but
  it still spends post-budget machinery on a no-effect pack-upgrade path.

For warehouse search, runtime diagnostics should remain audit/proposal-only and
should be less likely to keep no-effect quality candidates alive unless there
is a concrete objective or activation hypothesis being tested.

## Comparison To Prior 3R

Improvements over the prior 3R postrun:

- All requested rounds reached screening; no pre-Protocol failure.
- The prior order-level/swap attempt failed Verification with
  `V9_perf_guard`; this run's order-level `move_order.py` candidate passed
  Verification and screening and was faster on median runtime.
- Clean-fork branch-lesson fields now contain meaningful contrast for the
  order-level candidate.
- Code-stage source visibility remains intact.

Remaining regressions or unresolved issues:

- The run still spends three counted candidates on the same
  `subcategory_pack_upgrade.py` family before leaving it.
- Aggregate family coverage remains narrow: the campaign summary reports
  `family_coverage={"subcategory_consolidation": 5}` even though mechanism IDs
  split into `subcategory_pack_upgrade` and `split_neutral_cost_compaction`.
- Branch-lesson semantic satisfaction is still poor by the campaign's own
  projection counters: `1` satisfied versus `3` present-not-semantic.
- Hypothesis prompt manifests still truncate `compact_research_signals`.
- Tool-selection/general payload still consumes most of the visible prompt.

## Verdict

This run is valid and useful, but it should not pass the repaired warehouse
short debug gate as readiness for a full `3 x 24R` warehouse longrun.

It passes the execution/safety part of the gate:

- wrapper exit `0`;
- `run_validity.status=valid`;
- all 4 requested rounds reached screening;
- no Verification failures;
- no validation, frozen, or promotion occurred;
- the order-level candidate avoided `V9_perf_guard`;
- code-stage target source visibility was preserved.

It fails the research-quality/context part of the gate:

- branch-lesson usage is present but not reliably semantic;
- same-mechanism pack-upgrade variants repeat after low/no-effect evidence;
- hypothesis manifests still truncate compact research signals;
- tool-selection/general prompt bloat remains high;
- runtime-tie/fresh-champion diagnostics still create noise for no-effect,
  budget-exhausting warehouse candidates.

## Recommendation

Do a targeted repair before any full warehouse `3 x 24R` relaunch. The next
warehouse action should not be the full longrun yet.

Repair focus:

1. Make branch-lesson semantic satisfaction enforceable for clean forks and
   for same-branch continuation after no-effect evidence. Presence of
   `branch_lesson_usage` should not be enough.
2. Tighten branch lifecycle so a no-effect same-mechanism branch does not spend
   another counted candidate unless the new proposal changes the causal path in
   a measurable way.
3. Reduce hypothesis/tool-selection prompt overhead so compact research signals
   and branch lessons are not truncated.
4. Demote fresh-champion/runtime-tie followups for warehouse no-effect budget
   exhaustion unless there is objective or activation evidence that the replay
   can answer.
5. Keep the order-level bounded runtime guidance; it appears to have fixed the
   `V9_perf_guard` class for this short run.

After that targeted repair, run another short compact debug, preferably `4-6R`.
Acceptance for that run should require: all requested rounds reconciled, no
pre-Protocol failures, no `compact_research_signals` truncation in hypothesis
contexts, at least one clean-fork candidate with semantic lesson satisfaction,
and no more than one extra same-mechanism no-effect followup before parking or
forking.
