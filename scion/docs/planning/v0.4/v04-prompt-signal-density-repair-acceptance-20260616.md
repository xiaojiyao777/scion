# v0.4 Prompt Signal-Density Repair Acceptance - 2026-06-16

## Boundary

This repair is a v0.4 closeout blocker for the proposal prompt/rendering layer.
It must preserve the v3 boundary:

- LLM prompt/context remains tainted proposal material.
- Full artifacts may retain raw branch lessons, audit payloads, prompt
  manifests, and replay evidence.
- `DecisionFeatures`, Protocol, scheduler, promotion, and abandonment semantics
  must not consume prompt signal-density fields.

The repair must not compress or hide champion/source code needed for code-stage
grounding. The target is research-signal rendering, not solver source
visibility.

Current research-stage policy: do not impose hard character budgets, fixed item
caps, or synthetic truncation markers on useful projected research context.
The model context window is sufficient for the current debugging phase. The
right operation is to remove irrelevant noise and raw compliance/audit payloads,
while preserving the complete structured signal that remains. Any future
budgeting/truncation policy should be an explicit configurable governance or
ablation experiment, not the default research-stage renderer.

## Trigger Evidence

The warehouse `3 x 24R` longrun branch audits found provider-visible truncation
in critical hypothesis sections:

- `compact_research_signals`
- `branch_lesson_usage_context`

Manual trace inspection confirmed the root cause is Scion-side rendering:
`_bounded_json` inserted `<truncated agentic context>` into critical research
sections, and prompt manifests correctly reported those sections as truncated.
This is not a provider-window artifact and should not be hidden by changing
manifest accounting.

This violates the 6/11 audit and evidence-uplift roadmap direction:

- cross-branch lessons should be mechanism-level high-density signals;
- `required_response` compliance templates should move to schema/quality
  checks, not be repeated in prompt input;
- raw telemetry, audit payloads, and full branch records should remain
  artifacts, not dominate proposal context;
- v0.4 must complete this before v0.5 value experiments.

## Required Behavior

### Cross-Branch Research Map

Provider-visible rendering must be a structured mechanism-level map:

- lesson/signature id;
- target/action/mechanism linkage when available;
- guidance or summary;
- maturity/evidence strength;
- compact outcome/evidence counts.

Provider-visible rendering must not include:

- raw audit records;
- raw pair rows;
- session metadata;
- full portfolio steering objects;
- repeated `required_response` compliance templates for every lesson.

### Branch Lesson Usage Context

Provider-visible rendering must preserve enough information for the model to
emit valid `branch_lesson_usage`:

- compact lesson ids;
- candidate/required ids and `required_for`;
- target_file/action/mechanism or mechanism_family linkage;
- maturity;
- compact evidence/outcome summary;
- generic contrast dimensions.

The generic rule requiring `branch_lesson_usage` may appear once in the task or
prompt schema guidance. It must not be repeated as a large per-lesson
`required_response` object.

### Compact Research Signals

This section should be an index over the dedicated signal sections, not a sink
for raw cross-branch, measurement, or runtime payloads. It may point to
dedicated sections, but it must not use `_bounded_json`, character caps, list
caps, ellipses, or truncation markers that hide useful projected research
signal.

## Acceptance Tests

Add or update focused tests, preferably in
`scion/scion/tests/unit/test_hypothesis_context_profiles.py`.

The required stress test must construct 12+ verbose branch-lesson records and a
large cross-branch payload containing:

- oversized `required_response`;
- `reason_codes`;
- `raw_text`;
- `raw_rows`;
- `full_audit`;
- session/audit metadata;
- portfolio-style payloads.

Run:

`filter_hypothesis_context_for_prompt()` -> `_split_hypothesis_context()` ->
`build_api_visible_prompt_manifest()`.

Assertions:

- rendered prompt does not contain `<truncated agentic context>`, synthetic
  ellipses, or field-level truncation markers;
- `compact_research_signals`, `branch_lesson_usage_context`, and
  `cross_branch_research_map`, when present, are not `truncated`;
- prompt does not contain raw text, raw rows, full audit, session metadata, or
  repeated per-lesson `required_response` templates;
- prompt still contains lesson ids, maturity, target/action/mechanism linkage,
  evidence/outcome summary, and the `branch_lesson_usage` output requirement;
- prompt still contains all projected lesson ids from the stress fixture,
  including later records that would be hidden by fixed list caps;
- champion/current source code remains visible;
- context metadata remains excluded from `DecisionFeatures`.

Focused command:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
pytest -q \
  scion/scion/tests/unit/test_hypothesis_context_profiles.py \
  scion/scion/tests/test_proposal_validation.py \
  scion/scion/tests/unit/core/test_branch_lesson_usage.py
```

Also run:

```bash
git diff --check
```

## Status

Implemented by worker `Lovelace`
(`019ed10e-aa46-7e02-bcdc-71d5d05383b4`) and accepted by the main session.
Follow-up no-hard-truncation correction implemented by worker `Kant`
(`019ed11a-7885-7b40-840f-20ba66678ee9`) in commit `fd185cf`
(`fix: remove prompt research signal hard caps`) and accepted by the main
session.

Verification:

- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/test_hypothesis_context_profiles.py scion/scion/tests/test_proposal_validation.py scion/scion/tests/unit/core/test_branch_lesson_usage.py`
  passed (`79 passed`).
- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/core/test_proposal_pipeline_hypothesis.py scion/scion/tests/unit/core/test_proposal_pipeline_session_controls.py scion/scion/tests/test_proposal_trajectory_artifacts.py`
  passed (`45 passed`).
- Python compile on touched prompt modules passed.
- `git diff --check` passed.
- No-hard-truncation follow-up verification repeated the prompt, validation,
  branch-lesson, proposal pipeline, and artifact tests together with
  `124 passed`, plus Python compile and `git diff --check`.

Remaining field check: the next live warehouse/CVRP campaign should inspect
`api_visible_prompt_manifest_*_hypothesis.json` and `prompt_context.csv` to
confirm `compact_research_signals`, `branch_lesson_usage_context`, and
`cross_branch_research_map` remain included/non-truncated on real traces, and
that useful projected lesson/mechanism/evidence signal is not hidden by
field-level caps or synthetic ellipses.
