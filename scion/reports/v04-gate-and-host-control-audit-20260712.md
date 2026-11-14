# Scion v0.4 Gate and Host-Control Audit

*Date: 2026-07-12*
*Status: accepted audit; remediation pending*
*Scope: warehouse `direct_v3`, CVRP `agentic_ablation`, proposal through promotion*
*Run lock: no formal experiment until K4 and K5 pass final integrated acceptance*

## Executive Decision

Scion currently asks the research model to satisfy too many host-governance
contracts before the system will test the proposed algorithm. The same intent
can be rejected by agentic inner validation, `ProposalPipeline`, and the
Explore/Contract layer. Several generic lifecycle heuristics can then override
a formal `Decision` and turn `CONTINUE` or `REPAIR` into park, archive, or
`ABANDON`.

The refactor must preserve integrity and scientific validity while removing
research-dialect gates:

- host-known governance facts are projected by the host and recorded as audit;
- the model owns the research hypothesis, intended mechanism, code, and causal
  expectation, not Scion's internal branch-management vocabulary;
- one authoritative owner makes each formal rejection;
- circuit breakers count provider/transport/infra failure only;
- scheduler heuristics affect priority, never overwrite formal evidence;
- resource exhaustion, infrastructure failure, and research rejection remain
  distinct durable states;
- this phase introduces no new budgets, caps, truncation, or summary
  substitution.

## Versioned Experiment Evidence

The successor55 run is historical evidence from launch commit `ff184608`, not a
claim about every condition in the current checkout:

- the first target-intent call correctly selected
  `solution_pool.py / bounded_elite_solution_pool_search` at confidence `0.99`;
- the run produced three proposal attempts, one quality block, and two formal
  screenings, then ended with `max_rounds_exhausted`;
- the quality block required the old
  `branch_lesson_usage.clean_fork_diversity_claim` field;
- the postrun analysis attributes about 252,998 additional input tokens to this
  proposal-dialect repair rather than an algorithmic research iteration;
- the two screened candidates were solver-negative, while exact target
  binding, full-source visibility, verification, and the 48-pair screening
  protocol operated correctly.

The current checkout has already removed that exact clean-fork field, the old
reviewed-mechanism denylist, protected-case condition, and some repair/infra
prose rules. Current CVRP hypothesis quality still requires a mechanism id,
structured material-difference evidence, and mechanism-linked expected
telemetry. The old failure therefore proves the cost of governance-dialect
gates, but must not be described as an exact current-code failure.

The successor55 artifact records `AGENTIC_PROPOSAL=1` but predates durable
`proposal_runtime_mode`; it cannot prove the current mode-durability contract.

## Production Control Chain

### Provider preconditions

The following controls are legitimate integrity boundaries:

- launcher environment, API credential, runtime path, clean worktree/commit,
  input file, problem, protocol, split, seed, and measurement-readiness checks;
- authoritative proposal-context ownership, primitive safety, digest,
  projection, and provider revalidation;
- receipt-aware provider API, prompt receipt, trace, lineage, and attempt
  transition;
- exact campaign, branch, champion, problem, spec, split, seed, and approved
  hypothesis binding;
- explicit user-forced target and problem-owned editable/frozen/path/import
  permissions;
- target and integration-source full-content visibility.

Agentic-only planning requirements are not automatically integrity boundaries.
Target-intent mechanism labels, required read sequences, and planner-selected
file counts may produce diagnostics, but must not prevent an otherwise grounded
proposal from reaching the authoritative Contract owner.

### Hypothesis controls

Current or recently active rejection owners include:

1. schema and structured response parsing;
2. forced surface/action/target and active problem boundary;
3. target-intent binding and target-source grounding;
4. mechanism-name binding and novelty classification;
5. repair-first and weak-positive follow-up prose rules;
6. problem-owned hypothesis quality;
7. agentic preview/self-check/Contract preview;
8. `ProposalPipeline` post-provider checks;
9. Explore hypothesis Contract, material-difference, and branch-lesson gates.

Schema, exact target/source ownership, editable/frozen ownership, and the
single authoritative Contract remain hard. Governance prose, novelty metadata,
material-difference form, lesson declarations, and mechanism-label agreement
become audit or scheduler signals.

### Code controls

Typed edit schema, path ownership, import/sensitive API boundaries, AST and
interface checks, full source for `additional_changes`, and one authoritative
Contract/Verification owner remain hard.

Agentic preview and smoke may provide repair feedback, but become advisory only
when the outer Contract/Verification executes the equivalent hard checks.
Explicit boundary, objective-policy, and ownership contradictions remain
fail-closed at the authoritative owner. Model-written `test_hint` text and
telemetry declarations are not substitutes for executing real tests or
collecting runtime evidence.

### Candidate, protocol, and promotion controls

Keep hard:

- syntax, interface, tests, solution consistency, feasibility, objective
  recomputation, and nondeterminism checks;
- candidate crash, process timeout, infeasible canary, and unrecomputable
  candidate evidence;
- validation/frozen pairing, threshold/CI/positive-only policy, formal
  telemetry attribution required for promotion, and promotion transaction
  prepare/commit/recovery.

Downgrade ordinary comparative slowdown and missing screening-stage
activation/effect telemetry to evidence and Decision inputs. Process runaway
and formal promotion-evidence integrity remain hard.

## Controls to Preserve

### Safety and integrity

- primitive safe-input and forbidden validation/frozen/holdout/BKS/raw-metric
  isolation;
- context identity, source owner, digest, receipt, trace, lineage, and durable
  transition;
- exact target, hypothesis, champion, problem, split, and seed binding;
- file/path/action/import/API/editable/frozen ownership;
- AST, interface, feasibility, objective recomputation, and deterministic
  execution;
- provider balance exhaustion, authentication, interrupt, OS/process watchdog,
  and durable write/commit failure handling.

### Scientific protocol

- screening/validation/frozen stage separation and comparability;
- validation/frozen pair completeness;
- screening candidate-failure veto and champion-failure
  unclear/inconclusive semantics, without a new universal completeness gate;
- candidate-versus-champion comparability;
- formal thresholds, confidence intervals, positive-only policy, and promotion
  preconditions;
- canonical evidence and Decision feature provenance;
- atomic promotion and recovery.

## Controls to Downgrade to Audit or Scheduling

- causal-path, material-difference, branch-lesson, clean-fork, protected-case,
  and algorithmic-intervention document shapes;
- weak-positive bridge, same-mechanism, and repair-first prose;
- semantic novelty signature and target-intent mechanism-name equality;
- hypothesis-declared telemetry identity when the host can derive it;
- static complexity heuristics for combination counts, permutations, scale
  products, and ordinary nested loops; only clearly unbounded execution remains
  hard;
- comparative slowdown short of process/resource runaway;
- screening-stage activation/effect absence;
- repeated Contract/quality signatures;
- zero-win, no-effect, marginal, diagnostic, and runtime-loss streaks;
- frozen-stage resource exhaustion, which remains durably
  `resource_exhausted` while the formal result is `not_evaluated/incomplete`;
- self-reported `test_hint` textual issues.

These signals may change branch priority, select a clean fork, request more
evidence, or annotate a Decision. They may not prevent code generation,
invalidate objective results, or overwrite the formal Decision.

## Controls to Delete or Merge

- merge the duplicate agentic-inner and `ProposalPipeline` problem-quality
  decisions, then compose the remaining formal checks into Explore's single
  authoritative `HypothesisContractDecision`;
- make agentic Contract preview/smoke advisory and retain one outer
  Contract/Verification decision;
- remove model obligations for host-known governance fields;
- remove OpenAI agentic legacy output caps and truncation retry before agentic
  is used as a production research path;
- stop counting boundary, novelty, quality, and Contract rejection as an LLM
  circuit failure;
- remove repeated-quality and repeated-Contract hard terminators;
- consolidate telemetry identity into one canonical evidence owner;
- replace evaluation-exception `ABANDON` fallback with recoverable
  infra/no-decision state;
- prevent generic lifecycle heuristics from overriding a formal Decision.

## Hidden Controls Still Active

Launcher values of zero do not disable the following agentic controls:

- source projections at 800, 12k, 24k, and 96k characters;
- full-file read count of five and manifest count of nine;
- legacy provider output cap of 16,384 plus up to two truncation retries;
- one initial hypothesis plus semantic, preview, and grounding retry families;
- code timeout, edit-protocol, schema-shape, and repair retry families;
- preview/smoke timeouts and a pre-code wall-time reserve;
- 3,600-second session timeout;
- repeated quality signature and generic circuit thresholds;
- bad-proposal, telemetry-repair, validation-repair, same-family,
  branch-lifecycle, reconcile, scheduler-capacity, and campaign-safety
  terminators derived from requested rounds;
- global experiment, wall-clock, and stagnation abandonment thresholds;
- foreground 429 handling that can wait without advancing an attempt.

Warehouse `direct_v3` avoids the agentic session/tool/read/output controls and
uses provider-managed OpenAI output. It still passes through shared outer
problem-quality, Contract, lifecycle, circuit, protocol, and promotion logic.

The inventory above is a removal/audit target. It does not authorize adding or
tuning budgets in the current phase.

## Remediation Order

1. Host-project governance metadata and downgrade model-dialect hard gates.
2. Establish one authoritative hypothesis-quality and one authoritative patch
   Contract/Verification owner.
3. Restrict the circuit breaker to provider/transport/infra faults.
4. Prevent lifecycle and streak heuristics from overriding formal Decision.
5. Remove agentic output/source truncation and hidden read/file limits before
   using agentic mode for a production experiment.
6. Keep telemetry hard only for canonical formal-evidence integrity; make
   screening diagnostics advisory.
7. Separate resource exhaustion, infra failure, not-evaluated, and research
   rejection in durable state and postrun acceptance.

## Acceptance

- Both audited proposal paths—warehouse `direct_v3` and CVRP
  `agentic_ablation`—can reach code and screening without supplying
  host-governance dialect fields.
- The model cannot change host-derived governance, identity, or provenance.
- Each hypothesis and patch has one formal rejection owner.
- Repeated research-quality rejection does not trip the provider circuit.
- A formal `CONTINUE` or `REPAIR` Decision cannot be overwritten by generic
  lifecycle heuristics.
- No Scion-imposed hidden source/output truncation or fixed file/read count
  exists on the production proposal path; provider-native limits remain
  explicit transport facts.
- Infra, resource exhaustion, not-evaluated, and research rejection have
  distinct durable evidence and postrun states.
- Safety, correctness, protocol isolation, and promotion transaction tests stay
  fail-closed.
- No formal experiment is prepared or launched from a transition worktree.
