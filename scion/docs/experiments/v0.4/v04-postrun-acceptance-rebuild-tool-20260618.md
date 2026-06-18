# V0.4 Postrun Acceptance Rebuild Tool

Date: 2026-06-18

## Purpose

Historical v0.4 run roots were produced across several postrun-report schema
iterations. Some accepted roots have `summaries`, `failures`, and
`research_efficiency` reports but no current-format `analysis_brief` or
`inventory`; older `research_efficiency` files can also lack the current
effect-vs-MDE, research-shape, and branch-lesson projections.

This repair adds a single report-only rebuild entry point:

```bash
PYTHONPATH=scion python scion/tools/rebuild_postrun_acceptance.py RUN_ROOT
```

The tool rebuilds the standard postrun acceptance bundle and writes
`postrun_acceptance/rebuild/rebuild_manifest.v1.json` with per-family success
or failure. This gives the main thread and delegated postrun analysis workers a
stable handoff artifact without treating missing evidence as complete evidence.

## Boundary Check

- This is postrun reporting infrastructure only.
- It does not launch campaigns, replay candidates, call LLMs, mutate campaign
  state, alter Protocol/Decision/lifecycle policy, or write
  `DecisionFeatures`.
- Rebuilt reports are explicitly `report_only` and
  `decision_features_excluded`.

## Changed Behavior

`scion/tools/rebuild_postrun_acceptance.py` can rebuild:

- `postrun_acceptance/summaries/*.summary.json`
- `postrun_acceptance/failures/*.failures.json`
- `postrun_acceptance/research_efficiency/*.research_efficiency.v1.json`
- `postrun_acceptance/manifests/*.proposal_trajectory_manifest.v1.json`
- `postrun_acceptance/analysis_brief/*.postrun_analysis_brief.*`
- `postrun_acceptance/inventory/*.postrun_artifact_inventory.*`
- `postrun_acceptance/rebuild/rebuild_manifest.v1.json`

The rebuild manifest records the run root, campaign dir, report stem,
observed-control arm, optional control-pair key, prepared-only lifecycle status,
and each family result. In default mode it is best-effort and
machine-auditable; with `--strict`, it exits non-zero if any family fails.

Prepared-only roots are protected: the tool rebuilds only the analysis brief,
inventory, and rebuild manifest, while marking current-run postrun families as
`skipped`. This prevents copied resume campaign artifacts from being promoted
back into current-run research evidence.

## Smoke Evidence

The accepted warehouse validation-transfer root was rebuilt locally:

```bash
PYTHONPATH=scion python scion/tools/rebuild_postrun_acceptance.py \
  /home/clawd/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z/rep01/full_context \
  --report-stem rep01_full_context_rebuilt \
  --observed-control-arm on \
  --control-pair-key warehouse.validation-transfer-contract:rep01 \
  --strict
```

Result:

- Rebuild manifest `complete=True`.
- All six report families rebuilt with `status=ok`.
- Current `research_efficiency` reports
  `protocol_effects_vs_mde.interpretation=has_positive_protocol_effect_at_or_above_mde`.
- `research_shape.max_branch_depth=9`.
- `cross_branch_observability.branch_lesson_usage_present_count=5`.
- Inventory sees all six postrun report families and exposes Phase 4 coverage;
  `target_intent_trace=False` remains visible for this historical warehouse
  root rather than being hidden.

Prepared-only lifecycle coverage is tested separately: current-run summary,
failure, research-efficiency, and proposal-trajectory reports are skipped, while
analysis brief and inventory still mark `prepared_only=True` and zero
current-run effective rounds.

## Verification

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py
python -m py_compile \
  scion/tools/rebuild_postrun_acceptance.py \
  scion/tools/postrun_artifact_inventory.py \
  scion/tools/postrun_analysis_brief.py
git diff --check
```

Result:

- `8 passed`
- `py_compile` passed
- `git diff --check` passed
