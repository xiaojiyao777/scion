# Scion v0.4 Direct-Runtime Research Task

*Branch: `v0.4-dev`*
*Last updated: 2026-07-18*

This is the active task source. Read it with
`scion/docs/status/current-state.md`; use
`scion/design/scion-architecture-v3.md` as the architecture tie-breaker.
Chronology and large evidence tables belong in focused experiment reports.

## Objective

Close v0.4 only when the small direct V3 runtime demonstrates useful,
maintainable research behavior on both warehouse and CVRP:

```text
complete problem/current-source context
  -> one durable Hypothesis call
  -> structural Hypothesis Contract
  -> one durable Code call bound to approved H and complete SourceLedger
  -> structural Patch Contract
  -> Workspace -> Verification -> Protocol -> Safe Features -> Decision
```

Framework tests alone do not close v0.4. The completion matrix below separates
research-process, validated-effect, and retained-improvement claims so a
scientifically valid negative result is not mislabeled as a solver improvement.

## Non-Negotiable Boundaries

- V3 owns the architecture; the v0.4 direct-runtime addendum narrows obsolete
  retry/budget/context examples.
- LLM output is tainted. It cannot write Protocol verdicts, Decision inputs,
  scheduler state, or promotion state.
- CVRP/warehouse algorithm semantics stay problem-owned. Generic core owns
  lifecycle, contracts, lineage, replay identity, and safe data movement.
- Contract checks structure and approved-H/source binding; Verification checks
  executable correctness; Protocol owns comparative science; Decision maps the
  trusted verdict and hard safety flags deterministically.
- Normal candidates make exactly one H and one C call. Provider SDK retry is
  zero. Invalid H/C terminates that durable attempt.
- Do not add a Scion prompt/session/tool/file/item/token budget, content cap,
  top-k selection, truncation, automatic retry, semantic stop counter, or a
  heavier gate. The 30-second solver limit is a scientific subprocess limit.
- Do not force a research surface/action/target in open controls.
- Formal fresh roots use a clean exact pushed commit and one guarded wrapper
  launch. Diagnostic eval-only continuations use a distinct copied root and
  are never presented as fresh formal roots.
- Poll experiments observationally at low frequency, normally every three
  minutes. Polling must never trigger another provider attempt.
- Preserve user-owned `scion/docs/v0.4-measurement-readiness.md` and unrelated
  untracked documents.

## Accepted Runtime Contract

- One immutable `ProposalContextSnapshot` owns each provider request.
- H receives current problem facts, complete verified current source, and one
  canonical lossless record per visible screening observation.
- C receives one approved H and one complete SourceLedger. Multi-file and
  ordered same-file `exact_replace` edits retain source owner, provenance, and
  digest; stale or ambiguous composition fails closed.
- A single active scheduling branch is the v0.4 default. Screening evidence is
  durable, but code inheritance is controlled by typed candidate disposition:
  gate-failed code returns to its clean parent, provisional same-mechanism work
  may be refined, and a mechanism pivot starts clean. `queue_validate`
  re-evaluates the exact candidate without another H/C call.
- Proposal-only mechanism evidence is excluded from DecisionFeatures and
  gates. It may inform the next H but cannot manufacture causal certainty.
- Promotion remains atomic and requires complete formal evidence.
- H history may use a reversible normalized ledger to declare repeated schemas
  once while retaining every safe screening observation and pair. This is not
  truncation, top-k selection, summary substitution, or a context budget.

## Current Evidence

Warehouse's effective-research process is resolved, but retained improvement is
not proven. The direct loop generated substantive operators, adapted direction
from branch evidence, found a screening-positive cumulative candidate, expanded
it without a provider call, and correctly abandoned it on the locked validation
split. This proves iterative research, eval-only escalation, exact-candidate
identity, and negative lifecycle integrity; it is not a retained algorithm.
The remaining asset, attribution, and fixed-decomposition work is frozen in
`scion/docs/planning/v0.4/v0.4-warehouse-effective-research-closure-design-20260716.md`.

CVRP R4 proved two substantive evaluated algorithm rounds but both were
negative. R5 exposed an overly narrow one-change-object-per-file instruction;
the serial same-file typed-edit repair is pushed at `56ba4851` and R6 exercised
it live.

R6 is complete and valid:

- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-causal-feedback-r6-2r-gpt56sol-20260715T153632Z-claw`;
- exactly `2H/2C`, four successful attempts, retry=`0`;
- `64/64` valid screening pairs, no candidate/champion/infra failure;
- R1 route-cap-aware regret repair: case `0/4/4`, pair `9/16/7`, median
  `-3.25`, CI `[-9.25,0]`, `continue_explore`;
- H2 received the complete single R1 record plus verified current source and
  changed direction from repair tuning to local-search swap-star;
- cumulative R1+R2 candidate: case `5/1/2`, pair `20/11/1`, median `+3.5`,
  CI `[-11,12]`, `queue_validate`;
- exact branch code hash:
  `0d9c2ce5cd62dd88c4666fcfed7a6ef14001a07caf171a6af346c74c4706535a`;
- branch state: `ready_validate`; champion v1 unchanged.

The R2 signal was uncertain and heterogeneous. X lost `-55`; ALNS iterations
fell `1857 -> 789`; round-2 comparative runtime was unavailable because all
champion results were cached. The exact same candidate first completed a
fresh, disjoint eight-case validation in root
`v04-cvrp-r6-r2-exact-validation-1r-gpt56sol-20260715T180743Z-claw`:

- no new H/C/provider/trace activity;
- `32/32` valid pairs with fully fresh champion runtime;
- case `6/1/1`, pair `25/5/2`, median `+7.75`, CI `[0,77]`;
- runtime median ratio `1.0111` with 32 high-confidence pairs;
- `expand_validation / VALIDATION_EXPAND_HIERARCHICAL_UNCERTAIN`;
- branch `validating_expand`, candidate hash unchanged, champion v1 unchanged.

The repaired copied-state continuation then completed the preregistered
12-case expanded validation in root
`v04-cvrp-r6-r2-expanded-validation-1r-gpt56sol-20260715T201008Z-claw`:

- no new H/C/provider/trace or formal-candidate activity;
- `48/48` valid pairs with fully fresh champion runtime;
- case `8/2/2`, pair `33/13/2`, median `+6.5`, CI `[-7.25,47.75]`;
- runtime median ratio `1.0118`, median delta `+367.5 ms`, and `35/48`
  slower candidate pairs;
- `queue_frozen / VALIDATION_EXPAND_EXHAUSTED_MARGINAL_PASS`;
- branch `ready_frozen`, expand count one, candidate hash unchanged, champion
  v1 unchanged.

This is a marginal pass to an independent frozen holdout, not validation
certainty or promotion. Gains are concentrated on X-n120/X-n157/X-n190;
F-n72 and tai150a regress, tai75d is seed-sensitive, and the CI crosses zero.
Initial VNS time rises `+164.8%` while ALNS iterations fall `44.9%` relative to
champion. Formal mechanism evidence is empty, so do not causally attribute the
result to swap-star.

The exact candidate then completed its independent frozen continuation in root
`v04-cvrp-r6-r2-frozen-evaluation-1r-gpt56sol-20260715T213106Z-claw`:

- no new H/C/provider/trace or formal-candidate activity;
- deterministic evenly spaced frozen cases X-n139, X-n204, X-n251, X-n327,
  X-n401, X-n573, X-n641, and X-n1001 with seeds `[61,67,89]`;
- `24` attempted, `22` valid, and two invalid comparisons involving champion
  timeouts;
- on valid evidence, case `5/0/3`, pair `13/1/8`, median `+81.5`, CI
  `[0,337]`;
- Protocol `fail / INCOMPLETE_EVIDENCE + CHAMPION_RUNTIME_FAILURE` and
  Decision `abandon / INCOMPLETE_RUNTIME_EVIDENCE`;
- candidate hash and champion v1 unchanged; no promotion dossier.

This is promising partial evidence, not a frozen pass. The 120-second tier
systematically ran past its scientific limit, and the two failed pairs exposed
a shared baseline deadline defect. Do not rerun, extend, or reinterpret this
terminal root.

The fresh four-round R7 root
`v04-cvrp-direct-longitudinal-r7-4r-gpt56sol-20260715T232619Z-claw`
then completed only its first screening matrix before a core persistence
exception stopped the campaign:

- exactly `1H/1C`, no provider retry or replacement;
- substantive destroy-repair pair-weight hypothesis and implementation;
- `32/32` attempted, `22` valid, `10` candidate failures, and zero champion
  failures;
- the generated patch left four deleted marginal-weight names in three
  rejection branches, causing ten `NameError` fallbacks;
- Protocol correctly failed screening and Decision correctly abandoned for
  `CANDIDATE_RUNTIME_FAILURE`;
- canonical feedback then incorrectly asserted
  `valid_pairs == len(pair_feedback)` even though candidate-only failures are
  intentionally retained as synthetic screening losses;
- the correct R7 accounting was `22 valid + 10 candidate failures = 32 pair
  feedback rows`;
- wrapper exit `1`, postrun classification `valid_but_incomplete`, zero
  effective completed rounds, and no promotion.

R7 is a terminal diagnostic root, not a four-round scientific result. Its
common deadline behavior was healthy: formal 30/45-second rows produced no
champion timeout or watchdog failure. Do not resume or relaunch it.

Fresh four-round R8 is terminal and read-only:

- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r8-4r-gpt56sol-20260716T002051Z-claw`;
- clean detached runtime:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-4a42ee3f`;
- exact commit: `4a42ee3f98bed4cde90e4a9be54fe79aefe5585d`;
- requested/effective typed rounds: `4/1`;
- exactly `2H/2C`, four successful durable calls, no retry, replacement, or
  output ceiling; the transport ceiling is null and there is no truncation
  evidence;
- R1 implemented route-cap-aware regret repair with a bounded depth-2 ejection
  chain and completed `32/32` valid screening pairs;
- R1 case `1/1/6`, pair `4/8/20`, median `0`, CI `[-0.5,0]`, Protocol
  `SCREENING_FAIL_WIN_RATE`, Decision `continue_explore`;
- H2 received R1 objective, case, pair, and mechanism observations plus the
  Protocol failure, explicitly used that evidence, and moved to a materially
  different cross-exchange local-search mechanism; the old projection omitted
  outer Decision `continue_explore`, so this is partial longitudinal carryover,
  not complete feedback fidelity;
- C2 registered `_cross_exchange` without defining it and deleted the
  `_or_opt_1` header; V1b correctly returned
  `research_rejected / V1b_undefined_names` before Protocol;
- wrapper/postrun exits are zero, overall status is
  `valid_but_incomplete / incomplete`, and champion v1 is unchanged.

R8 exposed a P0 resume-safety defect: after the correct rejection, SQLite
retained the clean R1 hash, the final card retained failed-C2 as current, and
the physical durable workspace still contained failed C2. Never resume R8.
Candidate patches must be isolated until Verification succeeds, rejected
staging must be deleted and the clean identity persisted, and reopen must
recompute and compare physical/current/last-clean hashes. R8 also exposed a P1
legacy report false negative for typed `verification_fail`; a corrected
read-only query reports two gate outcomes, one V1b failure, and intercept rate
`0.5`.

The transactional repair is committed and pushed at
`db971c57b7ed5f7ac79c88f151b182b11e2bb816`. Fresh four-round R9 is terminal:

- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r9-4r-gpt56sol-4r-gpt56sol-20260716T034629Z-claw`;
- exact runtime: clean detached `db971c57`, `gpt-5.6-sol / direct_v3`;
- requested/effective typed rounds: `4/1`;
- exactly `2H/2C`, all successful, no retry or replacement;
- R1 implemented related-customer regret-2 pair insertion and completed
  `32/32` valid pairs with zero solver/fleet failure;
- R1 case `3/2/3`, pair `9/11/12`, median `0`, CI `[-5.5,4]`, Protocol
  `SCREENING_FAIL_WIN_RATE`, Decision `continue_explore`;
- H2 received the full R1 Protocol and outer Decision, changed direction to a
  cross-route 2-opt neighborhood, but C2 only registered the new name and
  deleted the `_two_opt_star` header;
- V1b correctly returned `research_rejected / V1b_undefined_names` before
  Protocol; wrapper/postrun exited zero and status is
  `valid_but_incomplete / incomplete`.

R9 accepts the transactional repair: rejected H2 exists only in its archive,
while the durable workspace, Branch current/last-clean, verified code, and
executable snapshot all remain H1 hash `4a9771a9...`; staging and promotion
journal directories are empty. The committed Decision intent, formal counts,
typed rejection, and legacy postrun projections agree. H1 is a valid negative
algorithm result; H2 is an implementation rejection, not an algorithm result.

The current addendum deliberately stops an invocation on any non-`EVALUATED`
outcome. Do not replace that with an unbounded internal loop or same-H repair
retry. The explicit, distinct diagnostic continuation is terminal at
`v04-cvrp-direct-longitudinal-r9-cont1-3r-gpt56sol-20260716T042653Z-claw`.
It copies only R9's clean durable campaign state and requests three new typed
Protocol rounds. It is not a fresh formal control. It completed `3/3` new
screening rounds with 96/96 valid pairs, no retry, and a unique cumulative
round-1-through-round-4 history.

The continuation proves longitudinal algorithm adaptation. H3 added an active
ejection chain but collapsed candidate/champion ALNS iterations to `422/1678`.
H4 removed it, installed a granular three-route cycle, and restored iterations
to `839/1678`. H5 moved from neighborhood design to promise-gated embedded VNS
and restored actual ALNS iterations to `8809/1678`, but objective quality still
failed: H3 pair `10/15/7`, H4 `8/15/9`, and H5 `10/15/7`; all Decisions were
`continue_explore / SCREENING_FAIL_WIN_RATE`. The generic cross-phase search
counter is not agent feedback; canonical mechanism evidence uses the correct
ALNS trace.

All continuation Decision intents are committed, verified/current/last-clean
identities agree, and candidate staging/journals are empty. Campaign status is
`valid / complete / requested_rounds_completed`. Historical outer wrapper
status remains `64` because its original postrun replay treated an opaque
stale-source champion ref as a relative path. The current repair makes future
producers require a verified campaign-local champion, adds identity-bound v3
compatibility for the three existing opaque refs, and keeps malformed, v1, v2,
missing, mismatched, or escaping refs fail-closed. A read-only rebuild now
passes `formal_candidate_diff_integrity` for all three new candidates with
`apply_check` and successful materialization; the campaign tree digest is
unchanged. Overall current-run readiness remains false only because the
terminal wrapper's historical failure status and markers are intentionally
preserved; delegation readiness is true. Do not rewrite those terminal
artifacts.

Fresh eight-round R11c is terminal and read-only at
`/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r11c-8r-gpt56sol-8r-gpt56sol-20260716T132422Z-claw`
with terminal wrapper PID `2892669`. It ran from clean detached runtime
`/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-56bc445d` at
exact pushed commit `56bc445d07b19587ecb8e4b763ab448c4ceb9115`, using
`gpt-5.6-sol / direct_v3`, `ROUNDS=8`, and the 30-second scientific solver
subprocess fallback. It is a fresh root: no resume, force controls, retry,
semantic budget, or truncation. Completion preflight is authenticated, HTTP
`200`, and nonempty. Only the `SCION_SHARED_PROXY_KEY` environment-variable
name is persisted. Wrapper, campaign, postrun rebuild, and strict readiness
exited zero, but the scientific status is `valid_but_incomplete`: four of eight
formal observations completed, then round 5 H3 failed light Verification with
`V1b_undefined_names` and typed `research_rejected` prematurely stopped the
campaign. R11c must not be resumed or backfilled.

The prospective-count/atomic-target fix passed: the expansion source stayed at
count zero until the completed Decision atomically committed count one, with no
owner mismatch or duplicate outcome. H1 route elimination never activated and
accumulated 1,540 empty selections; H2 SWAP* activated strongly and was broadly
positive, but on tai150a it extended initial VNS to about 46 seconds, produced
zero ALNS iterations, and lost all four seeds. Validation abandon is therefore
scientifically justified. H2 nevertheless inherited rejected H1 code, so its
effect is cumulative and not isolated. H3 used a clean branch and safe sibling
screening-only history, but one repairable code-closure rejection ended the
entire invocation. Full evidence and prioritized defects are recorded in
`scion/docs/experiments/v0.4/v04-cvrp-direct-longitudinal-r11c-postrun-20260716.md`.

Fresh eight-round R11b is terminal and read-only at
`/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r11b-8r-gpt56sol-8r-gpt56sol-20260716T115118Z-claw`
with terminal wrapper PID `2879552`. It ran from the clean detached runtime
`/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-6a2f6765` at
exact pushed code commit `6a2f6765ff141b8f1d17c3fae0391df73f3ac580`, using
`gpt-5.6-sol / direct_v3`. Completion preflight is authenticated, HTTP `200`,
and nonempty. This is a fresh `ROUNDS=8` campaign with no resume, force
controls, retry, semantic budget, or truncation; the 30-second limit is the
scientific solver subprocess fallback. Only the environment-variable name
`SCION_SHARED_PROXY_KEY` is persisted. The elapsed-time-SA finding remains
audit guidance and was not forced.

R11b H1/C1 were each generated once. H1 autonomously chose the same granular
CROSS family as R10 H4, but C1 is a distinct implementation: 8-neighbor
boundary filtering, original-orientation segments only, and explicit
`cross_exchange` phase telemetry. Verified/executable code identity is
`82878ff8...`; artifact, materialized file, source digest, and workspace agree.
CROSS was strongly active, while embedded VNS consumed about `84.7-85.5%` of
candidate algorithm time. Initial screening completed `32/32` valid with case
`4/1/3`, pair `19/11/2`, median `+4.75`, CI `[-2.5,13]`, and committed
`expand_screening`. Expanded screening completed another `48/48` valid with
case `6/5/1`, pair `30/16/2`, median `+3`, and CI `[-3.75,15.5]`. The unchanged
gate recomputes this as borderline negative, but no expanded Decision committed.

R11b stopped after the expanded Protocol because the source branch was
persisted with `screening_expand_count=0` and then mutated in memory to `1`.
The strict Decision completion owner check correctly rejected the mismatch:
`decision completion source branch is not the persisted owner`. Campaign exit
was zero, strict postrun readiness/effective wrapper exit was `64`, and status
is `valid_but_incomplete`; only one of eight typed rounds completed. This is a
P1 framework transaction-boundary defect, not a provider, infrastructure,
solver, or gate failure. Do not resume, backfill, or reinterpret R11b.

The repair makes expansion preparation side-effect free, exposes prospective
counts to Protocol/DecisionFeatures, and consumes the count only on the
completed Decision target. The source-owner fail-closed guard is unchanged.
Focused and adjacent review finds no P0/P1 blocker. The correctly rooted full
Scion suite passes `2058` with one existing skip; compileall and
`git diff --check` pass. The provisional formal artifact left by R11b's failed
pre-intent path and legacy nontransaction finalization windows remain explicit
P2 follow-up debt, not reasons to weaken the transaction guard.

The preceding fresh R11 root ending `20260716T114132Z-claw` is terminal,
invalid, and read-only. H1/C1 were each called once and C1 reached verified
candidate artifact recording, but the filesystem had only `4.6 MiB` free and
raised `ENOSPC`; zero Protocol rounds completed. It is infrastructure evidence,
not algorithm evidence, and was not resumed or retried in place. Removing only
the generated `/tmp/pytest-of-clawd` tree restored about `7.0 GiB`; historical
experiment roots were preserved. R11b is the distinct clean replacement root.

Fresh eight-round R10 is terminal and read-only at
`/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r10-8r-gpt56sol-20260716T063211Z-claw`
with terminal wrapper PID `2848393`. It ran from the clean detached runtime
`/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-c936cde4` at
exact pushed commit `c936cde41d746c9cbfcd308bae84ba54d85c7f4a`, using
`gpt-5.6-sol / direct_v3`. Completion preflight is healthy: authenticated,
HTTP `200`, nonempty response. It is a fresh campaign with `ROUNDS=8`, no
resume, force controls, retry, semantic budget, or truncation; the 30-second
limit remains the scientific solver subprocess fallback. It completed all
`8/8` experiments at `2026-07-16T10:31:55Z`; wrapper, campaign, postrun
rebuild, and readiness exited zero. Status is `valid / complete`,
`current_run_analysis_ready=true`, `delegation_ready=true`, and the failure
report is empty.

R10 H1/C1 were single-attempt,
substantive ejection-chain edits in `destroy_repair.py` plus `scheduler.py`.
All `32/32` pairs were valid with zero candidate/champion failure, but the
result was `1/21/10` pair and `0/5/3` case, median `-14.25`, CI `[-48.75,0]`.
The new repair produced `30` attempts and zero accepted chains while collapsing
candidate/champion ALNS iterations to `69/1665`; Protocol failed only
`SCREENING_FAIL_WIN_RATE` and Decision `continue_explore` committed. Its v3
formal base ref is the correct relative `champions/champion_v1`, and all replay
identities pass. H2 explicitly cited that route-limit/throughput failure and
added candidate-list incremental VNS plus CROSS exchange in `local_search.py`,
but retained H1's bad repair. H2 was again single-attempt and `32/32` valid,
yet pair `2/26/4`, case `0/7/1`, median `-7.25`, CI `[-50.5,-2.0]`, ALNS
`62/1665`; inherited ejection was `31/0/31` attempts, accepted, and route-limit
with `718244ms`. Protocol failed win rate and Decision committed. H3 now
directly removes ejection from the active scheduler portfolio and adds
cost-aware feasible repair selection; H3/C3 are single-attempt and verified at
`12ec5b...`. Initial screening was `32/32` valid, case `4/3/1`, pair `17/13/2`,
median `+1.75`, CI `[-2.5,19.5]`; Protocol requested an independent 48-pair
expansion. Expansion completed `48/48` valid with zero failures and
`SCREENING_PASS`; Decision `queue_validate` committed. Validation completed
`32/32` valid with zero failures, case `7/0/1`, pair `26/4/2`, median `+37.75`,
CI `[6,199]`; `VALIDATION_PASS_HIERARCHICAL` queued frozen. Frozen completed
`24/24` valid but reversed to case `4/4/0`, pair `11/13/0`, median `-19.5`, CI
`[-350,98]`; Protocol returned `FROZEN_FAIL_HIERARCHICAL_UNCERTAIN` and
Decision abandoned the branch. Ejection activation was zero and initial ALNS
recovered to `1010/1665`, but cost-aware weighting did not activate because
every solve remained below its 100-iteration update segment. Attribute the
screening recovery to ejection removal, not reward density; the frozen reversal
is real split instability.

R10 then opened H4 from champion v1 and added a length-one-through-three
granular CROSS exchange in `local_search.py`, verified at `454b6ab2...`.
Screening was `32/32` valid, case `6/1/1`, pair `21/7/4`, median `+3.75`, CI
`[0,7.5]`, and queued validation. Validation was also `32/32` valid, case
`4/0/4`, pair `20/5/7`, median `+11.75`, CI `[0,79.75]`, but the gate mapped
this no-loss hierarchical uncertainty to `VALIDATION_FAIL_NO_HIERARCHICAL_GAIN`
and abandoned it. The case win rate `0.5` cannot pass the existing `0.66`
threshold; however the preregistered 8-to-12-case expansion can still reach
that threshold. The current repair routes only this first, no-loss,
non-all-tie, mathematically reachable uncertain shape to the existing one-time
validation expansion. It does not lower the final threshold or use pair
evidence to pass.

R10 also proves a cross-branch context defect. H2 and H3 received one and two
complete canonical screening records, while H4's new branch received
`experiment_history=[]` even though the old branch durably owned four records.
H4 therefore repeated the CROSS family already attempted by H2. The current
repair projects all same-campaign canonical screening records across branches,
including terminal durable owners after reopen, with only context-local source
branch provenance. Validation/frozen details, terminal branch state, raw refs,
patch bodies, and failure prose remain hidden. No failed-hypothesis ledger,
summary substitution, top-N, budget, compression, or truncation is introduced.

R10's five formal v3 artifacts pass apply-check and materialization; all six
Decision intents are committed; both branches are abandoned; workspaces,
candidate staging, active slots, and promotion journals are empty. Champion v1
remains `06820ecd...` with no promotion dossier. `formal_ready=false` denotes
normal completion without promoted final evidence and does not block analysis.

The two R10-derived repairs are implemented and independently reviewed. The
campaign-wide context path reads active and terminal branches in stable order,
merges durable plus live canonical screening records, adds provenance only to
the H-context projection, and fails closed on duplicate ownership, reserved
provenance, unknown owners in a complete campaign scope, or corrupt terminal
evidence on reopen. The validation repair permits only the existing one-time
expansion for an initial no-loss hierarchical uncertainty that can still reach
the unchanged threshold. Focused tests pass `168`; the correctly rooted full
Scion suite passes `2053` with one existing skip. Compileall and
`git diff --check` pass. No retry, semantic budget, truncation, top-N,
compression, summary substitution, blacklist, or new gate was added.

## Current Framework Repair

R6 and its exact validation exposed four evidence-integrity problems:

1. Its v2 R2 formal artifact binds a champion base and cumulative code hash to
   only the incremental `local_search.py` patch. Champion plus that artifact
   produces `0cc217...`, not the live cumulative `0d9c2ce...` workspace.
2. Canonical feedback injected legacy `unknown` fields into a problem-owned
   evidence envelope, omitted Protocol outcome/scope, and allowed display
   schema evolution to duplicate a durable observation.
3. Cross-stage branch evidence retained screening facts while replacing their
   reason codes with validation reasons, producing a mixed resume/status card.
4. The launcher treated the formal-candidate index as a single-hop terminal
   artifact. A second resume copied candidate metadata but lost the inherited
   ownership index held in the source root's outer resume snapshot.

The current repair:

- records v3 `patch` as the current proposal and
  `replay_materialization` as the complete champion-to-current closure;
- separates proposal/cumulative digests and file attribution;
- validates base identity, closure content, candidate identity, and final code
  hash in recorder, fixed replay, and postrun materialization;
- preserves v1/v2 reader compatibility;
- keeps problem-owned envelopes typed and marks CVRP ALNS diagnostics as
  hypothesis attribution `unbound`;
- labels cumulative-vs-champion and case/pair aggregation scopes, includes
  Protocol outcome, removes cross-metric pair median, and reconciles formal
  pair counts with retained pair rows fail-closed;
- uses stable natural identity to upgrade an old durable row without duplicate
  H feedback;
- atomically replaces current protocol stage/stats/runtime/ref/reasons, exposes
  `latest_protocol_evidence`, and retains one compact latest record per stage;
- keeps full experiment history in append-only events/raw metrics instead of
  duplicating it into provider context;
- covers validation/frozen continue, abandon, and frozen promotion paths, and
  allows Protocol `continue` to re-enter exploration from validation/frozen;
- validates and flattens inherited plus source-live formal candidate indexes
  into one immutable union in the new root, while leaving the new live index
  empty for current-invocation accounting;
- fails preparation on noncanonical refs, row/metadata identity conflicts,
  missing or unindexed metadata, snapshot tampering, or mismatched ownership.

The frozen audit added two narrower repairs before another generative run:

- the problem-owned CVRP baseline now exposes the tighter of the runner
  deadline and its existing `BASELINE_TIME_FRACTION=0.80` absolute search
  deadline, and every expensive VNS neighborhood polls that deadline inside
  its nested candidate scan before returning the current valid incumbent;
- validation/frozen champion/shared evidence-acquisition failures remain
  Protocol failures but bypass Decision into durable `BLOCKED_INFRA`, preserve
  the raw partial-evidence ref, and require the existing explicit operator
  resume; the pre-block stage is persisted across process restart;
- two independent timeout results are exposed as `dual_runtime_failure`
  instead of the over-broad `shared_process_failure`; candidate-only runtime
  failure still hard-abandons.

R7 added two more narrow correctness repairs without increasing solver work or
governance weight:

- Verification now performs a stdlib `symtable` unresolved-name scan after
  syntax and before interface checks over complete primary and additional
  candidate modules. It rejects the exact four stale R7 names in milliseconds
  without executing candidate code or scheduling a retry;
- canonical screening history now reconciles pair feedback against
  `valid_pairs + candidate_failed_pairs`, while retaining exact W/L/T checks
  and excluding champion/shared/missing-output invalid rows from feedback.

The R8 repair slice now isolates each unverified patch in a candidate staging
tree and records a typed verified-candidate ownership artifact before a
two-phase `prepared -> committed` promotion. A promotion journal retains the
old durable workspace until the typed commit and branch state are committed.
On reopen, a persisted base identity rolls the physical promotion back; a
persisted candidate identity plus a valid typed commit completes promotion;
all conflicting identity combinations fail closed. A rolled-back journal keeps
the exact hypothesis owner until that uncommitted hypothesis is durably
terminalized, so a HypothesisStore failure remains recoverable on the next
reopen. Rejected staging is discarded even if hypothesis-status persistence
fails. A committed candidate
whose formal evaluation was interrupted is restored only for an explicit
screening eval-only continuation: the exact active-H candidate is evaluated
with `0H/0C`, one Protocol/Decision, and then marked completed. The active-H
typed commit takes precedence over old formal artifacts; strict legacy fallback
is allowed only when no typed marker exists.

Stale reconciliation now uses the same boundary instead of replacing the
durable workspace first: it rebases from the newly locked champion into an
isolated staging tree, records a content-addressed `commit_kind=reconcile`
artifact, promotes through the journal, and recovers an interrupted formal
screening as `action=reconcile` with `0H/0C`. Contract or Verification rejection
is pre-Protocol, keeps the old durable/hash/marker intact, and emits the typed
gate event plus StepRecord/check provenance. Typed commits bind the canonical H
content, lineage, base, patch, code, and executable identities; promotion
recovery verifies backup/candidate/durable trees before any destructive action.

The Decision boundary now writes a typed SQLite completion intent. Pending
screening Decisions, plus any-stage `CONTINUE_EXPLORE`,
`VALIDATION_REPAIR_REQUIRED`, or `ABANDON`, atomically commit the post-Decision
Branch, H status, completed marker, and typed decision fact. Startup converges
an unfinished intent before branch restore and makes no provider or Protocol
call. ABANDON cleanup is post-commit and uses a deterministic archive receipt,
so archive, partial-delete, and restart remain idempotent and identity checked.
It also:

- projects typed Contract/Verification failures through legacy reports and
  exposes stable `failed_check`, `failure_code`, and `failure_detail` without
  synthesizing a pre-Decision `decision_reason`; Contract opportunities include
  all gate outcomes, while Verification opportunities exclude Contract-failed
  attempts;
- exposes the outer Decision in canonical next-H screening history;
- labels CVRP `unbound` mechanism telemetry as association-only;
- tells destroy/repair proposals to propagate and poll the existing monotonic
  deadline context inside nested searches.

These are lifecycle, reporting, and generation-guidance repairs. They add no
research gate, provider retry, semantic budget, truncation, or solver work.

The final affected transaction/report/guidance review set passes `198`; the
current champion-ref repair focus passes `58`, and the correctly rooted
standard Scion suite passes `2040` with `1` skipped in `479.74s`. `compileall`
and `git diff --check` pass. Boundary coverage includes same-file cross-round edits,
create/delete, full reversion to champion, activation files, absent and
partially missing indexes, inherited resume indexes,
closure/content/base/final-hash tampering, promotion and Decision crash
recovery, exact pending-evaluation ownership, stale reconciliation, legacy
terminal-H recovery, and partial ABANDON cleanup.

Nonblocking P2 debt remains explicit: a process death after a local Protocol
returns but before intent preparation, or during an ordinary nonterminal
retained transition, may replay that Protocol with at-least-once semantics;
the typed recovery fact and canonical branch history do not reconstruct every
rich experiment/DecisionFeatures projection after that crash. Target-first
source projection remains an architectural simplification, and strict postrun
acceptance still lacks a cross-artifact count comparison. None is grounds to
add a retry, weaken source completeness/Verification/Protocol, or block R9.

A real X-n1001 seed-61 compliance probe with a 30-second scientific limit now
returns a feasible 43-route incumbent with exit `0` in `23.78s`; construction
used `20.745s`, initial VNS used `2.522s`, and the solver reported
`stop_reason=time_limit`.

## Approved Next Design: Search Allocation and Research Surfaces

The accepted design is
`scion/docs/planning/v0.4/v0.4-cvrp-search-allocation-and-alns-control-design-20260716.md`.
The R11c boundary and full terminal audit are complete. Implementation must now
follow that design instead of adding another runtime helper or gate.

The controlling conclusions are:

- the agent already has complete solver source and can modify VNS/ALNS, but the
  next H does not receive measured `vns_initial / vns_embedded / alns_core`
  allocation or repair-to-polish marginal value;
- search allocation belongs in compact, screening-only, problem-owned proposal
  evidence with `gate_influence=false`, not in DecisionFeatures or a new generic
  interactive tool loop;
- pure ALNS has already been studied under the old runtime: it is weaker but
  more measurable and reached validation/frozen more often, yet produced no
  promotion. The current task is a direct-v3/gpt-5.6 matched re-evaluation, not
  a blind repeat;
- current `USE_VNS=False` alone is not pure ALNS because it activates the
  size-70 two-opt fallback. The copied pure profile must also disable initial,
  embedded, and fallback polish while preserving the same ALNS scheduler;
- ALNS+VNS and pure ALNS remain separate champion profiles and campaigns. A
  pure-profile positive must undergo no-LLM transplant replay on the canonical
  profile before supporting a canonical solver claim;
- removing VNS changes iteration count and iteration-based SA cooling, so time
  competition and search-trajectory effects must be reported separately.

The implementation order is fixed; items 1-3 are complete:

1. terminalize and audit R11c without changing its runtime;
2. [complete] make `LocalSubprocessRunner` own and delete solver interchange
   files while preserving all formal raw metrics;
3. [complete] project existing runtime fields into problem-owned
   `SearchAllocationEvidence`, with no new instrumentation in the same slice;
4. [complete] make finalized H/Patch/Verification `research_rejected`
   attempt-terminal but scheduler-forward, with a new H and no same-H/C retry,
   cap, or formal count. One durable completion owner now binds campaign,
   provider attempt, canonical H/Patch identity, exact clean Branch target,
   typed event, and any candidate archive receipt; independent review has no
   P0/P1 and the full suite passes `2145` with `1` skipped;
5. [D1 and D2a complete; D2b-D4 contract frozen] add immutable candidate
   snapshots, exclusive append-only snapshot ownership, and the pure
   clean/provisional disposition truth table. D1 remains deliberately unwired;
   its combined focused suite passes `128`. D2a now adds typed caller-bound
   campaign open, atomic identity/mode ownership, strict pre-D2 legacy adoption,
   and a read-only exact legacy pending-candidate compatibility owner while
   leaving composition and production behavior unchanged. Its focused suite
   passes `117`, compatibility regression passes `67`, and the full suite passes
   `2332` with `1` skipped; two independent audits report no P0/P1.
   **Fresh-only supersession:** D2a's legacy adoption and
   `LegacyVerifiedCandidateReader` are historical dormant compatibility
   surfaces. The v0.4 fresh production composition must not import, call, or
   route through them. Only the non-adoption campaign/mode and immutable-
   identity foundations may be reused.
   Four
   adversarial rounds froze the cross-cutting D2-D4 contract. The narrower D2b
   implementation contract then passed five adversarial rounds by three
   reviewers with no open P0/P1; it freezes Branch+H revision CAS, the explicit
   evaluation lease and comparison guard, durable origin/mechanism ownership,
   sealed dispatch capability, exact receipt/infra/uncertain edges, and atomic
   successor-slot transfer. D2b.0a is complete: frozen v1 Branch/H codecs now
   have one pure owner, the separate strict stable source-H projection is
   canonical across Python/SQLite REAL, focused compatibility passes `193`, and
   the full suite passes `2388` with `1` skipped; two final reviews report no
   P0/P1. The D2b.0b global durable-owner migration contract is now frozen after
   three adversarial rounds by three reviewers with no open P0/P1. It requires
   immutable storage-digest tokens, one Campaign projection coordinator, a sole
   schema bootstrap, offline clean-stop cutover, database rejection of legacy
   writers, dormant lease predicates, exact completion revision/digest recovery,
   and collision-free champion snapshot publication. Implement D2b.0b.F as a
   production-unimported foundation. **Fresh-only supersession:** the global
   adoption/in-place migration composition is no longer queued. Only the
   transaction, store, Registry, digest, and writer-closure foundations that do
   not depend on legacy adoption may be reused by fresh staging/no-replace
   bootstrap. Its transaction/publication correction is
   frozen in
   `scion/docs/planning/v0.4/v0.4-d2b0b-foundation-transaction-publication-correction-20260716.md`
   after six adversarial rounds by three reviewers with no open P0/P1. The
   rejected first draft remains unwired. The corrected production-unimported
   SQLite layer is complete: sealed Campaign database authority, actual native
   main-handle verification, materialized participant results, exact
   thread/Context ownership, independent classification snapshots, and
   component-state cleanup passed two independent final reviews with no P0/P1.
   The corrected owner-write responsibility layer is also complete and remains
   production-unimported. `lineage/owner_transaction.py` owns only one-shot
   Branch/H permits, pending write facts, sealed receipts, exact ledger closure,
   and hard pre-commit enforcement; focused `branch_owner_store.py` and
   `hypothesis_owner_store.py` own fixed SQL, complete strict row decoding,
   exact pre-state guards, and same-transaction authoritative post-state
   tokens. The rejected partial metadata query/SQL-parser approach was removed.
   AST closure admits only the two focused store paths and automatically denies
   every unapproved private helper/importer. Two final independent reviews
   report no P0/P1/P2; the complete focused set passes `155`, lineage unit tests
   pass `191`, and the correctly rooted suite passes `2579` with `1` skipped in
   `504.50s`. The one-root Campaign owner Registry foundation is now complete
   and remains production-unimported. It owns one immutable Branch/all-H/current-
   H root, physical-database-unique startup authority, standalone drain,
   Context/thread-bound mutation views, fused focused-store CAS/staging, exact
   commit classification/publication, and ID-only monotonic refresh. It adds no
   creation authority, schema, writer cutover, retry, budget, cap, gate, cutoff,
   or truncation. Two independent implementation audits close at P0=0/P1=0;
   its expanded responsibility regression passes `183`, and the correctly
   rooted suite passes `2607` with `1` skipped in `474.04s`. The authorization-
   bound creation participants' implementation contract is
   now frozen in
   `scion/docs/planning/v0.4/v0.4-d2b0b-authorization-bound-owner-creation-plan-20260716.md`
   after three specialized audits and three adversarial revision rounds close
   at P0=0/P1=0. It separates a connection-scoped durable champion participant,
   proposal-attempt/H binding owner, provider-issued sealed generated result,
   problem-neutral authorization ledger, and Registry-only one-root
   publication. A provider-time generation view binds the exact Branch and H
   history head before one started attempt and one provider call. The earlier
   completion-only legacy activation inventory is superseded and forbidden in
   the fresh v0.4 composition; only freshly bootstrapped history is admitted.
   Its first dormant responsibility checkpoint is now
   complete: the generic ledger proves exact creation authorization/write/
   receipt/witness closure; the connection-scoped champion participant and
   focused Branch/H INSERTs require exact authorization; and a committed,
   strictly reread hypothesis START is the only source of the one-shot provider
   permit and provider-issued sealed generated result. Rolled-back/replaced
   STARTs and mismatched persisted context/prompt fail before transport. The
   combined focused set passes `219`; the correctly rooted suite passes `2672`
   with `1` skipped in `503.28s`; independent review closes P0=0/P1=0 after its
   rollback finding was fixed. Production remains uncomposed and no schema is
   created. A follow-up end-to-end H-creation audit found that the earlier
   instruction to add the proposal participant before the Registry generation
   view was unsafe: it conflicted over Branch/H/event/binding classification
   ownership, left provider result-to-view binding incomplete, and did not
   freeze code-source, Contract, taxonomy, clock, or UUID authority. That
   continuation is superseded by
   `scion/docs/planning/v0.4/v0.4-d2b0b-hypothesis-creation-vertical-correction-20260716.md`.
   The correction keeps one architecture but divides implementation into two
   complete dormant checkpoints. Checkpoint A owns authoritative champion-or-
   verified-workspace source selection, prompt projection, one Branch-local
   reservation, unique committed START, one provider permit/outcome, durable
   terminalization, and restart holds. Checkpoint B owns frozen Contract and
   taxonomy semantics, authority-bound clock/UUID target construction,
   generated event/binding/H, semantic/global classification, and one Registry
   publication. Checkpoint A is now complete and remains dormant. One leaf
   capability graph binds the exact six semantic owners; Registry owns the
   Branch-local reservation and exact owner context; the source owner captures
   champion-or-verified-workspace bytes once; Context/Prompt build one canonical
   provider snapshot; ProposalAttemptOwner persists and independently classifies
   START/terminal rows; ProviderCallOwner alone consumes the permit. START
   revalidates the captured Branch and complete H bundle inside the same
   `BEGIN IMMEDIATE`; provider-unknown, rollback, mixed storage, restart,
   pre-START abort, and terminal uncertainty all converge to exact release or
   hold states. The capability graph is GC-safe, uses one bounded Context proof,
   distinguishes invalid cross-binding from genuine replay, and has executable
   exact-caller dependency closure. Checkpoint B is also complete and remains
   dormant. It freezes exact legacy Contract/taxonomy semantics, binds target
   construction to sealed clock/UUID authorities, persists strict generated
   event/binding/revision-zero H ownership, classifies the complete Branch/H/
   event/binding outcome from one snapshot, and publishes exactly one Registry
   root. Normal capability reuse is distinguished from hidden claim/issue
   faults; rollback, restart, partial legacy rows, active lease, malformed
   terminal semantics, and resource-close-before-effect all converge to an
   explicit Branch or Campaign hold without a second provider call. No
   production composition, schema effect, retry, budget, cap, gate, cutoff, or
   truncation was added. The final Checkpoint A+B focused regression passes
   `171`; the correctly rooted full suite passes `2906` with `1` skipped in
   `516.67s`; compileall and diff-check pass. Independent leaf, Registry
   transaction/recovery, and static dependency reviews close at P0=0/P1=0.
   One nonblocking P2 remains explicit: the same `BEGIN IMMEDIATE` creation
   transaction repeats its START/lease preflight after consuming the generated
   result. It performs no retry or intervening state change and may be collapsed
   before activation only if doing so does not broaden the authority surface.
   The v1 historical activation addendum and schema remain immutable evidence,
   but implementation audit proved that their semantic classifier is not closed.
   The attempted executable v2 classifier is rejected and parked: converting
   filesystem, SQLite, decoder, join, digest, reason, and aggregate algorithms
   into JSON metadata created a second interpreter without closing semantics.
   The replacement boundary is design-frozen at SHA
   `ba7a72e2eeb2c6304718224c73b98fc9204e77b72d953a1e631601388f4be400`
   in `scion/docs/planning/v0.4/v0.4-d2b0b-fresh-only-activation-boundary-20260718.md`.
   V0.4 grants bootstrap authority only for one explicitly targeted, stably
   absent campaign database. Every present database and every corpus scan is
   non-authoritative and read-only. The previously named 827-root corpus
   classifier (752 roots remain), adoption, and historical selection/receipt
   chain are moved off the research critical path.
   Implement dormant fresh bootstrap primitives first; then complete the paired
   D2b slices, D2c exact Decision transport, D2d isolated snapshot handoff,
   D2e completion/recovery, D3/D4, and the reversible L1-L3 ledger. Only after
   those composition-changing slices freeze may one exact commit undergo final
   D2b.0b.C/V all-writer, reopen/crash, and end-to-end acceptance.
6. in parallel, run the serial no-LLM CVRP four-profile characterization and
   fixed-arm ancestry controls using Protocol-resolved scientific limits;
7. reconcile Warehouse protocol/manifest and locked-group semantics, then run
   champion/destroy-only/merge-only/cumulative fixed arms;
8. after the fresh runtime path is accepted, run two order-balanced matched
   pairs of fresh eight-observation direct-v3 roots, canonical versus pure ALNS;
9. replay pure-profile positives on the canonical profile and add operator-level
   VNS attribution only if the compact allocation evidence remains insufficient;
10. begin hot-path modularization only after these behavioral boundaries are
   stable.

R11c additionally exposed a normative candidate-ancestry defect: Protocol-
rejected code currently remains the durable branch head and contaminates later
mechanism pivots. The accepted correction is
`scion/docs/planning/v0.4/v0.4-candidate-disposition-and-research-ledger-design-20260716.md`.
It introduces immutable candidate snapshots, typed post-Protocol disposition,
clean/provisional continuation bases, rejected-ancestry exclusion from
SourceLedger/promotion, and a reversible normalized H research ledger. New
generative matched experiments must wait for this correction; runner cleanup,
SearchAllocationEvidence, and no-LLM controls may proceed first.

Disk pressure is no longer a current blocker. A safe cleanup on 2026-07-16
removed only inactive package caches and pre-R11c solver interchange files,
raising free space from about `6.1 GiB` to `23 GiB` without touching any
experiment root. Fourteen retention-audited whole-root batches have now removed
`391` exact roots with a recorded per-path sum of `10.773 GiB`. The third batch added `23` empty,
pre-Protocol failure, zero-effective duplicate-local, and superseded-prepared
roots only after protecting `73` active-doc roots and proving that canonical
evidence remained. The fourth used a tracked-evidence inventory and removed
only one fully reconstructible pre-Protocol replay failure and one empty
wrapper shell, while retaining roots with unique traces or raw metrics. The
fifth batch removed 20 copied prepared shells only after full campaign-tree
equality against retained CVRP/Warehouse canonical roots. Batches 6-7 removed
64 pre-campaign shells plus two superseded failures while preserving twelve
large-history candidates with unique or referenced evidence. Batch 11 removed
12 superseded failures/preflights or exact-subset roots with named retained
owners and zero unique scientific evidence. Batches 13-16 removed nine more
planned-only, pre-Protocol, or zero-round exact-subset roots after proving a
named retained owner, retained reserved schema or byte-identical copied
campaign, and zero unique scientific evidence. Batch 17 removed one additional
pre-campaign shell only after its substantive patch payload was proved byte-
identical to a retained completed eight-round owner. Batch 18 removed one pre-
evaluation permission-failure replay shell and one
zero-effective capacity-blocked successor after copy-isolated database review
proved complete retained-owner coverage and no unique scientific evidence.
Read-only batch 19 then rescanned all `752` remaining roots and found no
further whole-root candidate with complete retained-owner equivalence. Old
zero-valued status fields were not treated as absence: affected roots retained
unique traces, newer accounting/formal evidence, or protected launch archives.
No path and zero bytes were deleted in batch 19.
Batches 8-10 and 12 then compacted
`2,850` Git-restorable static subtree copies totaling `6.759 GiB` without
deleting any additional root or changing registry/DB/metrics/trace/formal/log
counts. `752` roots remain and about `37 GiB` is currently available.
The exact paths, predicates, restore manifests, inventories, and
retained gray set are recorded in
`scion/docs/experiments/v0.4/v04-experiment-retention-cleanup-20260716.md`.
The `scion_run_*.json` accumulation was a runner ownership bug, not formal
evidence loss. The ownership repair passed `2075` tests with `1` skipped;
focused regression passed `152`. After verifying that no live process held the
R11c interchange files, the terminal set of `252` files / `419,331,485` bytes
was removed and the residual count was zero. Future historical cleanup must
protect live/current roots,
unique unsummarized evidence, and the baseline-strength anchors required by the
accepted design, and delete exact superseded/no-evidence/duplicate roots only
from a recorded dry-run manifest. Component compaction is allowed only for an
exact Git-restorable static subtree with a full owner/hash/restore manifest;
scientific and lineage-owning artifacts remain in place.

## Execution Queue

### Execution governance

- The main session alone owns the architecture tie-break, scope and design
  freeze, `TASK.md`/`current-state.md`, task ordering, and final acceptance.
- Subagents receive bounded implementation, test, or read-only experiment-
  analysis tasks. They return exact files/commit or run root, commands,
  environment identity, tests, evidence, and unresolved findings.
- A subagent may not expand architecture, alter the next-stage contract, or
  chain into another generative stage without main-session acceptance.
- Development and experiment-analysis outputs are not accepted by self-report:
  the main session verifies hashes/status, focused tests, independent review,
  and the named scientific artifact before advancing the queue.

1. [Complete] The fresh-only activation boundary passed fixed-hash review. The
   executable historical-classifier draft and its untracked DSL implementation
   are rejected and removed; only a compact passive diagnostic record remains.
2. In parallel, run non-generative science that does not depend on proposal
   ownership, in exact internal order:
   - [Complete] CVRP B0: the Protocol-resolved mechanism-matrix contract passed
     independent code and science review with P0=0/P1=0 and was pushed as
     `90a109b2`. The accepted dry manifest is `0151e2be...882b1`.
   - [Complete] CVRP B1: the serial 16-case x 4-seed x 4-profile matrix at the
     root ending `20260718T074653Z-claw` completed 256/256 valid rows. The
     corrected verdict is `accepted_with_input_authority_caveat`: its sealed
     input has all 16 exact `.vrp` files but zero companion `.sol` files, so the
     runtime did not receive R11c's BKS route-count constraint. The original
     report/receipt/root stay immutable; `833335bb...851b` /
     `03d1c466...5d43` still replay exactly. Canonical's direction over embedded-
     VNS-disabled and pure ALNS persists after removing the 9/64 affected
     quartets, but B1 is support-only and cannot select a profile or authorize
     promotion. The accepted caveat analysis is
     `v04-cvrp-b1-r11c-input-authority-caveat-20260718.md`; do not rerun B1 or
     reuse its single-file materializer. The earlier root ending
     `20260718T074602Z-claw` is superseded non-evidence.
   - [Design frozen] CVRP F1: the exact champion, H1-only, SWAP-family-only,
     and cumulative ancestry matrix is frozen at design SHA
     `a8167117...07faa`; two independent fixed-hash reviews report
     P0=0/P1=0/P2=0. It seals and reparses all 16 exact `.vrp + .sol` pairs,
     executes 64 case/seed cells x 4 arms with stage-local Williams order, and
     keeps complete and incomplete closure separate. Implement and independently
     accept its materializer/preflight before a fresh serial launch. B1 does not
     select a production profile or authorize promotion.
   - [Complete] Warehouse W1 reconciles the exact 31-case Protocol population
     at `0599fc29`. W2 is accepted at pushed commit `d4d44689`: final design
     SHA `c0d85d60...671fc7a`, preservation manifest `0ee66091...90dfc9`,
     aggregate `ae6a0b32...6fd9e5`, and independent code/science reviews both
     P0=0/P1=0/P2=0. W3's 43-cell x 4-arm contract is frozen at pushed commit
     `024ae1e3`, design SHA `5538a81b...bb35`; implement and independently
     accept its manifest/preflight before one fresh serial launch. B1 no longer
     occupies the host.
3. [Design frozen] Implement fresh D2b.0b dormant primitives and isolated
   fixtures under execution-addendum SHA `25b2c424...3a939`, pushed at
   `9119e89b`: descriptor-
   pinned absence authority, one-shot staging/publication capabilities, offline
   main-only SQLite bootstrap, staging/no-replace publication, database/external
   phase receipts, and explicit cutover recovery/reopen reconcile.
   This step cannot make production runnable and does not yet claim final all-
   writer closure. Any present target is a hold and historical roots stay read-
   only. The first E1 implementation candidate is rejected: two final reviews
   reproduced close/reuse, cleanup-convergence, open-assignment, and fork-lock
   defects. A separate cancellation-safe descriptor-ownership correction is
   under design review; no E1 code is accepted yet. In E1-E6 any
   journal/WAL/SHM is a read-only hold; production stays blocked until a
   separately frozen controlled-VFS or equivalent design closes actual
   journal-handle recovery.
4. Complete D2b.1-D2b.4 snapshot/slot, dispatch capability, Protocol receipt,
   and uncertain/infra classification; then D2c exact DecisionOutcome transport,
   D2d isolated candidate snapshot handoff, and D2e exact completion, stage
   reuse, and recovery.
5. Complete D3 continuation with problem-owned CVRP/Warehouse mechanism owners,
   clean/provisional/pivot bases, and rejected-ancestry exclusion. Complete D4
   committed SourceLedger, replay, promotion, champion CAS, and recovery.
6. Complete L1-L3 normalized research ledger before multi-round generative
   experiments. Preserve every source, pair, observation, and problem fact;
   add no top-k, summary replacement, token cap, or truncation.
7. On one exact commit after steps 3-6, freeze the complete table/action-to-
   writer manifest and production composition root; prove zero reachable legacy
   constructors/helpers/direct SQL sites; then rerun final D2b.0b.C/V,
   publication/reopen/crash goldens, full suite, and compileall. Production
   remains non-runnable before the next step's acceptance.
8. Run an end-to-end no-LLM fresh control proving the full H -> C -> snapshot ->
   Protocol receipt -> Decision -> continuation -> exact reuse -> replay/
   promotion path. Then have two independent reviewers audit the same exact
   commit and the E2E artifact; only P0=0/P1=0 unlocks generative research and
   stops authority work as a research blocker.
9. Implement Warehouse problem-owned mechanism attribution, then run one fresh
   2-4 observation current-runtime control. Effective research means substantive
   algorithm edits and evidence-driven direction change; promotion is not
   required if the evidence correctly rejects the candidates.
10. Run the accepted CVRP B2 order-balanced canonical/pure-ALNS matched pairs
    with fresh roots, then B3 exact-candidate eval-only canonical transplant
    replay for every pure candidate that reaches validation and each pure cell's
    final verified cumulative candidate. Only positive replays may support a
    canonical improvement claim; the transplant is not a fresh generative root
    and never regenerates H/C.
11. Add deeper operator-level VNS instrumentation only if allocation evidence
    cannot separate initial VNS, embedded VNS, and ALNS contribution.
12. Correct replay identity, terminal status, and postrun projection only in
    their owning lifecycle slices. Historical migration, extra root cleanup,
    optional diagnostics, and large-file modularization must not block the fresh
    research path.

### V0.4 research completion matrix

| Problem | Mandatory process claim | Mandatory validated-effect claim | Retained-improvement claim |
|---|---|---|---|
| Warehouse | A fresh current-runtime control completes at least two formal observations, makes a substantive problem-owned algorithm edit, and changes direction using prior structured evidence without framework/gate noise. | W1-W3 independently reproduce at least one Warehouse mechanism or constraint effect; the fresh control's verdict is scientifically attributable even if negative. | Made only if a candidate passes its independent Protocol stage; promotion is not required to close the process/effect claims. |
| CVRP | A clean multi-round fresh run uses allocation and ancestry evidence, performs a substantive mechanism edit/pivot, excludes rejected ancestry, and is exactly replayable. | B1 + F1 + B2 isolate ALNS, initial/embedded VNS, and ancestry effects; B3 tests cross-profile transfer; at least one useful candidate receives independent validation support. | A pure-profile positive counts for canonical Scion only after its B3 canonical transplant replay and independent validation. |

If Warehouse candidates are all negative but the process and mechanism-effect
claims pass, Warehouse research is complete without a false improvement claim.
If CVRP has no independently validated useful candidate, the research process
may be reported as sound but the v0.4 objective remains incomplete.

Two, four, and eight are requested observation counts, not retry budgets or
automatic stop rules. Each generative experiment uses a distinct clean root;
terminal roots remain read-only.

## Verification and Git Discipline

- Server `claw` Python:
  `/home/clawd/miniconda3/envs/claw/bin/python`.
- WSL `scion` is for large/concurrent batches only after a fresh connectivity
  and preflight check.
- Run focused affected tests first, then the standard Scion suite, compileall,
  and `git diff --check`.
- Inspect `git status` before staging. Never stage the excluded user document
  or unrelated historical untracked files.
- The user has authorized direct stage/commit/push and subsequent experiment,
  analysis, and optimization work within these boundaries.

## Pointers

- Current state: `scion/docs/status/current-state.md`
- V3 authority: `scion/design/scion-architecture-v3.md`
- Direct-runtime addendum:
  `scion/design/scion-architecture-v3-v0.4-direct-runtime-addendum.md`
- Main audit:
  `scion/reports/v04-v3-runtime-and-research-effectiveness-audit-20260712.md`
- Gate/host-control audit:
  `scion/reports/v04-gate-and-host-control-audit-20260712.md`
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
- R11c terminal audit:
  `scion/docs/experiments/v0.4/v04-cvrp-direct-longitudinal-r11c-postrun-20260716.md`
- Multi-hop lineage repair report:
  `scion/docs/experiments/v0.4/v04-resume-formal-candidate-lineage-repair-20260715.md`
