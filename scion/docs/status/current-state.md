# Scion v0.4 Current State

*Last updated: 2026-07-16*

Read `scion/TASK.md` first. Use
`scion/design/scion-architecture-v3.md` as the architecture tie-breaker.

## Operational State

Fresh four-round R8 is running at
`/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r8-4r-gpt56sol-20260716T002051Z-claw`.
It uses the clean detached runtime
`/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-4a42ee3f` at
exact pushed commit `4a42ee3f98bed4cde90e4a9be54fe79aefe5585d`, with
`gpt-5.6-sol / direct_v3`, no resume source, and no force controls. Guarded
readiness and the wrapper-owned completion preflight passed before campaign
execution. Poll it observationally at low frequency and do not relaunch or
retry it in place.

The preceding R7 root ending `20260715T232619Z-claw` is terminal and read-only.
It requested four fresh generative rounds but completed only the first 32-pair
screening matrix before a canonical feedback persistence exception stopped the
wrapper. Postrun classifies it as `valid_but_incomplete`; effective completed
rounds are zero. Champion v1 is unchanged and no candidate was promoted.

The prepare-only roots ending `20260715T175626Z-claw` and
`20260715T193404Z-claw` were never launched and are superseded. The latter
proved that a second resume copied both candidate metadata files but lost the
inherited index held in the source root's outer snapshot. Do not start either
superseded root.

Do not resume or relaunch R4, R5, R6, either completed validation, the frozen
root, or R7 in place. Do not use R6's round-2 v2 artifact alone to reconstruct
the candidate. The R6 and R7 candidate paths are terminal. R8 is the sole live
experiment.

## R6 Identity

- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-causal-feedback-r6-2r-gpt56sol-20260715T153632Z-claw`;
- campaign:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-causal-feedback-r6-2r-gpt56sol-20260715T153632Z-claw/campaign`;
- runtime checkout:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-56ba4851`;
- exact runtime commit:
  `56ba4851c92ef8e925a5d5e368d988a138c80286`;
- model/runtime: `gpt-5.6-sol / direct_v3`;
- branch id: `ccc5d6df-642e-4f78-adc3-46d15b1b99ac`;
- branch state/status: `ready_validate / clean`;
- current and last-clean code hash:
  `0d9c2ce5cd62dd88c4666fcfed7a6ef14001a07caf171a6af346c74c4706535a`;
- champion: v1, unchanged;
- data identity: 81 files, digest
  `ca7e470ec8d1f3569a690d10df5a170c4994108c71fecf5aa1a7a76b42630743`.

Wrapper and campaign exits are `0`; requested/effective/evaluated rounds are
`2/2/2`; all are screening. Provider accounting is exactly `2H/2C`, four
successful durable attempts, retry/replacement=`0`. Formal pairs are `64/64`
valid with no candidate, champion, solver, Contract, Verification, Canary, or
infrastructure failure. Postrun readiness is 28 `ok`, 3 optional problem-owned
`skipped`, and no failure.

## R6 Scientific Result

### Round 1

The agent changed `destroy_repair.py` and `scheduler.py` to make regret repair
route-cap-aware and mildly noise-perturbed.

- case W/L/T: `0/4/4`;
- pair W/L/T: `9/16/7`;
- median/CI: `-3.25 / [-9.25,0]`;
- Decision: `continue_explore / SCREENING_FAIL_WIN_RATE`;
- route-limit: candidate/champion `32/98`;
- repair-error: candidate/champion `5/0`;
- fresh runtime median ratio: `1.0021`.

The mechanism reduced route-cap rejection but did not improve final quality.

### Round 2

H2 received exactly one complete R1 observation with all eight case rows, 32
pair rows, objective/CI/runtime facts, route-limit `-66`, repair-error `+5`,
and verified current source. It explicitly used the negative result and moved
to a different mechanism: capacity-feasible swap-star in `local_search.py`.
C2 exercised two ordered same-file `exact_replace` edits successfully.

The evaluated candidate is cumulative R1 repair plus R2 swap-star:

- case W/L/T: `5/1/2`;
- pair W/L/T: `20/11/1`;
- median/CI: `+3.5 / [-11,12]`;
- Decision: `queue_validate / SCREENING_PASS`;
- statistical status: `uncertain`;
- X-n110-k13 median: `-55`; CMT4 median: `-11`;
- ALNS iterations: `1857 -> 789`;
- initial VNS: `25639 -> 75078 ms`;
- embedded VNS: `778603 -> 798764 ms`.

All round-2 champion results were cached, so comparative runtime status is
`insufficient` and no runtime-ratio conclusion is allowed. The search-allocation
shift is descriptive risk that fresh validation must resolve.

## R6 Artifact Caveat

R6's live branch workspace is internally correct, but its old v2 R2 artifact is
not cumulative:

- declared base: `champions/champion_v1`;
- stored R2 files: only `local_search.py`;
- declared code hash: cumulative `0d9c2ce5...`;
- champion plus stored R2 patch hash: `0cc21753...`;
- missing inherited files: `destroy_repair.py`, `scheduler.py`.

The old postrun `git apply --check` accepted this incomplete artifact. Treat the
R6 report's formal-integrity check as superseded by the explicit audit. The
exact candidate remains safely available through the complete campaign
workspace.

## Exact Validation Identity and Result

- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-r6-r2-exact-validation-1r-gpt56sol-20260715T180743Z-claw`;
- campaign: `<root>/campaign`;
- runtime checkout:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-5a441e4`;
- runtime commit: `5a441e4488cc2d6d19ae7c92878ffb3864976e53`;
- branch/hypothesis: `ccc5d6df... / 2a988064...`;
- branch state/status: `validating_expand / clean`;
- candidate hash: `0d9c2ce5...6535a`, unchanged;
- champion: v1, unchanged;
- data identity: 81 files, `ca7e470e...30743`.

The one requested validation round completed with `32/32` valid fresh-runtime
pairs and no candidate/champion/infra failure. Current-invocation H/C/provider/
trace deltas are all zero; copied cumulative totals must not be attributed to
this invocation. Postrun readiness is 28 `ok`, three optional `skipped`, and no
failure.

- case W/L/T: `6/1/1`;
- pair W/L/T: `25/5/2`;
- median/CI: `+7.75 / [0,77]`;
- runtime ratio/delta: `1.0111 / +287.5 ms` across 32 fresh pairs;
- Decision: `expand_validation / VALIDATION_EXPAND_HIERARCHICAL_UNCERTAIN`.

The candidate is promising but unvalidated. `tai150a` loses by median `-84.5`;
ALNS iterations fall `1202 -> 604`, while initial VNS time rises
`138836 -> 299320 ms`. Formal validation has no swap-star-specific telemetry,
so neither gains nor losses can yet be causally assigned to that operator.

## Expanded Validation Identity and Result

- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-r6-r2-expanded-validation-1r-gpt56sol-20260715T201008Z-claw`;
- campaign: `<root>/campaign`;
- runtime checkout:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-b6c214a`;
- runtime commit: `b6c214a1046ea9a4ae14fccbfea8d65d5ee6e208`;
- branch/hypothesis: `ccc5d6df... / 2a988064...`;
- branch state/status: `ready_frozen / clean`;
- validation expand count: `1`;
- candidate hash: `0d9c2ce5...6535a`, unchanged;
- champion: v1, unchanged;
- data identity: 81 files, `ca7e470e...30743`.

The one requested expanded-validation round is complete and valid. Wrapper,
campaign, postrun reports, and postrun readiness all exited zero. SQLite
integrity is `ok`; postrun execution-outcome integrity allows algorithm
conclusions. The copied H/C transitions and four trace files are byte-identical
to the source, so current-invocation H/C/provider/trace deltas are all zero.
The repaired resume union retains both inherited candidate rows with exact
metadata coverage; the current live candidate index is absent.

- cases/seeds: 12 validation cases with `[47,53,71,83]`;
- pairs: `48/48` attempted and valid, no candidate/champion failure;
- case W/L/T: `8/2/2`;
- pair W/L/T: `33/13/2`;
- median/CI: `+6.5 / [-7.25,47.75]`;
- fresh runtime ratio/delta: `1.0118 / +367.5 ms`;
- Decision:
  `queue_frozen / VALIDATION_EXPAND_EXHAUSTED_MARGINAL_PASS`.

This is a marginal pass to frozen, not promotion or statistical certainty.
X-n120, X-n157, and X-n190 dominate the gains; F-n72 and tai150a regress and
tai75d changes sign across seeds. Candidate initial VNS time is `164.8%`
higher while ALNS iterations are `44.9%` lower than champion. Formal
`mechanism_evidence` is empty, so the outcome cannot be uniquely attributed to
swap-star.

## Frozen Evaluation Identity and Result

- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-r6-r2-frozen-evaluation-1r-gpt56sol-20260715T213106Z-claw`;
- campaign: `<root>/campaign`;
- source: the terminal expanded-validation campaign above;
- runtime checkout:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-a369112d`;
- runtime commit: `a369112d41a4da952f3751a53dedee7821125b48`;
- branch/hypothesis: `ccc5d6df... / 2a988064...`;
- terminal branch state/status: `abandoned / abandoned`;
- candidate hash: `0d9c2ce5...6535a`, unchanged;
- champion: v1, unchanged;
- data identity: 81 files, `ca7e470e...30743`.

The one requested frozen round is terminal, complete, and valid as an
orchestration run. Wrapper, campaign, postrun reports, and readiness exited
zero; SQLite integrity is `ok`; canary passed. Current-invocation H/C/provider/
trace/formal-candidate deltas are all zero, the inherited two-row ownership
index is unchanged, and the candidate archive recomputes to the exact 11-file
hash.

The eight cases were deterministic evenly spaced selections from the 12-row
frozen manifest, not its first eight rows:

- 60s: X-n139-k10, X-n204-k19;
- 90s: X-n251-k28, X-n327-k20, X-n401-k29;
- 120s: X-n573-k30, X-n641-k35, X-n1001-k43;
- seeds: `[61,67,89]`.

Formal outcome:

- attempted/valid/failed: `24/22/2`;
- recorded candidate/champion failures: `0/2`;
- case W/L/T: `5/0/3`;
- valid-pair W/L/T: `13/1/8`;
- median/CI: `+81.5 / [0,337]`;
- fresh runtime ratio/delta: `1.00818 / +847 ms`;
- Protocol:
  `fail / INCOMPLETE_EVIDENCE + CHAMPION_RUNTIME_FAILURE`;
- Decision: `abandon / INCOMPLETE_RUNTIME_EVIDENCE`.

The valid evidence is positive on X-n139 through X-n401 and tied on X-n573,
X-n641, and X-n1001. It is promising partial evidence, not a frozen pass or a
promotion result. X-n401 seed61 champion ended at `105.288s` under a 90-second
limit plus 15-second runner grace. X-n1001 seed61 crossed the 120+15 boundary
on both independently executed sides. All 18 side runs in the 120-second tier
exceeded the nominal scientific limit; the other 16 happened to serialize
within grace.

The root cause is problem-owned baseline time control: the declared 80%
internal search window was enforced only by outer scheduler checks, while
initial VNS saw the full subprocess clock and O(n^2)-to-O(n^3) neighborhood
loops polled only at coarse outer boundaries. The runner watchdog and frozen
gate worked fail-closed and must not be relaxed.

## R7 Stopped Root

- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r7-4r-gpt56sol-20260715T232619Z-claw`;
- campaign: `<root>/campaign`;
- runtime checkout:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-3dc0aee4`;
- runtime commit: `3dc0aee4d2b65375e1c4728e82c935bc73856c95`;
- model/runtime: `gpt-5.6-sol / direct_v3`;
- requested/effective rounds: `4/0`;
- provider activity: exactly `1H/1C`, both successful, retry/replacement zero;
- wrapper exit: `1`, `exception:ValueError`;
- postrun validity/completeness: `valid_but_incomplete / incomplete`;
- champion: v1, unchanged.

R7 H1 selected a substantive scheduler mechanism: joint adaptive weights for
destroy-repair operator pairs instead of independent marginals. C1 changed the
main path correctly but left `destroy_weights`, `repair_weights`, `d_idx`, and
`r_idx` in the `repair_error`, `infeasible`, and `route_limit` branches.
Formal screening finished `32/32` attempted with `22` valid objective pairs,
`10` candidate `NameError` failures, and zero champion failure. Valid-only pair
W/L/T was `10/7/5`; Protocol failed screening and Decision abandoned for
`CANDIDATE_RUNTIME_FAILURE`. This selectively incomplete evidence is not an
algorithm-quality result.

After that correct decision, canonical screening persistence asserted
`valid_pairs == len(pair_feedback)` and crashed. Candidate-only failures are
intentionally synthetic loss feedback, so R7's correct invariant was
`22 + 10 == 32`. Champion/shared/missing-output invalid rows remain excluded.
The stopped root must remain read-only and must not be presented as a
four-round campaign.

The shared deadline repair did hold in R7: the formal matrix used 30/45-second
case limits and had no champion timeout, watchdog failure, or infrastructure
failure. The candidate exceptions are entirely attributable to the incomplete
generated edit.

## Current Runtime Repair

Branch: `v0.4-dev`.

The formal-artifact, replay, feedback, protocol-projection, postrun, and
multi-hop resume repairs are pushed through `a369112d`. The current worktree
adds the frozen report and two pre-generative repairs:

- one atomic current/latest/per-stage branch protocol evidence projection;
- validation/frozen continue and frozen-promotion lifecycle coverage;
- transitive inherited formal-candidate ownership flattening in a dedicated
  launcher module;
- canonical row/ref/metadata identity validation, exact metadata coverage, and
  snapshot size/SHA binding before launch;
- inherited/live separation so old candidates remain cumulative lineage and a
  new invocation's live index remains current-only;
- exact validation terminal report;
- expanded-validation terminal report;
- frozen-evaluation terminal report;
- compact `TASK.md` and this resume document;
- focused multi-hop, conflict, tamper, legacy, and omitted-row tests.

The CVRP baseline now wraps the existing `BASELINE_TIME_FRACTION=0.80` as an
absolute local deadline and exposes the tighter of that deadline and the outer
runner time. Expensive two-opt, relocate, swap, or-opt, and two-opt-star inner
scans poll it cooperatively and return the current valid incumbent. A real
X-n1001 seed61 probe at a 30-second scientific limit returns feasible with exit
`0` in `23.78s`, with construction `20.745s` and initial VNS `2.522s`.

Later-stage champion/shared evidence-acquisition failure now remains a
Protocol fail but becomes durable `BLOCKED_INFRA` before Decision. Its raw
partial-evidence ref is preserved, the pre-block stage survives process
restart, and only the existing explicit operator event may resume it. There is
no automatic retry. Candidate-only runtime failure remains a hard abandon.
Two independent timeouts are exposed as `dual_runtime_failure` rather than a
shared-process crash.

The R7 repair worktree additionally contains:

- `V1b_undefined_names`, a stdlib `symtable` check over complete primary and
  additional candidate modules between syntax and interface verification;
  R7 replay rejects exactly its four stale names, while current CVRP sources
  scan without false positives;
- corrected canonical screening accounting:
  `len(pair_feedback) == valid_pairs + candidate_failed_pairs`, with exact
  W/L/T reconciliation and existing failure-side semantics retained;
- focused tests for mixed and candidate-only failures, champion/shared and
  missing-output exclusions, and mismatch fail-closed behavior;
- the R7 terminal analysis report.

Nonblocking P2 debt remains visible: construction and destroy/repair do not
poll inside every internal loop, although they now see the bounded context and
the maximum-scale compliance probe returns within the window. The explicit
deadline-context telemetry proxy must also be extended if a future baseline
module starts using another context API.

The resume/lineage/launcher slice passes `47`, the complete unit suite passes
`724`, and the standard Scion suite passes `1971` with `1` skipped. The merged
R7 verification/projection set passes `78`; the focused deadline/lifecycle/
protocol set passes `81`. Independent reviews found no P0/P1 in either R7
repair and agree the runner grace and frozen gate must remain unchanged.

Excluded and preserved:

- tracked user change: `scion/docs/v0.4-measurement-readiness.md`;
- unrelated untracked historical/future docs shown by `git status`.

## Immediate Resume Actions

1. Poll R8 observationally at low frequency, normally every three minutes.
2. At terminal, audit requested/effective typed rounds, exact H/C/provider/retry
   accounting, cumulative source/hash continuity, Protocol/Decision sequence,
   runtime compliance, and postrun integrity.
3. Analyze every durable observation and repair only evidence-backed framework
   defects; do not add automatic retry, semantic budgets, truncation, or a
   heavier gate.
4. Expand to a separate clean eight-round root only if four rounds still leave
   adaptation or reproducibility unresolved.

## Four-Round Prelaunch Checks

- current branch is exact with origin and the runtime checkout is detached,
  clean, and pinned to the new pushed commit;
- the root is fresh: no resume source, copied campaign, inherited branch, or
  historical formal-candidate index;
- `launch.env` records `ROUNDS=4`, `TIME_LIMIT_SEC=30`, model
  `gpt-5.6-sol`, runtime `direct_v3`, correct base URL, and only the proxy
  key environment-variable name;
- completion preflight is enabled and passes without making a durable proposal
  attempt;
- generated `run.sh` hash equals the launch and prepared-manifest anchors;
- data identity remains `ca7e470e...`;
- no force surface/action/target, retry control, semantic budget, truncation,
  or automatic expansion is present;
- one manual guarded launch follows one successful proxy preflight.

## Runner Notes

Server `claw`:

- repo: `/home/clawd/research/or-autoresearch-agent`;
- Python: `/home/clawd/miniconda3/envs/claw/bin/python`;
- use for focused tests and one experiment at a time.

WSL `scion` remains the large/concurrent runner only after a fresh connectivity
and preflight check.

Proxy key handling: `SCION_SHARED_PROXY_KEY` is the local proxy credential;
inject the value through process environment only. Do not print it, persist it,
or place it in argv.

## Pointers

- Active task: `scion/TASK.md`
- V3 architecture: `scion/design/scion-architecture-v3.md`
- Direct-runtime addendum:
  `scion/design/scion-architecture-v3-v0.4-direct-runtime-addendum.md`
- R5 terminal report:
  `scion/docs/experiments/v0.4/v04-cvrp-direct-causal-feedback-r5-postrun-20260715.md`
- R6 terminal report:
  `scion/docs/experiments/v0.4/v04-cvrp-direct-causal-feedback-r6-postrun-20260715.md`
- R6-R2 exact validation report:
  `scion/docs/experiments/v0.4/v04-cvrp-r6-r2-exact-validation-postrun-20260715.md`
- R6-R2 expanded validation report:
  `scion/docs/experiments/v0.4/v04-cvrp-r6-r2-expanded-validation-postrun-20260715.md`
- R6-R2 frozen evaluation report:
  `scion/docs/experiments/v0.4/v04-cvrp-r6-r2-frozen-evaluation-postrun-20260715.md`
- R7 stopped analysis:
  `scion/docs/experiments/v0.4/v04-cvrp-direct-longitudinal-r7-stopped-analysis-20260715.md`
- Multi-hop lineage repair report:
  `scion/docs/experiments/v0.4/v04-resume-formal-candidate-lineage-repair-20260715.md`
