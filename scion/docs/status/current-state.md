# Scion v0.4 Current State

*Last updated: 2026-07-18*

Read `scion/TASK.md` first. Use
`scion/design/scion-architecture-v3.md` as the architecture tie-breaker.

## Operational State

Fresh eight-round R11c is terminal and read-only at
`/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r11c-8r-gpt56sol-8r-gpt56sol-20260716T132422Z-claw`
with terminal wrapper PID `2892669`. Its clean detached runtime is
`/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-56bc445d` at
exact pushed commit `56bc445d07b19587ecb8e4b763ab448c4ceb9115`. It uses
`gpt-5.6-sol / direct_v3`, `ROUNDS=8`, and the 30-second scientific solver
subprocess fallback. It is fresh: no resume, force controls, retry, semantic
budget, or truncation. Completion preflight is authenticated, HTTP `200`, and
nonempty; only the `SCION_SHARED_PROXY_KEY` environment-variable name is
persisted. Wrapper/campaign/postrun/strict readiness exited zero, but scientific
status is `valid_but_incomplete`: formal observations `4/8`, then round 5 H3
failed `V1b_undefined_names`; the correctly typed `research_rejected` attempt
was incorrectly promoted to an invocation-wide stop. Do not resume or backfill
this historical root.

R11c accepted the prospective-count repair on its first expansion:
the source intent remained at count `0`, the completed Decision target committed
count `1`, no owner mismatch occurred, and only one final evaluation outcome
was recorded. The same run exposed a separate candidate-ancestry defect. H1's
route-elimination mechanism accumulated `1,540` empty selections and never
produced a nonempty candidate; expanded screening rejected it, yet H2 SWAP*
inherited the H1 files because `continue_explore` retained the
Verification-passed workspace. H2 was strongly active and broadly positive,
but tai150a lost all four seeds because initial VNS consumed about 46 seconds
and ALNS performed zero iterations. Validation abandon is justified; H2
evidence is still cumulative H1+H2, not SWAP*-only. The normative repair and
reversible prompt-ledger design is frozen in
`scion/docs/planning/v0.4/v0.4-candidate-disposition-and-research-ledger-design-20260716.md`.
No new generative matched root may start until rejected code ancestry is
excluded from continuation and promotion.

H3 used a clean champion base and received exactly three safe sibling screening
records without validation/frozen/terminal/raw-ref/patch leakage. Its joint
destroy-repair edit left six old variable references, and light Verification
correctly rejected it before Protocol. The P0 defect is campaign continuation:
a finalized pre-Protocol research rejection must end that attempt without a
same-H/C retry, then schedule a fresh H on the exact clean base rather than
ending the requested observation program. The terminal audit also found an
event replay-digest mismatch, stale top-level last outcome, and missing postrun
scientific projections. Full report:
`scion/docs/experiments/v0.4/v04-cvrp-direct-longitudinal-r11c-postrun-20260716.md`.

The first ancestry correction slice is now complete. H Contract, Patch
Contract, and Verification research rejection share one exact-once durable
completion owner; the rejected H/C is attempt-terminal, the exact clean Branch
base is restored, and CampaignLoop schedules a new H without adding a formal
observation, same-H/C retry, rejection cap, or attempt budget. Campaign identity,
canonical H/Patch digests, candidate archive receipts, typed completion events,
and active-H reopen ownership are verified from SQLite before continuation.
Legacy committed Decision and physically validated candidate owners remain
reopen-compatible, while genuinely unowned or ambiguous attempts hold
fail-closed. Independent review found no P0/P1. The full Scion suite passes
`2145` with `1` skipped in `490.33s`; compileall and `git diff --check` pass,
and no `scion_run_*.json` files remain.

D1 immutable candidate ownership foundation is now complete but deliberately
unwired. It adds a versioned manifest/delta snapshot, stable candidate identity
separate from the full artifact digest, explicit per-campaign ownership mode,
append-only natural-origin registry with prepared-to-committed recovery, and a
pure post-Decision disposition truth table. Authoritative workspace manifests
are read before prepare and again before commit; candidate-parent artifacts are
digest-pinned recursively; artifact and campaign-root reachability are pinned
by directory descriptors. Exact relocated retries, crash phases, manifest
collisions, hidden drift, strict decode, and root/directory replacement all have
regressions. The combined focused suite passes `128`; the correctly rooted full
Scion suite passes `2273` with `1` skipped in `492.10s`; independent review has
no open P0/P1. D2-D4 must now wire completion, continuation, lineage, replay,
and promotion before the rejected-ancestry defect is closed. No new generative
matched root may start before that migration and the following L1-L3 ledger
work are accepted.

The D2-D4 implementation contract is now frozen after four adversarial review
rounds by three independent auditors, with no open P0/P1. It separates stable
source identity from dispatch control state, makes snapshot/slot and formal
observation ownership exact, stages future H under an awaiting-plan owner,
requires prospective/verified mechanism agreement only for provisional
inheritance, and gives SourceLedger, promotion, champion-CAS conflict, and
formal replay explicit crash-recoverable owners. Implementation starts with D2a
campaign/mode compatibility and remains production-disabled until D3/D4 are
complete.

D2a campaign/mode compatibility is now complete and deliberately unwired. A
typed `CampaignOpenRequest` binds a stable caller-owned identity before
composition; one `BEGIN IMMEDIATE` atomically claims campaign identity and
candidate ownership mode. NEW rejects any prior durable state, REOPEN preserves
an exact immutable mode, and pre-D2 adoption requires positive authoritative
state rather than artifact or directory inference. The legacy path exposes only
a read-only `LegacyVerifiedCandidateReader`: exact campaign/mode, complete
canonical Branch/H (including proposal digest), committed verified artifact,
Patch, workspace identity, and pending validation/frozen state must agree. The
v1 completion codec and static byte goldens are unchanged. Focused D2a tests
pass `117`, adjacent v1/research-rejection compatibility passes `67`, and the
full suite passes `2332` with `1` skipped in `487.47s`; two independent audits
report no P0/P1. No campaign manager, composition, or CLI calls this surface
yet. This is historical completed-but-superseded compatibility work: fresh
v0.4 production must not import or call the legacy adoption request or
`LegacyVerifiedCandidateReader`; only the non-adoption identity/mode foundation
may be reused. D2b paired slot/dispatch/receipt is next, and generative
production remains disabled until D2-D4 are complete.

The D2b paired-evaluation implementation contract is now frozen in
`scion/docs/planning/v0.4/v0.4-d2b-paired-evaluation-ownership-implementation-plan-20260716.md`
after five adversarial rounds by three independent reviewers, with no open
P0/P1. It separates permanent snapshot/initial-pair identity from a temporary
Branch+H evaluation lease; migrates all Branch/H writers to typed revision CAS
with SQL lease predicates; requires durable origin and VerifiedCandidateOwner
derivation; pairs snapshot, initial slot, and pre-first-dispatch comparison
guard; seals dispatch with a non-reconstructible capability; and freezes exact
receipt, infrastructure, uncertainty, operator-resume, successor-slot transfer,
and crash-recovery edges. Initial snapshot dispatch requires H=`active`; every
D2e exact-reuse successor carries the exact transferred H=`advanced` revision
and atomically rearms its current-comparison guard. Production remains unwired.
D2b.0a pure durable-owner codec extraction is complete. Frozen v1 Branch/H
payload and row projections now have one owner without changing either v1
golden or historical fallback; Decision completion, research rejection, active
audit, rejection finalization, and the legacy candidate reader use it. A
separate `stable-source-hypothesis.v1` projection strictly binds the proposal
digest and structural H allowlist while excluding lifecycle/storage noise; its
numeric identity is canonical across Python and SQLite REAL, including signed
zero. No SQL mutation, schema, revision, lease, or production composition was
added. The focused compatibility matrix passes `193`; the correctly rooted
full suite passes `2388` with `1` skipped in `470.17s`; two independent final
reviews report no P0/P1. D2b.0b global Branch/H revision CAS, dormant
evaluation-lease schema, and SQL writer predicates are next. The remaining
private `_upsert_branch` cross-module dependency is explicitly owned by that
slice.

D2b.0b now has its own frozen migration contract in
`scion/docs/planning/v0.4/v0.4-d2b0b-global-durable-owner-migration-plan-20260716.md`.
Three independent reviewers accepted it after three adversarial rounds with no
open P0/P1. The design uses truly immutable complete-storage digest tokens,
focused Branch/H stores, one Campaign-local projection coordinator, one schema
bootstrap, exact Decision/rejection auxiliary revision+digest recovery, and
atomic durable promotion/weight facts. Schema activation and every legacy
writer migration are one indivisible offline cutover: runners must be stopped,
the campaign execution lock held, and database generation/revision triggers
make old `REPLACE` or bare UPDATE fail. Champion/weight snapshots publish to
unique no-replace immutable object paths, so a concurrent loser cannot overwrite
or delete the winner. D2b.0b.F dormant foundation is next; it must have no
production import or schema effect. No positive lease, slot, dispatch, receipt,
retry, budget, cap, or truncation writer is authorized in this slice.

The global legacy-migration composition above is historical completed-but-
superseded design. Fresh v0.4 must not activate its adoption or in-place
migration route. Its reusable dormant transaction/store/Registry foundations
may enter only the fresh staging/no-replace bootstrap and must pass the final
writer-manifest closure before production becomes runnable.

The first D2b.0b.F implementation review rejected the initial Registry/SQLite
draft before wiring: participant SQL could escape transaction ownership, and
local owner installation was not provably ordered after durable commit. The
corrected dormant contract is now frozen in
`scion/docs/planning/v0.4/v0.4-d2b0b-foundation-transaction-publication-correction-20260716.md`
after six adversarial rounds by three reviewers with no open P0/P1. It binds one
verified Campaign database authority, materializes results without raw cursor
leakage, gives Branch/H writes sealed same-transaction receipts, drains startup
standalone writers before restore, and publishes one immutable Campaign-owner
root only after a proved commit. Commit uncertainty uses a new verified
connection or holds fail-closed; it never retries a mutation. The rejected draft
was never wired. The corrected first responsibility layer is now implemented in
production-unimported `lineage/sqlite_connection.py`: it owns one sealed
Campaign database authority, private policy-verified connection construction,
actual native `sqlite3*` main-handle verification, materialized participant
results, exact thread/Context ownership, commit-uncertain original-connection
settlement, and independent consistent classification snapshots. Transaction
and snapshot cleanup is component-state/idempotent across one-shot faults; a
session becomes `CLOSED` only after capability, Context/thread owners, raw
connection/native handle, and proof descriptor are all released. Focused tests
pass `79`, the lineage unit suite passes `115`, and the correctly rooted full
suite passes `2503` with `1` skipped in `508.79s`; compileall and diff-check
pass. Two independent final reviews report no P0/P1. The module has no
production importer. The second corrected responsibility layer is now complete
and also dormant. `lineage/owner_transaction.py` contains only one-shot Branch/H
permits, pending facts, sealed receipts, exact identity closure, and a COMMIT
authorizer that rejects every unsealed ledger. The focused
`lineage/branch_owner_store.py` and `lineage/hypothesis_owner_store.py` own all
fixed owner SQL, complete strict row decoding, exact pre-state checks, and
same-transaction authoritative post-state tokens. Receipt issuance no longer
accepts a caller-selected committed token, and the rejected partial owner-row
query/SQL-parser approach is absent. AST closure automatically denies every
unapproved private helper/importer; no production module imports either store.
Two final independent reviews report no P0/P1/P2. The complete focused set
passes `155`, lineage unit tests pass `191`, and the correctly rooted suite
passes `2579` with `1` skipped in `504.50s`; compileall and diff-check pass.
The mutation-only one-root Campaign owner Registry is now complete and remains
production-unimported. One immutable root owns Branch, all H, derived current-H,
and publication generation. Startup is unique per physical database, drains
standalone leases without polling/cutoff, restores through one shared snapshot,
and seals once. Context/thread-bound views feed fused Registry-owned focused
CAS/staging; commit uncertainty is classified through one new snapshot, and
ID-only refresh publishes coherent monotonic Branch or full-Branch H bundles.
Creation views/receipt consumption remain absent pending champion and proposal-
attempt authorization participants. Two independent implementation audits close
at P0=0/P1=0; the expanded responsibility regression passes `183`, and the
correctly rooted suite passes `2607` with `1` skipped in `474.04s`; compileall
and diff-check pass. The old legacy-writer migration is no longer queued; only
fresh all-writer composition is allowed, and it must not be collapsed into the
SQLite, permit, focused-store, or Registry foundation layers.

The authorization-bound creation contract is frozen in
`scion/docs/planning/v0.4/v0.4-d2b0b-authorization-bound-owner-creation-plan-20260716.md`.
Three specialized audits and three adversarial revision rounds close at
P0=0/P1=0. Branch creation binds a sealed champion-lock lease, complete durable
current-champion token, authorization-bound write fact, creation receipt, and
one Registry publication. H creation captures the exact Branch and prior-H
history head before one started attempt/provider call, accepts only a real
provider-issued sealed generated result, and atomically owns generated event,
immutable attempt-to-H binding, revision-zero H, receipt, and publication.
Generic owner transaction code sees only authorization identity and receipt
closure; champion and attempt semantics remain in their focused participants.
The plan's legacy completion-only activation inventory is superseded and must
not be imported by fresh v0.4. Its non-adoption authorization foundations remain
dormant and reusable. The first dormant checkpoint is implemented: the
generic ledger closes exact creation authorization/write/receipt/witness
identity; the strict connection-scoped champion participant and focused
Branch/H INSERTs require it; and the only provider-generation permit consumes
an exact committed START event after independent-snapshot reread. Provider
issuance then binds the persisted context/prompt to one persisted receipt,
trace/manifest/raw response, and sealed generated result. Rolled-back or
replaced STARTs and mismatched context/prompt fail before transport. The
combined focused set passes `219`; the correctly rooted full suite passes
`2672` with `1` skipped in `503.28s`; independent review closes
P0=0/P1=0/P2=0. The code remains production-uncomposed and creates no schema.
An end-to-end audit rejected the old participant-first continuation before more
code was added. It exposed conflicting Branch/H/event/binding classification
ownership, an incomplete provider-result-to-view binding, and mutable or
caller-ambiguous code-source, Contract, taxonomy, clock, and UUID authority.
The accepted correction is
`scion/docs/planning/v0.4/v0.4-d2b0b-hypothesis-creation-vertical-correction-20260716.md`.
It keeps one H-creation architecture but requires two complete dormant
checkpoints: A binds champion-or-verified-workspace bytes, prompt projection,
one Branch reservation, unique START, provider outcome, terminal persistence,
and restart holds; B adds frozen Contract/taxonomy semantics, authority-bound
clock/UUID target construction, event/binding/H, semantic/global
classification, and one Registry publication. SQL, state/recovery, and
dependency audits close at P0=0/P1=0/P2=0. Checkpoint A is now complete,
independently accepted, dormant, and production-uncomposed. Its exact six-owner
leaf graph covers immutable code-source capture, canonical evidence/prompt,
Branch-local reservation, same-transaction Branch/H revalidation, unique START,
provider success/failure/unknown, pre-START and durable abort, terminal receipt,
restart holds, GC-safe one-shot capability state, and exact static caller
closure. Checkpoint B is now also complete, independently accepted, dormant,
and production-uncomposed. It freezes exact legacy Contract/taxonomy semantics,
binds target construction to sealed clock/UUID authorities, persists strict
generated event/binding/revision-zero H ownership, classifies the complete
Branch/H/event/binding outcome from one snapshot, and publishes one Registry
root. Normal reuse is distinct from hidden claim/issue faults; rollback,
restart, partial legacy rows, active lease, malformed terminal semantics, and
resource-close-before-effect converge to explicit holds without another
provider call. No production composition, schema, retry, budget, cap, gate,
cutoff, or truncation was added. The final Checkpoint A+B focused regression
passes `171`; the correctly rooted full suite passes `2906` with `1` skipped in
`516.67s`; compileall and diff-check pass. Independent leaf, Registry
transaction/recovery, and static dependency reviews report no open P0/P1. One
nonblocking P2 remains: the same creation transaction repeats its START/lease
preflight after generated-result consumption without retry or intervening state
change. Collapse it before activation only if the authority surface remains
unchanged. The v1 historical activation addendum and schema remain immutable
evidence, but implementation audit proved their semantic classifier is not
closed. An attempted executable v2 classifier then grew into a second JSON AST
interpreter while still leaving opaque operations; that design is rejected and
parked as diagnostic audit material. The replacement fresh-only boundary is
design-frozen at SHA
`ba7a72e2eeb2c6304718224c73b98fc9204e77b72d953a1e631601388f4be400`
in `scion/docs/planning/v0.4/v0.4-d2b0b-fresh-only-activation-boundary-20260718.md`.
V0.4 may bootstrap only one explicitly targeted database proved stably absent.
Every present database and every corpus scan has zero activation authority;
historical adoption, selection/receipt, and the previously named 827-root scan
(752 roots remain) are no longer research prerequisites. D2b.0b.C/V now means
fresh schema/all-writer bootstrap,
sealed receipt, and exact reopen/crash acceptance with zero runnable mixed-
writer state. Generic ledger and provider-result state machines remain
colocated until the full transition graph is stable; production remains
uncomposed and schema-inactive.

The next post-R11c work is design-frozen in
`scion/docs/planning/v0.4/v0.4-cvrp-search-allocation-and-alns-control-design-20260716.md`.
Raw runtime already exposed VNS/ALNS phase facts while next-H saw only ALNS
repair summaries. The first code slice is now complete: compact problem-owned
proposal evidence carries phase time/share, ALNS throughput, exact
destroy-repair lifecycle, repair-to-polish value, and static capacity
feasibility without touching DecisionFeatures, Protocol gates, or generic core
semantics. A real R11c replay matches `2300/1589` ALNS iterations, `511` empty
route-destroy selections, embedded-VNS runtime `662010/701990` ms, and the
`1 feasible / 7 infeasible` route-reduction split, with no path/case/seed
leakage. Independent review has no P0/P1; the 1430-line problem-owned module is
explicit P2 modularization debt. Focused verification passes `81`; the complete
suite passes `2093` with `1` skipped. The preceding runner ownership slice is
also complete: `RunResult.output_path`
is removed, returned solver results are self-contained, and the runner deletes
its own interchange file across success, failure, cancellation, and malformed
output paths. Focused regression passes `152`; the full suite passes `2075`
with `1` skipped. The test run created no residual interchange files. After
confirming zero live owners, the 252 R11c-era `scion_run_*.json` files totaling
`419,331,485` bytes were deleted; residual count is zero. A current direct-v3
matched canonical/pure-ALNS study follows only after the no-LLM four-profile
characterization and the ancestry/research-rejection corrections.

Disk pressure is no longer an active blocker. A safe cleanup removed inactive
pip/npm caches plus `42,630` solver interchange files created before R11c,
reclaiming about `16.6 GiB` and raising available space from about `6.1 GiB` to
`23 GiB`. No experiment root, runtime, repository, user document, proxy data,
or R11c output was touched in that pass. Fourteen retention-audited whole-root
batches then removed `391` exact experiment roots with a recorded per-path sum
of `10.773 GiB`. Batch 3 removed `23` empty, pre-Protocol failure,
zero-effective duplicate-local, and superseded-prepared roots only after
protecting `73` active-doc roots and verifying retained canonical evidence.
Batch 4 used a tracked-evidence inventory and removed only a reconstructible
pre-Protocol replay failure plus an empty wrapper shell; roots with unique
traces or raw metrics remained. Batch 5 removed 20 copied prepared shells after
full campaign-tree equality checks against retained CVRP/Warehouse canonical
roots. Batches 6-7 removed 64 pre-campaign shells and two superseded failures,
while retaining all unique/referenced large-history evidence. Batch 11 removed
12 superseded failures/preflights or exact-subset roots with named retained
owners and zero unique scientific evidence. Batches 8-10 and 12 removed
`2,850` Git-restorable static subtree copies totaling `6.759 GiB`
without deleting more roots or changing registry/DB/metrics/trace/formal/log
counts. Batches 13-16 removed nine more planned-only, pre-Protocol, or
zero-round exact-subset roots with named retained owners, retained reserved
schema or byte-identical copied campaign, and zero unique scientific evidence.
Batch 17 removed one additional pre-campaign shell only after its substantive
patch payload was proved byte-identical to a retained completed eight-round
owner. Batch 18 removed a pre-evaluation permission-failure replay shell and a
zero-effective capacity-blocked successor only after isolated database review
proved complete retained-owner coverage. `752` roots remain and about
`37 GiB` is currently available.
Read-only batch 19 rescanned those `752` roots and found no further exact-safe
whole-root deletion: every plausible boundary candidate retained a report
reference, a unique trace or research artifact, newer nonzero evidence, or no
provable complete retained owner. It therefore deleted zero roots and zero
bytes; the cleanup boundary is now unique research evidence, not disk space.
Exact whole-root,
gray, disposition, subtree-hash, and restore manifests are recorded in
`scion/docs/experiments/v0.4/v04-experiment-retention-cleanup-20260716.md`.
Current R6-R11c, baseline-strength inputs, recent roots, and ambiguous roots
remain protected. The runner ownership defect and its duplicate temp files are
closed; formal campaign metrics remain protected.

Warehouse direct-v3 has proven effective research behavior but not a retained
current improvement. R3 performed two substantive algorithm rounds, used the
first result to change direction, expanded the exact cumulative candidate to
`28/28` valid pairs without another provider call, and then correctly abandoned
it on `15/15` valid locked validation pairs. Champion stayed v1. The accepted
closure design is
`scion/docs/planning/v0.4/v0.4-warehouse-effective-research-closure-design-20260716.md`.
It protects the R2/R3 roots, aligns protocol counts to the distinct manifest
population, resolves locked-group semantics, adds no-LLM constraint probes,
and decomposes R3 into fixed destroy-only/merge-only/cumulative arms. No new
warehouse generative root is queued.

Fresh eight-round R11b is terminal and read-only at
`/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r11b-8r-gpt56sol-8r-gpt56sol-20260716T115118Z-claw`
with terminal wrapper PID `2879552`. Its clean detached runtime is
`/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-6a2f6765` at
exact pushed code commit `6a2f6765ff141b8f1d17c3fae0391df73f3ac580`.
It uses `gpt-5.6-sol / direct_v3`, `ROUNDS=8`, and the 30-second scientific
solver subprocess fallback. It is fresh: no resume, force controls, retry,
semantic budget, or truncation. Completion preflight is authenticated, HTTP
`200`, and nonempty; only the `SCION_SHARED_PROXY_KEY` environment-variable
name is persisted. The elapsed-time-SA lead was not forced.

R11b H1/C1 each used one provider call. The agent independently selected the
R10 H4 granular CROSS mechanism family, but implemented a non-identical 8-NN,
original-orientation segment exchange with explicit `cross_exchange` telemetry.
Verified/executable identity is `82878ff8...`, and artifact, materialized file,
source digest, and workspace agree. Initial screening completed `32/32` valid:
case `4/1/3`, pair `19/11/2`, median `+4.75`, CI `[-2.5,13]`, then committed
`expand_screening`. Expanded screening completed `48/48` valid: case `6/5/1`,
pair `30/16/2`, median `+3`, CI `[-3.75,15.5]`. CROSS was active in every pair,
but embedded VNS consumed about `84.7-85.5%` of candidate algorithm time and the
wider split did not show stable gain.

The expanded Protocol completed, but finalization failed with
`decision completion source branch is not the persisted owner`: the source had
been persisted at `screening_expand_count=0` and then mutated in memory to `1`.
Campaign exit is zero; strict readiness and effective wrapper exit are `64`.
Status is `valid_but_incomplete`, only `1/8` typed Protocol rounds committed,
and the expanded raw gate/Decision must not be presented as formal evidence.
This is a P1 framework transaction defect, not a provider, infra, solver, or
gate failure. R11b must not be resumed or backfilled.

The repair now computes prospective counts without mutating source, passes the
effective count to Protocol/DecisionFeatures, and consumes expansion only on the
completed Decision target. The owner guard stays strict. Focused and adjacent
tests plus independent review find no P0/P1 blocker; the correctly rooted full
Scion suite passes `2058` with one existing skip, and compileall/diff-check pass.
R11b's orphan formal artifact and the legacy nontransaction Decision crash
window remain explicit P2 follow-up debt.

The preceding fresh R11 root ending `20260716T114132Z-claw` is terminal and
invalid. Its one H/C pair reached verified candidate artifact recording, then
failed with `ENOSPC` while the filesystem had only `4.6 MiB` free. It completed
zero Protocol rounds and is not algorithm evidence. It was not resumed or
retried in place. Only the generated `/tmp/pytest-of-clawd` tree was removed,
restoring about `7.0 GiB`; historical experiment roots remain intact. R11b is
the distinct clean replacement.

Fresh eight-round R10 is terminal and read-only at
`/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r10-8r-gpt56sol-20260716T063211Z-claw`
with terminal wrapper PID `2848393`. Its clean detached runtime is
`/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-c936cde4` at
exact pushed commit `c936cde41d746c9cbfcd308bae84ba54d85c7f4a`. It uses
`gpt-5.6-sol / direct_v3`, `ROUNDS=8`, and the 30-second scientific solver
subprocess fallback. It is fresh: no resume, force controls, retry, semantic
budget, or truncation. Completion preflight is authenticated, HTTP `200`, and
nonempty. The launcher stores only `SCION_SHARED_PROXY_KEY` as the environment
variable name; no key value is persisted. It completed all `8/8` experiments
at `2026-07-16T10:31:55Z`; wrapper, campaign, postrun rebuild, and readiness
exited zero. Status is `valid / complete`,
`current_run_analysis_ready=true`, `delegation_ready=true`, and the failure
report is empty.

H1 implemented a real
ejection-chain repair in `destroy_repair.py` and `scheduler.py`; H/C were each
single-attempt and all `32/32` pairs were valid with zero candidate/champion
failure. The algorithm was strongly negative: pair `1/21/10`, case `0/5/3`,
median `-14.25`, CI `[-48.75,0]`, actual ALNS iterations `69/1665`, and
ejection-chain `30 attempts / 0 accepted`. Protocol failed only
`SCREENING_FAIL_WIN_RATE`; Decision `continue_explore` committed. Formal v3
replay now writes the correct relative
`base_workspace_ref=champions/champion_v1`, with complete identity and matching
current/replay/verified/executable hashes.

H2 explicitly received H1's route-limit and throughput evidence and added
candidate-list incremental VNS plus bounded CROSS exchange in `local_search.py`,
but retained H1's bad repair. H2/C2 were single-attempt and `32/32` valid with
zero candidate/champion/fleet failure, yet remained negative: pair `2/26/4`,
case `0/7/1`, median `-7.25`, CI `[-50.5,-2.0]`, ALNS `62/1665`. Inherited
ejection was `31 attempts / 0 accepted / 31 route-limit / 718244ms`. Protocol
failed win rate and Decision committed; formal base ref and all identities pass
at `65f379...`.

H3 directly removes ejection-chain from the active scheduler portfolio and
adds cost-aware feasible repair selection. Initial screening was `32/32` valid,
case `4/3/1`, pair `17/13/2`, median `+1.75`, CI `[-2.5,19.5]`; Protocol
requested an independent 48-pair expansion. Expansion completed `48/48` valid
with zero failures and `SCREENING_PASS`; Decision `queue_validate` committed.
Validation completed `32/32` valid with zero failures, case `7/0/1`, pair
`26/4/2`, median `+37.75`, CI `[6,199]`, and
`VALIDATION_PASS_HIERARCHICAL`; Decision `queue_frozen` committed. Frozen has a
fresh 24-pair target and completed `24/24` valid with zero failures, but
reversed to case `4/4/0`, pair `11/13/0`, median `-19.5`, CI `[-350,98]`.
Protocol returned `FROZEN_FAIL_HIERARCHICAL_UNCERTAIN`; Decision abandoned the
branch. Champion remains v1. Ejection activation was zero and initial ALNS
recovered to `1010/1665`.

Do not attribute that recovery to H3's cost-aware weights: every solve stayed
below `SEGMENT_LENGTH=100`, so no updated weight was reused in the same solve;
runtime-density/weight telemetry is also absent. Treat ejection removal as the
supported causal change; frozen establishes split instability rather than a
promotable result.

H4 then opened a fresh branch from champion v1 and added a granular CROSS
exchange of length-one-through-three route segments, verified at `454b6ab2...`.
Screening was `32/32` valid, case `6/1/1`, pair `21/7/4`, median `+3.75`, CI
`[0,7.5]`, and passed. Validation was `32/32` valid, case `4/0/4`, pair
`20/5/7`, median `+11.75`, CI `[0,79.75]`, but the current gate classified the
no-loss hierarchical uncertainty as `VALIDATION_FAIL_NO_HIERARCHICAL_GAIN`
and abandoned it. The case win rate `0.5` cannot pass the `0.66` gate, but the
predeclared 8-to-12-case expansion can still mathematically reach it. The
repair sends only this first, zero-loss, non-all-tie, reachable uncertain shape
to the existing one-time expansion; expanded evidence still must meet the
original case-level policy.

R10 also exposes cross-branch research-memory loss. H2 and H3 received one and
two complete canonical screening records; after H3's branch was abandoned, H4
received `experiment_history=[]` although that terminal branch durably owned
four records. H4 consequently repeated the CROSS family already attempted by
H2. The repair aggregates all same-campaign canonical screening records from
active and terminal durable branches and adds only context-local
`source_branch_id / current|sibling` provenance. It does not expose
validation/frozen details, terminal state, raw refs, patch bodies, or failure
prose and introduces no ledger, summary substitution, top-N, budget,
compression, or truncation.

R10's five formal v3 artifacts pass apply-check and materialization; all six
Decision intents are committed; both branches are abandoned; active slots,
candidate staging, workspaces, and promotion journals are empty. Champion v1
hash `06820ecd...` is unchanged and there is no promotion dossier.
`formal_ready=false` only records normal completion without promoted final
evidence; it does not block current-run analysis.

The R10-derived context and validation repairs are implemented and independently
reviewed. Campaign-wide canonical screening history now survives terminal
reopen, retains complete durable plus live evidence, and adds only context-local
source provenance. Duplicate ownership, provenance spoofing, unknown owners in
a complete campaign scope, and corrupt terminal evidence fail closed. The
validation change uses only the existing one-time expansion when the initial
no-loss uncertain case result can still reach the unchanged threshold.
Focused tests pass `168`; the correctly rooted full Scion suite passes `2053`
with one existing skip. Compileall and `git diff --check` pass. The changes add
no retry, semantic budget, truncation, top-N, compression, summary substitution,
blacklist, or new gate.

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
reconstruct the candidate. No generative root is live; R11c is the latest
terminal control and remains read-only.

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

The runner-ownership focus passes `152`, and the correctly rooted standard
Scion suite passes `2075` with `1` skipped in `474.66s`. `compileall` and
`git diff --check` pass. The earlier final affected
transaction/report/guidance set passed `198`; the champion-ref repair focus
passed `58`.

Excluded and preserved:

- tracked user change: `scion/docs/v0.4-measurement-readiness.md`;
- unrelated untracked historical/future docs shown by `git status`.

The non-generative problem lanes have advanced. CVRP B0 passed independent
code and science review with P0=0/P1=0 and is pushed at `90a109b2`; its accepted
dry manifest is `0151e2be...882b1`. Formal B1 is now running under user unit
`scion-cvrp-b1-20260718T074653Z.service` at the fresh root ending
`20260718T074653Z-claw`; F1 stays locked until all 256 raw results, the integrity
check, closed receipt, and comparison report are accepted. The earlier root
ending `20260718T074602Z-claw` stopped before manifest publication and is
superseded non-evidence. The exact live/superseded identities are in
`scion/docs/experiments/v0.4/v04-cvrp-b1-mechanism-matrix-inflight-20260718.md`.

Warehouse W1 is complete at `0599fc29`. W2's origin-group semantics design is
fixed at SHA `86bdc1ae...b970`, with preservation manifest SHA
`0ee66091...dfc9`; independent architecture and domain reviews report no P0/P1.
This freezes design only. W2 implementation must still make the exact allowed
prose/empty-string initializer correction, produce the directed Oracle/adapter/
fixed-candidate-MILP probe artifact, replay all protected hashes, and pass two
implementation reviews before W3 unlocks.

## Immediate Resume Actions

1. The fresh-only boundary is fixed-hash reviewed and the rejected executable-
   classifier/DSL prototype is removed. Keep historical roots read-only and
   non-authoritative.
2. Low-frequency monitor the live CVRP B1 unit and accept B1 before F1. In
   parallel, implement the frozen Warehouse W2 contract and accept its probe
   artifact before W3. These lanes do not require proposal ownership.
3. Keep Checkpoints A and B dormant while implementing fresh activation
   primitives and isolated fixtures: staging/publication capabilities, offline
   main-only bootstrap, no-replace publication, phase receipts, and exact
   cutover recovery. Do not make production runnable or claim final all-writer
   closure yet.
4. Complete D2b.1-D2e, D3-D4, and L1-L3 for the fresh path.
5. On that same exact commit, freeze the final writer/composition manifest and
   pass D2b.0b.C/V, reopen/crash goldens, the full no-LLM end-to-end control,
   and two independent reviews with no P0/P1.
6. Resume generative work with a fresh Warehouse 2-4 observation control and
   CVRP order-balanced canonical/pure-ALNS campaigns. Use canonical transplant
   replay before claiming a pure-profile positive as a canonical improvement.

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
