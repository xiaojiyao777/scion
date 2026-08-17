# Scion autonomous prior-evidence research design

*Date: 2026-08-17*

*State: `DESIGN_ONLY / NOT_IMPLEMENTED / NOT_AUTHORIZED_FOR_PROVIDER_OR_SOLVER_EXECUTION`*

## Correction of scope

This is not a redesign of the VRP algorithm as the next host-authored
scientific object. The system under development is **Scion**. Warehouse and
VRP solvers are problem-owned research objects on which Scion demonstrates its
ability to conduct autonomous algorithm research.

The V3 boundary remains:

- the Scion Agent owns Hypothesis and Code proposals;
- deterministic Scion modules own Contract, Verification, Protocol, Safe
  Features and Decision;
- problem adapters own domain semantics and the safe projection of
  domain-specific evidence;
- the host selects the research question, resources and scientific population,
  but does not select the patch, target file, mechanism or repair;
- rejected work cannot contaminate the verified branch source, while one
  ordinary scientific record remains available for later research.

M7-FC1 was useful negative VRP evidence, but its fixed-candidate carrier bypassed
the Agent: provider, Hypothesis, Code, current Contract and current Verification
calls were all zero. It tested a candidate and downstream experiment controls;
it did not test whether Scion could learn from that result and create the next
candidate. The next work must exercise the normal Scion research loop.

## Primary research question

> Scion 能否在不给人工指定 patch、target file 或算法修复方案的情况下，
> 利用 M7 的结构化失败证据，自主提出、实现、验证并评估下一代 VRP solver
> candidate？

The framework-level form is deliberately problem-neutral:

> Can Scion consume a problem-adapter-projected prior research observation and,
> without host-forced action, surface, target, patch or mechanism, autonomously
> propose, implement, verify, evaluate and decide a next solver candidate?

“Use the evidence” is an observed research behavior, not a host gate. Scion may
form a hypothesis that does not mention the prior failure, and that is a valid
negative result about research effectiveness. The host must not turn a desired
interpretation into a required phrase, target-file allowlist or patch template.

## Roles and ownership

| Component | Owns | Must not own |
| --- | --- | --- |
| Scion core | ordered ordinary inputs, safe provider context, H-to-C value flow, workspace isolation, Verification, Protocol orchestration, Safe Features, Decision, branch transition and minimal lineage | VRP/Warehouse fields, domain diagnoses, target selection, repair rules or hard-coded algorithm advice |
| Problem adapter | domain vocabulary, source surfaces, objective/feasibility semantics, and safe projection of problem evidence | Decision or promotion authority |
| Agent | hypothesis, action, change locus, target file and patch | Protocol population, gates, Decision or promotion |
| Experiment input | the concrete prior observation, research question, budgets and fresh evaluation population | reusable authorization, identity, lease, registration, receipt or self-proof state |
| VRP/Warehouse solver | the algorithm being researched | Scion framework policy |

Consequently, no `X-n200-k36`, customer/route/fleet field, CVRP error parser or
M7 label belongs in `scion.core`, `scion.proposal` or another generic module.
Those values may appear in an ordinary CVRP experiment input and may be
interpreted by the CVRP adapter. A Warehouse campaign can use the same Scion
interface with Warehouse-shaped evidence, and a problem may provide no prior
observation at all.

## Required framework capability

### 1. One ordinary prior-research input

The normal `scion run` path should accept an optional ordered JSON value
containing prior research observations. This is a scientific input, not a
registry. It is loaded once for a fresh campaign, included once in the ordinary
run record, and never signed, leased, registered, reopened or surrounded by a
hash/receipt chain.

The Scion core validates only generic safety properties:

- the value is finite, primitive JSON with bounded size;
- order is preserved;
- raw prompts, secrets and current holdout results are absent;
- the value cannot alter surfaces, editable paths, Protocol, Decision or
  scheduling.

The core does not validate or branch on domain field names.

### 2. Problem-owned safe projection

An optional problem-adapter provider projects each raw observation into the
safe research vocabulary shown to H. The provider may discard fields or return
no observation. This is the same architectural direction as problem-owned
mechanism evidence: Scion transports a safe ordinary value but does not learn
what a route, bin, fleet or neighborhood operator means.

The projected observations enter the Hypothesis context under one explicit
field such as `prior_research_observations`. They do not enter the Code context
directly. Code receives the same Contract-approved ordinary H value plus the
editable source, so prior evidence can influence C only through the Agent's
stated hypothesis.

### 3. One research-history path

Within a campaign, scientific observations should continue to derive from the
existing typed step/outcome values. The extension must not recreate a special
`last_rejection`, repair-feedback ledger or branch-owned evidence mirror.
Problem-safe observations relevant to a future H can be projected through the
same adapter boundary; infrastructure/provider failures and private current
holdout details are not algorithm evidence.

The scientific lineage remains sufficient to answer:

1. what safe context H saw;
2. what H proposed;
3. what C changed;
4. which Contract and Verification facts were obtained;
5. which declared cases/seeds Protocol ran;
6. which Safe Features reached Decision; and
7. whether the branch retained, rejected, expanded, validated, froze or
   promoted the candidate.

That is the required backtracking guarantee. It does not require object
identity, reopening, ownership tokens or closure receipts.

### 4. Holdout separation

Once an M7 failure fact is shown to the Agent, that fact is research context,
not a secret holdout. A later formal evaluation must therefore use a newly
declared population whose validation and frozen cases/seeds are disjoint from
the evidence exposed to H. The current campaign's validation/frozen details
remain unavailable to H until they cease to be holdout data in a later,
separately designed study.

## M8 implementation experiment

M8 is a framework capability module, not a VRP patch.

### Offline behavioral tests

Use fake providers and runners only. The acceptance tests must show:

1. a generic adapter can project one prior observation into H exactly once;
2. H remains free to choose any declared action, surface and target;
3. the identical Contract-approved H ordinary value reaches C;
4. raw prior evidence does not enter C, Contract, Verification, Protocol,
   Safe Features or Decision as an authority input;
5. current validation/frozen/private fields are rejected from H context;
6. a Contract or Verification rejection leaves the verified branch source
   unchanged and the scheduler may ask for a fresh H where V3 permits;
7. an evaluated candidate follows the normal Protocol -> Safe Features ->
   Decision chain;
8. one test problem with a differently shaped observation and one problem with
   no observation both use the same core path; and
9. generic production modules contain no CVRP/Warehouse imports, field names or
   conditional branches.

These tests establish transport, isolation and decision-chain behavior. They do
not claim that an LLM conducts good research.

## M9 live research-effectiveness experiment

After M8 passes, prepare a fresh ordinary `scion run` experiment with:

- the current verified CVRP B0 source as the starting champion;
- an external CVRP observation file containing the safe M7-FC1 facts;
- the question above;
- no forced action, surface, target file, patch, mechanism or repair text;
- real H and C calls with provider retry zero;
- current Hypothesis Contract, Patch Contract and executable Verification;
- a small, fixed development Protocol population followed only on success by a
  separately preregistered formal population;
- fresh evaluation cases/seeds disjoint from all M7 evidence shown to H; and
- the normal Safe Feature and deterministic Decision path.

The CVRP adapter may translate the M7 terminal into safe domain evidence, for
example that a previously evaluated candidate survived two screening stages
but failed to construct a feasible solution for a larger instance. It must not
translate that fact into “edit this file”, “apply this algorithm”, or a required
patch. The exact M7 payload belongs to this experiment's input, not to Scion
source code.

### Outcomes and claims

Separate three conclusions:

1. **Framework behavior:** the observation reached H safely; H and C remained
   Agent-owned; current Contract, Verification, Protocol and Decision actually
   ran; rejected state stayed clean.
2. **Research effectiveness:** the Agent formed a grounded hypothesis and
   produced an evaluated candidate. Whether it substantively used M7 evidence
   is assessed from H, patch and resulting behavior after the run, not enforced
   before it.
3. **Algorithm improvement:** only a declared Protocol promotion plus fresh
   frozen and retained-baseline evidence can support this claim.

A weak hypothesis, invalid patch, Verification rejection, scientific veto or
non-promotion is a valid result about Scion's current autonomous research
ability. It must not trigger a host-authored repair or hidden retry.

## Authorization boundary

This document authorizes design and provider-/solver-free implementation tests
only. It does not authorize a live provider call, solver subprocess or formal
campaign. Before M9 starts, its exact ordinary input, provider-call cap,
solver/time budget, population, stop conditions and claim boundary must be
reviewed and explicitly authorized once. That authorization must apply to the
normal Scion campaign, not to an R67/M7 fixed-candidate carrier.
