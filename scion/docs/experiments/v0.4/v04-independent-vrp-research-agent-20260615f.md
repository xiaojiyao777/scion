# Independent VRP Research Agent F Launch - 2026-06-15

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
