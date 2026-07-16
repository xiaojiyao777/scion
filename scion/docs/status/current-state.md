# Scion v0.4 Current State

*Last updated: 2026-07-16*

Read `scion/TASK.md` first. Use
`scion/design/scion-architecture-v3.md` as the architecture tie-breaker.

## Operational State

Fresh eight-round R10 is live at
`/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r10-8r-gpt56sol-20260716T063211Z-claw`
with wrapper PID `2848393`. Its clean detached runtime is
`/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-c936cde4` at
exact pushed commit `c936cde41d746c9cbfcd308bae84ba54d85c7f4a`. It uses
`gpt-5.6-sol / direct_v3`, `ROUNDS=8`, and the 30-second scientific solver
subprocess fallback. It is fresh: no resume, force controls, retry, semantic
budget, or truncation. Completion preflight is authenticated, HTTP `200`, and
nonempty. The launcher stores only `SCION_SHARED_PROXY_KEY` as the environment
variable name; no key value is persisted. Do not start another generative root
while R10 is live.

H1/C1 are terminal and H2 is in formal screening. H1 implemented a real
ejection-chain repair in `destroy_repair.py` and `scheduler.py`; H/C were each
single-attempt and all `32/32` pairs were valid with zero candidate/champion
failure. The algorithm was strongly negative: pair `1/21/10`, case `0/5/3`,
median `-14.25`, CI `[-48.75,0]`, actual ALNS iterations `69/1665`, and
ejection-chain `30 attempts / 0 accepted`. Protocol failed only
`SCREENING_FAIL_WIN_RATE`; Decision `continue_explore` committed. Formal v3
replay now writes the correct relative
`base_workspace_ref=champions/champion_v1`, with complete identity and matching
current/replay/verified/executable hashes.

H2 explicitly received H1's route-limit and throughput evidence. It targets
`local_search.py` with candidate-list incremental inter-route VNS and bounded
CROSS exchange; H2/C2 are again single-attempt and verified at `65f379...`.
Formal evaluation is pending. The key audit is whether H2 causally removes the
throughput bottleneck or only stacks local search while retaining H1's bad
ejection repair.

The explicit R9 diagnostic continuation is terminal and read-only at
`/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r9-cont1-3r-gpt56sol-20260716T042653Z-claw`.
It uses the clean detached runtime
`/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-db971c57` at
exact pushed commit `db971c57b7ed5f7ac79c88f151b182b11e2bb816`, with
`gpt-5.6-sol / direct_v3`, no force controls, retry, semantic budget, or
truncation. It is a distinct copied-root invocation from R9's verified clean
H1 branch and is diagnostic, not a fresh formal-root control. It completed its
requested `3/3` typed rounds with 96/96 valid pairs and
`requested_rounds_completed`; campaign status is `valid / complete`.

Together with fresh R9 H1, the cumulative canonical trajectory has four
screening rounds. H3's ejection chain collapsed ALNS throughput; H4 replaced it
with a granular three-route cycle and partially restored throughput; H5 moved
to promise-gated embedded VNS and restored actual ALNS iterations to
`8809/1678`, but all three continuation rounds still failed only
`SCREENING_FAIL_WIN_RATE`. Champion v1 is unchanged. All four Decision intents
are committed, verified/last-clean/workspace identities agree, and staging and
promotion journals are empty.

The historical outer wrapper remains at effective exit `64` because its
original postrun readiness failed `formal_candidate_diff_integrity`. The
current repair now resolves the three existing opaque v3 champion refs only
through a campaign-local champion bound independently to the editable identity
manifest and full snapshot hash. A read-only rebuild passes that formal check
for all three candidates with `apply_check` and successful materialization;
the campaign digest remains
`02b2b2171598e1166ce2fe4728de326e73b51753f24a4a5efb755a5fe4d6315d`.
`delegation_ready=true`; `current_run_analysis_ready=false` only because the
immutable historical wrapper failure status and markers remain required
checks. Do not rewrite them. This does not invalidate the 96 solver pairs or
completed Protocol/Decision transactions.

Fresh four-round R9 is terminal at
`/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r9-4r-gpt56sol-4r-gpt56sol-20260716T034629Z-claw`.
It completed one valid screening round, then stopped when H2 C2 was correctly
rejected by V1b. R1's related-customer pair repair produced case `3/2/3`, pair
`9/11/12`, median `0`, CI `[-5.5,4]`, and
`continue_explore / SCREENING_FAIL_WIN_RATE`. H2 saw the complete Protocol and
outer Decision and changed to cross-route local search, but its code left two
undefined names. Wrapper/postrun exited zero; status is
`valid_but_incomplete / incomplete`; champion v1 is unchanged.

R9 and its continuation accept the R8 transactional repair. The rejected H2 tree exists only in
the archive; the durable workspace and all typed clean identities agree on H1
hash `4a9771a9...`; candidate staging and promotion journals are empty. Formal
and rejected-attempt accounting, Decision completion, and postrun reports also
agree. Do not resume R9 or its continuation in place.

R8 remains terminal and must never be resumed. Its rejected C2 polluted the
physical durable workspace while SQLite retained R1's clean identity. That P0
defect is repaired and live-accepted by R9 at `db971c57`.

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
root, R7, R8, or R9 in place. Do not use R6's round-2 v2 artifact alone to
reconstruct the candidate. R10 is the only live experiment.

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

## R8 Stopped Root

- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r8-4r-gpt56sol-20260716T002051Z-claw`;
- runtime commit: `4a42ee3f98bed4cde90e4a9be54fe79aefe5585d`;
- requested/effective typed rounds: `4/1`;
- provider activity: exactly `2H/2C`, all successful, retry/replacement zero,
  null transport ceiling, and no truncation evidence;
- wrapper/postrun exits: `0/0`;
- status: `valid_but_incomplete / incomplete`;
- stop: `execution_research_rejected`;
- champion: v1, unchanged.

R1 implemented route-cap-aware regret repair with a bounded depth-2 ejection
chain. Screening was fully valid: case `1/1/6`, pair `4/8/20`, median `0`, CI
`[-0.5,0]`, Protocol `SCREENING_FAIL_WIN_RATE`, and Decision
`continue_explore`. The descriptive candidate/champion route-limit counts
`0/89` are `hypothesis_attribution=unbound` and cannot support causal claims.

H2 received R1 objective, case, pair, and mechanism observations plus the
Protocol failure; it demonstrably used that evidence and changed direction to
inter-route cross-exchange. The old next-H projection omitted outer Decision
`continue_explore`, so this proves partial longitudinal carryover rather than
complete feedback fidelity. There is no evidence that the missing Decision
caused C2's editing error. C2 did not complete that mechanism: it referenced
`_cross_exchange` and `_or_opt_1` without definitions after an incorrect
same-file replacement. V1b correctly rejected it before Protocol. R2 has no
formal algorithm result.

The rejection exposed a P0 durable-workspace defect. Physical workspace hash
was failed C2 `7c3b0905...`; the final card's last-clean hash and SQLite clean
hash were R1 `209d40d...`, while the card current hash remained C2. Resume
would have reused the polluted tree without hashing it. The repair uses
isolated unverified staging plus a typed verified-candidate commit, a retained
backup, and a two-phase `prepared -> committed` promotion journal. Reopen rolls
back when persisted identity is still the base, completes promotion when the
persisted and physical candidate plus typed commit agree, and fails closed on
all conflicting combinations. A `rolled_back` journal retains the exact H2
owner until its uncommitted status is durably terminalized; a HypothesisStore
write failure therefore remains recoverable on the next reopen. Rejection
cleanup restores the clean identity even if hypothesis-status persistence
fails.

R8 also exposed a P1 report projection defect. Typed lineage had one
`verification_fail`, but legacy summary/failure reports returned zero. The
corrected read-only projection exposes stable `failed_check`, `failure_code`,
and `failure_detail` while leaving pre-Decision `decision_reason` null. Contract
opportunities include all gate outcomes; Verification opportunities exclude
Contract-failed attempts. For R8 both denominators are `2`: Contract intercept
rate is `0.0`, Verification intercept rate is `0.5`, and the sole failure code
is `V1b_undefined_names`. Stored R8 reports remain untouched as evidence of the
original false negative.

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

The current R8 repair worktree additionally contains:

- isolated candidate workspaces with verified-only promotion and rejected
  staging cleanup;
- typed verified-candidate ownership, a retained backup, and a two-phase
  promotion journal that rolls back or completes only provable identities;
- an exact pending-evaluation continuation with `0H/0C`, screening-only
  Protocol/Decision, and no H3 generation;
- active-H typed ownership precedence, with strict legacy fallback only when no
  typed marker exists;
- transactional stale reconciliation from a newly locked champion into
  isolated staging, with content-addressed `commit_kind=reconcile` ownership,
  pre-Protocol typed Contract/Verification rejection, and exact recovered
  screening at `0H/0C`;
- persisted clean-hash restoration, reopen-time physical/executable identity
  validation, and rejection rollback despite hypothesis-status write failure;
- canonical H, lineage, base, patch, promotion-journal, backup/candidate/durable
  identity binding before destructive recovery;
- typed Decision completion for pending screening and any-stage terminal-H
  Decisions, atomically committing Branch + H + marker + typed decision fact;
- startup Decision convergence before branch/reconcile restore, plus
  deterministic ABANDON archive receipts that recover a partially deleted
  workspace without duplicate archives;
- typed Contract/Verification failure projection with separate gate
  opportunities and no synthetic pre-Decision reason;
- outer Decision projection into canonical next-H history;
- an association-only interpretation constraint for CVRP `unbound` mechanism
  telemetry;
- target guidance requiring nested destroy/repair searches to propagate and
  poll the existing monotonic deadline context;
- the R8 terminal analysis report.

Nonblocking P2 debt remains visible: process death after local Protocol return
but before Decision-intent preparation, and ordinary nonterminal retained
transitions, use consistent at-least-once Protocol replay; typed recovery does
not recreate every rich experiment/DecisionFeatures projection after that
crash. Target-first source projection remains an architectural simplification,
and strict postrun acceptance still lacks a cross-artifact count comparison.
Construction and destroy/repair also do not poll inside every internal loop,
although proposal guidance now requires the existing monotonic deadline
context and the maximum-scale compliance probe returns within the window. The
explicit deadline-context telemetry proxy must be extended if a future
baseline module starts using another context API.

The final affected transaction/report/guidance review set passes `198`; the
current champion-ref repair focus passes `58`, and the correctly rooted
standard Scion suite passes `2040` with `1` skipped in `479.74s`. `compileall`
and `git diff --check` pass. The earlier merged R7 verification/projection set
passed `78`, and its focused deadline/lifecycle/protocol set passed `81`.

Excluded and preserved:

- tracked user change: `scion/docs/v0.4-measurement-readiness.md`;
- unrelated untracked historical/future docs shown by `git status`.

## Immediate Resume Actions

1. Monitor R10 H2 at low frequency without disturbing the live process.
2. Audit each completed R10 round for substantive code change, activation,
   objective/case/pair/mechanism evidence, throughput, Protocol, and Decision.
3. At terminal state, require end-to-end postrun wrapper/readiness acceptance
   and update the operating docs. R10 is reproducibility and longer-adaptation
   evidence; R9 already proves substantive algorithm editing.

## R9 Continuation Terminal Checks

- runtime checkout is detached, clean, and pinned to pushed commit
  `db971c57`;
- resume preparation quarantined copied terminal status/summary/exit files and
  flattened inherited formal-candidate ownership into the resume snapshot;
- the copied Branch is `EXPLORE`, schedulable, and physically/typed clean at
  H1 hash `4a9771a9...`;
- `launch.env` records `ROUNDS=3`, `TIME_LIMIT_SEC=30`, model
  `gpt-5.6-sol`, runtime `direct_v3`, the R9 resume source, and only the proxy
  key environment-variable name;
- no force surface/action/target, retry control, semantic budget, truncation,
  or automatic expansion is present;
- an independent completion probe immediately before the manual diagnostic
  launch returned authenticated HTTP 200 with nonempty content;
- current-invocation formal counters began at zero; copied H/C traces and DB
  history remain cumulative evidence and must not be counted as new calls;
- current-invocation requested/effective rounds are `3/3`, cumulative H/C calls
  are `5/5`, and no retry or replacement occurred;
- canonical screening history is unique at rounds 1 through 4;
- the repaired read-only postrun rebuild passes
  `formal_candidate_diff_integrity` for all three current-invocation candidates;
  whole-run readiness still records only the immutable historical wrapper
  status/marker failures, while delegation readiness is true.

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
- R8 stopped analysis:
  `scion/docs/experiments/v0.4/v04-cvrp-direct-longitudinal-r8-stopped-analysis-20260716.md`
- R9 stopped analysis:
  `scion/docs/experiments/v0.4/v04-cvrp-direct-longitudinal-r9-stopped-analysis-20260716.md`
- R10 inflight analysis:
  `scion/docs/experiments/v0.4/v04-cvrp-direct-longitudinal-r10-inflight-20260716.md`
- Multi-hop lineage repair report:
  `scion/docs/experiments/v0.4/v04-resume-formal-candidate-lineage-repair-20260715.md`
