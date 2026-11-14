# Gates, Telemetry, Retry, and Edit Protocol

Audit question: are hypothesis/code gates, telemetry activation rules, retry paths, and typed edits both safe and research-capable?

## Positive Findings

Telemetry activation is no longer over-hardening rare or conditional mechanisms.

- Formal telemetry validation does not treat `mechanism_executed_no_improvement`, `effect_attribution_missing`, `activated_no_positive_effect`, `evaluated_no_effect`, `not_evaluated/not_triggered`, or zero/sub-ms runtime diagnostics as hard failures: `scion/scion/core/telemetry_validation.py:323-359`.
- Proposal-time smoke marks non-blocking activation/telemetry/static diagnostics as passed diagnostic status when there is no hard smoke failure: `scion/scion/proposal/tools/previews/algorithm_smoke_feedback.py:143-172`.

The typed edit protocol is now safe on the model-facing final parse path.

- `_parse_patch` sets `reject_legacy_code_content_full_file_modify=True`: `scion/scion/proposal/engine/parsing.py:109-115`.
- No-source existing-file full-file modifies are rejected in tests: `scion/scion/tests/unit/test_code_edit_protocol.py:514-521`.
- Host-internal compatibility requires an explicit flag: `scion/scion/tests/unit/test_code_edit_protocol.py:524-545`.
- Whole-file and near-whole exact replacements are rejected for host-visible existing files: `scion/scion/proposal/edit_protocol/normalization.py:645-665` and `scion/scion/proposal/edit_protocol/normalization.py:693-719`.

## Finding G-1: hardcoded telemetry phase allowlist can mask mechanism identity drift

Severity: P1, same root cause as B-1.

The code-stage identity check subtracts hardcoded phase names from new telemetry ids:

- Hardcoded phase set: `scion/scion/proposal/agentic_session_patch_flow.py:21-30`.
- Subtraction from unexpected telemetry ids: `scion/scion/proposal/agentic_session_patch_flow.py:838-840`.

This is safer than accepting arbitrary telemetry ids, but it is still generic code deciding that `local_search` or `construction` is structural. A candidate can add telemetry under a broad phase name without proving it corresponds to the approved mechanism id.

Suggested fix: make structural telemetry ids provider-declared and include them in the active fact packet/provenance. Generic APS should enforce exact mechanism id unless the selected surface declares a structural phase id.

## Finding G-2: schema preview and final parser strictness can disagree

Severity: P2.

Schema preview normalizes typed edits with preview source context but does not set the same final-parser strict flag:

- Preview normalization: `scion/scion/proposal/tools/previews/schema.py:439-442`.
- Preview source context builder: `scion/scion/proposal/tools/previews/schema.py:446-457`.
- Final strict parse: `scion/scion/proposal/engine/parsing.py:109-115`.

The final path is safe, so this is not an edit safety bypass. The risk is wasted repair loops: a preview can appear shape-valid and then the final parser rejects legacy full-file content.

Suggested fix: pass `reject_legacy_code_content_full_file_modify=True` in schema preview for model-facing patch validation, or label preview results as non-authoritative when source context is incomplete.

