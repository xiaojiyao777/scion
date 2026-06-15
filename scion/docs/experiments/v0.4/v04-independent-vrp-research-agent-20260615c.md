# Independent VRP Research Agent Control C - 2026-06-15

## Purpose

This is a fourth external-control run for Scion v0.4 CVRP research. The
subagent `Anscombe` (`019ecc8e-d45e-7983-b346-3621f90d38f4`) was launched as a
fresh, non-forked agent so it would not inherit Scion task context or prior
Scion conclusions.

This is intentionally not a Scion task. It tests whether a plain Codex research
subject can improve the standalone `vrp/` baseline and document its research
process without reading Scion rules, design documents, status reports, prompts,
or experiment analyses.

## Boundaries

The subagent was instructed:

- Do not read or use files under `scion/`.
- Do not read Scion design docs, `TASK.md`, audit/status docs, experiment
  reports, or Scion prompts.
- Inspect and edit only standalone VRP files, especially under `vrp/`.
- Keep all changes isolated in a separate worktree.
- Do not commit or push.

## Roots

- Main repo:
  `/home/clawd/research/or-autoresearch-agent`
- Suggested isolated worktree:
  `/home/clawd/research/or-autoresearch-agent-vrp-control-20260615c`
- Artifact root:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615c`

## Required Outputs

- `research_log.md`: chronological hypotheses, commands, failures, evidence,
  and decisions.
- `candidate.patch`: patch against the standalone VRP worktree, if a candidate
  is found.
- `results/`: raw JSON/CSV paired-run outputs.
- `summary.md`: final report with benchmark shape, W/L/T, mean/median objective
  delta, feasibility and route-count regressions, runtime impact, and whether
  the result is strong enough to feed back to Scion as a hypothesis.

## Interpretation Contract

This run can produce external-control hypothesis seeds only. It is not Scion
Protocol evidence, does not change the canonical CVRP baseline, and must not be
used as a Decision feature. Any promising mechanism must be translated into a
problem-owned Scion CVRP candidate and replayed through the v0.4 measurement
and Protocol gates before adoption.
