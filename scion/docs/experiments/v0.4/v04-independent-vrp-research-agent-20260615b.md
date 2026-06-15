# Independent VRP Research Agent Control B - 2026-06-15

## Purpose

This was a third external-control run for Scion v0.4 CVRP research. The
subagent `Peirce` (`019ecc78-2582-75f2-8d0d-1448fa0761bf`) was explicitly
forbidden from reading Scion design, task, audit, status, or experiment
artifacts. It worked only in a clean standalone VRP worktree and an experiment
root:

- Worktree:
  `/home/clawd/research/or-autoresearch-agent-vrp-control-20260615b`
- Artifact root:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615b`

This is not Scion Protocol evidence. It is a process-quality control for how a
plain Codex researcher behaves on standalone VRP without Scion context.

## Artifacts

- Research log:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615b/research_log.md`
- Summary:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615b/summary.md`
- Candidate patch:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615b/candidate.patch`
- Final paired result:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615b/results/paired_relocate_intra_fast_full_seq.json`

The subagent changed only the isolated standalone VRP worktree:

- `/home/clawd/research/or-autoresearch-agent-vrp-control-20260615b/vrp/src/local_search/operators.py`
- `/home/clawd/research/or-autoresearch-agent-vrp-control-20260615b/vrp/src/solver.py`

No commit was made.

## Limitation

The real `cvrplib/` benchmark data was absent from the allowed roots for this
isolated control. The subagent therefore generated deterministic synthetic
CVRPLIB-format fixtures under:

`/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615b/synthetic_cvrp`

This makes the result weaker than the earlier independent controls that ran on
real CVRPLIB data. Treat this run as a hypothesis seed only.

## Mechanism

The surviving candidate adds an intra-route relocate neighborhood to standalone
VNS:

- Add `relocate_intra(solution)`, a first-improvement single-customer relocation
  within the same route.
- Insert it into `default_vns_operators()` immediately after `two_opt_intra`.

This is different from the stronger earlier independent-control signal, which
was a medium/large `_two_opt_intra` polish scheduling/gating mechanism.

## Result

On the executable synthetic paired comparison:

- Pairs: `38`
- W/L/T: `18/5/15`
- Mean cost delta: `-4.8421`
- Median cost delta: `0.0`
- Mean runtime delta: `+0.0041s`
- Feasibility regressions: `0`
- Benchmark-feasibility regressions: `0`
- Route-count regressions: `0`

By subset:

- `medium`: `30` pairs, W/L/T `17/5/8`, mean cost delta `-5.1667`, median
  delta `-2.5`
- `smoke`: `8` pairs, W/L/T `1/0/7`, mean cost delta `-3.625`, median
  delta `0.0`

## Interpretation

This result is plausible but weak. It shows that an independent Codex research
subject can produce another local-search hypothesis and record a coherent
paired comparison, but it does not validate a CVRPLIB benchmark improvement.

The stronger Scion follow-up remains the earlier two-opt scheduling hypothesis,
because that one was tested on real standalone CVRPLIB rows and maps directly
onto Scion CVRP's existing `_two_opt_intra` implementation. The intra-route
relocate idea should not be prioritized ahead of the two-opt direct replay
unless later real-CVRPLIB evidence supports it.
