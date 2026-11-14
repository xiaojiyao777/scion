# CVRP Agent Behavior Debug Audit - 2026-06-15

## Scope

This is a read-only audit of existing CVRP v0.4 artifacts. No experiment was
launched, no solver job was started, and no source code was modified.

Required order was followed:

1. `scion/design/scion-architecture-v3.md`
2. `scion/TASK.md`
3. `scion/docs/experiments/v0.4/v04-cvrp-1r-debug-repaired-postrun-20260615.md`
4. `scion/docs/experiments/v0.4/v04-cvrp-baseline-strength-phaseC-postrun-20260615.md`
5. `scion/docs/planning/v0.4/v04-cvrp-size70-tier1-postrun-analysis-plan-20260615.md`

V3 boundary used for this audit:

- LLM text, BKS/gap facts, mechanism rankings, branch lessons, prompt ratios,
  and raw problem diagnostics remain tainted/problem-owned diagnostics.
- They may guide reports, proposal context, lifecycle/debug design, and
  human-approved experiment planning.
- They must not be added to generic `DecisionFeatures`.
- CVRP/VRP mechanism semantics stay in problem-owned analysis and proposal
  layers unless a separate v3 boundary decision says otherwise.

## Artifacts Inspected

| Area | Artifact(s) inspected | What was checked |
| --- | --- | --- |
| Architecture/task constraints | `scion/design/scion-architecture-v3.md`, `scion/TASK.md` | Decision boundary, branch governance intent, effective-research definition, latest CVRP/warehouse status. |
| Phase C accepted run | `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseC-longrun-20260614T174532Z/postrun_acceptance` | Accepted-cell list, `sql/*.csv`, summaries, research-efficiency JSON, proposal trajectory manifests/compares, six campaign DBs. |
| Phase C raw cell samples | six `cells/*/campaign/scion.db` and selected `agentic_sessions/*/output.json` / prompt manifests | Hypothesis chains, parent IDs, decision rows, prompt truncation, branch lesson usage samples. |
| Repaired 1R debug | `/home/clawd/research/scion-experiments/v04-single-round-debug-cvrp-compact-1r-repaired-gpt55-20260615T175742Z-claw` | Campaign summary, SQLite rows, prompt manifests, LLM trace response, metrics JSON. |
| Candidate large-X replay | `/home/clawd/research/scion-experiments/v04-cvrp-candidate-largeX-replay-20260615T164410Z` | Phase C validation-positive candidate replay outcome and best-update telemetry. |
| Two-opt size70 evidence | `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z` | Follow-up smoke, large-X diagnostic replay, external candidate artifact, fixed validation manifest. |
| Size70 Tier 1 gate | plan plus synced root `/home/clawd/research/scion-experiments/v04-cvrp-size70-tier1-largeX-20260615T211545Z` | Gate definition and current synced status only. This was not treated as postrun evidence. |

## Gaps And Limits

| Gap | Impact |
| --- | --- |
| No accepted Size70 Tier 1 postrun was available. The synced root still showed `status=running`, `27` JSON rows, and no `summary.json/csv`; all `X-n1001` rows were absent in the inspected sync. | Cannot decide whether size70 may proceed to formal validation. Wait for Noether/Tier 1 postrun. |
| Phase C proposal trajectory joins are report-only and not complete for all sessions. Across six manifests: `128` sessions, `61` formal candidates, `61` joined formal candidate sessions, and `67` missing session-to-formal joins. | Enough for aggregate behavior, not enough for per-session causal proof that a lesson caused a later candidate. |
| Raw prompts are not the main persisted artifact; prompt manifests and block-family accounting were inspected instead. | Good for visibility/truncation/block-family analysis, weaker for full semantic reading of every prompt token. |
| I sampled selected hypotheses and prompt manifests rather than manually reading all `61` Phase C candidate patches. | Evidence supports behavior-level audit, not a full patch-by-patch algorithm review. |
| Candidate large-X and two-opt replays are no-LLM/direct-solver diagnostics. | They can guide proposal context and experiment design, but are not Scion Protocol or promotion evidence. |

## Evidence Table - Branch Depth

| Evidence | Finding | Interpretation |
| --- | --- | --- |
| Phase C `branch_depth.csv` | `36` branches total. ALNS+VNS: `19` branches, `11` single-hypothesis branches, `3` branches with parent depth `>=3`, max depth `5`, max same-mechanism chain `5`. ALNS-only: `17` branches, `8` single-hypothesis branches, `1` branch with parent depth `>=3`, max depth `3`, max same-mechanism chain `3`. | Branch depth is real but sparse. The run is no longer pure one-off search, but most branches are still shallow. |
| Phase C DB hypothesis counts | Six cells had `61` hypotheses; `25` had a non-empty `parent_hypothesis_id`. | Parent lineage is durable enough for analysis; depth is not just a postrun fiction. |
| Deep-chain sample: `81f16ff4...` | ALNS-only rep01 had a 3-step construction chain refining `route_merge_seed_compression` with non-worsening and ordering guards. | This is a valid same-mechanism refinement example. |
| Deep-chain sample: `2ee40785...` | ALNS+VNS rep01 had a 5-step scheduler chain around `operator_effect_observability` / micro-replay; it ended abandoned after mixed/negative evidence. | This is lineage depth, but part of the depth spent budget on observability/attribution rather than direct objective-improving mechanism design. |
| Validation-positive branches `4504a238...`, `cc6f489c...` | Both reached validation/frozen paths but later collapsed on frozen/large-X diagnostics. | Branch depth/reach alone did not imply robust mechanism quality. |

## Evidence Table - Branch Transfer

| Evidence | Finding | Interpretation |
| --- | --- | --- |
| Phase C `hypothesis.branch_lesson_usage` in output artifacts | `125` output artifacts carried structured lesson usage. Counts: `avoided=205`, `contrasted=175`, `borrowed=15`, `preserved_same_branch=53`, `rejected_weak_positive=56`. | The simple failure mode "no structured lessons are emitted" is false. |
| Phase C prompt context CSV | `62/468` traces had branch-lesson truncation; `76/468` had compact-research truncation. | Lesson material exists, but it is still competing for space and can be truncated. |
| Semantic sample: route-tightness repair | A sampled hypothesis contrasted an always-on bias lesson and narrowed it to a conditional tie-break. | Some lesson use is semantically meaningful. |
| Semantic sample: rank-reheated acceptance | A sampled hypothesis borrowed a runtime-evidence bridge and preserved same-branch weak-positive activation. | Some transfer reaches mechanism design language, not only boilerplate. |
| 1R repaired debug | The single hypothesis contains `branch_lesson_usage`, but its source branch is the same one-round branch and cannot prove sibling/ancestor transfer. | One-round debug is path-health evidence only; it cannot validate cross-branch learning. |
| Phase C outcome | Despite lesson objects, no promotion occurred; ALNS-only validation positives collapsed at frozen/large-X. | Structured lesson references have not yet proven they improve mechanism selection. |

## Evidence Table - LLM Context Signal

| Evidence | Finding | Interpretation |
| --- | --- | --- |
| Phase C aggregate prompt block families | Across six trajectory manifests, token-share estimates were: tool-selection `32.85%`, general `14.78%`, research-signal `13.69%`, source-context `13.24%`, active-facts `10.63%`, tool-observation `10.38%`, feedback `2.88%`, governance `1.55%`. | Source and research signal are present, but actual research intent is still surrounded by a large tool/general payload. |
| Phase C prompt context CSV | `128` sessions, `468` traces, `468` prompt manifests loaded; all six cells used `compact-measurement-diagnostics`. | The accounting surface is usable and complete enough for prompt-shape audits. |
| Phase C sampled hypothesis manifest | One rep02 ALNS+VNS hypothesis prompt estimated `52,703` tokens: research-signal `23.16%`, source-context `17.15%`, general `19.42%`, active-facts `16.39%`; truncated sections included `compact_research_signals` and `branch_lesson_usage_context`. | Even when research signal share is decent, the most important compact research and lesson sections can still be truncated. |
| Repaired 1R postrun and prompt manifest | Hypothesis prompt was about `120,089` chars / `30,023` estimated tokens; `compact_research_signals` was truncated. | 1R still shows hypothesis-context overload. |
| Repaired 1R code prompt | Full target `local_search.py` and required integration files (`baseline_algorithm.py`, `scheduler.py`, `state.py`) were visible; target source was full and no code prompt truncation was found. | Current blocker is less about code source visibility and more about hypothesis-context composition. |

## Evidence Table - Mechanism Quality

| Evidence | Finding | Interpretation |
| --- | --- | --- |
| Phase C arm aggregates | ALNS+VNS: `48` effective rounds, `45` screening rows, `3` validation rows, `0` frozen, `0` promotions, max effect/MDE `0.677`. ALNS-only: `48` effective rounds, `42` screening rows, `4` validation rows, `4` frozen rows, `0` promotions, `6` rows above its MDE, max effect/MDE `10.968`. | The framework can reach validation/frozen on the weaker research surface, but canonical ALNS+VNS remains below measurement floor and no candidate promoted. |
| Phase C validation-positive large-X replay | Two ALNS-only validation-positive candidates produced `29` completed pairs: objective W/L/T `2/0/27`, median delta `0.0`, candidate best-update count `0` on completed rows. | The validation positives were not merely killed by runner grace; they lacked broad large-X leverage. |
| Repaired 1R candidate | `split_route_ejection_merge` passed Contract/Verification/Canary/Protocol, but screening was case W/L/T `2/1/5`, pair W/L/T `6/5/21`, median delta `0.0`, CI `[0.0, 5.25]`, decision `expand_screening`. | Valid path-health row; low-SNR mechanism evidence, not a useful CVRP mechanism proof. |
| Two-opt follow-up smoke | `initial_only` still had B-family regressions; `size70` passed smoke with W/L/T `6/0/6`, no route/fleet regressions, and B rows tied with zero two-opt activation. | External/no-LLM work shows targeted failure-cause repair can improve mechanism design. |
| Two-opt size70 large-X diagnostic | Completed planned-pair W/L/T `23/0/0`, median candidate-minus-champion delta `-192.0`, no route/fleet regressions, two-opt activation present; still direct no-LLM and missing `m=2` in that run. | CVRP has a real-looking opportunity. Scion did not discover this through its own Phase C loop. |

## Judgment

Current Scion is **research-capable but not yet research-effective for CVRP**.

It is doing more than "just entering Protocol":

- Phase C produced valid six-cell, 16-round runs with formal artifacts.
- Validation and frozen paths were exercised.
- Branch parentage and same-mechanism chains exist.
- Structured branch-lesson usage is emitted in most agent outputs.
- Code-stage source visibility is healthy in inspected samples.

But it has not yet demonstrated effective CVRP research:

- No Phase C promotion occurred.
- The canonical ALNS+VNS arm never produced a row above its MDE.
- The ALNS-only validation positives did not survive frozen/large-X diagnostics.
- The two strongest Phase C candidates mostly collapsed to ties with zero
  best-update leverage on large-X replay.
- Branch lessons are visible and structured, but their causal impact on later
  mechanism choices is not proven.
- Hypothesis contexts remain large and can truncate the compact research and
  branch-lesson sections that should drive mechanism selection.
- The strongest current CVRP mechanism seed, size70 two-opt scheduling, came
  from external/no-LLM control and follow-up diagnostics, not from Scion's own
  LLM campaign trajectory.

Therefore the immediate bottleneck is not generic Protocol reach. It is the
research loop's ability to convert problem-owned opportunity evidence and
branch lessons into targeted, mechanism-continuous CVRP candidates.

## Single-Round Debug Boundary

The repaired 1R debug proves:

- the repaired CVRP runtime path can carry one LLM candidate through Contract,
  Verification, Canary, screening Protocol, metrics, and Decision;
- the pre-repair runtime-boundary failure no longer blocks Protocol;
- code-phase source visibility can survive compact context;
- low-SNR trajectory-divergent screening can produce `expand_screening`.

The repaired 1R debug does not prove:

- branch depth;
- sibling/ancestor lesson transfer;
- repeated same-mechanism improvement;
- mechanism quality;
- validation/frozen behavior;
- promotion readiness;
- that visible branch lessons changed the candidate.

Use single-round debug as a path-health smoke. Do not use it as CVRP research
quality evidence.

## Recommended Next Debug-Mode Design

Do not start another blind long CVRP LLM campaign now. If a debug-mode Scion run
is needed after the size70 Tier 1 postrun, use a **fixed-mechanism behavior
debug** whose purpose is lesson/context use, not promotion.

Recommended shape:

| Dimension | Recommendation |
| --- | --- |
| Precondition | Wait for accepted Size70 Tier 1 postrun over all `36` keys. If it fails, feed the failure reason into proposal context instead of launching Scion. |
| Baseline surface | ALNS-only copied diagnostic surface, clearly labeled as research-surface evidence, not canonical replacement. |
| Rounds | `4-6` effective rounds for first debug. This is enough to inspect same-branch continuation without creating a long solver campaign. |
| Branching | Fix or strongly seed one branch around the size70/two-opt scheduling mechanism for the first `3` rounds. Prefer max one active branch if the run config supports it; otherwise make branch creation a postrun failure mode to inspect. |
| Stage drain | `SCION_STAGE_TRANSITION_DRAIN_LIMIT=0` for behavior debug unless the explicit purpose is validation/frozen reach. This prevents stage drain from hiding whether the proposal loop used lessons. |
| Early stop | Disabled, so negative or tie-heavy rows still expose branch/lifecycle decisions. |
| Context arm | `compact-measurement-diagnostics`, but require postrun checks that `compact_research_signals` and `branch_lesson_usage_context` are not truncated in the hypothesis calls under audit. |
| Main success metric | Same-mechanism semantic follow-up and problem-owned evidence use, not promotion. |

Required postrun checks:

- For every `hypothesis_target_intent`, `hypothesis`, and `code` trace:
  `context_profile_metadata`, block-family shares, `truncated_sections`,
  branch-lesson visibility, compact research signal visibility, and source
  visibility.
- For every candidate: visible opportunity or lesson -> proposed mechanism ->
  target file -> code change -> Protocol/direct diagnostic result.
- Branch lineage: parent hypothesis IDs, branch state transitions,
  same-mechanism chain length, and whether the agent preserves, narrows, or
  abandons the seeded size70 mechanism for explicit evidence-backed reasons.
- Mechanism evidence: case/pair WLT, median/CI/MDE, runtime completeness,
  two-opt activation, route/fleet regressions, and large-X wall-clock pressure.
- Failure taxonomy: code generation, stale source, Contract/Verification,
  timeout/runtime, and quality-block events.

Acceptance should explicitly allow "no promotion" if the run produces a clear,
evidence-backed research conclusion. It should fail if the agent switches to
unrelated shallow mechanisms, only cites lessons templatically, or truncates the
problem-owned evidence needed to make the mechanism choice.

## Recommendations By Layer

### Proposal / Context / Report Layer

- Add a report-only semantic lesson-use audit for CVRP debug runs: count is not
  enough; each sampled hypothesis should be classified as `semantic_use`,
  `template_only`, `self_reference`, or `not_applicable`.
- Move concise same-branch lesson state and problem-owned opportunity facts
  ahead of broad cross-branch maps in hypothesis context.
- Keep full target/current source guarantees for code phase; do not compress the
  research object code.
- Render size70/Tier1 evidence as a bounded proposal seed after Tier1 postrun:
  mechanism, target file, activation facts, failure boundaries, and open
  runtime caveats. Do not render raw BKS rows or raw replay logs into generic
  Decision input.
- Add a postrun table that joins each candidate's visible lesson/opportunity to
  its actual mechanism and target file. This is report-only.

### Lifecycle / Research-Loop Policy

- For behavior debug, prefer fixed-branch or single-active-branch runs so
  same-mechanism continuation can be observed directly.
- Treat low-SNR continuation as useful only when the next hypothesis narrows or
  repairs the same mechanism. Repeated zero-effect refinements without a new
  causal diagnostic should be pressured toward abandonment or a clean fork.
- Keep validation/frozen and promotion gates unchanged unless a separate v3
  boundary review justifies generic changes.

### Code / Tooling Repair Candidates

These are not Decision gate changes:

- If fixed-branch/max-one-active-branch debug cannot be configured with current
  run knobs, add a debug-only campaign/proposal control outside
  `DecisionFeatures`.
- Repair or strengthen trajectory join artifacts so more than the `61` formal
  candidate sessions can be joined without relying on fallback sequence
  inference. The current `67` missing joins limit causal lesson analysis.
- Tighten prompt composition so `compact_research_signals` and
  `branch_lesson_usage_context` do not truncate in the hypothesis calls selected
  for behavior debug.
- If Tier1 exposes systematic large-X timeout/completeness issues, repair or
  pre-register the large-X wall-clock policy before formal validation.

### Wait For Size70 Tier 1 Postrun

Do not make these decisions from current partial Tier1 sync:

- Launch formal size70 validation replay.
- Claim size70 mechanism readiness.
- Seed a Scion CVRP campaign with size70 as accepted mechanism evidence.
- Interpret missing `X-n1001` rows or current `27/36` partial rows as pass/fail.

The Tier1 gate requires all `36` keys accounted, regression/timeout analysis,
phase activation, best-update/actionability checks, and a formal evidence
decision.

## Bottom Line

Scion v0.4 CVRP is no longer blocked at "can it reach Protocol?" It can. The
remaining CVRP question is whether the agent can perform targeted mechanism
research. Current evidence says **not reliably yet**: branch depth and lesson
fields exist, but mechanism quality has not caught up, and the best current CVRP
opportunity was discovered outside the Scion agent loop. The next useful debug
run should be small, branch-fixed or strongly seeded, and judged by semantic
lesson use plus mechanism-continuity evidence rather than promotion alone.
