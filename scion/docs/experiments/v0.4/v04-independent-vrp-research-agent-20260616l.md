# Independent VRP Research Agent L Launch - 2026-06-16

## Purpose

Launch a thirteenth independent VRP-only Codex control as a continuing external
research lane. This is intentionally not a Scion subagent and not Scion
Protocol evidence. The control asks whether a plain Codex research subject,
isolated from Scion's architecture, status, audit reports, prompts, and
experiment history, can improve the standalone `vrp/` baseline and leave a
research trace that can be compared with Scion-guided branch research.

This extends the existing independent-control sequence after the `Helmholtz`
phase K result. The first `Newton` cycle is bounded so that the work remains
auditable; the broader lane can continue in later cycles if the process remains
useful.

## Agent

- Subagent: `Newton`
- Agent id: `019ecded-8a24-7a03-b64b-8b1929c9af49`
- Launch time: `2026-06-16T00:56:23Z`
- Context mode: fresh, non-forked

## Boundary

Hard constraints in the brief:

- Do not read, search, summarize, or open Scion files or artifacts: no `scion/`,
  no `TASK.md`, no Scion design/status/audit/planning/experiment docs, and no
  Scion experiment results.
- Treat `/home/clawd/research/or-autoresearch-agent/vrp/` as the only research
  subject, along with available VRP problem data and standard Python tooling.
- Do not modify the main repository in place. Work in copied/scratch workspaces
  under the assigned artifact root.
- Use real VRP cases from the available repository/data, not synthetic-only
  cases.
- Prefer simple, localized solver changes over broad rewrites.

## Artifact Root

`/home/clawd/research/vrp-independent-codex-research/phase-l-20260616`

Expected artifacts:

- `research_journal.md`
- `candidate.patch`, or `rejected_candidates.md` if no candidate survives
- `experiment_results.json` or `experiment_results.jsonl`
- `summary.md`
- `README.md`

## First-Cycle Experiment Shape

- Target roughly `5-8` representative real cases.
- Use at least `3` seeds.
- Start with a `1s` budget per solve.
- Add a second small budget tier only if it is useful for diagnosis.
- Preserve feasibility and route-count/fleet constraints; feasibility or fleet
  regressions override objective gains.
- If a positive candidate appears, run at least one follow-up sanity check on
  cases outside the motivating set.

## Acceptance

The result is accepted only as external-control process evidence unless the
agent returns a cleanly applying `candidate.patch` plus paired
baseline/candidate results. Even then, a positive candidate is only hypothesis
material. It must pass a later no-LLM replay before it can influence Scion
experiments, Protocol evidence, or any default solver setting.
