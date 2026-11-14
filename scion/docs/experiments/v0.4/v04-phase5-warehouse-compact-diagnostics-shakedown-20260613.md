# v0.4 Phase 5 Warehouse Compact Diagnostics Shakedown

*Date: 2026-06-13*
*Run root: `/home/clawd/research/scion-experiments/v04-phase5-warehouse-compact-diagnostics-shakedown-3arms-2r-20260613T084629Z-claw`*
*Launch commit: `5159249fc5312e14035ef1b1c0cf8be06765e992`*
*Accounting repair commit: `3835670`*

## Purpose

This was a prompt/manifest shakedown, not a governance-value experiment. It
checked whether the new `compact-measurement-diagnostics` proposal context mode
removes the standalone measurement diagnostics block while keeping branch,
cross-branch, research-memory, and source-visibility context available.

All arms kept `measurement_governance=on`; only proposal-visible context
changed. The launch file explicitly records
`purpose=prompt_manifest_shakedown_not_governance_value_conclusion`.

## Configuration

- Problem: `scion/problems/warehouse_delivery/problem.yaml`
- Protocol: `scion/problems/warehouse_delivery/protocol_prod.yaml`
- Split: `scion/problems/warehouse_delivery/split_manifest_prod.yaml`
- Seeds: `scion/problems/warehouse_delivery/seed_ledger.yaml`
- Model: local `gpt-5.5` proxy at `http://127.0.0.1:8080`
- Repeats: `1`
- Rounds per arm: `2`
- Solver cap: uniform `30s`
- Agentic proposal timeout: `600s`
- Early stop: disabled
- Arms, in order: `full`, `compact-measurement-diagnostics`,
  `no-measurement-diagnostics`
- Report-only control key: `warehouse.compactdiag-shakedown:rep01`

`cell_status.tsv` shows all three cells exited `0`.

## Results

| arm | experiments | decisions | promotions | case W/L/T | pair W/L/T | sessions/traces/candidates | joined after fix | hypothesis manifests | token estimate |
| --- | ---: | --- | ---: | --- | --- | --- | ---: | ---: | ---: |
| `full` | 2 | `continue_explore=2` | 0 | `2/2/12` | `7/7/18` | `4/12/2` | 2 | 3 | 138829 |
| `compact-measurement-diagnostics` | 2 | `abandon=2` | 0 | `3/4/9` | `11/14/7` | `4/12/4` | 2 | 4 | 133453 |
| `no-measurement-diagnostics` | 2 | `continue_explore=2` | 0 | `2/2/12` | `7/7/18` | `4/15/2` | 2 | 4 | 171391 |

There were no run failures: all three `*.failures.json` files report
`total_failures=0`.

Do not interpret the outcome counts as a causal result. This was one repeat and
two rounds per arm, and LLM/tool-selection trajectories diverged.

## Prompt Visibility

Hypothesis prompt manifests matched the intended visibility contract.

- `full`: all 3 hypothesis manifests have
  `measurement_diagnostics_visibility="full"` and include a standalone
  `problem_measurement_diagnostics` section.
- `compact-measurement-diagnostics`: all 4 hypothesis manifests have
  `measurement_diagnostics_visibility="compact"`,
  `measurement_diagnostics_standalone_section=false`, no standalone
  `problem_measurement_diagnostics` section, and a bounded
  `compact_research_signals` section with
  `compact_problem_measurement_diagnostics`.
- `no-measurement-diagnostics`: all 4 hypothesis manifests have
  `measurement_diagnostics_visibility="suppressed"`, no
  `problem_measurement_diagnostics`, and no
  `compact_problem_measurement_diagnostics` string in the arm artifacts.

Compact preserved the broader research context in every sampled hypothesis
manifest: `cross_branch_research_map`, `branch_lesson_usage_context`,
`experiment_history_this_branch`, `sibling_branches`,
`agentic_proposal_tool_observations`, and champion research code were still
present. This is the key difference from `minimal-research-context`, which
removed too much research memory in the earlier ablation.

## Boundary Checks

Postrun report artifacts are report-only and non-mutating:

- `comparison_is_decision_input=false`
- `campaign_state_mutated=false`
- `scheduler_state_mutated=false`
- `promotion_state_mutated=false`
- `raw_prompt_excluded=true`
- `raw_response_excluded=true`
- `patch_body_excluded=true`
- `decision_features_excluded=true`

Leakage scan found no raw prompt/response body, `code_content`, BKS/gap detail,
or raw A/A rows in `postrun_acceptance`. The only `raw_prompt` and
`raw_response` hits are exclusion flags.

All three pairwise compares under
`postrun_acceptance_rebuilt_after_joinfix/compares` have matched
`control_pair_key=warehouse.compactdiag-shakedown:rep01`,
`observational_only=false`, and `llm_deterministic_replay=false` with
`control_pair_key_matched_not_deterministic_llm_replay`.

## Findings Fixed After The Run

The shakedown found two manifest/accounting issues. Both are fixed in
`3835670 fix: repair proposal manifest accounting`.

1. Proposal trajectory join did not handle activation-complete duplicate formal
   candidate rows. The original compact manifest had
   `formal_candidate_count=4` but `formal_candidate_joined_session_count=0`.
   Rebuilding report-only manifests after the fix gives
   `formal_candidate_joined_session_count=2`, leaving only the two
   hypothesis-only sessions missing. The joined candidates are the
   activation-complete rows containing `registry.yaml`.
2. Code-phase source visibility accounting treated create-new placeholders as
   missing existing source when the code prompt context omitted `action` but
   did include `target_file_exists=false` and `source_status=new_file`. The fix
   infers create-new mode from explicit file absence or `new_file` source
   status when action is absent. Existing prompt manifests from this run remain
   historical artifacts; future manifests use the repaired accounting path.

Acceptance for the repair:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_proposal_trajectory_artifacts.py \
  scion/scion/tests/test_cli_reports_postmortem.py \
  scion/scion/tests/unit/test_agentic_target_file_grounding.py \
  scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py
# 84 passed

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion python -m py_compile \
  scion/scion/core/proposal_trajectory_artifacts.py \
  scion/scion/proposal/prompt_manifest_source_visibility.py

git diff --check
```

## Interpretation

This shakedown accepts `compact-measurement-diagnostics` as a viable prompt
surface: it removes the large standalone diagnostics block without suppressing
branch/cross-branch research memory. It also confirms that
`no-measurement-diagnostics` suppresses prompt-visible measurement diagnostics.

It does not prove governance value. The next formal Phase 5 experiment should
use more repeats and stronger pairing, with `compact-measurement-diagnostics`
as the main candidate prompt baseline against `full` and/or
`no-measurement-diagnostics`. Pull-based on-demand diagnostics remain deferred
unless a longer compact run shows that agents need explicit access to detailed
measurement facts.
