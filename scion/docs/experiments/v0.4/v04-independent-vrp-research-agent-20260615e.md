# Independent VRP Research Agent E Result - 2026-06-15

## Purpose

This is a sixth independent VRP-only external control. The goal is to test
whether a plain Codex research subject can improve the standalone `vrp/`
baseline while recording its research process, without seeing Scion
architecture, Scion task context, Scion audits, Scion status, or Scion
experiment results.

This is not a Scion subagent assignment. It is intentionally exempt from the
usual v3-first brief because contamination by Scion research history would
defeat the control.

## Agent

- Agent: `Lovelace`
- Agent id: `019ecce4-4806-7581-b033-d33911f8b276`
- Context: fresh non-forked subagent
- Allowed source: standalone `vrp/`
- Forbidden source: `scion/`, `TASK.md`, Scion design docs, Scion audit
  reports, Scion status docs, and Scion experiment artifacts
- Artifact root:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-baseline-research-longrun-20260615`

## Outputs

The agent brief requires the following artifacts under the artifact root:

- `research_log.md`
- `status.md`
- `experiments.csv` or `experiments.jsonl`
- candidate patches or variant files under the artifact root only
- `candidate.patch` if a positive candidate survives
- `final_summary.md` when a phase completes

All required outputs were produced. Additional artifact directories include:

- `scripts/run_matrix.py`
- `variants/construction_portfolio/`
- `variants/route_elim/`
- `variants/route_elim_post/`

## Result

The agent completed a bounded phase and did not modify main-repository tracked
files. `git status --short -- vrp` still shows only the pre-existing
`M vrp/src/solver.py`.

Important caveat: the observed baseline for this run included that pre-existing
dirty `vrp/src/solver.py` state. The agent noted that the current working-tree
baseline already had a large-instance `two_opt_intra` fallback after
construction and ALNS repair when full VNS is skipped. Treat this control as
external research relative to the current dirty standalone baseline, not as
clean-mainline VRP evidence.

Baseline sanity:

- `8` cases x `3` seeds x `1s`
- all `24` runs `ok`
- reference reached on `A/A-n32-k5` and `B/B-n50-k7`
- remaining useful gaps on `A/A-n60-k9`, `F/F-n72-k4`,
  `X/X-n101-k25`, and `X/X-n143-k7`

Candidate results:

- `route_elim` as VNS operator: `3` improved / `3` worse / `18` same,
  sum delta `-11`; stable positive on `F/F-n72-k4`, but regressions on
  `A/A-n60-k9` and `E/E-n51-k5`.
- `route_elim_post`: `0` improved / `0` worse / `25` same; safe but
  ineffective.
- `construction_portfolio`: saved as `candidate.patch`.
  - `1s` sanity: `2` improved / `0` worse / `24` same, sum delta `-11`.
  - `2s` expansion: `2` improved / `2` worse / `21` same, sum delta `-20`.
  - Observed regressions were small `+1` rows on `A/A-n60-k9 seed2` and
    `F/F-n72-k4 seed3`.

The saved patch applies cleanly:

```bash
git apply --check /home/clawd/research/scion-experiments/v04-independent-vrp-baseline-research-longrun-20260615/candidate.patch
```

## Interpretation

`construction_portfolio` is a useful external mechanism seed, not a merge-ready
candidate. It is simple and cheap, but the observed `+1` regressions mean it
needs gating and a larger 3-5s/more-seed replay before it should influence
Scion CVRP work.

This result is weaker than the size70 two-opt seed for current Scion CVRP
priority because it showed no sampled X-case benefit and no route-count change.
It should remain in the external-control backlog.

The agent may run standalone VRP cases and propose baseline algorithm changes,
but it must not modify tracked main-worktree files, commit, push, or read Scion
materials.

## Acceptance

Any result from this agent is external-control evidence only. A positive
candidate may become a human-approved mechanism seed for a separate no-LLM
Scion CVRP replay, but it is not Scion Protocol evidence and cannot support
promotion by itself.
