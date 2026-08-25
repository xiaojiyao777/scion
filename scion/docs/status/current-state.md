# Scion v0.4 Current State

*Last updated: 2026-08-25*

Read [`../../TASK.md`](../../TASK.md) first. The sole architecture authority is
[`../../design/scion-architecture-v3.md`](../../design/scion-architecture-v3.md).
The direct-runtime addendum narrows current implementation examples only.
Historical experiment reports and Git history preserve chronology; they do not
create current execution authority.

## Objective

Warehouse acceptance is complete. Synthetic Warehouse reached and independently
retained `v1 -> v2 -> v3`; production-style Warehouse reached and independently
retained `v1 -> v2`.

CVRP remains open. B0/v1 is champion. No candidate has completed the declared
screening -> validation -> frozen -> deterministic promotion -> independent B0
retention chain. Scion can produce testable hypotheses, patches and development
screens, but it has not yet demonstrated effective CVRP research under that
acceptance standard. A valid negative observation or partial stage does not
close the task.

## Current boundary

The active autonomous H/C research path is:

```text
safe complete problem/source context
  -> optional finite H research, or direct one-shot
  -> at most one tainted H -> Hypothesis Contract
  -> optional finite C research bound to that approved H, or direct one-shot
  -> at most one tainted C -> Patch Contract
  -> isolated Workspace -> Verification
  -> problem Protocol -> Safe Features -> deterministic Decision
```

Finite Creative turns are resource-bounded internal deliberation, not provider
retry. One attempt exports at most one H and one C. Creative drafts and
`research_basis` are tainted. Source/history/public-development values and
problem-owned family association are non-authoritative proposal-only context.
Only an exported H/C proceeds through Contract -> Verification -> Protocol ->
Safe Features -> Decision.

The narrow provider-free fixed-candidate estimand has no H/C: it uses
`run_fixed_candidate_funnel.py`, a fresh output directory and the same
complete-pair canary/Protocol/Safe Features/Decision chain where applicable.

Retain ordinary references, exact scientific source/stage reuse, fixed
case/seed selection, minimal append-only lineage and local subprocess isolation.
Remove self-proof lifecycle: object/capability identities, owner registries,
leases, issuance/claim/spend, registration, nonce, intent/commit/closure,
activation/reopen proof, source-acceptance receipts, self-hashing manifests,
duplicate digest closure, promotion/readiness dossiers and authorization
refreeze/sentinel state machines.

Distribution, deployment, installation, packaging, reproducible-build,
root/systemd/D-Bus/cgroup/native-spawn and H11 authority work are outside the
current project boundary.

`Frozen Holdout`, split manifests, seed ledgers, ordinary source references,
problem-owned operator registries, new-directory collision protection and
subprocess cleanup remain scientific or operational mechanisms, not authority
lifecycles.

## Accepted evidence

- Warehouse exact results and roots remain in the linked experiment reports in
  [`../../TASK.md`](../../TASK.md).
- CVRP R3 contains a complete positive quality screen followed by an externally
  interrupted validation. It is valid partial science, not a promotion and not
  a resumable candidate.
- Later CVRP diagnostics and short experiments remain preserved under
  [`../experiments/v0.4/`](../experiments/v0.4/) and in the
  [longitudinal mechanism audit](../experiments/v0.4/v0.4-cvrp-longitudinal-mechanism-reopen-audit-20260815.md).
- R67 is terminal `PREP_INVALID / AUTHORIZED_PREFLIGHT_LIVE_CONTROL_ROOT_COLLISION / KNOWN_ZERO_BEFORE_SCIENTIFIC_DELEGATION`: solver, provider, Protocol and Decision observations are zero, the one-shot was consumed, and no candidate-quality conclusion exists; the complete historical record remains in its
  [preregistration](../experiments/v0.4/v0.4-cvrp-r67-provider-free-r3-cumulative-exact-source-full-funnel-confirmation-preregistration-20260815.md).
- M7-FC1 is terminal `CANDIDATE_SUBJECT_VETO`. Initial screening expanded and
  fresh expanded screening passed, but validation stopped on candidate
  `X-n200-k36`, seed 2069, after the runtime audit reported a solver algorithm
  error. No validation result, frozen result, promotion or retained-B0 result
  exists; the exact evidence and claim boundary remain in its
  [preregistration](../experiments/v0.4/v04-cvrp-m7-fc1-r3-cumulative-new-population-full-funnel-preregistration-20260816.md).
- M28 is terminal `stopped / execution_resource_exhausted / valid_incomplete`.
  One candidate completed a valid initial screen but failed case quality; no
  expanded or later stage ran, no carrier qualified and conditional M29 was not
  materialized. Its exact terminal and claim boundary remain in its
  [preregistration](../experiments/v0.4/v04-cvrp-m28-seen-bank-qualification-autonomous-continuation-preregistration-20260824.md).
- M30 is terminal `stopped / execution_resource_exhausted / valid_incomplete`.
  Its only formal candidate completed `6/6` valid initial pairs but failed the
  preregistered initial case-quality gate; two later H attempts produced no
  formal chain. No expanded or held-out stage ran, the public carrier audit
  returned `QUALIFICATION_CARRIER_UNAVAILABLE`, and conditional M31 expired.
  Its exact terminal and claim boundary remain in its
  [preregistration](../experiments/v0.4/v04-cvrp-m30-fresh-development-qualification-only-autonomous-continuation-preregistration-20260824.md).

## Active work

`TASK.md` modules M0-M6 are closed. The subtraction removed the dormant
platform/activation stack, mutable owner and candidate graphs, prompt/source
identity, two-phase promotion, duplicate scheduler/status/accounting closures,
provider-call receipts and historical compatibility readers. The live path now
passes ordinary values directly: C is bound to the same-attempt exact
Contract-approved H, one `CandidateWorkspace` enters Verification and Protocol, Decision
selects one branch action, and promotion is one operation.

M7-FC1 ran once under explicit authorization and is terminal
`CANDIDATE_SUBJECT_VETO / ONE_SHOT_CONSUMED`. Initial screening completed 32/32
valid pairs and expanded; fresh expanded screening completed 96/96 valid pairs
and passed. Validation then stopped on candidate `X-n200-k36`, seed 2069,
because the runtime audit reported an algorithm error while packing customer
106 into 36 routes. No validation stage metrics, frozen stage, promotion
snapshot or retained-B0 result exists.

CVRP remains open. M8 is complete: the normal `scion run` path accepts an
optional bounded `--research-input`, records it once in a fresh campaign, and
lets a problem-owned provider project ordered observations into H. Raw evidence
does not enter C, Protocol or Decision; C still receives the Contract-approved
H and editable source. Generic Scion has no CVRP/Warehouse evidence fields or
branches, and no registry, identity, hash, receipt or reopen lifecycle was
added. The design and implementation boundary are recorded in the
[autonomous prior-evidence research design](../experiments/v0.4/v04-scion-autonomous-prior-evidence-research-design-20260817.md).

M8 validation collected 1,635 tests. A broad 301-test provider-/solver-free
selection passed, including a 21-test independent boundary suite covering
exactly-once H exposure, order, absent/differently-shaped inputs, recursive
sensitive-field rejection, C isolation, authority isolation and generic-core
domain neutrality. Production Ruff F/E9, touched-file Ruff import checks,
in-memory compilation and `git diff --check` passed.

The M9 resource prerequisite is also complete. Commit `9ae49b21` adds optional
`--provider-call-cap` and `--outer-hardwall-sec` to the normal CLI. H and C
share one in-memory pre-dispatch counter; exhaustion produces
`RESOURCE_EXHAUSTED / PROVIDER_CALL_CAP_EXHAUSTED` without another provider
request or trace. The outer watchdog uses SIGTERM rather than the provider's
SIGALRM, interrupts a hung provider, and lets the runner's `BaseException` path
kill and unregister an active solver child before terminalization as
`INTERRUPTED / OUTER_HARDWALL_EXCEEDED`. Configured limits are written once as
ordinary `resource_envelope.json`; no registry or proof lifecycle was added.

M9 is terminal
`PRE_MGR_RUN_FRESH_OUTPUT_SELF_COLLISION / ONE_SHOT_CONSUMED`. Its exact
carrier passed source, input, output-absence and local proxy metadata checks.
Before `mgr.run`, however, `ExperimentProtocol` created the campaign `metrics/`
directory and `CampaignManager` then rejected that directory under the fresh
output invariant. The preserved root contains only that empty directory. H,
C, Contract, Verification, Protocol, Safe Features, Decision, provider
generation, solver and scientific observations are all zero; no typed campaign
terminal exists. This is a framework launch-path finding, not evidence about
Agent research effectiveness or CVRP algorithm quality. The exact preparation
and terminal record are in the
[M9 preregistration](../experiments/v0.4/v04-cvrp-m9-autonomous-m7-prior-development-screen-preregistration-20260817.md).

The generic initialization-order bug was fixed without weakening the strict
fresh-output check. After one corrected, non-scientific shell preflight, the
authorized rerun on carrier `b558695b` completed normally and stopped at the
requested single evaluated screening. It used four provider calls and 27
solver subprocesses. Candidate one was rejected by Verification unit tests;
candidate two passed Contract, Verification and canary, then completed all 12
screening pairs. Protocol returned `fail / SCREENING_FAIL_CASE_QUALITY` and
Decision returned `abandon / CANDIDATE_RUNTIME_FAILURE`. Champion remains v1;
validation, frozen, promotion and a third candidate are zero. The result is
positive evidence for the bounded autonomous V3 framework chain, negative/mixed
evidence for this research attempt, and no evidence of algorithm improvement
or generalization. The original failed root and terminal rerun root are both
preserved; no retry, later development stage, R67 recovery or formal rung is
authorized. Full facts and claim limits are in the M9 preregistration.

The five continuity gaps exposed by M9 are now closed in committed generic
framework code. Protocol attributes candidate-only, champion-only, shared and
bilateral failures pair-locally. Safe Contract/Verification rejections reach
the next H. C can use a bounded read/search/revise/test/revise/finalize session
whose public tests run in an isolated development sandbox and never replace
formal Contract or Verification. Explicit `--research-history` transports
ordinary H, patch, rejection, screening Protocol and Decision values to H only,
without reading old campaign databases or summaries. C source context is built
from the approved target, transitive local dependencies, callers and related
public tests; peer source is read on demand and generic core has no CVRP or
Warehouse selection branch.

M10 is terminal. Five autonomous H values reached bounded C research, but two
drafts failed D4 public regression, two drafts were invalid duplicate-file
payloads, and the last stopped at the shared provider cap. The terminal state
is `RESOURCE_EXHAUSTED / PROVIDER_CALL_CAP_EXHAUSTED`, with 18 provider calls,
four research rejections, zero formal candidates, zero solver calls and no
algorithm evidence.

The generic failure channel is corrected at clean production commit
`fcad63d78fbe11ecef9bff5439ab6a62cf844518`: invalid drafts return enumerated
open-session action feedback, public test failures return an enumerated reason and public test path,
and transcript accounting counts actual provider wire. M11 is terminal
`RESOURCE_EXHAUSTED / PROVIDER_CALL_CAP_EXHAUSTED` after 30 provider calls,
three C research rejections, zero formal candidates and zero solver/Protocol
observations.

Host-only replay showed that the repeated M11 D4 failures were not candidate
failures. The development scratch omitted the frozen `policies` package
markers, making `policies.__file__` null before the candidate entrypoint ran.
Commit `0860331b` adds those two read-only files to the CVRP problem-owned
development closure; both retained M11 drafts then pass D1-D4. M12 ran once
with that correction. Its first two attempts were C research rejections. The
third autonomous candidate passed bounded development checks, formal
Verification and canary and completed all 12 screening pairs. Ten pairs were
valid; the two invalid `X-n256-k16` pairs were correctly classified as
bilateral champion-and-candidate runtime failures rather than candidate-only
failures. Among valid pairs the candidate produced two case wins, one case
loss and two ties; the screening gate was `fail /
SCREENING_FAIL_CASE_QUALITY` with partial champion evidence.

M12 then stopped as `unhandled_exception` while appending ordinary research
history: the safety validator rejected the canonical aggregate key
`case_feedback[].seed_pattern`. Consequently the complete raw Protocol metrics
and the ordinary experiment event's `continue_explore` Decision are durable,
but the evaluated StepRecord, Safe Features projection and typed execution
outcome are not. M12 is not a valid completed campaign and is not retried.
Commit `7737bb0a`
corrects that generic schema boundary and also removes the redundant mandatory
`ready` turn after an unchanged draft has passed development checks. See the
[M12 preregistration](../experiments/v0.4/v04-cvrp-m12-corrected-development-closure-continuation-preregistration-20260820.md).

M13 completed validly from clean carrier `fa235837`. Its committed input
contained the two M12 rejection records plus one strict reconstruction of the
complete M12 screening; runtime Scion did not reopen M12. It used ten provider
calls and produced two autonomous H/C candidates. Both passed bounded
development checks, Patch Contract, Verification and canary, completed 12/12
screening pairs, wrote ordinary history and received `continue_explore`.

The first candidate lowered `SIGMA_ACCEPTED` and was negative: zero case wins,
two losses and three ties, with total-distance CI `[-457, 0]`. The second made
route removal honor its sampled destroy quota exactly and was mixed: one win,
one loss and three ties, with CI `[-2.1025439344, 20.5]`. Both gates were
`SCREENING_FAIL_CASE_QUALITY`; champion remains v1. Each stage had ten valid
pairs and two `X-n256-k16` failures attributed as shared champion-and-candidate
baseline failure, with candidate-only failures zero. No validation, frozen,
promotion or retained-B0 stage ran. See the
[M13 preregistration](../experiments/v0.4/v04-cvrp-m13-history-safe-continuation-preregistration-20260820.md).

M14 completed validly from clean carrier `ed307edd`. Four autonomous attempts
used 17 provider calls: two typed C responses were safely rejected before a
candidate, and two candidates passed development checks, formal Contract,
Verification and canary and reached screening. The reversal-aware 2-opt-star
candidate was negative/mixed (one case win, two losses, two ties; CI
`[-761.5, 1.5]`). The constant-time boundary-delta candidate was uniformly
negative and failed the runtime solution audit on both X-n195-k51 seeds because
its state update duplicated customers and omitted others; Decision returned
`abandon / CANDIDATE_RUNTIME_FAILURE`. Both stages continued to classify the
two X-n256-k16 failures as shared rather than candidate-only. Champion remains
v1 and no later stage ran. A new problem-owned public unit test now exercises
an improving cross-route exchange and requires exact customer conservation;
it passes B0 and fails the preserved M14 patch. See the
[M14 preregistration](../experiments/v0.4/v04-cvrp-m14-continuous-mechanism-refinement-preregistration-20260820.md).

M15 completed validly from clean carrier `8ec13e29`. Both autonomous candidates
passed the new public customer-conservation test, all other development checks,
formal Contract, Verification and canary. Candidate 1 made intra-route two-opt
scoring exact and constant-time: it produced two case wins, zero losses and
three ties, CI `[0, 439]`, and Protocol returned
`SCREENING_EXPAND_INITIAL_QUALITY`. Candidate 2 extended the helper to a second
polish path but regressed X195, yielding one win, one loss and three ties, CI
`[-644.5, 2.1025439344]`. Both screens retained two shared X256 failures and no
candidate-only failure. Decision's partial-champion safety rule returned
`continue_explore`, so no expanded stage ran; champion remains v1. See the
[M15 preregistration](../experiments/v0.4/v04-cvrp-m15-customer-conservation-continuation-preregistration-20260820.md).

M16 completed validly from clean carrier `78b6e256`. Both autonomous
candidates passed public development tests, formal Contract, Verification and
canary. The first deferred repeated solution-wide repair rebuilding and was
negative/mixed: B/P/A/F tied, X195 lost 97.5, CI `[-97.5, 0]`. The second
replaced `_or_opt` trial reconstruction with an exact directed constant-time
delta and produced a second positive initial development screen: A improved by
2, X195 improved by 244, B/P/F tied and CI was `[0, 244]`. Both screens had ten
valid pairs, two shared X256 failures and zero candidate-only failure. Protocol
returned `SCREENING_EXPAND_INITIAL_QUALITY` for candidate 2, but Decision's
partial-champion safety rule kept the branch in exploration. No expansion,
validation, frozen or promotion ran; champion remains v1. See the
[M16 preregistration](../experiments/v0.4/v04-cvrp-m16-positive-mechanism-continuation-preregistration-20260820.md).

M17 stopped after its two-call canary and before the first formal population
pair. The fixed-screen config incorrectly made the declared initial and
expanded case counts both six; `ExperimentProtocol` rejected it because
expanded screening must be strictly larger. The terminal is
`failed / UNHANDLED_EXCEPTION`; metrics, Protocol, Safe Features, Decision and
candidate-quality observations are zero. The root is preserved and not
retried. See the
[M17 preregistration](../experiments/v0.4/v04-cvrp-m17-oropt-fixed-candidate-confirmation-preregistration-20260820.md).

M18 completed once from carrier `1703d225`. Its fixed-candidate expanded screen
attempted 24/24 pairs: 20 were valid, four `X-n627-k43` pairs were shared
champion-and-candidate construction failures, and candidate-only failures were
zero. Four valid cases tied and `X-n351-k40` improved by 26.5 distance units,
giving one win, zero losses, four ties and CI `[0, 26.5]`. Median runtime was
effectively unchanged (`candidate/champion = 0.9998438774`). Protocol returned
`SCREENING_FAIL_CASE_QUALITY` plus partial-champion evidence, Decision returned
`continue_explore`, and terminal type was `CONFIRMATION_NOT_SUPPORTED`. No
provider, H/C, patch, validation, frozen or promotion action ran. The candidate
is safe on this population but is not confirmed as a broad or faster
improvement. See the
[M18 preregistration](../experiments/v0.4/v04-cvrp-m18-oropt-fixed-candidate-confirmation-preregistration-20260820.md).

M19 completed validly from clean carrier `45fd6a41`. Both autonomous
candidates passed bounded development checks, formal Contract, Verification
and canary and completed the fresh six-case/two-seed screen. Each produced
three case wins, zero losses and two ties, with CI `[0, 15]` and `[0, 44]`;
both had two shared X429 construction failures and zero candidate-only failure.
Protocol recommended expansion but partial champion evidence kept Decision at
`continue_explore`, so no later stage ran. The two patch files were
byte-distinct but semantically equivalent directed constant-time `_or_opt`
implementations. Thus M19 supplies stronger positive development evidence for
that mechanism and negative evidence about current-campaign research
diversity: the second H received the first experiment yet repeated it. No
validation, frozen, promotion, global-improvement or production claim follows.
See the
[M19 preregistration](../experiments/v0.4/v04-cvrp-m19-fresh-population-continuous-research-preregistration-20260820.md).

M20 is terminal `stopped / valid_incomplete / execution_not_evaluated`.  The
generic frontier instruction succeeded: H moved beyond the repeated `_or_opt`
rewrite and autonomously proposed an exact directed O(1) `_swap` edge delta.
The candidate passed development checks, Contract, Verification and canary,
then completed 12/12 valid initial-screen pairs with three wins, zero losses
and three ties; case-median distance improvement was 6 with CI `[0, 460.75]`
and median runtime was effectively unchanged.  Protocol correctly requested
expanded screening.  The next call stopped before science because the frozen
config declared equal initial and expanded case counts.  Thus no second H,
expanded result, validation, frozen, promotion or champion change exists.  The
root is preserved and not retried.  Generic multi-round shape validation is
being moved ahead of provider/solver work before a fresh continuation.  See
the [M20 preregistration](../experiments/v0.4/v04-cvrp-m20-mechanism-frontier-continuation-preregistration-20260820.md).

M21 is terminal `stopped / valid_incomplete / execution_blocked_infra`.  Its
first C payload was safely rejected.  Its second autonomous candidate removed
a redundant VNS relocation neighborhood, passed all development/formal gates
and completed 6/6 valid initial pairs, but all three cases tied and the tiny
median runtime reduction was not meaningful; Protocol failed case quality and
Decision continued exploration.  The third H pivoted to deadline-fraction
simulated-annealing cooling.  After staging a first valid revision, its sixth C
research turn received an upstream 504 with no output, so Scion stopped without
retry.  It used 14/30 provider calls and wrote three ordinary history records;
expanded, validation, frozen, promotion and champion change are zero.  See the
[M21 preregistration](../experiments/v0.4/v04-cvrp-m21-strict-expansion-continuation-preregistration-20260820.md).

M22 completed validly from clean carrier `cdbd582d`.  Three autonomous attempts
used 13 provider calls: one destroy-operator draft was safely rejected, while
two candidates passed bounded development checks, formal Contract,
Verification and canary and completed 6/6 valid initial-screen pairs each.
The deterministic construction portfolio tied all three cases.  The exact
inter-route 2-for-2 exchange tied two cases and lost `B-n57-k9` by 10 distance
units, giving zero wins, one loss, two ties and CI `[-10, 0]`.  Both Protocol
results were `fail / SCREENING_FAIL_CASE_QUALITY`; Decision continued
exploration, champion remains v1, and no expanded or later stage ran.  M22
confirms provider recovery and the continuous V3 chain, but supplies negative
mechanism evidence rather than algorithm improvement.  See the
[M22 preregistration](../experiments/v0.4/v04-cvrp-m22-post-infra-continuation-preregistration-20260820.md).

M23 framework preparation is implemented and independently reviewed. H may now
perform a finite, resource-bounded read/search research session over complete
ordinary source and history indexes before exporting one proposal. Its required
`research_basis` records what it read, the nearest prior work, material delta,
alternatives and an observable prediction, but remains tainted and never enters
Protocol or Decision. C retains its finite read/search/revise/public-test path
and still exports at most one patch proposal bound to the exact approved H. The
direct one-shot path remains available and byte-compatible when research limits
are absent.

Problem-owned CVRP evidence can now associate a complete paired observation
with a changed mechanism family. The status is explicitly family association,
not exact activation or causal proof; incomplete comparator evidence and source
states without an actual symbol delta report unavailable. Generic Scion carries
the ordinary mapping but contains no CVRP mechanism selector, and the mapping
does not reach Safe Features or Decision.

Provider-free fixed-candidate evaluation is consolidated into one funnel. It
copies the explicitly declared baseline and candidate once into private
read-only input snapshots and uses direct byte equality, not identity or hash
authority. It then runs strict complete-pair canary -> expanded screening ->
validation -> frozen -> deterministic promotion -> separately declared retained
comparison. An ordinary per-pair solver failure is recorded and the current
formal Protocol stage completes its declared pair matrix before the driver
stops. Champion-only, shared or bilateral failures produce
`completed_incomplete / INCOMPLETE_COMPARATOR_EVIDENCE`; Decision is not called
for an incomplete main-chain stage and no later stage runs. Candidate-only
failures remain candidate evidence and reach deterministic Decision after the
stage completes. Strict canary incompleteness stops before formal Protocol.
Retained comparator incompleteness ends as
`completed_incomplete / INCOMPLETE_COMPARATOR_EVIDENCE` with
`stop_stage=retained`; it is never reported as `PROMOTED_NOT_RETAINED`.

No distribution, packaging, build, deployment, root/systemd, Trust/Hash
authority, object identity, lease, signing, registration, receipt or
duplicate-closure work is authorized by these changes. The provider-free M23
fixed-candidate funnel is now terminal `completed / NOT_CONFIRMED` at
`expanded_screening`; its strict canary passed and all 24 expanded-screening
pairs were valid, with zero candidate, champion, shared or bilateral failures.
The exact M20 candidate won `X-n439-k37` by paired-effect median `27.0` and
`X-n502-k39` by `106.5`, tied the other four cases and lost none. Overall
median delta was `0.0`, CI was `[0.0, 66.75]`, and win rate was `1/3`.
Protocol returned `unclear` and Decision returned `continue_explore` with
`SCREENING_EXPAND_EXHAUSTED_CASE_LEVEL_UNCERTAIN`. Median runtime ratio was
`1.0002066`, median runtime delta was `+8.5 ms`, and protected-objective
regressions were zero. Terminal counters were 50 solver subprocesses, 2,420
nominal subject-seconds and 3,170 guarded subject-seconds. Validation, frozen,
promotion and retained observations are zero. The output root is preserved and
the one-shot is consumed without retry. See the
[M23 preregistration and result](../experiments/v0.4/v04-cvrp-m23-m20-swap-provider-free-full-funnel-preregistration-20260821.md).
The next scientific operation is the still-unchecked serial bounded autonomous
campaign, not a repair or rerun of M23.

That next operation is now prepared as M24. It uses normal `scion run`, the
current committed B0 source, 33 ordered native research-history records through
M22 and three problem-owned prior observations ending with M23. H receives
complete ordinary source/history indexes and may spend at most eight bounded
research turns before exporting one proposal with a cited `research_basis`.
C may spend at most eight bounded read/search/revise/public-test actions plus
one independent final decision. H and C share a 34-call provider cap; SDK retry
is zero.

M24's metadata-only population has an initial three-case screen strictly nested
in a six-case expanded screen, plus declared but unreachable validation and
frozen splits. All selected cases and seeds are disjoint from the current M7,
R67, M20-M23 and tracked-input comparison inventory; this is not a globally
case-unseen claim. Two formal rounds allow either initial -> expanded reuse of
one verified branch or two autonomous initial screens. Validation, frozen and
promotion remain zero. The host does not select a mechanism, target or patch,
and the experiment makes no distribution, build, deployment or Trust/Hash
lifecycle investment. See the
[M24 preregistration](../experiments/v0.4/v04-cvrp-m24-autonomous-direction-research-development-preregistration-20260821.md).
Its first fenced-shell execution stopped in the process-absence preflight
because `pgrep` matched the enclosing shell text containing the later live
line. The output root remained absent and all scientific/provider/solver counts
remained zero. The guard is corrected to inspect Python executables only; the
single scientific invocation then ran once.

M24 is now terminal
`stopped / invalid_no_evaluated_outcome / PROVIDER_CALL_CAP_EXHAUSTED`. It used
exactly 34/34 provider calls, all in bounded H research, with no extra dispatch.
Nine plausible H drafts were rejected because every `nearest_prior_refs` list
included at least one history the same session had not both read and cited; the
tenth scheduled H stopped before dispatch at the cap. The provider-facing
schema/prompt did not state this exact requirement and the rejection was not
fed back as an in-session ordinary action result, so the Agent repeated the
same error. C, Contract, Verification, solver, canary, Protocol, Safe Features,
Decision, formal rounds and algorithm evidence are all zero. The M24 root is
preserved and consumed without retry. The next operation is a provider- and
solver-free generic H feedback/evidence-binding repair, not M24 resumption or
an automatic M25.

That generic repair is now complete. The complete source/history inventories
remain available for bounded read/search, while finalize-basis enums contain
only refs successfully read in the current session. Recognized invalid finalize
actions return fixed bounded correction categories, and repeated
INVALID/ABSTAINED H outcomes enter only a saturated H-local same-campaign
summary. When readable current source or ordinary history is available, H must
read each kind before finalizing, cite a nonempty read nearest prior, and record
a separate falsification condition. The basis, feedback and summary remain
Creative audit context and cannot enter C, Protocol, Safe Features or Decision.
Local transcript/turn/result exhaustion and the shared provider cap remain
typed resource stops.

An independent provider- and solver-free replay on the actual M25-sized context
passed with 13 source entries and 37 history/observation entries: read source,
reject an unread-history finalize with fixed feedback, read history, then
export one valid H in four bounded calls without replaying the rejected raw
body. The tracked regression separately fixes the 37-entry ordering and the
same four-action correction sequence. Two live bubblewrap isolation tests also
passed without a provider or solver. Focused regression and independent review
found no P0/P1.

M25 is now terminal `completed / valid / requested_rounds_completed` after its
single authorized invocation. Framework behavior is positive: H used three
provider calls to read current source, read ordinary history and finalize one
evidence-bound proposal; C used four calls to publicly test and independently
finalize one aligned patch. Contract, Verification and canary passed, and both
formal Protocol -> Safe Features -> Decision stages completed. Total use was
seven provider calls, 42 serial solver subprocesses and about 1,458 seconds,
with no provider retry.

The selected direction was an exact O(1) directed intra-route 2-opt delta in
`local_search.py`. It was Agent-selected, source/history-grounded, explicit
about its alternatives and falsifier, and implemented consistently by C. The
initial screen completed 6/6 valid pairs with no failure and returned
`expand / SCREENING_EXPAND_INITIAL_QUALITY`: one case win, two ties, median
delta `0.0`, CI `[0.0, 28.5]`. This is positive framework evidence and a
plausible, testable research-direction result, not causal proof.

The same verified branch then completed the declared expanded screen with
12/12 attempted pairs, 11 valid pairs and one candidate-only timeout. Across
six cases it produced one win, one loss and four ties, median delta `0.0`, CI
`[-0.5, 0.5]`. Protocol returned
`fail / SCREENING_FAIL_CASE_QUALITY`; Decision returned
`abandon / CANDIDATE_RUNTIME_FAILURE`. This is negative/mixed development
algorithm evidence. Validation, frozen, promotion and retained replay are
zero, so M25 does not establish a retained CVRP improvement or complete v0.4.
The root is preserved and consumed without retry, resume or reuse. See the
[M25 preregistration and terminal result](../experiments/v0.4/v04-cvrp-m25-evidence-grounded-autonomous-continuous-research-preregistration-20260821.md).

M26 is now terminal `completed / valid / requested_rounds_completed` after its
single authorized invocation on M25's outcome-exposed development bank. It
used 15/34 provider calls: seven H research turns, six C research turns and two
independent C final decisions. Both candidates passed Contract, Verification
and canary, and each completed 6/6 valid initial-screen pairs without failure.
Exactly 32 solver subprocesses ran serially: four Verification, four canary and
24 formal calls, with maximum concurrency one. The recorded interval from
first-branch creation to terminal status update was `1053.552895s`, well within
the hardwall; it is not the full CLI process lifetime.

Candidate 1 had case win/loss/tie counts `0/1/2`, pair counts `1/1/4`, median
delta `0.0` and CI `[-61.5, 0.0]`. Candidate 2 had case counts `0/1/2`, pair
counts `0/2/4`, median `0.0` and CI `[-90.5, 0.0]`. Both Protocol results were
`fail / SCREENING_FAIL_CASE_QUALITY`, and both Decisions returned
`continue_explore`. Therefore the two requested rounds were two candidate
initial screens: expansion, validation, frozen, promotion and retained replay
were all zero, and champion v1 did not change.

Embedded-falsifier adoption was completely observable twice in order. A
3,272-character source projected `failed` while its ordinary host checks
passed 5/5; a later 326-character source projected `passed` while its host
checks also passed 5/5. Both C sessions went directly to ready with no
post-probe revision, then finalized independently. Source bodies remain only
in the tainted raw provider response trace and were neither replayed nor
admitted to ordinary history. The enums are non-evidentiary development hints:
they did not control readiness and this non-randomized run cannot establish a
causal probe effect.

Research-direction quality was negative. H1 reimplemented a historical
mechanism. H2 read the same-campaign `history-0041` record and completed a
pivot, but its candidate was byte-identical to failed `history-0034`, which
that session had not read. `research_history.jsonl` contains exactly two
ordinary JSONL records in candidate order. Family telemetry was
`unavailable_legacy` / association-only, never exact activation or causal
mechanism evidence.

Mechanically, the bounded H/C, probe, host-test and formal paths completed as
designed. Scientifically, both paired screens are negative development
evidence only on an already outcome-exposed bank; they establish no algorithm
improvement, fresh-population result, confirmation or generalization. At the
post-terminal audit, live campaign/child/solver/bubblewrap/prlimit and
M26-named processes were zero, as were branch workspaces and probe residue; the
checked run-root temporary and launch-era `/tmp/scion_run_*` patterns showed no
M26-scoped residue. The two durable candidate workspaces are expected campaign
evidence, not leaks. The root is preserved and consumed without retry, resume,
reuse or automatic M27. See the
[M26 preregistration and terminal result](../experiments/v0.4/v04-cvrp-m26-embedded-falsifier-autonomous-continuation-preregistration-20260821.md).

The generic nearest-history audit is now implemented at ordinary H
finalization. For an otherwise valid candidate it scans the complete current
history index, deterministically ranks only usable headline-bearing entries,
routes their lexical top-1 ref, and requires that H read it and cite it in both basis arrays. The
fixed rejection contains only that existing ref. Candidate changes recompute
the requirement; a preemptive exact-ref read can satisfy it without a trigger.
The ranker reads no history body, patch or metric, judges no novelty, adds no
provider action or durable state, and does not reach C, Contract, Verification,
Protocol, Safe Features or Decision. The direct one-shot H path is unchanged.

M27 is now terminal `completed / valid / requested_rounds_completed` after one
authorized invocation under label/root
`v04-cvrp-m27-nearest-history-audit-autonomous-continuation-20260821`. The first
H prompt contained six observations plus 37 native records, exactly 43 index
entries; only the 37 headline-bearing native records were ranking-eligible.
One H session used four provider turns: source read, otherwise-valid finalize
and fixed audit trigger for `history-0030`, required history read, then accepted
finalize. Accepted coverage was 1/1 and incomplete coverage zero. The read was
not preemptive, and the accepted basis cited the required ref in both
`read_refs` and `nearest_prior_refs`.

The candidate changed after the trigger, but recomputation kept its top-1 at
`history-0030`. H did not explicitly label its `material_delta` as pivot or
refinement, so that frozen audit field is `not_observable`. Direct comparison
against all 37 ordinary priors found zero exact structured-H replays and zero
exact complete ordered-patch replays. Qualitative direction review nevertheless
describes same-mechanism refinement/reimplementation, not a pivot or proof of
novelty.

C proceeded `revise -> test_patch -> ready -> finalize_patch`. The single test
supplied a 1,199-character falsifier source; its next durable prompt projected
probe information only as `passed`, while the ordinary host outcome and all
five host checks passed. There was no post-probe revision. This is complete
trace-observable adoption, but the provider-authored probe and nearest-history
audit remain non-evidentiary and support no causal effect claim.

The campaign used 8/34 provider calls: four H turns, three C turns and one final
decision. Exactly 42 solver subprocesses ran serially with maximum concurrency
one: two Verification, four canary and 36 formal calls. Initial screening
completed 6/6 valid pairs without failure. Case win/loss/tie counts were
`1/0/2`, pair counts `1/0/5`, median total-distance delta `0.0`, CI
`[0.0, 28.5]`, median runtime ratio `0.99951391` and median runtime delta
`-9.5ms`. Protocol and Decision expanded screening.

Expanded screening attempted 12 pairs and completed 10 valid pairs. The two
candidate-only timeouts reached the declared `90s + 15s` host guard; recorded
end-to-end elapsed values were `105112ms` and `105116ms`, including bounded
post-kill drain/accounting. Both paired champion runs completed. Case counts
were `1/1/4`, pair counts `1/2/9`, median delta `0.0`, CI `[-0.5, 0.5]`, median
runtime ratio `1.00062879` and median runtime delta `+17ms`. Protocol returned
`fail / SCREENING_FAIL_CASE_QUALITY`; Decision returned
`abandon / CANDIDATE_RUNTIME_FAILURE`. The two ordinary records contain the
same structured H and complete ordered patch, recording initial then expanded
evidence for one candidate.

Family telemetry was `unavailable_current_source` / association-only.
Validation, frozen, promotion, retained comparison and champion change were
zero. The recorded interval from run-root birth to the root-directory mtime
immediately following terminal-summary publication was `1545.200343s`, not the
full shell lifetime, and the `14000s` hardwall was not hit. Post-terminal
scoped process count, active slots and children below the checked run-root
`workspaces`, `candidate_workspaces` and `archive` directories were all zero;
no M27-era `/tmp/scion_run_*` match remained. The root is preserved and
consumed without
retry, resume, reuse or automatic M28.

Mechanically, M27 establishes the live bounded audit/read/citation path and
probe projection boundary. Scientifically, it supplies negative/mixed paired
development evidence only on the outcome-exposed seen bank; M26-to-M27 remains
non-randomized and non-causal. CVRP acceptance remains unmet. See the
[M27 preregistration and terminal result](../experiments/v0.4/v04-cvrp-m27-nearest-history-audit-autonomous-continuation-preregistration-20260821.md).

M28 is terminal after its sole authorized invocation under label/root
`v04-cvrp-m28-seen-bank-qualification-autonomous-continuation-20260824`. It
exited 21 as `stopped / execution_resource_exhausted`, with valid-incomplete
run validity and `PROVIDER_CALL_CAP_EXHAUSTED` at `proposal_code`. The exact
34/34 provider calls were 25 H turns, eight C research turns and one C final
decision. Four scheduled attempts produced one evaluated formal stage, two
research rejections and the terminal resource stop; only one of the two
requested formal rounds completed.

The sole evaluated `modify` candidate passed Contract, Verification and
canary and completed initial screening `6/6` valid with zero failures. Case
win/loss/tie was `1/1/1`, pair win/loss/tie was `2/1/3`, median total-distance
delta was `0.0` and CI was `[-2.5, 206.0]`. Protocol failed
`SCREENING_FAIL_CASE_QUALITY`; Decision returned `continue_explore`, so the
candidate did not expand. A second accepted H reached C but ended
`PATCH_PROPOSAL_INVALID`; a third accepted H reached the provider cap before C
dispatch. The public terminal counters contain two research rejections, while
the three durable ordinary steps/history rows contain only one rejected row.
The omitted H abstention classification was observed through the bounded live
safe-public projection and is not reconstructable from terminal-only ordinary
history.

Exactly 16 solver subprocesses ran with observed concurrency one: two
Verification, two canary and twelve initial-screening subjects. The precise
campaign-root-birth to terminal-status-publication interval was
`1142.579593783s`; it is not full shell lifetime or a hardwall measurement.
The 15,000-second hardwall was not reached. Post-exit scoped campaign, solver,
bubblewrap and prlimit process counts were zero. One durable candidate
workspace and one artifact file in the `metrics` directory preserve the
evaluated candidate; temporary `workspaces`, `archive` and `champions` were
empty.

Expanded screening, validation, frozen, promotion and retained comparison are
zero. No branch reached `READY_VALIDATE`, so M28 is not qualified and CVRP
acceptance remains unmet. The conditional M29 selector expired without
materialization; there is no M29 prep or launch authority. Independent review
found one P1 in the frozen carrier audit: its total-branch-count equality can
false-negative a hypothetical qualified run when non-ready branch records are
preserved. It did not affect this outcome because the scientific qualification
predicate already failed and no ready carrier existed. The terminal root is
preserved and consumed without retry, resume or reuse. See the
[M28 preregistration and terminal result](../experiments/v0.4/v04-cvrp-m28-seen-bank-qualification-autonomous-continuation-preregistration-20260824.md).

The M28 P1/P2 prerequisites are repaired through qualification-only runtime
carrier `2f424a2f1b870ce05833dd6683bfe3c9d2013820`, and the final problem-neutral
qualification auditor is committed at exact M30 runtime/source base
`5d282ea8e9133e0146c47588f2310c9bd2493e50`. Candidate-carrier selection
allows preserved non-ready branches and nonmatching historical workspaces but
fails closed unless exactly one ready branch, two aligned same-H/patch screens
and one production-hash-matching durable workspace agree. Provider-safe null-H
rows retain ordinary accounting without a hypothesis headline or
candidate-specific nearest-history rank. Qualification-only runtime separately
bounds EXPLORE H/C proposal attempts, Verification-passing chains and formal
screening stages; legal exhaustion is completed/valid negative, while a
positive branch stops before heldout dispatch for postrun audit.

M30 is terminal after its sole authorized qualification-only invocation from
carrier `15f69121b83f31aa77c4a6d3cebc3bf1ba6ebaae`. It stopped
`execution_resource_exhausted / valid_incomplete` with exit `21`, qualification
disposition `incomplete`, proposal/verified-chain/formal-stage counters
`3/1/1`, initial/expanded counts `1/0`, and screening/validation/frozen counts
`1/0/0`. The sole formal candidate passed Contract, Verification and canary
and completed all `6/6` initial pairs valid with every failed-pair class and
fleet regression zero. Case win/loss/tie `0/2/1`, pair win/loss/tie `1/3/2`,
median delta `-5.5` and CI `[-6.5, 0.0]` nevertheless failed case quality;
Decision continued exploration and qualification-only cleanup parked the
chain. A second H abstained, and a third stopped at the eight-turn H-session
cap as `HYPOTHESIS_RESEARCH_TURN_CAP_EXHAUSTED`. The run used 25/60 provider
calls and 16 serial solver subprocesses; expanded screening and every held-out
stage remained zero.

The sole public postrun audit returned `QUALIFICATION_CARRIER_UNAVAILABLE`.
M31 therefore expired without identity, preparation, launch, retry or resume
authority, and the preserved M30 root is consumed. After the CLI had naturally
exited and the frozen postrun audit had already failed, a monitoring command
opened SQLite with `-readonly`; the only observed metadata change was to
`scion.db-shm`. Cached metadata showed no post-terminal mtime change to the main
database or WAL. No database hash was taken, nothing was repaired or rerun,
and the public scientific JSON/JSONL/metrics were not changed. See the
[M30 preregistration and terminal result](../experiments/v0.4/v04-cvrp-m30-fresh-development-qualification-only-autonomous-continuation-preregistration-20260824.md).

The current CVRP work is research-effectiveness M32, not another qualification.
Carrier `25b78037` implements a default-off, shared-budget, session-local K=2 H
draft bank; `b0d81ddb` adds count-only proposal-attempt telemetry; and
`bda346e9` adds a pure provider-/solver-free single-arm effectiveness scorer.
Carrier `3e97243d` adds the pure exact-five-block comparator and its cross-block
replay/`U_F` reducer. All four have only implementation and synthetic-test
evidence. They provide no matched CVRP result, population selection or live
authority, and no K=2 research benefit has yet been observed. The selected
success-cost shape is an initial-development diagnostic boundary that durably
records unchanged initial Protocol/Decision, then parks and clears the candidate
and continues from fresh B0 without expanded or held-out dispatch. That
default-off production boundary, an ordinal-only safe initial-cell producer and
a strict study-root audit must be implemented and independently reviewed before
exact resources or an outcome-blind population are frozen. Preregistration and
independent reviews remain separate gates before any live authorization. No
later H/C-reflection, multi-agent or qualification rung opens unless five
matched blocks improve both efficiency and the frozen development-quality
endpoint without evidence leakage.

The B30 safe selector saw 2,163 tracked paths, filtered 524, skipped all 18
controlled `.vrp`/`.sol` blobs before read, allowlisted 506, found zero unknown
suffixes, parsed 69 JSON/YAML files without error and found seed lines in 322.
Its 2,962-value union, 82 exclusions, 19,918 eligible M30 seeds and selected
five identities/digests exactly match the independently completed safe scan.
An earlier provisional wide replay did read those 18 tracked controlled
synthetic bodies; this real prep-boundary violation did not affect the union or
ranking. It did not open the external CVRPLIB corpus or reserved heldout raw.

## Current validation rule

Current M23 safe validation collected 1,844 tests. Exact isolated invocations
passed 340 core/proposal tests, 180 focused Protocol/campaign/funnel tests and
103 context/history/mechanism boundary tests. Production Ruff F/E9 and
touched-file import checks, in-memory compilation of 262 production Python
files and `git diff --check` passed with bytecode and pytest caches disabled.
Independent review covered the production and scientific boundaries. These
checks made no provider
request, real solver call, formal experiment, build or deployment action.

M9 preparation additionally passed 139 isolated prior-input, context-boundary,
provider-cap and hardwall tests. All three YAML files load through production
config types; the production CVRP parser loads every selected instance and
companion solution; exact case/seed overlap checks and the 32-subprocess,
1,100 subject-second and 1,580 guarded-solver-second arithmetic pass. The
explicit `python -S -B -m scion.cli.main` entry resolves the current repository
modules and exposes the new CLI flags. These checks made no provider request,
solver call or campaign directory.

Post-attempt read-only audit found one `0700` root containing one empty `0700`
`metrics/` directory, with zero files and symlinks and no live related process.
The tracked worktree and index remained clean and production source still
matched `9ae49b21`. The bounded proxy metadata checks succeeded, but provider
generation and solver counts remained zero.

No provider or formal scientific launch ran during this subtraction. Two early
local smoke/e2e pytest selections were interrupted after being recognized as
out of scope and may briefly have started local solver subprocesses; therefore
this work is not described as globally solver-zero and produced no scientific
result.

Tests whose only purpose is to prove an obsolete identity/hash/receipt/closure
topology are deleted rather than repaired. An offline reachability search may
confirm removal, but it does not become another runtime gate.

## Documentation roles

- [`../../TASK.md`](../../TASK.md): prospective modules and acceptance.
- This file: compact current operating truth.
- [`v0.4-history.md`](v0.4-history.md): curated historical milestones.
- [`../experiments/v0.4/`](../experiments/v0.4/): exact experiment designs,
  results, terminal records and claim boundaries.
- `docs/planning/v0.4/`: historical plans unless `TASK.md` explicitly adopts a
  current item.

Do not append raw authorization text, hash inventories, per-run counters or
experiment chronology here. Preserve those only in their experiment record.
