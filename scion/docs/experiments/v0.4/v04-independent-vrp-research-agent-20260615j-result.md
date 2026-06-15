# Independent VRP Research Agent J Result - 2026-06-15

## Boundary

This is an external-control plain Codex VRP baseline research result. It is not
a Scion campaign, not Scion Protocol evidence, and not promotion evidence. The
agent was explicitly forbidden from reading Scion design, task, status, audit,
prompt, planning, or experiment artifacts.

## Agent

- Subagent: `Russell`
- Agent id: `019ecd64-52d1-75b3-8b39-45ca1a78b7eb`
- Artifact root:
  `/home/clawd/research/vrp-independent-codex-research/phase-j-20260615`

## Artifacts

Required artifacts are present:

- `status.md`
- `research_log.md`
- `experiments.jsonl`
- `candidate_summary.md`
- `run_matrix.py`
- `raw/*.jsonl`
- `raw/*.csv`

Validation checks:

- `experiments.jsonl` parses as valid JSONL with `4` rows.
- `candidate.patch` is intentionally absent.
- Candidate edits were confined to artifact-root scratch copies.
- Main checkout still has the pre-existing unrelated `M vrp/src/solver.py`
  dirty state; this result does not modify or rely on applying that file.

## Baseline Characterization

The agent used standalone `vrp/` only and copied data from `vrp/cvrplib/` into
scratch workspaces. Its characterization identified X-subset instances as the
clearest medium-scale weakness in existing standalone results:

- mean best gap around `5.86%`;
- max gap around `12.85%`;
- sampled hard cases included `X-n513-k21`, `X-n411-k19`, `X-n143-k7`, and
  `X-n237-k14`.

## Candidate Screens

All completed screens used paired cases/seeds/budgets:

- cases: `X-n513-k21`, `X-n411-k19`, `X-n143-k7`, `X-n237-k14`, `A-n32-k5`
- seeds: `0`, `1`, `2`
- budget: `1s`
- `vns_iterations=50`

| Candidate | W/T/L | Mean cost delta | Decision |
|---|---:|---:|---|
| `no_vns_param` | `0/0/15` | `+240.73` | rejected |
| `rotated_sweep_initial` | `0/15/0` | `0.0` | neutral, not retained |
| `max_destroy_160_param` | `0/15/0` | `0.0` | neutral, not retained |

One preliminary row, `h1_no_vns_screen`, failed before solver comparison
because the base Python environment lacked `numpy`; it was rerun successfully
as `h1_no_vns_screen_claw`.

## Interpretation

No candidate survived. This is useful negative external-control evidence:
another plain Codex VRP research subject, isolated from Scion context, also did
not easily produce a robust standalone VRP baseline improvement on a hard
X-focused paired screen.

This result should not seed Scion replay. It should remain part of the external
comparison corpus used to judge whether Scion's CVRP difficulty comes from the
problem/baseline itself, the measurement floor, or Scion-specific research
behavior.
