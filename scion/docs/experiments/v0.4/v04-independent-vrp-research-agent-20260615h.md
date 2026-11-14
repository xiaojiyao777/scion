# Independent VRP Research Agent Phase H - 2026-06-15

## Boundary

This is an external VRP-only Codex control, not a Scion campaign and not Scion
Protocol evidence. The agent was instructed not to read Scion design, task,
status, audit, prompt, or experiment artifacts. Its outputs are hypothesis
seeds for later no-LLM validation only.

## Artifacts

- Artifact root:
  `/home/clawd/research/vrp-independent-codex-research/phase-h-20260615`
- Status:
  `/home/clawd/research/vrp-independent-codex-research/phase-h-20260615/status.md`
- Research log:
  `/home/clawd/research/vrp-independent-codex-research/phase-h-20260615/research_log.md`
- Raw runs:
  `/home/clawd/research/vrp-independent-codex-research/phase-h-20260615/experiments.jsonl`
- Candidate summary:
  `/home/clawd/research/vrp-independent-codex-research/phase-h-20260615/candidate_summary.md`
- Candidate patch:
  `/home/clawd/research/vrp-independent-codex-research/phase-h-20260615/candidate.patch`

## Isolation Notes

- Source commit recorded by the agent:
  `923b14f2ed8e4d76202d42f1014d68a1ff8e9d91`
- Workspace HEAD observed by the harness at runtime:
  `6049e90d85d6a8ddefe81a1c62cfdec69add2722`
- Tested code source:
  `git archive HEAD vrp | tar -x` into the phase `snapshot/vrp`
- Main workspace files were not modified.
- No Scion files were used by the pilot.

The branch moved while the pilot was running, so treat the source commit fields
as part of the caveat. The tested code was the isolated exported `vrp/`
snapshot, not the dirty main worktree.

## Matrix

Candidates:

- `baseline`
- `c01_narrow_destroy`
- `c02_cooler_sa`
- `c03_vns_cap100`
- `c04_lower_accept_reward`

Cases:

- `A-n32-k5`, `A-n80-k10`
- `B-n78-k10`
- `P-n101-k4`
- `E-n76-k14`, `E-n101-k14`
- `X-n101-k25`, `X-n200-k36`, `X-n303-k21`

Seeds: `0`, `1`, `2`

Budgets: `0.5s`, `1.0s`

Rows: `270`

All `270` rows finished with `status=ok`, and all returned CVRP-feasible
solutions.

## Result

Recommended pilot candidate: `c02_cooler_sa`.

Patch:

```diff
diff --git a/vrp/src/acceptance.py b/vrp/src/acceptance.py
--- a/vrp/src/acceptance.py
+++ b/vrp/src/acceptance.py
@@
-        start_ratio: float = 0.05,
-        end_ratio: float = 0.0001,
+        start_ratio: float = 0.02,
+        end_ratio: float = 0.00005,
```

Paired pilot result versus baseline:

| candidate | wins | ties | losses | total distance delta | mean gap pct delta | mean wall delta |
|---|---:|---:|---:|---:|---:|---:|
| `c02_cooler_sa` | 11 | 42 | 1 | `-236` | `-0.1403` pp | `+0.021s` |

Other candidates:

- `c01_narrow_destroy`: more wins (`19`) but clear X regressions and worse
  total distance; hold for broader validation only.
- `c03_vns_cap100`: improves runtime but hurts X-n200 quality; reject as a
  quality candidate without replacement search strategy.
- `c04_lower_accept_reward`: no effect in the short-budget matrix.

## Interpretation

This is a useful external hypothesis seed, not a production improvement and not
a Scion validation result. It is small, one-file, and more robust than the
other Phase H candidates in the pilot matrix. It still needs broader no-LLM
validation before any Scion replay or default solver change.

Required before adoption:

- at least 10 seeds;
- more X cases, especially around dimension 150-400;
- longer budgets, at least `2s` and `5s`;
- separate all-CVRP-feasible versus benchmark-feasible analysis;
- explicit measurement of initial VNS wall time, because `X-n200-k36` exceeded
  nominal budget in several pilot rows due to local-search work outside the
  ALNS loop.
