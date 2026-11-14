# Independent VRP Research Agent K Result - 2026-06-15

## Boundary

This is an external-control plain Codex VRP baseline research result. It is not
a Scion campaign, not Scion Protocol evidence, not promotion evidence, and not
an accepted solver change. The agent was explicitly forbidden from reading
Scion design, task, status, audit, planning, prompt, or experiment artifacts.

## Agent

- Subagent: `Helmholtz`
- Agent id: `019ecd83-3324-7820-912e-2c7d94517e7e`
- Artifact root:
  `/home/clawd/research/vrp-independent-codex-research/phase-k-20260615`

## Artifacts

Required artifacts are present:

- `research_log.md`
- `experiments.jsonl`
- `summary.md`
- `candidate.patch`
- `scripts/run_smoke_experiments.py`
- `raw_results/baseline_rows.jsonl`
- `raw_results/multi_construction_rows.jsonl`
- `raw_results/regret4_repair_rows.jsonl`
- `raw_results/comparison_multi_construction.csv`
- `raw_results/comparison_regret4_repair.csv`

Validation checks:

- `experiments.jsonl` parses as valid JSONL with `3` rows.
- `candidate.patch` changes only `vrp/src/alns/repair.py`.
- `candidate.patch` adds `regret4_insertion(...)` and registers
  `("regret4", regret4_insertion)` in `REPAIR_OPERATORS`.
- `git apply --check` passes in a temporary clean `HEAD` archive, so the patch
  is not dependent on the current dirty worktree.
- The patch was not applied to the main checkout.

Clean patch check:

```bash
tmp=$(mktemp -d /tmp/scion-phase-k-patch-check.XXXXXX)
git archive HEAD | tar -x -C "$tmp"
cd "$tmp"
git apply --check /home/clawd/research/vrp-independent-codex-research/phase-k-20260615/candidate.patch
rm -rf "$tmp"
```

## Smoke Matrix

- Cases: `A-n60-k9`, `M-n151-k12`, `X-n120-k6`, `X-n143-k7`,
  `X-n204-k19`
- Seeds: `0`, `1`, `2`
- Time limit: `1.0s` per solve
- Metric: candidate cost minus baseline cost; negative is better

The agent created an isolated venv under the artifact root because the default
Python environment lacked `numpy`. This does not modify tracked repo files.

## Candidate Screens

| Candidate | Hypothesis | W/T/L | Mean delta | Median delta | Failures | Decision |
|---|---|---:|---:|---:|---:|---|
| `baseline` | H0 baseline confirmation | `0/15/0` | `0.0` | `0.0` | `0` | confirmed |
| `multi_construction` | H1 multi-construction initial solution | `6/6/3` | `+17.533` | `0.0` | `0` | reject as-is |
| `regret4_repair` | H2 regret-4 repair operator | `8/5/2` | `-32.333` | `-11.0` | `0` | retain as external seed |

H2 positive rows:

- `A-n60-k9`: improved all three seeds by `20`, `20`, and `35`.
- `M-n151-k12`: tied seed `0`, improved seeds `1` and `2` by `12` and `11`.
- `X-n120-k6`: tied seed `0`, improved seed `1` by `257`, lost seed `2` by
  `121`.
- `X-n143-k7`: lost seed `0` by `44`, improved seed `1` by `155`, tied seed
  `2`.
- `X-n204-k19`: tied seeds `0` and `2`, improved seed `1` by `140`.

## Interpretation

`regret4_repair` is a positive external-control hypothesis seed. The signal is
stronger than the previous Russell phase J negative result, and the patch is a
small algorithmic addition rather than a parameter-only sweep.

The result is still too small to merge or to treat as Scion evidence:

- only `5` cases x `3` seeds were tested;
- the smoke matrix includes two X-family regressions;
- all runs used a `1.0s` standalone VRP budget, not Scion Protocol validation;
- the result was generated outside Scion and outside v3 governance.

## Next Gate

Before any Scion replay or default VRP solver change, run a broader no-LLM
validation:

- cases: A/B/P/E stable subset sample plus the X cases used here;
- seeds: `0..9`;
- budgets: `1.0s`, with optional `2.0s` diagnostic expansion;
- acceptance: non-positive median delta, positive W-L margin, no repeated
  family-specific regressions, and feasibility preserved.

Only after that broader no-LLM replay should the main thread decide whether to
prepare a Scion fixed-candidate replay or a problem-owned research-surface
seed.
