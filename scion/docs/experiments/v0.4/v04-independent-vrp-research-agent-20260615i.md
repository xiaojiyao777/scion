# Independent VRP Research Agent Phase I - 2026-06-15

## Boundary

This is an external VRP-only Codex control, not a Scion campaign and not Scion
Protocol evidence. The agent was instructed not to read Scion design, task,
status, audit, prompt, or experiment artifacts. Its outputs are hypothesis
seeds for later no-LLM validation only.

The agent recorded one boundary caveat: a broad dependency-metadata command
printed `scion/pyproject.toml` paths, but no Scion file contents were read.
Treat the run as acceptable external-control process evidence with that caveat.

## Artifacts

- Artifact root:
  `/home/clawd/research/vrp-independent-codex-research/phase-i-20260615`
- Status:
  `/home/clawd/research/vrp-independent-codex-research/phase-i-20260615/status.md`
- Research log:
  `/home/clawd/research/vrp-independent-codex-research/phase-i-20260615/research_log.md`
- Raw experiment ledger:
  `/home/clawd/research/vrp-independent-codex-research/phase-i-20260615/experiments.jsonl`
- Candidate summary:
  `/home/clawd/research/vrp-independent-codex-research/phase-i-20260615/candidate_summary.md`
- Candidate patch:
  `/home/clawd/research/vrp-independent-codex-research/phase-i-20260615/candidate.patch`

## Acceptance Checks

Main-thread verification:

```bash
python -m json.tool \
  /home/clawd/research/vrp-independent-codex-research/phase-i-20260615/runs/pilot_matrix_001/paired_vs_baseline.json
python -m json.tool \
  /home/clawd/research/vrp-independent-codex-research/phase-i-20260615/runs/ags_sweep_001/paired_vs_baseline.json
git apply --check \
  /home/clawd/research/vrp-independent-codex-research/phase-i-20260615/candidate.patch
python - <<'PY'
import json
p = "/home/clawd/research/vrp-independent-codex-research/phase-i-20260615/experiments.jsonl"
for line in open(p):
    json.loads(line)
print("jsonl_ok")
PY
```

The patch check passed, and `experiments.jsonl` contained `8` valid JSONL rows.
The research run did not modify the main workspace `vrp/src/solver.py`; that
file was already dirty and was left untouched.

## Matrix

Baseline characterization:

- Pilot matrix: `9` cases x `3` seeds = `27` baseline rows.
- Status: `27/27` ok, `27/27` CVRP-feasible, `21/27`
  benchmark-feasible under route-count checking.
- X pilot mean gap: `10.158%` over `15` rows.
- Large `Leuven2` was construction-only with `790.875%` gap, confirming weak
  large-instance fallback construction.

Pilot candidates:

- `destroy160`
- `vns_threshold0`
- `fixed_fleet_bks`
- `rotated_sweep8`

Large-only follow-up:

- `10` AGS cases, seed `0`
- `baseline` versus `rotated_sweep8`

## Result

Recommended external hypothesis seed: `rotated_sweep8`.

Patch behavior:

- Adds `SWEEP_MULTI_STARTS = 8`.
- Refactors sweep route construction into `_sweep_solution_for_order()`.
- Runs sweep construction from up to `8` angular offsets and returns the
  lowest-cost feasible sweep solution.

Pilot matrix paired result:

| candidate | pairs | wins | ties | losses | total distance delta | mean gap delta | mean runtime delta | judgment |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `destroy160` | 27 | 0 | 27 | 0 | `0` | `0.000` pp | `+0.736s` | Reject: no quality gain and slower. |
| `vns_threshold0` | 27 | 1 | 18 | 8 | `+624` | `+0.267` pp | `-0.146s` | Reject for quality. |
| `fixed_fleet_bks` | 27 | 0 | 21 | 6 | `+156` | `+0.699` pp | `-0.059s` | Evaluation-mode idea, not an optimizer. |
| `rotated_sweep8` | 27 | 3 | 23 | 1 | `-8,978` | `-0.234` pp | `-0.084s` | Weak positive signal, driven by large sweep. |

AGS large-only follow-up:

| candidate | pairs | wins | ties | losses | total distance delta | mean gap delta | mean runtime delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| `rotated_sweep8` | 10 | 7 | 3 | 0 | `-61,847` | `-1.184` pp | `+0.151s` |

## Interpretation

This is a useful external-control seed for the large construction fallback, not
a solution to the main X-subset ALNS gap. It improves AGS construction-only
instances without feasibility regression, but AGS gaps remain extremely high
and route-count comparability remains unresolved.

Before any Scion replay or default VRP solver change, the candidate needs a
broader no-LLM validation matrix:

- all AGS cases and a larger X/A/P regression set;
- multiple seeds;
- explicit route-count / benchmark-feasibility stratification;
- longer runtime settings where ALNS/VNS actually run;
- separate evaluation of `fixed_fleet_bks` as a comparability mode, not as a
  distance-improving candidate.

This result is external hypothesis material only. It must not be counted as
Scion Protocol evidence or Decision input.
