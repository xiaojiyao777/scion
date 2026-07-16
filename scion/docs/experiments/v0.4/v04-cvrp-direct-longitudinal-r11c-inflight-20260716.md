# CVRP Direct Longitudinal R11c Inflight

## Launch Identity

- run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r11c-8r-gpt56sol-8r-gpt56sol-20260716T132422Z-claw`;
- wrapper PID: `2892669`;
- started: `2026-07-16T13:24:24Z`;
- clean detached runtime:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-56bc445d`;
- exact pushed code commit:
  `56bc445d07b19587ecb8e4b763ab448c4ceb9115`;
- model/runtime: `gpt-5.6-sol / direct_v3`;
- requested typed rounds: `8`;
- scientific solver subprocess fallback: `30s`;
- control-pair metadata: `cvrp.direct-longitudinal:r11c-gpt56sol-8r`.

R11c is a fresh formal root. It does not copy R11b campaign state and has no
resume, force surface/action/target, provider retry, semantic budget, output
truncation, or automatic stop extension. The launcher persists an empty
`SCION_API_KEY` plus only the environment-variable name
`SCION_SHARED_PROXY_KEY`; no key value is stored in launch metadata or command
arguments. Completion preflight is authenticated, HTTP `200`, and returned
nonempty content.

## Purpose

R11c is the first clean run after the R11b P1 transaction repair at
`56bc445d`. The repair does not weaken the source-owner guard:

- `EvaluationOrchestrator` computes a prospective expand round without
  mutating the durable source Branch;
- Protocol and DecisionFeatures receive the effective count;
- a completed expanded Protocol consumes the count only on the Decision target;
- transactional terminal decisions commit that target atomically;
- Protocol failure does not consume an expansion round.

The repair passes focused/adjacent review, the correctly rooted full Scion
suite (`2058` passed, one skipped), compileall, and `git diff --check`.

This remains an open algorithm control. Neither CROSS nor the elapsed-time
simulated-annealing lead is forced. Judge any generated candidate from its code
diff, activation, objective/case/pair evidence, throughput, Protocol, Decision,
and replay identity.

## Monitoring Rules

- poll no more frequently than about three minutes;
- do not signal, mutate, resume, or launch another generative root while R11c is
  live;
- if screening or validation expands, verify one Protocol run, prospective
  source count, exactly one committed target increment, one final execution
  outcome, and matching typed/canonical lineage;
- if a sibling branch opens, verify complete safe screening history without
  validation/frozen, terminal-state, raw-ref, patch-body, or failure-prose
  leakage;
- require terminal wrapper, postrun rebuild, and readiness acceptance.
