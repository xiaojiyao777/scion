# Scion v0.4 V3 Runtime and Research-Effectiveness Audit

*Date: 2026-07-12*
*Architecture authority: `scion/design/scion-architecture-v3.md`*
*Scope: current checkout, successor evidence through successor55, local Pi and Claude Code references*

## Executive Judgment

Scion has preserved several important v3 guarantees, but the current CVRP
research loop is no longer operating as the lean two-stage research process
described by v3. The dominant failure mode is now governance saturation:

- prompt projections and compatibility payloads overwhelm the algorithmic
  question;
- proposal gates reward exact fields and vocabulary more than executable
  causal quality;
- telemetry contracts conflate activity, state transitions, accepted moves,
  and objective effects;
- exact target binding turns the agent into an implementer of a human-selected
  successor rather than an independent researcher;
- experiment history is compiled into production prompt/gate source and does
  not expire;
- runtime state is represented by overlapping maps, summaries, compatibility
  properties, and report projections;
- large files and excessive fragmentation coexist: splitting more files alone
  will make the system harder to understand.

This is the risk already named in v3 section 21: governance can become so
strong that search collapses into small repairs, and context can become a log
heap. The current evidence says that risk has materialized.

The immediate recommendation is to freeze new CVRP successors after
successor55, preserve the deterministic scientific pipeline, and refactor the
proposal runtime in the following order:

1. one lossless context ownership/inventory surface before any context ablation;
2. one proposal approval boundary with host-filled audit metadata;
3. typed telemetry with explicit attribution semantics;
4. successor history as durable data, not source constants;
5. a narrow two-call proposal kernel as the default;
6. one durable runtime state and transition journal;
7. removal of compatibility projections and scattered helper modules.

## What Still Works

The audit does not treat every part of v0.4 as failed. The following are real
framework-positive evidence:

- `DecisionFeatures` remains numeric/enum/bool and rejects free text:
  `scion/scion/core/models.py:430-488` and
  `scion/scion/core/features.py:83-97,184-237`.
- Contract, Verification, Protocol, and deterministic Decision remain distinct
  major stages.
- CVRP semantics and providers remain under the problem package:
  `scion/scion/problems/cvrp/adapter.py:80-143`.
- the active solver has a small `baseline_algorithm.py` facade and named
  construction, destroy/repair, local-search, acceptance, state, and scheduler
  modules.
- screening, validation, and frozen cases/seeds remain separately declared.
- warehouse remains a useful positive control for framework behavior.

These facts justify refactoring rather than replacing the whole project. They
do not constitute CVRP solver success. CVRP still has no promotion-grade
algorithmic result, and warehouse success cannot substitute for that evidence.

## P0 Findings

### P0.1 Prompt context overwhelms the research problem

V3 Round 1 describes a small context: problem summary, champion/current code,
structured branch history, failed hypotheses, and brief sibling state. The
current path builds many overlapping raw and rendered views:

- `ContextManager.build_hypothesis_context` assembles roughly fifty fields and
  retains both source and projected forms:
  `scion/scion/proposal/context_manager/manager.py:615-1036`.
- `hypothesis_prompts.py` adds search memory, research log, branch dossier,
  cross-branch maps, follow-up policy, measurement diagnostics, opportunity,
  runtime feedback, and quality feedback:
  `scion/scion/proposal/engine/hypothesis_prompts.py:93-196`.

Successor55 provides a direct measurement. The first seven calls, before the
first screening row, consumed 612,729 input tokens; the completed run consumed
982,885 input tokens across 12 calls:

| Item | Size |
| --- | ---: |
| LLM calls before first screening / completed run | 7 / 12 |
| Input tokens before first screening / completed run | 612,729 / 982,885 |
| Completed-run output tokens | 10,431 |
| Target-intent input tokens | 149,706 |
| Hypothesis input tokens | 350,103 |
| Code input tokens | 77,176 |
| Tool-selection input tokens | 35,744 |
| Latest formal hypothesis input | 176,653 tokens |
| `Compact Research Signals` | 401,011 chars |
| embedded `launch_research_focus` | about 360,599 chars |
| `Prepared Research Obligations` | 148,243 chars |
| `Prepared Successor Focus` | 37,064 chars |

Target-intent plus hypothesis accounts for 81.6% of the pre-screening input
tokens. All 12 completed-run calls reported zero cache-read input tokens, so
the cache markings did not produce an observed saving in this run.

The root compatibility payload is itself about 338k JSON characters. It is
then serialized into compact signals, projected again into prepared
obligations, and partially projected again into successor focus. The function
named `_compact_text_signal` accepts size parameters but does not currently
enforce them, while structured compaction performs an unbounded JSON dump.

Impact:

- algorithmic source and runtime facts compete with hundreds of thousands of
  characters of governance history;
- repeated calls pay again for stable obligations;
- prompt correctness is tested by historical-text presence, encouraging more
  accumulation;
- target-intent correctness does not prove independent research when the
  desired mechanism is already bound in the prompt.

Required repair:

- create one immutable provider-visible context snapshot per call;
- first emit a lossless section/source/digest inventory and duplicate map;
- consolidate renderer ownership while preserving provider-visible bytes;
- do not introduce prompt budgets, truncation, top-N selection, or omission in
  the current refactor stage;
- treat any later context reduction as a separately preregistered ablation.

### P0.2 Proposal gates validate dialect and shape, not causal truth

The CVRP causal-path gate requires mechanism identity, material-difference
shape, effect telemetry, an exact nested CMT2/CMT4 claim, and algorithmic
intervention language:

- required checks: `hypothesis_contract.py:425-449`;
- free-text keyword matching for algorithmic sufficiency: `:647-679`;
- nested-string matching for CMT2/CMT4: `:631-644,682-698`;
- exact retry dialect and object shape: `:504-575`.

The gate asks for an explicit `algorithmic_intervention` record, but the
current `HypothesisProposalInput` does not have such a first-class field. The
gate instead searches across tainted proposal prose for words such as
`search_state`, `selection`, `attempted`, `accepted`, `budget`, and
`total_distance`. Semantically identical proposals can therefore receive
different outcomes based on vocabulary.

Successor55 selected the intended mechanism and file on the first attempt, but
was blocked only because `branch_lesson_usage.clean_fork_diversity_claim` was
missing. The retry learned the exact gate dialect. This did not consume an
effective protocol round, but it did cause another full target-intent and
hypothesis path and contributed to the 612k-token pre-screen total.

There are also overlapping approval paths: problem proposal-quality hook,
Contract checks, and `ExploreStepPipeline` material-difference/lesson checks.
The pipeline already has host-side canonical repair logic, but the earlier
problem hook can reject before that repair path.

R3.1 remediation is now implemented in the working tree: the CVRP hook no
longer hard-requires that nested CMT prose shape, while the generic
branch-lesson gate/canonical repair and formal CMT Protocol evidence remain.
The line anchors above describe the audited pre-remediation source snapshot.

Required repair:

- hard Contract checks only schema, path, API, interface, import, and execution
  safety;
- host-known metadata is computed by the host and stored as audit data;
- research-quality diagnostics are warnings or one local field repair unless
  the missing fact makes execution or attribution untrustworthy;
- CMT2/CMT4 coverage is enforced by the problem-owned protocol, not by asking
  every hypothesis to restate case names;
- no gate should decide algorithmic sufficiency by keyword search.

### P0.3 Telemetry pressure produces false causal confidence

The first successor55 candidate illustrates the problem:

- pool admission records `accepted=1` under the mechanism;
- anchor switching also records `accepted=1` under the same mechanism;
- a later best improvement records another accepted move plus `delta`;
- any later ALNS new best while `pool_anchor_active` is set is attributed to
  the solution-pool mechanism without a counterfactual boundary.

Evidence is in the run workspace:

- `policies/baseline_modules/solution_pool.py:17-90`;
- `policies/baseline_modules/scheduler.py:295-305,325-336`.

The runtime aggregate then merges admission, switch, and objective records
into phase accepted moves and effect summaries. Static quality checks largely
verify that a mechanism-named `record_move(..., delta=...)` exists, not that
the delta is causally valid.

Required repair:

```text
record_attempt(outcome, reject_reason)
record_state_transition(kind, before_ref, after_ref)
record_objective_effect(before, after, attribution_scope, confidence)
```

Pool admission and anchor selection must not increment algorithmic
`accepted_moves`. A downstream best after an anchor switch is an associated
outcome unless a declared before/after causal boundary can support a stronger
claim.

The completed run also exposed an artifact-integrity blind spot: both exported
`candidate.diff` files fail `git apply --check` as corrupt patches (lines 241
and 357), although their `candidate.patch.json` full-file payloads can replay.
Postrun readiness still reported ready. Canonical patch replay and diff
parse/apply validation therefore belong in the integrity boundary, not only in
operator convenience tooling.

### P0.4 The evaluation signal is dominated by downstream search

The two completed successor55 screening rows show a structural measurement
issue. Their accumulated phase runtimes were:

| Candidate | ALNS core | embedded VNS | pool bookkeeping |
| --- | ---: | ---: | ---: |
| 1 | 154,722 ms | 1,148,289 ms | 162 ms |
| 2 | 153,460 ms | 1,157,147 ms | 450 ms |

Many prior successors changed construction, destroy/repair, ALNS selection, or
small local-search components, while the full-solver outcome remained heavily
dominated by downstream VNS. This matches v3's warning that full-pool A/B can
dilute the effect of a new operator.

The promotion protocol must remain full-solver and deterministic. The repair
is not to weaken promotion gates. Add a problem-owned diagnostic assay before
promotion that can answer whether the proposed mechanism changes the intended
state boundary before downstream polishing. Its result is proposal feedback,
not Decision input and not promotion evidence.

## P1 Findings

### P1.1 The agent is implementing preregistered successors

Successor55 is directly named in `NEXT_REQUIRED_DIRECTION` and in
`target_intent_required_mechanism_ids`:
`scion/scion/problems/cvrp/research_guidance.py:898-915,1897-1902`.

The launcher enables the agentic planner and disables early stop by default;
tool and observation limits use zero as unbounded and session timeout defaults
to an hour. Target-intent and tool-selection calls are layered around the v3
hypothesis/code flow.

This arrangement is useful for a controlled implementation experiment, but it
should not be reported as autonomous mechanism discovery. Open research should
default to deterministic host source retrieval, one hypothesis call, and one
code call. The agentic planner should be an explicit ablation adapter.

### P1.2 Successor history is production code

The problem quality contract contains reviewed successor ids and narrative
outcomes as constants. `CURRENT_QUESTION` embeds a long successor chronology,
and tests require many old ids and case names to appear in rendered guidance.
This conflicts with v3's scoped blacklist design (`scope_tags`,
`evidence_count`, and `expiry_round`).

New experiment evidence should append a data record. It should not require a
new production constant, prompt paragraph, gate branch, and test assertion.
Runtime should retrieve a champion-scoped, expiry-aware top-k policy view.

### P1.3 There are multiple runtime truth surfaces

`CampaignManager` exposes compatibility properties, campaign composition owns
many mutable maps, services receive aliases of those maps, and adapters fall
back between orchestrator and owner attributes. Proposal fields used by live
quality checks are not all represented in the durable `HypothesisRecord`, so
resume/report paths reconstruct them from other artifacts.

The target is one `CampaignRuntimeState`, typed transition events, and one
append-only evidence writer. Prompt, status, operator, and Decision views must
be projections of committed evidence, not additional mutable truth stores.

### P1.4 Code is both monolithic and over-fragmented

Current production scale includes:

| Area | Python files | Lines |
| --- | ---: | ---: |
| `scion/scion/proposal` | 202 | about 75,593 |
| `scion/scion/core` | 120 | about 55,077 |
| `scion/scion/problems/cvrp` | 93 | about 32,912 |
| top-level `agentic_session*.py` only | 30 | about 14,631 |

At the same time, individual files such as `branch_step_runner.py`,
`research_guidance.py`, `branch_lesson_usage.py`, prompt renderers, and postrun
tools remain very large. A plan that only splits large files will increase
fragmentation. Each refactor slice must name a stable owner, delete or merge
compatibility modules, and show a net reduction path.

### P1.5 Active status documents have become run logs

`TASK.md` says it is not a run log but is 1,215 lines. `current-state.md` says
the same and is 1,283 lines. Both repeat successor chronology and more than
thirty next actions. They should each remain near 100-150 lines and point to
focused reports for details.

## Pi and Claude Code Reference Findings

The references support the same direction but should not be copied wholesale.

Pi snapshot `8479bd84`:

- useful: small inner agent loop, immutable turn snapshot, ordered event sink,
  active tool subset, append-only session projection;
- avoid: its current 3,246-line `AgentSession`, 1,185-line extension runner,
  and unfinished durable harness features.

Local Claude Code snapshot `a1285a5` is an unofficial 2026-03-31 snapshot, not
evidence of the July 2026 product:

- useful: explicit state transitions, centralized tool execution pipeline,
  typed failures, finite recovery, durable transcript with projected context,
  transition-centered observability;
- avoid: UI/plugin/permission-mode complexity, 1,900-file product structure,
  large global state, natural-language interactive compaction, and hook-driven
  state mutation.

The Scion-specific target remains:

```text
ProposalRuntimeKernel
  -> immutable ProposalTurnSnapshot
  -> ContextProjector
  -> phase-scoped ToolRegistry / ToolExecutor
  -> ProposalEnvelope or typed runtime failure

ProposalEnvelope
  -> Contract
  -> Verification
  -> Protocol
  -> Safe Feature Extractor
  -> deterministic Decision
```

Contract, Verification, Protocol, and Decision stay outside the agent loop.

## Stop/Continue Decision

Successor55 is complete and reviewed. Therefore:

- do not launch successor56;
- accept or reject successor55 only as experiment evidence;
- do not repair its telemetry by adding another same-line solver successor;
- use its prompt, gate, candidate code, runtime, and protocol artifacts as the
  characterization fixture for the refactor;
- start with behavior-preserving tests and one prompt snapshot per call;
- change prompt content and gate policy only in later, separately reviewed
  slices.

The implementation plan is
`scion/docs/planning/v0.4/v0.4-runtime-simplification-and-research-reset-plan-20260712.md`.

## Current Remediation Status

The transition worktree now implements the audit recommendation rather than
continuing the incremental repair strategy:

- direct V3 is the only production proposal runtime for warehouse and CVRP;
- APS, target intent, model tool selection, fix/retry/resume, session budgets,
  compact/truncate, successor steering, telemetry gates, and heuristic branch
  lifecycle closures are physically deleted;
- H and C each have one durable provider attempt and one authoritative context
  owner; C is bound to the approved H and complete multi-file SourceLedger;
- Contract resolves one capability bundle, Verification shares one canary
  output, Protocol owns the scientific verdict, Decision only maps the trusted
  verdict, and scheduler is state/FIFO/active-slot management;
- telemetry remains real solver evidence and diagnostics but cannot block code,
  change a Protocol verdict, or trigger another model call;
- production `proposal/` is reduced from the audited 202 Python files/about
  75.6k lines to 46 files/8,139 lines;
- the full Scion suite passes `1810` tests with one skip, and real warehouse and
  CVRP direct outer smokes are green.

Formal research effectiveness is deliberately not claimed yet. The worktree
must be reviewed and committed, completion preflight must pass from that clean
commit, and one warehouse plus one open CVRP control must be judged from actual
proposals, code, solver behavior, and Protocol outcomes.
