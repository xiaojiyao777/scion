# Independent VRP Research Agent F Result - 2026-06-15

## Purpose

This is a seventh independent VRP-only external control. The goal is to keep a
plain Codex research subject working on the standalone `vrp/` baseline while
recording its research process, without seeing Scion architecture, Scion task
context, Scion audits, Scion status, or Scion experiment results.

This is not a Scion subagent assignment. It is intentionally exempt from the
usual v3-first brief because contamination by Scion research history would
defeat the control.

## Agent

- Agent: `Schrodinger`
- Agent id: `019eccfc-0e6c-78e2-bf02-67b1689963f8`
- Context: fresh non-forked subagent
- Allowed source: standalone `vrp/`, standard Python tooling, and its artifact
  directory
- Forbidden source: `scion/`, `TASK.md`, Scion design docs, Scion audit
  reports, Scion status docs, and Scion experiment artifacts
- Artifact root:
  `/home/clawd/research/vrp-external-research/independent-vrp-baseline-research-phase-f-20260615`

## Required Outputs

The agent brief requires these artifacts under the artifact root:

- `research_log.md`
- `status.md`
- `experiments.jsonl` or `experiments.csv`
- `final_summary.md`
- candidate patches or self-contained variants under the artifact root only
- `candidate.patch` only if a candidate survives enough checks

All required process artifacts were produced:

- `research_log.md`
- `status.md`
- `experiments.jsonl`
- `combined_summary.csv`
- `final_summary.md`
- `matrix_runner.py`

## Scope And Constraints

The agent must not modify tracked files in the main repository. It must first
establish the observed standalone baseline and record whether `vrp/src/solver.py`
is dirty in the shared worktree. It should start with cheap sanity experiments,
expand only candidates with nontrivial signal, include at least three seeds for
candidate comparisons beyond sanity checks, and classify candidates with
regressions as unsafe even when net objective movement is favorable.

## Acceptance

Any result from this agent is external-control evidence only. A positive
candidate may become a human-approved mechanism seed for a later no-LLM Scion
replay, but it is not Scion Protocol evidence and cannot support promotion by
itself.

This lane answers a different question from Scion's internal experiments:
whether an uncontaminated Codex research subject can find useful standalone VRP
baseline mechanisms when not constrained by Scion's proposal, branch, protocol,
and governance framework.

## Result

The bounded phase completed and did not modify tracked repository files. The
agent confirmed that `vrp/src/solver.py` was already dirty before this external
lane started and treated that dirty checkout as the observed standalone
baseline.

Key results:

| Phase | Variant | n | Improved | Tied | Regressed | Unsafe | Net delta |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| expansion | `no_route_destroy` | 18 | 11 | 7 | 0 | 0 | -93 |
| expansion | `narrow_destroy` | 18 | 9 | 6 | 3 | 0 | -41 |
| stress | `no_route_destroy` | 6 | 2 | 0 | 4 | 4 | +188 |
| large | `sweep500_multistart` | 9 | 0 | 0 | 9 | 8 | +101263 |

Negative delta is better. `no_route_destroy` looked promising in expansion but
failed targeted stress on `E/E-n76-k10` and `X/X-n101-k25`, where it produced
repeated regressions and benchmark-infeasible rows. `sweep500_multistart` was
strongly rejected on large X cases.

No candidate survived, and no `candidate.patch` was retained.

## Interpretation

This is negative external-control evidence. It does not refute the stronger
size70 two-opt CVRP mechanism seed, but it makes whole-route destroy removal
unsafe as an adoption candidate. A narrower future mechanism could test
adaptive route-removal dampening after route-count or benchmark-feasibility
regressions, but that would be a new external seed requiring its own replay.
