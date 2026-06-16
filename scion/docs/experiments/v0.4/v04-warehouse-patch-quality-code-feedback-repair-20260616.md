# Warehouse Patch-Quality Code Feedback Repair

*Date: 2026-06-16*
*Branch: `codex/v04-evidence-repair-plan`*
*Status: locally accepted; field rerun required*

## Context

The clean warehouse patch-quality rerun from commit `6e13b11` completed at:

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-validation-transfer-patch-quality-rerun6r-6e13b11-20260616T203530Z`
- Server sync:
  `/home/clawd/research/scion-experiments/v04-warehouse-validation-transfer-patch-quality-rerun6r-6e13b11-20260616T203530Z`

The run validated the prior session-ref repair, but it failed research-quality
acceptance. It finished `6/6` effective screening rows with wrapper exit `0`,
`0` validation/frozen/promotions, and `6` proposal quality blocks. Four blocks
repeated `warehouse_validation_transfer_patch_quality_missing`, usually for
missing activation/effect diagnostic code and later also missing
screening/lexicographic guard.

Direct manifest inspection found that code prompts did not contain
`agentic_prior_quality_blocks` or the previous
`warehouse_validation_transfer_patch_quality_missing` text. The framework had
recorded the quality block, but the next code-generation call did not receive
that feedback.

## Repair

The repair keeps the v3 boundary intact:

- Prior agentic quality blocks remain tainted proposal context.
- A successful hypothesis now stages current branch quality feedback for the
  immediately following code phase instead of dropping it.
- Code context now receives staged prior quality blocks, a code-specific hard
  repair rule, and the existing negative-fact projection.
- Code prompts render those prior quality blocks in a dynamic user-prompt
  section named `Prior Agent Quality Blocks For This Code Patch`.
- The staged code feedback is cleared after code succeeds, and stale staged
  feedback is cleared when a later hypothesis has no current quality feedback.
- Quality-block ledgers now preserve compact session/ref fields when available:
  `session_id`, `session_status`, `termination_reason`,
  `agent_block_reason`, `failure_code`, `quality_gate_name`, and
  `retry_constraint`.

No `DecisionFeatures`, Protocol thresholds, validation/frozen gates, or
warehouse problem-owned quality semantics changed.

## Local Acceptance

Commands:

```bash
PYTHONPATH=scion python -m pytest scion/scion/tests/unit/core/test_proposal_pipeline_quality_blocks.py -q
PYTHONPATH=scion python -m pytest scion/scion/tests/unit/core/test_proposal_pipeline_*.py -q
PYTHONPATH=scion python -m pytest scion/scion/tests/unit/test_agentic_feedback_exposure.py scion/scion/tests/unit/test_warehouse_target_preview.py -q
PYTHONPATH=scion python -m pytest scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py -q
python -m py_compile scion/scion/core/proposal_pipeline/agentic_lifecycle.py scion/scion/core/proposal_pipeline/facade.py scion/scion/core/proposal_pipeline/agentic_requests.py scion/scion/proposal/engine/code_prompts.py scion/scion/core/evidence_recording/accounting_quality_blocks.py scion/scion/core/campaign_loop.py
git diff --check
```

Results:

- Proposal quality-block tests: `21 passed`.
- Proposal pipeline tests: `77 passed`.
- Agentic feedback plus warehouse target preview tests: `23 passed`.
- Evidence status tests: `53 passed`.
- `py_compile`: passed.
- `git diff --check`: passed.

## Next Gate

Run a fresh short warehouse production rerun from the new commit. Accept the
repair only if one of these is true:

- repeated patch-quality omissions stop; or
- the code prompt manifests prove that prior quality-block feedback was visible
  and the remaining failure is a genuine research/adapter limitation rather
  than another feedback propagation break.
