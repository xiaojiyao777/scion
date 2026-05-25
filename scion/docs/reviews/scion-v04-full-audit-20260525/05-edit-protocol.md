# Typed Edit And Diff Protocol

Audit question: has the typed edit/diff protocol landed, and does it avoid full large-file output, full overwrite, and C6/C8/C9/C11 false-kill risks?

## Finding EP-1: exact_replace normalization is implemented

- Severity: OK.
- Evidence: `scion/scion/proposal/engine/parsing.py::_parse_patch` calls `normalize_patch_typed_edits` before `PatchProposalInput`. `scion/scion/proposal/edit_protocol/normalization.py::_apply_exact_replace` validates `source_digest`, unique `old_string`, replacement content, and serializes to canonical `code_content` before Contract.
- V3 judgment: conforms. The model-facing protocol can be small typed edits, while deterministic layers still receive canonical full after-content.
- Suggested fix: keep host-generated compact diff metadata for audit; do not accept model-generated unified diffs until a separate parser is implemented.
- Suggested tests: exact_replace with digest succeeds; stale digest fails; missing old string fails; duplicate old string requires `replace_all`.

## Finding EP-2: markdown wrapper/C6 risk has a regression path

- Severity: OK.
- Evidence: `test_code_edit_protocol.py::test_parse_patch_exact_replace_with_wrapped_target_uses_raw_code` validates that markdown-wrapped target source is parsed back to raw Python before Contract C6 syntax. `normalization._source_files_from_context` parses `target_file_code`, `original_code`, and integration file markdown blocks into source files.
- V3 judgment: conforms. This addresses the previous C6 false-kill class where display wrappers could be hashed or compiled as code.
- Suggested fix: keep display rendering and raw source maps separate in prompt manifests.
- Suggested tests: add the same wrapper regression for integration files and algorithm smoke preview, not only primary target.

## Finding EP-3: repeated same-file exact_replace edits are composed before schema validation

- Severity: OK.
- Evidence: `normalization._normalize_patch_set_changes` applies same-file edit slots against evolving source state and composes them into one canonical change. `test_duplicate_additional_exact_replace_changes_are_composed` and `test_primary_and_additional_same_file_exact_replace_are_composed` cover this behavior.
- V3 judgment: conforms. This avoids old duplicate-path schema loops while keeping deterministic patch normalization.
- Suggested fix: keep composition metadata in `repair_attribution` so audit can recover the original typed edits.
- Suggested tests: non-serializable second edit fails with a typed protocol error; mixed create/delete/modify same-file sequences fail clearly.

## Finding EP-4: existing-file full-file modify rejection still has a no-context escape hatch

- Severity: P1 high.
- Evidence: `normalization._validate_existing_file_full_file_modify` returns immediately when `before is None`. `test_full_file_fallback_remains_compatible` confirms `_parse_patch` still accepts `action=modify` with legacy `code_content` or typed `full_file/content_after` when no source context is provided.
- V3 judgment: partial violation. The live prompt path tries to make source visible, and `agentic_session_patch_flow._code_integration_visibility_issue` repairs missing full integration source for `additional_changes`, but the host parser itself does not enforce "existing modifies must be exact_replace" unless it has source context.
- Suggested fix: split compatibility into two modes. Model-facing `_parse_patch` should reject existing editable modifies with `full_file`/legacy `code_content` unless the path is a create/delete or a host-internal flag explicitly authorizes compatibility. Host-internal canonical `PatchProposal.code_content` remains valid after parsing.
- Suggested tests: direct `_parse_patch` with known editable target and no source rejects full-file modify; APS code generation fails before Contract when any modify path lacks source; create with `full_file` remains allowed.

## Finding EP-5: whole-file and near-whole exact_replace are blocked

- Severity: OK.
- Evidence: `normalization._apply_exact_replace` rejects `old_string == before`; `_validate_exact_replace_granularity` rejects near-whole-file replacements for sufficiently large files.
- V3 judgment: conforms. This prevents the model from using exact_replace as a disguised full-file overwrite.
- Suggested fix: keep thresholds documented in the typed edit reference and make error feedback concise enough for repair.
- Suggested tests: large file 95% replacement fails; small local replacement succeeds; generated error contains digest, file path, and guidance.

## Finding EP-6: C8/C9/C11 false-kill risk is reduced but not eliminated

- Severity: P1 medium.
- Evidence: typed edits are normalized before Contract, so static gates see canonical code. The remaining false-kill risk is not parsing; it is provider ownership and source visibility. Generic C9 still contains a CVRP entrypoint rule, and missing source context can still permit legacy full-file modify.
- V3 judgment: mostly conforms after EP-4/GT-2 are fixed.
- Suggested fix: move provider-specific hard checks out of generic C9, and make source visibility a protocol invariant for all modify paths.
- Suggested tests: regression suite for C6 wrapper, C8 sensitive API, C9 provider wrapper rule, C11 telemetry schema, each using typed exact_replace raw output.

