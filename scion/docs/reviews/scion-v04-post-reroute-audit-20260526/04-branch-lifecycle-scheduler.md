# Branch Lifecycle, Scheduler, and Campaign Loop

Audit question: are non-clean branches, same-mechanism follow-up, clean fork/reroute, and proposal/effective-round accounting clear and consistent?

## Positive Findings

The post-reroute lifecycle repair matches the intended v3 policy better than the previous state.

- Non-clean branches require same-mechanism continuation; new mechanism ids are blocked with `new_mechanism_requires_clean_fork`: `scion/scion/core/branch_repair_policy.py:150-196`.
- A lifecycle policy block marks the selected branch ineligible for new-mechanism proposal selection and records a reroute marker: `scion/scion/core/branch_hygiene.py:116-146`.
- Scheduler excludes ineligible research branches from proposal capacity and reroutes to clean branch/fork when all research branches are ineligible: `scion/scion/core/scheduler.py:63-104`.
- Tests cover reroute to clean branch and clean-fork creation at nominal capacity: `scion/scion/tests/test_scheduler.py:113-158`.
- Branch lifecycle policy blocks do not consume proposal attempts or effective rounds: `scion/scion/core/campaign_loop.py:211-217`, with tests at `scion/scion/tests/unit/core/test_retry_round_accounting_campaign_loop.py:780-838` and `scion/scion/tests/unit/core/test_retry_round_accounting_campaign_loop.py:842-913`.

## Finding BL-1: proposal-attempt default can stop before requested effective rounds

Severity: P1.

The round accounting labels are now clear, but the default budget is not aligned with current-state documentation or 8-effective-round validation expectations.

- Default proposal attempt limit equals requested rounds: `scion/scion/core/campaign_loop.py:333-355`.
- The loop stops before another step when attempts reach the limit: `scion/scion/core/campaign_loop.py:141-148`.
- Ordinary proposal blocks consume attempts: `scion/scion/core/campaign_loop.py:223-230`.
- Current-state still documents default repair headroom: `scion/docs/status/current-state.md:75-79`.

This means a requested 8-round run can stop with fewer than 8 effective screened rounds after ordinary proposal blocks unless `SCION_PROPOSAL_ATTEMPT_LIMIT` is set higher.

Suggested fix: choose one policy and make code, tests, status docs, and launch instructions agree. For research validation, prefer an explicit effective-round target plus a separate, higher proposal-attempt cap.

## Finding BL-2: branch lifecycle ineligibility is sticky by implementation

Severity: P2.

`record_branch_lifecycle_policy_block` sets `branch_lifecycle_new_mechanism_ineligible=True` and there is no obvious clear path in the current branch hygiene code. The guidance says the scheduler should use a clean branch/fork for new mechanisms or continue only under the same mechanism ids: `scion/scion/core/branch_hygiene.py:347-355`.

This may be intended. It should be documented as persistent until branch terminalization or explicit recovery, not "temporary", unless a clear condition is added.

