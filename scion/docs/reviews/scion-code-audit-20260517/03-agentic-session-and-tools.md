# 03 - Agentic Session And Tools

## Reviewed Areas

- Planner/code-phase tool allowlists.
- Required context reads.
- Two-phase hypothesis and code generation.
- Repair loop and algorithm smoke loop.
- Observation budgets and transcript/artifact auditability.

APS artifacts in both inspected experiments had `schema_version: agentic-proposal-session.v1`, `tainted: true`, `tool_budget_used`, `tool_loop_config`, and transcript digests in `agentic_session_index.json`. This is good audit scaffolding. The main issues are stale code provenance and fail-open budget behavior.

## Findings

### F-03 - `context.read_surface` returns champion code in branch code phase

- Severity: High
- Files:
  - `scion/scion/proposal/tools.py:795`
  - `scion/scion/proposal/tools.py:804`
  - `scion/scion/proposal/tools.py:3336`
  - `scion/scion/proposal/tools.py:3459`
  - `scion/scion/core/proposal_pipeline.py:513`
- Problem: The non-tool code context is built through `problem_runtime.build_code_context(..., branch_workspace=...)`, but the APS surface-read tool has only `context.champion` and reads `_read_champion_file`. In solver-design mode it also reads support artifacts from the champion root.
- Trigger path: The code phase requires or falls back to `context.read_surface(detail="full")`. On a branch with existing solver-design changes, the LLM receives branch target code from `target_file_code` but champion code from the tool observation. It may prefer the more recent tool observation and generate stale or destructive edits.
- Impact: Repair loops and multi-module algorithm work can regress to champion APIs. This is especially risky for `policies/baseline_modules/*.py`, where the branch-owned modules are the research object and support module APIs are part of the algorithm.
- Suggested fix: Extend `ProposalToolContext` with `branch_workspace` or a read-only branch snapshot root. Return branch code by default during code phase. If champion reference code is included, label it as reference and keep it separate from current artifact.

### F-07 - Code phase can proceed after skipping the full surface read

- Severity: Medium
- Files:
  - `scion/scion/proposal/agentic_session.py:660`
  - `scion/scion/proposal/agentic_session.py:2036`
  - `scion/scion/proposal/agentic_session.py:2047`
  - `scion/scion/proposal/agentic_session.py:2059`
- Problem: `_run_code_context_fixed_tools` adds `context.read_surface(detail="full")` when no code-phase surface read exists, but it can skip that fallback when `_code_phase_budget_reserved(state)` is true. The session then proceeds to `_generate_code_with_timeout_retry`.
- Trigger path: A session spends enough observation budget during planning/feedback that the code-phase fallback is skipped to reserve self-check budget. There is no final hard failure for "no full selected surface read".
- Impact: Code generation can run with partial or stale context. For solver-design, this increases the odds of missing imports, wrong helper signatures, and shallow patches that repair loops could have avoided.
- Suggested fix: Treat the full selected-surface read as mandatory for code generation. Reserve its budget up front, or fail the APS session with a bounded repairable error if it cannot be read. Preserve self-check budget after the mandatory read rather than before it.

### F-11 - Active boundary surfaces do not filter feedback tools unless `forced_surface` is set

- Severity: Medium
- Files:
  - `scion/scion/proposal/agentic_session.py:3736`
  - `scion/scion/proposal/tools.py:945`
  - `scion/scion/proposal/tools.py:1070`
- Problem: `_feedback_query_args` only adds a surface filter when `context.forced_surface` is present. It ignores `context.active_problem_boundary_surfaces`.
- Trigger path: A v0.4 campaign may constrain active problem-boundary surfaces to `solver_design` without using a forced surface. APS feedback queries can then include screening/runtime feedback from component-policy or operator surfaces.
- Impact: This does not leak holdout data because the feedback tools use safe screening/history summaries, but it can steer a solver-design candidate back toward component-policy failures and post-baseline tweaks instead of the intended branch-owned algorithm subject.
- Suggested fix: If exactly one active problem-boundary surface is configured, default feedback queries to that surface. For multiple active boundary surfaces, include explicit surface labels and rank same-boundary feedback first.

### F-12 - Transcript audit is compact but not self-contained

- Severity: Low
- Files:
  - `scion/scion/proposal/agentic_session.py:3275`
  - `scion/scion/proposal/tools.py:724`
  - inspected experiment artifact: `/home/clawd/research/scion-experiments/v04-api-manifest-sonnet-3r-20260517T034512Z/campaign/agentic_sessions/0748a85c-220a-4145-9e7a-93dd64941200/transcript.json`
- Problem: Compact transcripts record tool names, status, step IDs, evidence refs, and summaries, but not the full structured observation bodies inline.
- Trigger path: Post-hoc analysis must join transcript events to output artifacts or other evidence stores to reconstruct exact prompt-visible observations.
- Impact: This is acceptable for storage, but it raises audit friction. It also makes provenance bugs like F-03 harder to diagnose because the transcript alone only says `context.read_surface` succeeded.
- Suggested fix: Add a bounded `observation_digest`, source provenance, and a small normalized payload summary for code-bearing observations. Keep large bodies offloaded but make branch/champion provenance visible in the compact transcript.

## Positive Evidence

- APS sessions persist `tainted: true` in session index and transcript metadata.
- `proposal.algorithm_smoke` is excluded from planner-selected model-facing tools and used in controlled preview/repair paths.
- Recent sessions recorded tool budgets and repeated-call/loop control metadata.

