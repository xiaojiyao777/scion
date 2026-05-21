# Branch Lifecycle And Experiments

v3 baseline: a branch represents one research direction. Non-degenerate, weak, or diagnostically incomplete evidence should not be collapsed into ordinary win-rate failure. Experiment status must distinguish proposal attempts, effective screened rounds, diagnostic repair loops, and interrupted in-flight attempts.

## Alignment - Low-Signal Branch Lifecycle Is No Longer Simple Win-Rate Failure

Evidence:
- `scion/scion/core/branch_lifecycle_policy.py:50-114` keeps low-win screening branches exploring when appropriate, excludes telemetry-repairable failures from ordinary low-win handling, and uses stable reason codes.
- `scion/scion/core/branch_lifecycle_policy.py:116-140` soft-abandons only when there is concrete negative evidence: losses without wins, candidate runtime failures, negative median delta, slowdown, or high runtime regression rate.
- `scion/scion/core/evaluation_orchestrator.py:165-199` applies lifecycle policy after Decision returns `CONTINUE_EXPLORE`.
- `scion/scion/core/decision_finalizer.py:470-500` preserves low-signal screening workspaces only when the screening experiment was effective and not negative/regressive.

Assessment:
- This is aligned with v3's "continue non-degenerate directions" intent.
- It specifically avoids treating diagnostic telemetry repair as ordinary low-win failure.

Suggested regression tests:
- Branch with all ties, no candidate failed pairs, and no slowdown stays explorable until the zero-win budget is exhausted.
- Branch with activation-missing telemetry is not soft-abandoned by the low-win lifecycle policy.
- Branch with negative median delta or candidate runtime failures is soft-abandoned.

## Finding LIFECYCLE-P2-1 - `proposal_attempts` / `total_rounds` Count Started Attempts, Not Completed Attempts

Severity: P2

Type: experiment/ops problem.

Evidence:
- `scion/scion/core/explore_step_pipeline.py:261-270` increments the round number before the step completes for non-retry attempts.
- `scion/scion/core/campaign.py:290-292` reports both `total_rounds` and `proposal_attempts` as `_round_num`, while `n_steps` is `len(_step_history)`.
- `scion/scion/core/campaign_loop.py:141-153` later classifies completed `StepResult` attempts, but an interrupted in-flight attempt has no completed result.

Why this matters for v3:
- Recent stopped-run analysis reported `proposal_attempts=7` while only two attempts reached effective screening and the last was interrupted by SIGTERM.
- The current fields are not wrong as "attempts started", but their names invite interpretation as completed proposal attempts or effective rounds.

Recommended fix:
- Rename or split status fields:
  - `outer_attempts_started`
  - `completed_steps`
  - `proposal_blocks_completed`
  - `effective_screened_rounds`
  - `telemetry_repair_attempts`
  - `in_flight_attempt_started_at`
- Keep old fields as compatibility aliases only if needed, and document their semantics.

Suggested tests:
- Simulate SIGTERM after round increment but before StepResult append; status should expose one in-flight attempt and not report it as completed.
- Summary/postmortem should distinguish proposal blocks from screened experiments.

## Finding OPS-P2-1 - `exit.txt` Is Still A Launcher Convention, Not A CLI Artifact

Severity: P2

Type: experiment/ops problem.

Evidence:
- `scion/scion/cli/commands/init_run.py:30-49` installs SIGTERM/SIGINT handlers that request a graceful campaign stop.
- `scion/scion/cli/commands/init_run.py:439-445` finalizes the requested stop and exits with `128 + signum`.
- `scion/scion/core/campaign.py:238-252` writes final status and campaign summary on external stop.
- `scion/docs/operations/experiment-runbook.zh.md:215-224` shows a shell `write_exit` trap that writes `exit.txt`.
- Active tree search found only archived launch scripts under `scion/archive/run-scripts/`; there is no checked-in current launch template that guarantees `exit.txt`.

Why this matters for v3:
- v3 auditability depends on durable termination evidence. If each experiment operator writes their own launcher, missing `exit.txt` can reappear.
- The CLI now handles graceful stop state, but `exit.txt` remains outside the CLI contract.

Recommended fix:
- Add a first-class CLI option such as `--exit-file` / `--run-root` that writes exit code, reason, and UTC timestamp.
- Or check in the current v0.4 launcher template outside `archive/` and make the runbook point to it.

Suggested tests:
- CLI signal test that sends SIGTERM and verifies status, summary, exit code, and optional `exit.txt`.
- Runbook linter/smoke test that the referenced launcher path exists.

## Alignment - Transient LLM Errors Are Routed As Infra, Not Proposal Quality

Evidence:
- `scion/scion/proposal/llm_client.py:94-130` detects gateway/transport errors.
- `scion/scion/proposal/llm_client.py:467-487` retries transient provider errors.
- `scion/scion/core/proposal_pipeline/agentic_lifecycle.py` routes transient LLM API failures separately from proposal-quality blocks.

Assessment:
- This addresses the recent 502/transport retry concern. Keep the provider-specific markers current, but no architecture blocker was found here.
