# Independent VRP Research Agent L Result - 2026-06-16

## Boundary

This is an external-control plain Codex VRP baseline research result. It is not
a Scion campaign, not Scion Protocol evidence, not promotion evidence, and not
an accepted solver change. The agent was explicitly forbidden from reading
Scion design, task, status, audit, planning, prompt, or experiment artifacts.

## Agent

- Subagent: `Newton`
- Agent id: `019ecded-8a24-7a03-b64b-8b1929c9af49`
- Artifact root:
  `/home/clawd/research/vrp-independent-codex-research/phase-l-20260616`

## Artifacts

Required artifacts are present:

- `research_journal.md`
- `rejected_candidates.md`
- `experiment_results.jsonl`
- `summary.md`
- `README.md`

No `candidate.patch` was retained. The implemented but rejected scratch edits
remain outside the main checkout:

- `/home/clawd/research/vrp-independent-codex-research/phase-l-20260616/candidate/src/local_search/operators.py`
- `/home/clawd/research/vrp-independent-codex-research/phase-l-20260616/candidate/src/solver.py`

## Candidate

The only implemented candidate was an intra-route Or-opt extension inside VNS:
same-route 1/2/3-customer segment relocation. The edit was localized in the
scratch `candidate/` copy and was not applied to the main repository.

## Experiment Matrix

- Primary: `7` real CVRPLIB cases x `3` seeds x `1.0s`, `21` paired rows.
- Follow-up sanity: `3` outside real CVRPLIB cases x `3` seeds x `1.0s`,
  `9` paired rows.
- Combined machine-readable records: `30` rows in `experiment_results.jsonl`.

Primary cases:

- `cvrplib/A/A-n45-k6.vrp`
- `cvrplib/B/B-n50-k7.vrp`
- `cvrplib/E/E-n76-k10.vrp`
- `cvrplib/P/P-n55-k10.vrp`
- `cvrplib/F/F-n72-k4.vrp`
- `cvrplib/M/M-n101-k10.vrp`
- `cvrplib/X/X-n101-k25.vrp`

Follow-up cases:

- `cvrplib/A/A-n60-k9.vrp`
- `cvrplib/B/B-n68-k9.vrp`
- `cvrplib/P/P-n76-k4.vrp`

## Metrics

| Slice | W/T/L | Mean delta | Median delta | Mean delta percent |
|---|---:|---:|---:|---:|
| Primary | `5/11/5` | `-0.142857` | `0.0` | `-0.035658%` |
| Follow-up sanity | `2/1/6` | `+5.666667` | `+6.0` | `+0.596152%` |
| Combined | `7/12/11` | `+1.6` | `0.0` | `+0.153885%` |

Negative delta means candidate better. The combined result is slightly worse
than baseline, and the outside-case sanity check is clearly negative.

Constraint checks:

- Subprocess status errors: `0`
- CVRP feasibility failures: `0`
- Candidate route-count regressions versus baseline: `0`
- Benchmark feasibility regressions where baseline was benchmark-feasible: `0`
- Candidate benchmark-infeasible rows: `6`
- Baseline benchmark-infeasible rows: `9`

Some selected cases exceeded BKS route count in both baseline and candidate, so
benchmark feasibility was not uniformly satisfied by the baseline itself. This
did not create a candidate route-count regression.

## Decision

Reject this candidate. It is not worth broader no-LLM replay, Scion fixed
replay, or any default solver change. The first matrix was neutral and the
outside-case sanity check was negative.

The control remains useful as process evidence: in this isolated plain-Codex
cycle, the agent produced a localized mechanism, tested it on real cases, and
correctly rejected it rather than retaining a weak or overfit patch.
