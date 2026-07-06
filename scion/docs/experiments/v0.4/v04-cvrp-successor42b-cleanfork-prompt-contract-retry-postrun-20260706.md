# CVRP Successor42b Prompt-Contract Retry Postrun

Date: 2026-07-06

## Run

- Run root: `/home/clawd/research/scion-experiments/v04-cvrp-successor42b-cleanfork-prompt-contract-retry-server-claw-2r-gpt55-2r-gpt55-20260706T092004Z-claw`
- Launcher commit: `ff2258f3`
- Model: local `gpt-5.5`
- Resume source: successor41b route-skeleton diagnostic campaign
- Status: valid, complete, postrun-ready
- Stop reason: `max_rounds_exhausted`
- Effective rounds: 2

## Purpose

Successor42b retried successor42 after the CVRP-owned solver-design prompt
contract repair. The repair made the exact
`material_difference.changed_dimensions` / `contrast` / `evidence` schema
visible in fresh clean-fork hypothesis prompts and kept CMT2/CMT4 priority
coverage problem/protocol-owned.

## Trace And Boundary Check

The successor42b hypothesis prompt exposed the exact material-difference
schema and CMT2/CMT4 clean-fork protection requirement. The accepted hypothesis
named `elite_route_memory_repair` in
`policies/baseline_modules/route_memory.py` and included
`branch_lesson_usage.clean_fork_diversity_claim` for CMT2/CMT4.

Generated solver code stayed in the CVRP workspace: a new
`route_memory.py` module plus minimal scheduler wiring. No generic Decision,
scheduler, protocol, or promotion logic was given CVRP case semantics, and no
case-id or BKS hardcoding was found in the generated solver code.

## Protocol Evidence

Row 1 completed 48/48 pairs with zero failed pairs and effective priority cases
including CMT2 and CMT4. Pair W/L/T was 24/22/2. The branch evidence was
`marginal`, with median delta `0.0` and CI `[-7.5, 3.75]`. Case-level winners
included A-n80, M-n151, and tai150c. Case-level losses included P-n101, CMT2,
and CMT4.

Row 2 expanded the same mechanism to 64/64 pairs with zero failed pairs. Pair
W/L/T was 29/28/7. The branch stayed `marginal`, with median delta `0.0` and
CI `[-6.0, 2.0]`. Case-level winners remained A-n80, M-n151, and tai150c.
Case-level losses included P-n101, CMT2, CMT4, and X-n110.

The mechanism was not fake-active: row 1 observed
`elite_route_memory_repair` runtime on 47 pairs and positive mechanism best
delta on 46 pairs; row 2 observed runtime on 61 pairs and positive mechanism
best delta on 58 pairs. The direct mechanism signal did not translate into a
promotion-grade or protected-case-safe solver result.

## Protected Cases

The CMT2/CMT4 priority-case repair worked as protocol coverage: both rows
included those cases in effective priority coverage. The solver mechanism
failed the protection goal:

- CMT2: 1W/2L/1T, median delta `-8.0`
- CMT4: 1W/3L/0T, median delta `-10.5`

## Judgment

The framework repair succeeded. The original successor42 failure was a prompt
contract assembly gap, and successor42b showed the repaired prompt, causal-path
gate, local `gpt-5.5` calls, generated code path, protocol selection, and
postrun readiness are working.

The solver line should not continue for v0.4. `elite_route_memory_repair`
is active and modular, but below MDE, low-signal, and unsafe on protected
CMT2/CMT4 cases. Treat unchanged route-memory repair and same-mechanism
threshold/template-count tuning as reviewed/default-avoid. The next CVRP slot
should clean-fork to a materially different problem-owned causal path while
keeping the exact material-difference prompt contract and CMT2/CMT4 priority
coverage.

## Follow-Up Notes

- Keep the CVRP prompt-contract repair; it improved hypothesis quality without
  moving CVRP semantics into generic Decision/Scheduler paths.
- Keep protocol-level priority-case coverage recording.
- Do not long-run successor42b.
- A minor projection inconsistency remains: one session summary reported
  `clean_fork_diversity_claim_present=false` even though the complete
  hypothesis contained that field and passed the contract. This is not a
  blocker for successor42b but is worth cleaning up if summary projections are
  used in later analysis.
