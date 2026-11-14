# CVRP Direct Longitudinal R8 Stopped Analysis

*Date: 2026-07-16*
*Disposition: terminal, read-only, never resume*

## Identity

- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r8-4r-gpt56sol-20260716T002051Z-claw`;
- runtime:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-4a42ee3f`;
- exact runtime commit:
  `4a42ee3f98bed4cde90e4a9be54fe79aefe5585d`;
- model/runtime: `gpt-5.6-sol / direct_v3`;
- requested formal rounds: `4`;
- wrapper/postrun exits: `0/0`;
- validity/completeness: `valid_but_incomplete / incomplete`;
- completed typed Protocol rounds: `1`;
- stop reason: `execution_research_rejected`;
- champion: v1, unchanged.

The actual campaign ran from `2026-07-16T00:23:39Z` through
`2026-07-16T00:56:37Z`. Guarded readiness and completion preflight passed.
Provider accounting is exactly `2H/2C`: four durable successful calls, with no
retry, replacement, transport output ceiling, or truncation evidence. The
formal-round count is one because R2 never reached Protocol.

## Evaluated Round 1

H1 proposed a substantive route-cap-aware regret repair with a bounded depth-2
ejection chain in `destroy_repair.py`, plus scheduler registration. C1 applied
the mechanism and produced clean candidate hash
`209d40d7346c8ff62bac816bfc0bbcaf265f1e9a56de2b0c5c93b4137ac86d0b`.

Formal screening completed with `32/32` valid comparisons and no candidate,
champion, or infrastructure failure:

- case W/L/T: `1/1/6`;
- pair W/L/T: `4/8/20`;
- median/CI: `0 / [-0.5,0]`;
- case-level win rate: `0.125`;
- Protocol: `fail / SCREENING_FAIL_WIN_RATE`;
- Decision: `continue_explore`;
- fresh runtime median ratio: approximately `0.99994`.

Candidate/champion descriptive ALNS telemetry reported route-limit rejections
`0/89`, repair errors `2/0`, and iterations `1405/1693`. That telemetry was
explicitly marked `hypothesis_attribution=unbound`, proposal-only, excluded
from DecisionFeatures, and unable to affect the gate. It is association
evidence, not proof that H1 caused the observed differences.

The result is scientifically negative: the mechanism changed repair behavior
but did not meet the screening win-rate requirement.

## Rejected Round 2

H2 received the R1 objective, case, pair, and mechanism observations plus the
Protocol failure. Its response explicitly used CMT2 and the mechanism
diagnostics, then changed direction from repair feasibility to an inter-route
length-1/2 segment cross-exchange in `local_search.py`. This establishes that
objective/case/mechanism carryover worked, but not complete feedback fidelity:
the old canonical next-H projection omitted outer Decision
`continue_explore`. There is no evidence that this omission caused C2's
undefined-name editing error.

C2 was incomplete:

- it registered `_cross_exchange` without defining it;
- it deleted the `_or_opt_1` function header while leaving the name registered;
- the displaced body was absorbed into `_swap`;
- syntax still compiled, but V1b found `_cross_exchange` and `_or_opt_1` as
  undefined names in the complete touched module.

Verification correctly returned
`research_rejected / VERIFICATION_LIGHT_REJECTED / V1b_undefined_names` in
milliseconds. No R2 candidate was screened, and no algorithm-quality claim may
be made about cross-exchange. Stopping the invocation after this rejected
durable attempt is the direct-runtime contract; adding an automatic retry
would be incorrect.

## Framework Findings

### P0: rejected staging polluted the durable workspace

R8 exposed a resume-safety defect after the correct V1b rejection:

- final in-memory card current hash: failed C2 `7c3b0905...`;
- final in-memory last-clean hash: evaluated C1 `209d40d...`;
- SQLite persisted both hashes as clean `209d40d...`;
- the physical durable branch workspace still contained failed C2
  `7c3b0905...`.

The old path applied a candidate directly to the durable workspace, archived
it on rejection, but did not restore the filesystem. Resume loaded that tree
without recomputing its hash. A later patch touching another file could
therefore have inherited the broken `local_search.py` while V1b inspected only
the new touched file.

R8 must never be resumed. The repair boundary is transactional candidate
staging plus a typed verified-candidate ownership artifact. Promotion is a
two-phase `prepared -> committed` operation with a journal and retained durable
backup. On reopen, persisted base identity rolls the physical promotion back;
persisted and physical candidate identity plus a valid typed commit completes
promotion; every conflicting combination fails closed. Rejection archives and
deletes staging, restores the clean branch identity, and still rolls back if
hypothesis-status persistence fails.

Physical rollback writes a durable `rolled_back` journal that retains the exact
hypothesis owner. That journal is finalized only after the uncommitted
hypothesis is durably terminalized; if HypothesisStore persistence fails, the
next reopen repeats the same identity-checked convergence instead of losing
recovery evidence.

A committed candidate interrupted before formal evaluation is restored only as
the exact active-H candidate. An explicit next `run_one_step()` performs
screening eval-only with `0H/0C`, one Protocol/Decision, and then marks the
candidate completed; it does not generate H3. The active-H typed commit takes
precedence over an old formal artifact. Strict legacy fallback is allowed only
when no typed marker exists.

The same boundary now covers stale reconciliation. The new champion is locked,
copied into branch-owned staging, and patched without replacing the old durable
tree. A verified reconcile writes a content-addressed typed commit and promotion
journal before formal screening; rejection writes typed Contract/Verification
evidence and leaves the old durable/hash/marker untouched. Reopen validates the
canonical H content, lineage, base, patch, executable identity, journal owner,
and every backup/candidate/durable tree before mutation.

Decision finalization is separately transactional. Pending screening Decisions
and any-stage `CONTINUE_EXPLORE`, `VALIDATION_REPAIR_REQUIRED`, or `ABANDON`
commit Branch, H, marker, and a typed decision fact in one SQLite transaction.
Startup finishes an incomplete intent before restoring schedulable branches,
without H/C or Protocol calls. ABANDON archives through a deterministic typed
receipt before cleanup; a crash after only part of the workspace was deleted
therefore resumes from the verified archive rather than rejecting the residual
tree or producing a duplicate archive.

Independent review found no remaining P0/P1 under this boundary. The affected
review set passes `198`; the full Scion suite passes `2034` with `1` skipped in
`462.74s`; `compileall` and `git diff --check` pass.

### P1: legacy failure reports hid the typed rejection

Typed lineage and the analysis brief correctly recorded one V1b rejection, but
legacy `summary.json` and `failures.json` queried only
`verification_result='failed'`. The authoritative typed row uses
`event_kind='verification_fail'` and left that legacy field null, so both
reports incorrectly returned zero failures while readiness still said ready.

The repair projects typed `contract_fail`/`verification_fail` events through
the shared legacy reader with stable `failed_check`, `failure_code`, and
`failure_detail`, while keeping pre-Decision `decision_reason` null. Contract
opportunities include every gate outcome; Verification opportunities exclude
attempts already terminated by Contract. A read-only requery of R8 then
reports:

- gate outcomes: `2`;
- Contract opportunities/intercepts/rate: `2 / 0 / 0.0`;
- Verification opportunities/intercepts/rate: `2 / 1 / 0.5`;
- verification failures: `1`;
- failure type: `verification:V1b_undefined_names`.

The stored R8 postrun reports remain untouched as evidence of the original
false-negative projection.

### P1/P2: proposal interpretation and guidance

- Canonical next-H history carried Protocol outcome but omitted the outer
  Decision. It should expose `decision=continue_explore` and its available
  reason codes without adding a gate.
- CVRP proposal-visible `unbound` mechanism telemetry needs a concise adjacent
  instruction that it supports association only, not causal attribution.
- The H1 nested ejection search did not receive or poll the existing monotonic
  deadline context. Target guidance should require deadline/reserve propagation
  and inner-loop polling without changing the scientific time limit.
- C2's target module was only a minority of a large full SourceLedger prompt.
  Target-first source projection is a later architectural simplification, not
  an evidence-backed reason to weaken source completeness or V1b now.
- Strict postrun acceptance still lacks a cross-artifact count comparison.
  This is P2 observability debt; it must not become a research gate.
- A process death after local Protocol return but before Decision-intent
  preparation, or during an ordinary nonterminal retained transition, may
  replay that Protocol with at-least-once semantics. Typed recovery preserves
  state consistency but does not reconstruct every rich experiment and
  DecisionFeatures projection after that crash. This is explicit P2 recovery
  debt, not authority for an automatic retry in a normal run.

## Next Experiment

After the P0/P1 repair is independently reviewed, fully tested, committed, and
pushed, launch a fresh four-round R9 root from that exact clean commit. Do not
copy or resume R8 state. R9 should test whether one verified negative round can
lead to another materially different, executable candidate while maintaining
physical/hash/lineage consistency. Expand to a separate eight-round root only
if a clean four-round terminal result still leaves longitudinal adaptation or
reproducibility unresolved.
