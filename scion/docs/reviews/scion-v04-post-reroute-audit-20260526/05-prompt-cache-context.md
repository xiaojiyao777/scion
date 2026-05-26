# Prompt, Cache, and Context Visibility

Audit question: does the API-visible prompt contain what the agent is assumed to have read, avoid meaningless bloat, and support long-cycle runs?

## Positive Findings

The most important old prompt/context bug is addressed for code-stage modified files.

- Prompt manifests are based on rendered system blocks and user prompt, not raw prompt context: `scion/scion/proposal/prompt_manifest.py:1-6` and `scion/scion/proposal/prompt_manifest.py:41-59`.
- The code file visibility ledger records whether full target/integration source is visible in the rendered prompt: `scion/scion/proposal/prompt_manifest.py:206-272`.
- Visibility records require the exact content to appear in the provider prompt and the section to be included: `scion/scion/proposal/prompt_manifest.py:275-302`.
- Code-stage integration edits fail and retry if modified integration files are not fully visible: `scion/scion/proposal/agentic_session_patch_flow.py:911-958`.
- Tests cover required full integration source and target/integration prompt visibility: `scion/scion/tests/unit/test_agentic_code_stage_invariants.py:183-242` and `scion/scion/tests/unit/test_agentic_target_file_grounding.py:488-530`.

Cache splitting also follows the right control principle: stable active facts and source projections can be cacheable, while observations/retry feedback stay dynamic.

- Hypothesis cache split: `scion/scion/proposal/engine/hypothesis_prompts.py:215-244`.
- Tool-selection cache split: `scion/scion/proposal/engine/tool_selection.py:100-123`.

## Finding PC-1: large source/context caps should be observed during live runs

Severity: P2.

The framework gives top models substantial context, which is appropriate for v0.4 research. The risk is live-run cost/noise, not a static correctness failure.

- Full algorithm reads can project very large sections: `scion/scion/proposal/engine/prompt_common.py:23-27`.
- Bounded JSON and section limit helpers visibly mark truncation: `scion/scion/proposal/engine/prompt_common.py:249-295`.
- Full algorithm read projections require non-truncated full payloads before treating them as full source: `scion/scion/proposal/engine/prompt_common.py:1670-1731`.

Suggested operational check before long runs: sample prompt manifests from the first 2-3 live attempts and verify `truncated_sections`, `code_file_visibility_ledger`, cacheability, and repeated large section counts.

## Finding PC-2: solver-design prompts remain surface-specific

Severity: P2 for current CVRP, P1 before broader problem-generic claims.

The generic proposal engine still has solver-design-specific prompt sections and grounding text. This is acceptable as a v0.4 CVRP solver-design framework, but not as a fully generic research-surface framework. The right end state is provider-declared prompt guidance plus generic cache/rendering controls.

