# v0.4 Research Context Actionability Brief Repair

Date: 2026-06-18

## Purpose

R3/R4 delegated analysis already had separate prompt-context visibility and
research-continuity summaries. Reviewers still had to manually join those
sections to decide whether semantic branch-lesson gaps, same-mechanism misses,
or weak-positive transfer misses were caused by missing prompt-visible research
signal.

This repair adds a report-only `research_context_actionability_summary` to the
postrun analysis brief.

## Boundary

- Report-only delegated-analysis input.
- Does not change `DecisionFeatures`, Protocol gates, lifecycle policy,
  scheduler state, promotion, campaign state, or problem semantics.
- Uses prompt block-family accounting and `research_continuity` diagnostics
  already produced by postrun acceptance artifacts.

## Change

`scion/tools/postrun_analysis_brief.py` now joins:

- prompt research/source/cross-branch/governance token counts;
- omitted/truncated prompt-section counts;
- same-mechanism selected/observed follow-up counts;
- branch-lesson satisfied/required/semantic-gap counts;
- semantic failure/block counts;
- weak-positive accepted/observed transfer counts.

The brief emits conservative actionability gaps such as:

- `branch_lesson_semantic_gap_without_cross_branch_prompt_signal`;
- `branch_lesson_semantic_gap_despite_cross_branch_prompt_signal`;
- `same_mechanism_opportunities_without_research_signal_prompt`;
- `weak_positive_transfer_without_research_or_lesson_signal`;
- `research_signal_sections_omitted_or_truncated_during_semantic_gap`;
- `governance_tokens_dominate_during_research_continuity_gap`.

## Verification

Local verification:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py
# 6 passed in 0.21s

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_cli_report_research_efficiency.py
# 23 passed in 1.65s

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion python -m py_compile \
  scion/tools/postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_analysis_brief.py
# clean
```

WSL verification after fast-forwarding the synchronized checkout to `900714e`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_cli_report_research_efficiency.py
# 23 passed in 1.41s

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile \
  scion/tools/postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_analysis_brief.py
# clean
```

## Acceptance

Accepted as an R3/R4 delegated-analysis repair. Future postrun briefs can now
tell reviewers whether research-continuity gaps line up with missing or weak
prompt-visible research/cross-branch signal, without making those diagnostics
part of governance decisions.
