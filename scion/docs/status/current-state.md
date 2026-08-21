# Scion v0.4 Current State

*Last updated: 2026-08-21*

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
retention chain. A valid negative observation or partial stage does not close
the task.

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
