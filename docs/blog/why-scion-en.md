# Why Scion: From LLM-Written Code To OR Autoresearch

*April 2026 · Xiao Jiyao*

---

Everyone is talking about LLMs writing code. Scion asks a narrower and more
useful question:

> Can an LLM, inside a human-defined combinatorial-optimization sandbox, propose
> hypotheses, modify heuristic operators, run experiments, and keep only changes
> supported by auditable evidence?

Scion is inspired by Andrej Karpathy's `autoresearch`: the human writes the
research program and boundaries; agents run experiments inside those boundaries.
Scion brings that idea to operations research and adds governance, statistical
validation, and lineage.

## Why Not Just LLM + Evolutionary Search?

FunSearch, EoH, ReEvo, and related systems show that LLMs can generate useful
algorithmic code. Many of these systems treat the LLM as a mutation operator:

1. provide an existing program;
2. ask the LLM to mutate it;
3. evaluate on benchmarks;
4. select the best candidate;
5. repeat.

That works, but it underuses what LLMs are good at: reasoning, explaining, and
forming hypotheses from failure.

Scion takes a different route: **the LLM must propose an auditable hypothesis
before it writes code**. Each candidate has to say:

- what weakness of the current champion it targets;
- which operator family it changes;
- which objective it expects to improve;
- why it should preserve feasibility.

Code is only the second step. The system records the whole chain:

```text
hypothesis -> implementation -> verification -> evidence -> promote/abandon
```

## Core Architecture

Scion treats LLM output as tainted data. The LLM cannot directly decide
promotion and cannot persuade the decision layer with free-form text.

```text
Creative Layer (LLM)
  -> Hypothesis
  -> Code
  -> Contract Gate
  -> Verification Gate
  -> Screening
  -> Validation
  -> Frozen Holdout
  -> Decision Layer
  -> Champion / Abandon
```

The important constraints are:

- **Decision Input Guard**: the decision layer reads only numeric features and
  closed-set enums, never LLM prose.
- **Contract Gate**: checks files, imports, interfaces, and obvious complexity
  hazards.
- **Verification Gate**: checks feasibility, objective consistency, solution
  state consistency, nondeterminism, and performance risk.
- **Three-stage protocol**: screening filters quickly, validation confirms, and
  frozen holdout tests unseen cases.
- **Lineage**: hypotheses, patches, metrics, promotions, and weight revisions
  are traceable.

The point is not to make the LLM more free. The point is to harden the boundary
first, then let the LLM search inside it.

## What v0.3 Achieved

v0.3 is Scion's first real framework milestone.

It separated the research object from the framework:

```text
surrogate/      = warehouse-delivery VNS research object
scion/scion/    = autoresearch framework
```

It added:

- a ProblemAdapter boundary;
- adapter-driven objective policy;
- separate synthetic and production protocols;
- synchronous weight optimization;
- metrics lineage and LLM traces;
- production incomplete-evidence and timeout fixes;
- auditable `status.json`, `campaign_summary.json`, and SQLite lineage.

The active evidence map is:

- `scion/docs/evidence-manifest.md`
- `scion/docs/v0.3-final-visual-report.md`
- `scion/docs/v0.3-production-timeout-fix-analysis.md`

Main results:

```text
formal 12-campaign validation: 12/12 completed
synthetic: 6/6 campaigns promoted, 10 total structural promotions
production rerun after evidence/runtime fixes:
  Sonnet: 3/3 promotions
  GPT-mini: 0/3 promotions
```

Best synthetic champion:

```text
campaign = sonnet-4-6_synthetic_seed29
final champion = v5_r0
vs v1 baseline on 47 comparable cases:
  better = 45
  equal  = 2
  worse  = 0
  median delta f1 = -17
```

After production evidence/runtime fixes, Sonnet produced three complete-evidence
cost-improving promotions. GPT-mini remained 0/3, mainly due to code reliability
and solution-consistency failures.

## What This Proves

v0.3 proves:

- hypothesis-driven LLM search can improve a controlled warehouse-delivery
  heuristic on synthetic frozen validation;
- a strong model can produce complete-evidence cost improvements on
  production-style warehouse instances;
- Scion's full loop works end to end:
  `hypothesis -> code -> verification -> protocol -> promote -> weight opt -> lineage`;
- governance is necessary. Without evidence completeness and runtime guards,
  production conclusions can be polluted by slow operators and skipped failures.

v0.3 does not prove:

- Scion is already a general OR autoresearch framework;
- production success is stable across all model classes;
- the current champion is close to optimal;
- the LLM truly understands the problem rather than repeatedly making useful
  moves under a statistical protocol;
- Scion can beat specialized state-of-the-art OR solvers.

Those boundaries matter. Scion should tie every claim to auditable evidence.

## Why v0.4 Moves To CVRP

The earlier roadmap considered FCMCNF + Benders as the second problem. That is
still valuable, especially for lower bounds, optimum gaps, and
decomposition-aware adapters.

v0.4 will prioritize **CVRP** instead.

The reason is simple:

- CVRP is one of the standard combinatorial-optimization problems;
- benchmarks and classical methods are mature;
- it is a true routing problem, while the current warehouse problem is closer
  to assignment/bin-packing;
- it tests route sequences, distance objectives, capacity feasibility, and
  route-local operators;
- it naturally stresses runtime complexity, which is exactly what v0.4 needs
  to harden.

In short:

```text
warehouse delivery: orders -> vehicles
CVRP: customers -> ordered routes
```

If Scion can improve a strong modular CVRP baseline under the same hypothesis,
verification, promotion, and runtime-aware protocol, it becomes much closer to a
real OR autoresearch framework.

## What's Next

v0.4 focuses on:

- performance-aware promotion;
- complete-evidence gates;
- a CVRP ProblemAdapter;
- CVRP baseline evidence in the manifest;
- final quality/runtime reporting;
- one shared report format across warehouse and CVRP.

v1.0 should then focus on:

- warehouse + CVRP evidence consolidation;
- mechanism ablations;
- stronger campaign operations;
- stable problem-interface documentation.

Scion is not yet a general OR autoresearch framework. A more accurate statement
is that it is an auditable agentic algorithm-optimization framework validated on
warehouse delivery, now moving toward multi-problem generalization through CVRP.

That is the most valuable place for the project to be right now.
