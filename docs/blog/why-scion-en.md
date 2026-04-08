# Why Scion: Rethinking How LLMs Improve Optimization Algorithms

*April 2026 · Xiao Jiyao*

---

Everyone is talking about LLMs writing code. But can they **design better algorithms**?

That's the question behind Scion — a framework for automatically improving combinatorial optimization heuristics using LLM reasoning. This post explains the motivation, what makes Scion different from existing approaches, and what we learned from v0.1.

## The Problem with Current Approaches

The past two years have seen an explosion of work using LLMs to improve optimization algorithms. Google's FunSearch, Evolution of Heuristics (EoH), ReEvo, AILS-AHD — all share a similar blueprint:

1. Give the LLM an existing heuristic
2. Ask it to mutate or rewrite
3. Evaluate on benchmarks
4. Select the best, repeat

This is **evolutionary search with an LLM as the mutation operator**. It works — FunSearch found new constructions for the cap set problem, EoH discovered competitive bin-packing heuristics. But there's a fundamental limitation:

**The LLM is treated as a stochastic code generator, not as a reasoning agent.**

It has no memory of what it tried before. It doesn't form hypotheses about *why* something might work. It doesn't learn from its failures within a run. Each generation is essentially independent — the LLM's reasoning capabilities are largely wasted.

And there's a more practical concern: **nobody talks about safety**. When LLM-generated code runs inside a solver that handles real logistics, manufacturing, or scheduling, a silent bug can corrupt solutions without anyone noticing. State mutations, constraint violations, subtle changes to objective functions — these don't crash the program, they just produce wrong answers.

## The Scion Approach

Scion takes a different path. Three core ideas:

### 1. Hypothesis-Driven Search

Instead of "here's the code, make it better," Scion asks the LLM to first articulate a **hypothesis** — a structured explanation of *what* it wants to change and *why* it expects improvement:

```
Round 1 (Hypothesis):
"The current merge_vehicles operator only considers adjacent routes.
Merging vehicles that share the same dominant subcategory should reduce
splits more effectively, because..."

Round 2 (Code):
[Implementation based on the hypothesis above]
```

This two-round proposal process forces the LLM to reason before coding. More importantly, when a hypothesis fails, the framework feeds back *what* failed and *why* — enabling the LLM to refine its understanding across rounds.

### 2. Three-Layer Governance

Scion treats LLM output as **tainted by default**. Everything it produces passes through multiple gates before it can affect the algorithm pool:

```
Creative Layer (LLM)      → produces code (tainted)
    ↓
Contract Gate (static)     → syntax, interface, forbidden imports (C1-C10)
    ↓
Verification Gate (dynamic)→ state leak detection, constraint preservation
    ↓
Experiment Protocol        → Screening → Validation → Frozen Holdout
    ↓
Decision Layer (oracle)    → numerical features only, no LLM text influence
```

The **Decision Input Guard** is particularly important: the decision layer receives only numerical features (win rate, median delta, evaluation counts) — never free-form text from the LLM. This architecturally prevents the LLM from "talking its way" into promotion.

### 3. Statistical Rigor over Fitness Scores

Most LLM+evolution approaches use a single fitness score to decide what survives. Scion uses a three-stage experimental protocol inspired by clinical trials:

| Stage | Purpose | Data |
|-------|---------|------|
| Screening | Quick filter on small instances | N=20 pairs |
| Validation | Confirm on medium instances | N=18 pairs |
| Frozen Holdout | Final check on held-out large instances | N=12 pairs |

Each stage requires a statistical threshold (win rate ≥ 2/3 + median delta ≥ minimum practical significance). The frozen holdout instances are **never seen during earlier stages**, directly addressing the overfitting problem that plagues single-fitness approaches.

## What We Learned from v0.1

We ran Scion on a real-world warehouse delivery VNS (Variable Neighborhood Search) problem with subcategory consolidation. 22 benchmark instances, 54–675 orders, 15 rounds of LLM interaction.

### The Learning Curve

The most interesting finding wasn't the final result — it was watching the LLM learn:

- **Rounds 1-3**: The LLM generated code that modified the input solution's state (a common bug in VNS operators). All three were caught by the Verification Gate.
- **Round 4**: The LLM's hypothesis explicitly stated: *"the KEY difference from the 3 failed attempts: deep_copy() immediately, build ALL new data structures from scratch."* It passed verification.
- **Round 4's operator (SubcatMergeSafe)** went on to achieve 95% win rate in screening, 100% in validation, **100% in frozen holdout** — reducing subcategory splits by 50-58 across large instances.

This wouldn't happen in a memoryless evolutionary framework. The LLM accumulated understanding across failures and applied it.

### The Gate Funnel

Out of 10 operators generated:
- 6 (60%) were caught by Verification Gate (state leak violations)
- 3 passed verification but failed statistical significance
- **1** survived all three stages and was promoted

This 10% survival rate tells us two things: LLMs are creative but unreliable (60% produce bugs), and statistical gates are essential (3 more looked promising but weren't significant). Both findings validate the multi-layer architecture.

### Honest Limitations

- Only tested on one problem domain — generalization is unproven
- Only 1 successful promotion — sample size is small
- No head-to-head benchmark against FunSearch/EoH (planned for v0.2)
- 60% V5_state_leak rate suggests prompt engineering has room to improve
- No cross-campaign memory yet — each run starts fresh

## Where This Is Going

Scion v0.1 is a proof of concept that **hypothesis-driven search with governance** is viable. The roadmap:

- **v0.2**: Enhanced Verification Gate (deeper semantic checks), parameter-level search
- **v0.3**: RAG memory module for cross-campaign knowledge transfer
- **v1.0**: Multi-problem generalization, formal comparison with existing approaches, paper

## Why Open Source It Now?

Because the field is moving fast, and nobody is seriously working on the governance problem. Papers keep showing "LLM found a better heuristic!" without asking "how do you make sure it doesn't break things?" or "how do you prevent overfitting to your benchmark?"

Scion is opinionated about these questions. The code is real (9,272 lines, 239 tests, complete campaign pipeline). If you're working on LLM-driven algorithm design and care about reliability, we'd love your feedback.

**Repository**: [github.com/xiaojiyao777/scion](https://github.com/xiaojiyao777/scion)

---

*Scion is a research project exploring LLM-driven algorithm improvement with formal governance. Contributions, criticism, and collaborations welcome.*
