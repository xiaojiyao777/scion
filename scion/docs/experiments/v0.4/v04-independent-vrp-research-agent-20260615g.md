# Independent VRP Research Agent Phase G Launch - 2026-06-15

## Purpose

Launch an eighth independent VRP-only control agent as a standalone Codex
research subject. This is an external-control lane for comparing plain Codex
algorithm research against Scion-guided research behavior.

The question is not whether another random VRP tweak can be found. The question
is whether an uncontaminated Codex researcher, without Scion prompts, governance,
branch maps, or measurement diagnostics, can form stable VRP baseline
hypotheses, test them reproducibly, and produce a candidate whose evidence is
strong enough to seed later no-LLM Scion replay.

## Agent

- Agent: `Tesla`
- Agent id: `019ecd11-665c-7c32-b30a-0e023f0f29ef`
- Spawn mode: fresh, non-forked context
- Role: independent external VRP researcher
- Workspace scope: repository `vrp/` package plus the artifact root below
- Artifact root:
  `/home/clawd/research/vrp-independent-codex-research/phase-g-20260615`

## Boundary

This agent is explicitly not a Scion subagent and is exempt from the normal
v3-first Scion subagent reading rule.

It must not read or use:

- `scion/`
- `scion/TASK.md`
- Scion design, audit, status, prompt, or experiment artifacts
- Scion campaign outputs or branch maps

It may read and modify only standalone VRP research material:

- `vrp/`
- standard Python tooling needed to run VRP cases
- `/home/clawd/research/vrp-independent-codex-research/phase-g-20260615`

Any positive result is external-control hypothesis material only. It is not
Scion Protocol evidence and must go through a later no-LLM Scion replay before
it can influence Scion experiments.

## Required Artifacts

The agent must maintain:

- `research_log.md`: timestamped hypothesis, code/read context, experiment,
  and decision log.
- `status.md`: current phase, active hypothesis, running commands, current
  result summary, and next step.
- `experiments.jsonl`: one row per experiment with timestamp, candidate id,
  hypothesis, command, case set, budget, seeds, baseline metric, candidate
  metric, delta, runtime, verdict, and notes.
- `candidate.patch` and `candidate_summary.md` only if a viable candidate
  survives.
- `final_summary.md` if no candidate survives.

## First-Milestone Guardrail

The first milestone is a bounded autonomous pilot:

- Start with small and medium representative cases.
- Use short budgets sufficient for signal hunting.
- Do not launch a broad WSL/server-heavy sweep without returning a proposed
  matrix for main-thread approval.
- Do not launch a single command expected to run longer than 2 hours without
  approval.
- Prefer reproducible scripts and logged commands.

## Acceptance Questions

The postrun analysis must answer:

- Which hypotheses were tried, and what evidence killed or retained each one?
- Did any candidate improve quality without unsafe runtime or case-family
  regressions?
- Did the agent demonstrate deeper research iteration, or only shallow
  mechanism switching?
- Did the independent research trace produce ideas that Scion failed to
  surface, or did it repeat the same weak/unstable patterns?
- If a candidate survives, what exact no-LLM replay tier is required before
  any Scion adoption?

## Completion

The first bounded pilot completed at `2026-06-15T21:15:40Z`.

Artifacts:

- `/home/clawd/research/vrp-independent-codex-research/phase-g-20260615/research_log.md`
- `/home/clawd/research/vrp-independent-codex-research/phase-g-20260615/status.md`
- `/home/clawd/research/vrp-independent-codex-research/phase-g-20260615/experiments.jsonl`
- `/home/clawd/research/vrp-independent-codex-research/phase-g-20260615/pilot_runs.csv`
- `/home/clawd/research/vrp-independent-codex-research/phase-g-20260615/pilot_summary.csv`
- `/home/clawd/research/vrp-independent-codex-research/phase-g-20260615/candidate.patch`
- `/home/clawd/research/vrp-independent-codex-research/phase-g-20260615/candidate_summary.md`

The agent did not apply code changes. It found `vrp/src/solver.py` dirty at
startup and treated the existing dirty solver as the external-control baseline.
The retained candidate is therefore an external seed relative to the current
local VRP baseline, not a canonical production solver conclusion.

Successful pilot command:

```bash
/home/clawd/miniconda3/envs/claw/bin/python \
  /home/clawd/research/vrp-independent-codex-research/phase-g-20260615/pilot_matrix.py \
  --repo-root /home/clawd/research/or-autoresearch-agent
```

The first PATH `python` attempt failed before solving because `numpy` was not
installed in that interpreter. The rerun used the existing `claw` conda
environment and completed.

## Candidate

The best survivor was `narrow_destroy_ratio`, a parameter-only patch changing
the default ALNS destroy-ratio range in `vrp/src/solver.py` from `(0.10, 0.40)`
to `(0.05, 0.25)`.

Hypothesis: under tight short-run budgets, the current 10-40% destroy range can
over-disrupt already reasonable Clarke-Wright/VNS solutions. A narrower 5-25%
range may preserve useful route structure while still allowing ALNS to improve
small and medium instances.

Pilot matrix:

- Cases: `A-n80-k10`, `B-n78-k10`, `P-n101-k4`, `X-n143-k7`,
  `X-n237-k14`, `X-n513-k21`, `tai150a`
- Seeds: `0`, `1`
- Nominal per-run budget: `0.4s`
- Rows: `98` solve rows in `pilot_runs.csv`; `7` aggregate candidate rows in
  `pilot_summary.csv`

Aggregate result:

- Baseline mean gap: `7.6449519187010235%`
- Candidate mean gap: `7.354517114570147%`
- Delta: `-0.29043480413087686` percentage points
- Wins/ties/losses: `5 / 7 / 2`
- Baseline mean wall time: `1.0870077047230942s`
- Candidate mean wall time: `0.785479294934443s`

Rejected or neutral controls:

- `no_vns_control`: `0/0/14`, mean gap worsened by `+1.154172959117476`.
- `vns_1000`: `0/13/1`, mean gap worsened by `+0.06293266205160464`.
- `destroy_cap_60`: `0/13/1`, mean gap worsened by `+0.020018198362147466`.
- `destroy_cap_240`: exact aggregate quality tie in this pilot.
- `wide_destroy_ratio`: `1/9/4`, mean gap worsened by `+0.09028495044221341`.

Negative signal for the retained candidate:

- `X-n143-k7` lost one seed and tied one seed.
- `tai150a` tied one seed and lost one seed.
- `X-n513-k21` tied both seeds because no ALNS iteration ran under the short
  budget.

Validation checks:

```bash
git apply --check /home/clawd/research/vrp-independent-codex-research/phase-g-20260615/candidate.patch
/home/clawd/miniconda3/envs/claw/bin/python -m py_compile \
  /home/clawd/research/vrp-independent-codex-research/phase-g-20260615/pilot_matrix.py
```

Both checks passed.

## Interpretation

This is the strongest Phase G output: a small, low-risk parameter seed with a
short-budget positive signal and no observed feasibility failures. It is still
too narrow for adoption. The pilot has only `14` paired rows, two losses, and
one case where the candidate could not activate ALNS under the short budget.

Compared with recent Scion CVRP behavior, the independent agent did produce a
simple actionable parameter hypothesis quickly. The result is not a deep
mechanism improvement and should not be treated as evidence that plain Codex
has solved the VRP bottleneck. It is useful as a control seed for a broader
no-LLM replay.

## Recommended Next Tier

Run a broader no-LLM validation matrix before changing any default:

- Compare `(0.10, 0.40)`, `(0.05, 0.25)`, and `(0.05, 0.30)`.
- Cases: all A/B/P/CMT plus stratified X/tai cases across dimensions
  approximately 100-600.
- Seeds: `0..4`.
- Budgets: `0.5s`, `1.0s`, and `3.0s`.
- Acceptance: improve mean and median gap, avoid material worst-case gap
  increase, produce no feasibility regressions, and avoid runtime regressions.

Only after that no-LLM tier should this seed be considered for Scion replay or
solver default changes.
