# Scion v0.4 Novelty Gate Redesign Analysis

Date: 2026-05-26

Status: design analysis, no code changes

## Executive Recommendation

The current `novelty gate` is doing useful work, but the design is wrong as a
single hard gate. In v3 terms, Scion is a boundary, protocol, and audit
framework. It should not become the algorithm-research authority that decides
whether a proposed CVRP idea is interesting enough to try.

Recommended direction:

1. Cancel the monolithic novelty hard gate.
2. Keep only a strict premise-contradiction hard gate, and only when it has
   high-confidence, prompt-visible, adapter-owned evidence plus an exact
   contradicted text span.
3. Split the current behavior into four mechanisms:
   - duplicate detection: soft diagnostic and memory/routing signal;
   - premise contradiction: narrow hard gate with evidence requirements;
   - branch lifecycle policy: separate branch-governance gate;
   - telemetry contract: separate measurement/activation contract.
4. Let the agent query novelty/memory/facts as tools before proposing, while
   the host records diagnostics and routes branches instead of directly
   blocking most algorithmic variants.

This preserves v3 boundary control and auditability while reducing false kills
of plausible research variants.

## Evidence Reviewed

Required sources reviewed:

- `scion/docs/AGENT_ONBOARDING.md`
- `scion/design/scion-architecture-v3.md`
- `scion/scion/proposal/mechanism_novelty.py`
- `scion/scion/proposal/agentic_session_hypothesis.py`
- `scion/scion/proposal/agentic_grounding.py`
- `scion/scion/proposal/agentic_failure_classification.py`
- `scion/scion/contract/checks/novelty.py`
- `scion/scion/contract/gate.py`
- `scion/scion/core/explore_step/pipeline.py`
- `scion/scion/core/branch_repair_policy.py`
- `scion/scion/core/branch_hygiene.py`
- `scion/scion/problems/cvrp/adapter.py`
- `scion/scion/problems/cvrp/active_solver_facts.py`
- `scion/scion/problems/cvrp/mechanism_novelty/provider.py`
- `scion/scion/problems/cvrp/mechanism_novelty/*`
- `/home/clawd/research/scion-experiments/v04-v3-provider-taxonomy-gpt55-8r-20260526T050749Z-claw/analysis/provider_taxonomy_8r_round_trace_analysis.md`
- `/home/clawd/research/scion-experiments/v04-v3-reconcile-accounting-gpt55-12r-20260526T062239Z-claw/analysis/reconcile_accounting_12r_round_trace_analysis.md`
- `/home/clawd/research/scion-experiments/v04-v3-code-guidance-gpt55-12r-20260526T091350Z-claw/analysis/code_guidance_12r_round_trace_analysis.md`

The typed-edit-guard analysis directory was not present at review time:

- `/home/clawd/research/scion-experiments/v04-v3-typed-edit-guard-gpt55-12r-20260526T115319Z-claw/analysis/`

## v3 Interpretation: What Novelty Should Own

v3 draws a hard line between creative research and deterministic governance.
LLMs propose hypotheses and code. Deterministic Scion components enforce
boundaries, protocol credibility, auditability, traceability, and promotion
decisions. Free text is tainted. Deterministic decisions should be based on
contracted structure, verification, protocol results, safe features, and
adapter-owned facts.

From that design, novelty should own only:

- Recording whether a proposal appears to repeat a known mechanism.
- Providing branch-local and sibling-branch memory to help the agent avoid
  wasted retries.
- Detecting exact contradictions against active algorithm facts when the agent
  claims a mechanism/state is absent but adapter facts say it is present.
- Citing fact ids, packet digests, provenance, and exact proposal spans so the
  rejection is auditable.
- Feeding diagnostics into branch routing and prompt context.

Novelty should not own:

- Deciding that an algorithmic variant is not worth trying.
- Enforcing CVRP-specific research taste from generic Scion code.
- Collapsing a broad family, such as proximity clustering or regret repair, into
  "already present" when the proposal is a materially different variant.
- Blocking a proposal because it resembles a failed/no-effect mechanism on
  another branch.
- Enforcing same-mechanism branch lifecycle rules. That is branch governance.
- Enforcing telemetry measurability or activation contract. That is telemetry
  contract, not novelty.

The onboarding doc is especially clear that generic Scion may request active
algorithm fact snapshots and provenance, but must not synthesize hidden facts.
The proposal agent and semantic gates must share the same fact packet. If a
novelty or premise check rejects a hypothesis, it must cite fact ids and packet
digest/provenance, and the gate must not be better informed than the agent.

## Current Behavior and Calling Chain

The current implementation has several distinct gates under overlapping names.

| Mechanism | Location | Current behavior | Hard block? | Consumes effective round? |
| --- | --- | --- | --- | --- |
| Required solver-design grounding | `proposal/agentic_grounding.py`, `agentic_session_hypothesis.py` | Requires active solver design, algorithm files, call graph, and target file context before hypothesis approval. Retries once when target file is missing. | Yes, after retry/fail-closed | No |
| Mechanism novelty provider | `proposal/mechanism_novelty.py`, `problems/cvrp/mechanism_novelty/provider.py` | Detects duplicate mechanisms and contradicted premises against active solver facts. Retries once with semantic feedback, then emits `agentic_mechanism_novelty_rejection`. | Yes | No |
| Recent repeated mechanism block | `proposal/mechanism_novelty.py` | Blocks when recent failed/no-effect step has same mechanism id, novelty signature, or target/family/failure signature, unless proposal claims a material difference. | Yes | No |
| Contract C10 novelty | `contract/checks/novelty.py`, `contract/gate.py` | Requires structured novelty identity for semantic-signature surfaces and blocks duplicate keys against active, blacklist, and rejected hypotheses. | Yes | Usually no; routes as search guidance |
| Patch premise self-check | `proposal/agentic_failure_classification.py` | Code phase can self-declare `premise_check=contradicted`, `duplicate`, or `wrong_owner`; this becomes an agent-quality or contract block. | Yes | No for quality blocks |
| Branch lifecycle policy | `core/branch_repair_policy.py`, `core/branch_hygiene.py` | Active/no-effect/runtime-regression branches require same-mechanism follow-up unless a clean fork is used. | Yes | No |
| Telemetry/activation diagnostics | `proposal/agentic_failure_classification.py`, algorithm smoke classifications | Missing or unsupported activation signals can be recorded as quality diagnostics. | Mixed; often blocks proposal/code path | No when quality-blocked |

The pipeline generally protects round accounting correctly. Proposal-time
quality blocks, grounding failures, novelty/premise blocks, C10 search guidance,
and branch lifecycle blocks are recorded as non-effective steps and do not count
toward `max_rounds`. That is a good v3 property. The design issue is not budget
accounting. The issue is that a monolithic novelty/premise layer is making too
many algorithm-selection decisions before code and screening.

## Recent Failure Classes

### Regret Insertion Absent

Observed in the code-guidance run as `demand_boundary_ruin`: the proposal
claimed or implied regret insertion repair was absent even though the active
solver has `_regret2_insertion` and `_regret3_insertion`.

Assessment:

- When the text literally says regret insertion is missing, the premise
  contradiction is valid.
- This is mostly agent misreading or ignoring active algorithm facts, not adapter
  fact insufficiency.
- The current predicate tries to allow variants that acknowledge existing regret
  repair, but the regex-based hard gate is brittle. A proposal for a modified
  regret scoring, boundary-aware regret, or ruin-specific regret policy can be
  killed if phrased as "add missing regret" instead of "modify existing regret".

Design conclusion:

- Keep hard premise contradiction for explicit absence claims.
- Convert duplicate/regret-family similarity into soft diagnostic unless the
  contradicted span is exact and high-confidence.
- Prompt feedback should say: "existing regret2/regret3 repair facts were
  visible; propose a variant by naming the existing mechanism and the material
  difference."

### Route Removal Absent

Observed in reconcile-accounting as `route_compression_destroy`: the proposal
claimed route-level or whole-route destroy was absent while `_route_removal` was
already present.

Assessment:

- The adapter facts are sufficient for the basic absence contradiction.
- If the proposal is actually a compression, merge, route-pair, or state-aware
  route-removal variant, the hard gate should not decide it is duplicate merely
  because it touches whole-route removal.
- The current route predicate has exceptions, but it remains text-pattern
  sensitive.

Design conclusion:

- Explicit "whole-route removal is missing" should remain a hard premise
  contradiction.
- Route removal family overlap should be diagnostic/routing only.
- Variant proposals should be allowed if they acknowledge `_route_removal` and
  specify the changed selection rule, trigger, scope, or acceptance interaction.

### Shaw / Proximity Cluster

Observed in provider-taxonomy and code-guidance:

- `edge_conflict_removal` claimed related/proximity-cluster destroy was missing.
- `edge_regret_ruin` and `route_reorder_dp` similarly claimed Shaw/proximity
  clustering was absent despite `_shaw_removal`.

Assessment:

- The active solver facts are adequate: `_shaw_removal` is present and includes
  distance, demand, and original-route relatedness.
- For literal "missing Shaw/proximity" claims, the gate is correct.
- For geographically clustered variants, centroid variants, boundary variants,
  or different relatedness metrics, hard novelty is too strong. The fact that a
  baseline Shaw removal exists should inform the proposal, not prevent the agent
  from researching a different proximity mechanism.

Design conclusion:

- Hard block only exact absence claims.
- Duplicate-family detection should become a soft warning.
- The agent should be allowed to continue when it names `_shaw_removal` and
  states a concrete difference such as metric, seed selection, cluster shape,
  route-boundary handling, or coupling with repair.

### Route-Limit / Fleet State

Observed in code-guidance as `exact_tiny_dp`: the proposal assumed current
route-limit excess or positive fleet violation in the default construction/ALNS
state without runtime evidence.

Assessment:

- This is not novelty. It is a premise and telemetry-evidence issue.
- The active facts show route-limit guards and infeasible-solution rejection.
- The gate also checks for positive runtime evidence before allowing claims
  about route-limit/fleet violations. That is directionally right.
- The failure mode is partly agent over-claiming a bottleneck without querying
  runtime or screening evidence.

Design conclusion:

- Keep a hard premise contradiction for explicit claims that the current solver
  commonly emits route-limit or fleet-violation states when prompt-visible facts
  and runtime evidence contradict that claim.
- If the proposal is a protective guard, instrumentation, or fallback for rare
  violations, do not block it as novelty.
- Route-limit performance claims should be routed through telemetry contract:
  what metric proves activation, and where will it be observed?

### Same-Mechanism Follow-Up

Observed heavily in reconcile-accounting and code-guidance:

- Reconcile-accounting had 8 branch lifecycle blocks.
- Code-guidance reduced that to 5 blocks and showed one same-mechanism follow-up
  that reached screening.
- The blocks occurred when the scheduler selected a non-clean active/no-effect
  branch and the agent proposed an unrelated new mechanism instead of a repair or
  same-mechanism continuation.

Assessment:

- These blocks are mechanically correct under current branch policy.
- They are not novelty failures.
- The productivity issue is branch selection and pre-generation steering:
  selecting an ineligible branch for a new mechanism causes a wasted LLM call and
  a non-counted block.

Design conclusion:

- Keep branch lifecycle policy separate and auditable.
- Move more of this decision before hypothesis generation: if the scheduler
  selects a same-mechanism-only branch, either force a same-mechanism prompt or
  route to a clean fork before spending an LLM call.
- Do not represent these as novelty failures.

## Option Comparison

### Option A: Completely Remove Novelty Hard Gate

Pros:

- Eliminates false positives from text-pattern family matching.
- Gives the agent more freedom to research algorithmic variants.
- Aligns with v3's view that the LLM should explore while deterministic layers
  verify boundary/protocol/evidence.

Cons:

- Allows obvious duplicate proposals to reach code/screening.
- Loses early correction for clear false premises such as "regret insertion is
  absent" when active facts show it exists.
- Could increase wasted code attempts unless diagnostics and memory are strong.

Verdict:

- Do not remove all checks. Remove novelty as a hard algorithm-value gate, but
  keep strict premise contradiction.

### Option B: Novelty as Soft Diagnostic / Memory / Routing

Pros:

- Preserves audit and learning signal.
- Avoids blocking plausible variants.
- Can improve prompts, branch routing, blacklist summaries, and duplicate
  avoidance without turning Scion into the algorithm judge.
- Matches v3's context-manager idea: rejected/repeated hypotheses are compressed
  with scope, evidence, and expiry rather than used as broad global hard bans.

Cons:

- Some duplicate code attempts may get through.
- Requires better dashboards and prompt integration to remain useful.

Verdict:

- Recommended for duplicate detection, family overlap, recent failed/no-effect
  similarity, and cross-branch novelty memory.

### Option C: Keep Strict Premise Contradiction Hard Gate

Pros:

- Preserves the important safety property: proposals should not proceed when
  their central premise directly contradicts prompt-visible adapter facts.
- Reduces wasted code attempts caused by agent hallucinating missing mechanisms.
- Auditable when every rejection cites fact ids, spans, digest, and provenance.

Cons:

- Still vulnerable to false positives if "contradiction" is inferred from broad
  mechanism-family overlap.
- Requires disciplined predicates and tests.

Verdict:

- Recommended, but only with high-confidence requirements:
  exact contradicted span, adapter-owned fact id, prompt-visible fact packet,
  explicit contradiction type, and variant-safe escape path.

### Option D: Split into Four Independent Mechanisms

Pros:

- Makes failure classification honest.
- Lets each mechanism use the right policy:
  duplicate is soft, premise contradiction is narrow hard, branch lifecycle is
  hard branch governance, telemetry contract is evidence/measurement control.
- Makes experiments easier to interpret.

Cons:

- Requires model/schema changes and migration of counters.

Verdict:

- Recommended as the target architecture.

### Option E: Agent-Queried Novelty/Memory, Host Only Records and Hints

Pros:

- Gives the research agent agency and better situational awareness.
- Reduces hidden-gate behavior.
- Aligns with the onboarding requirement that the gate must not be better
  informed than the agent.

Cons:

- The host still needs hard controls for protocol boundaries and clear premise
  contradictions.
- Requires reliable tools and prompt discipline.

Verdict:

- Recommended as a P1/P2 direction. The host should keep hard premise and
  boundary checks, but novelty memory should primarily be a tool and diagnostic.

## Recommended Target Design

### 1. Rename the Concept

Stop treating `novelty` as one gate. Use explicit names:

- `duplicate_diagnostic`
- `premise_contradiction`
- `branch_lifecycle_policy`
- `telemetry_contract`
- `semantic_identity_schema`

This will prevent future reports from calling same-mechanism branch reroutes or
route-limit telemetry assumptions "novelty failures."

### 2. Hard Blocks Allowed

Only these should hard-block before code generation:

- Missing required grounding for solver-design proposals.
- Prompt/gate fact-packet mismatch.
- Invalid schema or target surface boundary.
- Strict premise contradiction:
  - exact proposal span exists;
  - active fact id exists;
  - fact packet digest/provenance is present;
  - the same fact packet was visible to the agent;
  - the contradiction is literal, not broad family similarity;
  - the provider can explain how to make a valid variant.
- Branch lifecycle policy when a non-clean branch requires same-mechanism
  follow-up.
- Telemetry contract failure when the proposal's expected evidence cannot be
  measured or contradicts available runtime facts.

### 3. Soft Diagnostics

These should not directly block code generation:

- Same mechanism family as active solver.
- Same broad destroy/repair/local-search family as a sibling branch.
- Similarity to a recent failed/no-effect mechanism.
- Duplicate signature unless it is exact same branch, same target, same action,
  same central mechanism, and no material-difference claim after retry.
- Low novelty score from text or embeddings.

Soft diagnostics should be written into:

- prompt context for the next proposal;
- branch memory and sibling summary;
- failure ledger as diagnostic, not `premise_contradicted`;
- routing hints for clean fork versus same-mechanism follow-up.

### 4. Agent Tooling

Expose a tool-level workflow:

- `context.read_active_solver_design`
- `context.read_solver_call_graph`
- `context.list_algorithm_files`
- `memory.search_mechanisms` or equivalent branch/sibling mechanism lookup
- `diagnostics.check_mechanism_overlap` as a non-authoritative advisory result

The agent should be expected to ask:

- "Does active solver already have this mechanism?"
- "Which branch last tried this family?"
- "If similar, what material difference am I proposing?"
- "What runtime evidence supports my premise?"

The host still records the resulting facts, but does not hide superior novelty
knowledge behind a late hard block.

## Development Landing Plan

### P0: Stop False Kills Without Losing Premise Control

Goal: remove novelty-as-hard-gate behavior while preserving strict premise
contradiction and accounting.

Modules:

- `scion/scion/proposal/mechanism_novelty.py`
  - Split result type into `duplicate_diagnostic` and
    `premise_contradiction`.
  - Make recent failed/no-effect similarity diagnostic by default.
  - Keep `to_rejection()` only for high-confidence premise contradictions.

- `scion/scion/problems/cvrp/mechanism_novelty/provider.py`
  - Return hard contradiction only for literal absence/state claims.
  - Return soft duplicate diagnostics for mechanism-family overlap.
  - Require exact spans, fact ids, fact packet digest, and guidance.

- `scion/scion/problems/cvrp/mechanism_novelty/destroy_repair/*.py`
  - Add variant-positive tests for regret, route removal, and Shaw/proximity
    mechanisms.
  - Treat "modify existing X" and "variant of existing X" as allowed.

- `scion/scion/problems/cvrp/mechanism_novelty/route_limit.py`
  - Keep hard contradiction for explicit positive route-limit/fleet-state
    claims without evidence.
  - Route protective guards and instrumentation proposals to telemetry contract
    diagnostics instead of novelty rejection.

- `scion/scion/proposal/agentic_session_hypothesis.py`
  - Inject duplicate diagnostics into retry/prompt context.
  - Continue to code generation after soft diagnostics.
  - Preserve hard block for strict premise contradiction and grounding parity.

- `scion/scion/contract/checks/novelty.py`
  - Reclassify semantic signature identity as schema/identity control.
  - Stop using duplicate C10 as a broad hard gate for algorithm variants.

- `scion/scion/core/branch_repair_policy.py`
  - Keep hard same-mechanism policy, but make classification independent from
    novelty/premise terminology.

Tests:

- Unit tests for literal absence claims:
  - "regret insertion is absent" blocks when regret facts are present.
  - "whole-route removal is absent" blocks when route removal facts are present.
  - "Shaw/proximity destroy is missing" blocks when Shaw facts are present.

- Unit tests for valid variants:
  - "modify existing regret2/regret3 scoring" does not hard block.
  - "change existing route removal trigger/selection" does not hard block.
  - "variant of existing Shaw using a different relatedness metric" does not
    hard block.

- Route-limit tests:
  - positive current fleet-violation claim without evidence blocks;
  - protective rare-case guard does not block as novelty.

- Pipeline tests:
  - soft duplicate diagnostic records ledger/context but permits code path;
  - hard premise contradiction remains non-counted and auditable;
  - branch lifecycle block remains non-counted and classified separately.

### P1: Improve Routing Before Spending LLM Calls

Goal: reduce non-counted wasted steps from branch lifecycle mismatch and agent
fact misreads.

Work:

- Add pre-generation branch eligibility filtering:
  - if branch is same-mechanism-only, either generate a same-mechanism repair
    prompt or select a clean fork before the LLM call.

- Add memory/novelty query tools:
  - active mechanism lookup;
  - branch-local failed/no-effect mechanism lookup;
  - sibling mechanism summary;
  - advisory overlap check.

- Improve prompt rendering:
  - active algorithm facts first;
  - "known active mechanisms" as concise bullets;
  - separate "do not claim absent" facts from "you may propose variants if you
    name the material difference."

- Split dashboards and counters:
  - `premise_contradiction_hard_blocks`;
  - `duplicate_diagnostics`;
  - `branch_lifecycle_policy_blocks`;
  - `telemetry_contract_blocks`;
  - `grounding_fail_closed`.

### P2: Better Duplicate Semantics and Experiment Automation

Goal: make novelty memory useful without making it a brittle hard gate.

Work:

- Use structured mechanism identity plus optional embeddings for advisory
  duplicate scoring.
- Add expiry/scope to duplicate memory:
  - branch-local;
  - sibling branch;
  - campaign-global;
  - champion/current solver.
- Add trace replay fixtures from v0.4 reports.
- Add A/B experiment harness for old hard gate versus split soft/hard design.

## Experiment Validation Plan

Replay or fixture the known cases:

- `edge_conflict_removal`
- `edge_regret_ruin`
- `route_reorder_dp`
- `demand_boundary_ruin`
- `route_compression_destroy`
- `exact_tiny_dp`
- same-mechanism branch blocks from reconcile-accounting and code-guidance

Metrics:

- effective rounds completed;
- proposal attempts per effective round;
- hard premise contradictions;
- duplicate diagnostics;
- branch lifecycle blocks;
- hypothesis-to-code conversion rate;
- screening conversion rate;
- number of ties/wins/losses;
- fact-packet parity failures;
- false-positive audit count from trace review.

Validation sequence:

1. Run unit tests and trace fixtures.
2. Run a short 3-round smoke campaign to verify counters and classifications.
3. Run a 12-round productivity campaign against the same task family as the
   reports.
4. Compare to current baselines:
   - reconcile-accounting: 8 branch lifecycle blocks, 5 quality blocks, all 12
     screened steps tied;
   - code-guidance: 5 branch lifecycle blocks, 3 premise-quality blocks, 1
     successful same-mechanism follow-up reaching screening.

Success criteria:

- No increase in boundary violations.
- No hidden fact mismatch: hard premise blocks always cite prompt-visible facts.
- Fewer hard proposal blocks caused by mechanism-family similarity.
- Fewer branch lifecycle wasted LLM calls.
- More hypotheses reach code/screening without reducing audit quality.

## Should This Change Land Before the Current 12-Round Run Ends?

Do not land the redesign mid-run if the current typed-edit-guard 12-round
experiment is already running and still producing useful traces. A mid-run gate
change would make the trace harder to interpret.

Exception: if the run is clearly stuck in repeated pre-screen hard premise or
branch lifecycle blocks and the goal is no longer clean comparability, stop and
restart after P0. Otherwise, let the run finish, analyze it, then apply P0 before
the next 12-round productivity run.

## Final Position

Yes: cancel `novelty hard gate` as a monolithic gate.

No: do not remove all premise protection. Keep a narrow, auditable,
high-confidence premise contradiction hard gate.

The right v0.4 design is not "no novelty" and not "hard novelty." It is:

- hard boundaries for protocol, surfaces, grounding, and explicit false
  premises;
- soft novelty diagnostics for duplicate and family overlap;
- separate branch lifecycle routing;
- separate telemetry contract enforcement;
- agent-visible tools and facts so the agent can do actual algorithm research
  instead of guessing around hidden host gates.
