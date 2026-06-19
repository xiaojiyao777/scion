# v0.4 Code-Phase Source Slot-Reserve Repair

Date: 2026-06-19

## Purpose

Code-phase source visibility must be a prerequisite for patch generation. The
fallback code-context loop already knew which target and surface reads were
mandatory, but the final-preview slot reserve could still skip the next fallback
tool before checking whether it was a required target/source read.

## Change

- Required code-phase target file reads and required selected-surface reads now
  bypass the final-preview slot-reserve skip when at least one hard tool call and
  one hard tool step remain.
- Optional fallback reads still yield to final-preview slot reservation.
- Hard tool-loop limits, session timeout, and observation-budget exhaustion
  remain hard stops.

No Decision, lifecycle, promotion, scheduler, protocol, or problem-specific
solver semantics changed.

## Verification

Focused regression:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/unit/test_agentic_session_tool_selection.py::test_code_phase_required_target_source_read_survives_preview_slot_reserve
```

Local result: `1 passed in 0.61s`.

Adjacent source/tool-planner sweep:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/unit/test_agentic_session_tool_selection.py \
  scion/scion/tests/unit/test_agentic_session_model_planner.py
```

Local result: `36 passed in 41.96s`.

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/unit/test_agentic_target_file_grounding.py
```

Local result: `35 passed in 8.77s`.

Syntax check:

```bash
PYTHONPATH=scion python -m py_compile \
  scion/scion/proposal/agentic_session_code_tools.py
```

Local result: passed.

## Acceptance

Accepted as a source-visibility protection repair. Code-phase mandatory source
context is no longer treated as optional self-check budget material at the
final-preview slot boundary.
