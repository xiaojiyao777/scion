# CVRP 1R Behavior Debug Repaired Postrun - 2026-06-15

## Purpose

This was the repaired rerun of the one-round CVRP behavior debug. Its purpose
was not promotion. It tested whether the CVRP runtime-boundary repair restored
the path from LLM proposal through Contract, Verification, Canary, Protocol,
metrics, and Decision after the pre-repair run died before Protocol.

## Artifacts

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-single-round-debug-cvrp-compact-1r-repaired-gpt55-20260615T175742Z-claw`
- Server sync:
  `/home/clawd/research/scion-experiments/v04-single-round-debug-cvrp-compact-1r-repaired-gpt55-20260615T175742Z-claw`
- Launch commit: `96ba571`
- Tmux session:
  `scion_cvrp_1r_repaired_20260615T175742Z`
- Shape: one cell, `rounds=1`, WSL `gpt-5.5`,
  `measurement_governance=on`, `compact-measurement-diagnostics`,
  `time_limit_sec=30`, `SCION_STAGE_TRANSITION_DRAIN_LIMIT=0`, and foreground
  `timeout 2h`.

## Outcome

Wrapper exit was `0`. Campaign validity:

- `run_validity.status=valid`
- `run_validity.reason=valid`
- `effective_protocol_rounds=1`
- `formal_screened_candidates=1`
- `proposal_attempts_total=1`
- `agentic_sessions=2`
- `screening_protocol_results=1`
- `protocol_metric_results=1`
- `validation_protocol_results=0`
- `frozen_protocol_results=0`
- `verification_failure_consumed_candidates=0`
- `quality_block_ledger=0`

LLM request counts were `hypothesis_target_intent=1`, `hypothesis=1`,
`tool_selection=6`, and `code=1`.

The formal candidate replay identity was complete:

- Candidate id: `72dfe7cacba99f88`
- Hypothesis id: `6d223be5-4309-4614-bcbe-d1f357622d33`
- Branch id: `ee9ffa00-7d66-4849-a006-0d1baa99f40c`
- Target file: `policies/baseline_modules/local_search.py`
- Patch digest:
  `dfc74a47bdc6118d1599de8cd0c4e74fefcf36482ca3ea4f52e59c52b2b2a061`
- Metrics ref: `metrics/45f966a4-14c1-4251-a074-1c17dad951af.json`

## Candidate

The candidate was not the independent-control two-opt scheduling hypothesis. It
proposed a new bounded VNS/local-search neighborhood:

`split_route_ejection_merge`

The patch added `_split_route_ejection_merge()` to
`policies/baseline_modules/local_search.py` and inserted it into
`_default_vns_operators()` before `_two_opt_star`.

The mechanism targets short/light residual routes: choose a small set of
candidate routes, greedily test capacity-feasible insertion of all customers
into other routes, and accept only a full-route dissolution or strict
distance-improving route-count-preserving merge.

## Protocol Result

The candidate passed Contract, Verification, and Canary, then reached screening
Protocol.

Screening result:

- Case W/L/T: `2/1/5`
- Pair W/L/T: `6/5/21`
- `win_rate=0.25`
- `median_delta=0.0`
- CI `[0.0, 5.25]`
- Decision: `expand_screening`
- Reason: `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT`

This is a valid Protocol row and a valid path-health result. It is not evidence
of a useful CVRP mechanism.

## Prompt And Source Findings

Read-only postrun analysis by subagent `Carson`
(`019ecc90-853a-7111-a164-166df16f2de6`) accepted this artifact for framework
path health only.

Key findings:

- Source visibility passed.
- The hypothesis prompt had full dedicated `local_search.py`.
- The code prompt had full target `local_search.py` plus required `state.py`.
- The code prompt had no section truncation.
- The hypothesis prompt remained large: about `120,089` characters and
  `30,023` estimated tokens.
- `compact_research_signals` was still truncated in the hypothesis prompt.
- Branch/cross-branch material was visible, but one round is too shallow to
  prove meaningful lesson use.

## Interpretation

This run closes the immediate post-repair path-health gate. The pre-repair
runtime-boundary failure did not recur, and Scion successfully carried one CVRP
LLM candidate through Contract, Verification, Canary, Protocol, metrics, and
Decision.

It does not prove effective VRP research quality. There is only one candidate,
the candidate differs from the independent-control two-opt hypothesis, and the
Protocol signal was low-SNR screening expansion rather than validation,
frozen, or promotion evidence.

The remaining CVRP research problem is therefore no longer "cannot reach
Protocol after the boundary fix"; it is whether branch lessons, compact
problem-owned signal, and mechanism follow-up can consistently produce better
CVRP candidates under enough rounds and a measurable research surface.

## Next Gate

Do not start a long CVRP campaign solely because this one-round debug is valid.
Use it as path-health clearance, then continue with:

1. Narrow follow-up for the two-opt polish scheduling hypothesis, because the
   smoke was active and positive in aggregate but regressed on B-family rows.
2. A deeper behavior run only after the prompt/context and branch-lesson
   questions are framed as artifact checks, not inferred from promotion status.
3. Continued separation between problem-owned diagnostics and generic
   `DecisionFeatures`.
