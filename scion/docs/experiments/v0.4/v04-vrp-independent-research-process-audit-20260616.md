# Scion v0.4 VRP Independent Research Process Audit - 2026-06-16

## Boundary

This is a report-only process audit of the independent Codex VRP research lane.
It is not a Scion campaign result, not Scion Protocol evidence, not promotion
evidence, and not an accepted solver change. The audit read
`/home/clawd/research/or-autoresearch-agent/scion/design/scion-architecture-v3.md`
first and preserves the v3 boundary:

- LLM/free-text research logs, candidate rationales, BKS gaps, raw rows,
  per-case diagnostics, and process interpretations are tainted/process
  artifacts for human audit and future problem-owned experiment design.
- They must not be converted into `DecisionFeatures`.
- Formal Scion decisions remain limited to Contract, Verification, Protocol,
  safe feature extraction, and deterministic Decision over structured features.
- VRP/CVRP mechanisms, BKS semantics, route-count constraints, ALNS/VNS
  details, and family/slice diagnostics remain problem-owned, not generic
  Scion core governance.

The core conclusion is that the independent lane has produced usable research
records and several narrow hypothesis seeds, but it has not produced a robust
broadly valid improvement because most candidates attack local or parameter
surface symptoms, not the residual mechanism causing the paired incumbent to
miss BKS under the active runtime/protocol budget. BKS gap is headroom, not a
guarantee that a simple operator or parameter tweak improves the current
incumbent in paired 1s/Protocol-style runs.

## Process Records Inventory

The process records are mostly usable and replayable. The main weakness is not
absence of artifacts; it is that the artifacts repeatedly show shallow
candidate mechanisms whose positive signals are slice-specific, seed-sensitive,
or below the measurement/power needed for broad solver claims.

Primary evidence:

| Phase | Process records present | Candidate records | Experiment rows | Replay value |
|---|---|---|---|---|
| Phase K Helmholtz | `/home/clawd/research/vrp-independent-codex-research/phase-k-20260615/research_log.md`, `summary.md`, `scripts/run_smoke_experiments.py` | `candidate.patch` adds only `regret4_insertion` to `vrp/src/alns/repair.py` | `experiments.jsonl`, `raw_results/*.jsonl`, `raw_results/comparison_*.csv` | High: hypothesis, command, cases, seeds, raw rows, patch, and `git apply --check` are recorded. |
| Phase L Newton | `/home/clawd/research/vrp-independent-codex-research/phase-l-20260616/research_journal.md`, `README.md`, `summary.md` | `rejected_candidates.md`; candidate edits preserved under `candidate/` scratch copy, no retained patch | `experiment_results_primary.jsonl`, `experiment_followup_results.jsonl`, combined `experiment_results.jsonl`, summaries | High: scratch baseline/candidate copies, primary/follow-up matrices, and explicit rejection are recorded. |
| Regret4 broader validation | `/home/clawd/research/scion-experiments/v04-vrp-regret4-broader-validation-20260616/README.md`, `summary.md`, `summary.json` | Candidate is Phase K `candidate.patch` applied only to scratch candidate workspace | `validation_results.jsonl`, `raw/validation_results.csv` | High: clean `git archive HEAD` baseline/candidate workspaces, copied CVRPLIB data, exact commands, 80 paired rows. |
| Prior G-J context | `research_log.md`, `experiments.jsonl`, plus candidate summaries where applicable | G/H/I retained candidate patches; J retained none | JSONL/csv/json ledgers | Medium-high: enough to compare repeated patterns; some caveats around dirty/moving worktree in G/H/I are explicitly recorded. |

Direct record-quality evidence:

- Phase K `research_log.md` records the operating constraint, "Do not read
  files under `/home/clawd/research/or-autoresearch-agent/scion`", then logs
  VRP source inspection, hypotheses H0/H1/H2, exact command, cases
  `A-n60-k9`, `M-n151-k12`, `X-n120-k6`, `X-n143-k7`, `X-n204-k19`, seeds
  `0,1,2`, and raw output locations.
- Phase K `summary.md` says "`candidate.patch` ... adds `regret4_insertion`
  ... and registers `("regret4", regret4_insertion)`"; the patch itself
  changes only `/home/clawd/research/or-autoresearch-agent/vrp/src/alns/repair.py`.
- Phase L `research_journal.md` records copied `baseline/` and `candidate/`
  scratch workspaces, inspected files, hypotheses considered, implemented
  intra-route Or-opt, compile smoke check, primary/follow-up matrices, and
  combined decision.
- Phase L `rejected_candidates.md` states "Status: rejected, no
  `candidate.patch` retained" and gives the rejection metrics.
- Broader validation `README.md` records the exact `git archive HEAD` baseline
  and candidate setup, CVRPLIB copy, Phase K patch application in scratch, venv
  setup, smoke command, primary matrix command, and output count verification.

Therefore, the independent lane is auditable. The failure mode is not "agents
left no trace"; it is "the trace shows a sequence of bounded, mostly local
mechanism probes that do not generalize."

## Phase K Helmholtz Analysis

Phase K Helmholtz produced the best-looking independent candidate:
`regret4_repair`.

Evidence chain:

1. Hypothesis:
   `/home/clawd/research/vrp-independent-codex-research/phase-k-20260615/research_log.md`
   defines H2 as "Regret-4 Repair Operator": adding regret-4 insertion might
   improve cases where regret2/regret3 under-prioritize customers with fewer
   good insertion options.
2. Code change:
   `/home/clawd/research/vrp-independent-codex-research/phase-k-20260615/candidate.patch`
   adds:

   ```text
   def regret4_insertion(...):
       regret_insertion(..., k=4)
   ...
   ("regret4", regret4_insertion)
   ```

   This is a very small repair-pool addition, not a new construction strategy,
   acceptance model, runtime schedule, or family-conditioned mechanism.
3. Matrix:
   `scripts/run_smoke_experiments.py` hard-codes cases
   `A-n60-k9`, `M-n151-k12`, `X-n120-k6`, `X-n143-k7`, `X-n204-k19`, seeds
   `[0,1,2]`, and default `1.0s` budget. It compares candidate cost minus
   baseline cost, where negative is better.
4. Result:
   `experiments.jsonl` records H2 `regret4_repair` as `8` wins, `5` ties,
   `2` losses, mean delta `-32.333333333333336`, median delta `-11.0`,
   failures `0`.
5. Interpretation:
   `summary.md` correctly frames H2 as the strongest candidate but says it
   needs a wider run before merging.

Why it looked positive:

- The smoke matrix was small: 5 cases x 3 seeds = 15 paired rows.
- It over-weighted slices where regret4 happened to help or not hurt:
  `A-n60-k9` improved all three smoke seeds; `M-n151-k12` improved two and tied
  one; each X case had at least one win and many ties.
- The smoke set was not family-balanced. It had one A, one M, and three X
  cases. It had no B/E/P coverage, and no broader A/B/P/E stable-regression
  surface.
- It included real BKS gaps, but the positive rows were seed-specific: on
  `X-n120-k6` it tied seed 0, won seed 1 by 257, and lost seed 2 by 121; on
  `X-n143-k7` it lost seed 0 by 44, won seed 1 by 155, and tied seed 2. This
  is exactly the kind of signal that requires broader seed replay before
  broad mechanism claims.

Mechanism diagnosis:

- Current repair already has greedy, regret2, and regret3 insertion. Regret4 is
  an incremental variant of the same insertion family. It may change selection
  order among removed customers, but it does not create a new route-level
  decomposition, construction, acceptance, restart, runtime-tier, or
  instance-conditioned scheduling mechanism.
- In an ALNS loop with adaptive repair weights, adding a fourth repair option
  splits early sampling mass and relies on short-run adaptive scoring to learn
  when the extra operator is useful. In a 1s budget with tens of iterations,
  that learning can be too noisy to stabilize across families.
- The patch preserves feasibility and route constraints, but preserving
  constraints is not the same as improving the paired incumbent. The broader
  validation confirms this distinction.

## Phase L Newton Analysis

Phase L Newton rejected its only implemented candidate, and that rejection is
good process evidence.

Evidence chain:

1. Hypothesis:
   `/home/clawd/research/vrp-independent-codex-research/phase-l-20260616/research_journal.md`
   records three considered hypotheses. It chose same-route segment relocation
   because intra-route 2-opt reverses segments but does not directly move a
   short segment to another position in the same route.
2. Code change:
   The scratch diff between `baseline/src/local_search/operators.py` and
   `candidate/src/local_search/operators.py` adds `intra_or_opt`,
   `intra_or_opt_1`, `intra_or_opt_2`, and `intra_or_opt_3`. The scratch
   `candidate/src/solver.py` imports those operators and inserts them after
   `two_opt_intra` in `default_vns_operators()`.
3. Matrix:
   Primary matrix: 7 CVRPLIB cases x 3 seeds x 1.0s = 21 paired rows:
   `A-n45-k6`, `B-n50-k7`, `E-n76-k10`, `P-n55-k10`, `F-n72-k4`,
   `M-n101-k10`, `X-n101-k25`.
   Follow-up sanity: 3 outside cases x 3 seeds x 1.0s = 9 rows:
   `A-n60-k9`, `B-n68-k9`, `P-n76-k4`.
4. Result:
   `/home/clawd/research/vrp-independent-codex-research/phase-l-20260616/summary.md`
   records primary W/T/L `5/11/5`, mean delta `-0.142857`, median `0.0`;
   follow-up W/T/L `2/1/6`, mean delta `+5.666667`, median `+6.0`; combined
   W/T/L `7/12/11`, mean delta `+1.6`, median `0.0`.
5. Decision:
   `/home/clawd/research/vrp-independent-codex-research/phase-l-20260616/rejected_candidates.md`
   rejects the candidate and retains no `candidate.patch`.

Why rejection was correct despite BKS gap:

- The candidate attacked same-route route ordering, not necessarily the
  residual BKS gap. The solver already has intra-route 2-opt plus inter-route
  relocate, Or-opt 1/2/3, swap, and 2-opt* in the local-search/VNS surface in
  the current code shape; Phase L adds only same-route segment relocation to
  an already local-search-heavy system.
- The raw Phase L rows show candidate iteration counts often lower than
  baseline. Examples from `experiment_results.jsonl`: `A-n45-k6` seed 1 drops
  from 128 to 84 iterations while losing by 16; `E-n76-k10` seed 1 drops from
  34 to 10 and ties; `P-n76-k4` follow-up seed 1 drops from 40 to 23 and loses
  by 12. The extra VNS work can consume short-budget search opportunity.
- It did not create route-count regressions or feasibility failures, but it
  also did not reliably improve final objective. It often changed local-search
  work distribution more than solution quality.
- Follow-up cases exposed overfit: the primary matrix was effectively neutral,
  but outside sanity cases went `2/1/6` with positive mean and median deltas
  where positive delta is worse.

Newton's process quality was stronger than its mechanism quality. It considered
alternatives, implemented a localized candidate in scratch, tested outside
cases, and stopped rather than retaining a weak patch.

## Broader Regret4 Validation Analysis

The broader no-LLM validation is the decisive explanation for why the Phase K
smoke signal did not become a robust broad improvement.

Evidence chain:

1. Setup:
   `/home/clawd/research/scion-experiments/v04-vrp-regret4-broader-validation-20260616/README.md`
   records clean `git archive HEAD` baseline and candidate workspaces, copied
   CVRPLIB data, and application of only
   `/home/clawd/research/vrp-independent-codex-research/phase-k-20260615/candidate.patch`
   to the candidate workspace.
2. Matrix:
   Cases: `A-n60-k9`, `M-n151-k12`, `X-n120-k6`, `X-n143-k7`,
   `X-n204-k19`, `B-n66-k9`, `E-n76-k10`, `P-n70-k10`.
   Seeds: `0..9`. Budget: `1.0s`. Rows: `80`.
   The harness passed reference `.sol` route count as `max_routes` to both
   solvers.
3. Result:
   `/home/clawd/research/scion-experiments/v04-vrp-regret4-broader-validation-20260616/summary.json`
   records `acceptance_passed=false`, complete rows `80`, W/T/L `21/31/28`,
   W-L margin `-7`, mean delta `-4.4625`, median delta `0.0`, failures `0`,
   feasibility regressions `0`, route regressions `0`, and repeated regression
   families `E`, `M`, `P`.
4. Decision:
   `summary.md` recommends `reject_or_request_narrower_diagnostic`.

Per-family split:

| Family | Rows | W/T/L | Mean delta | Median delta | Interpretation |
|---|---:|---:|---:|---:|---|
| A | 10 | `3/4/3` | `-1.7` | `0.0` | Mixed, no broad gain. |
| B | 10 | `5/0/5` | `0.4` | `0.0` | Split evenly, no median gain. |
| E | 10 | `2/1/7` | `13.8` | `10.5` | Clear repeated regression. |
| M | 10 | `3/3/4` | `-0.5` | `0.0` | Smoke M signal collapses to neutral/slightly negative W-L. |
| P | 10 | `2/3/5` | `6.6` | `0.5` | Repeated regression. |
| X | 30 | `6/20/4` | `-18.1` | `0.0` | Positive mean from a few wins, mostly ties, not broad enough. |

Case/BKS details from `validation_results.jsonl` show why "there is BKS gap"
is insufficient:

| Case | Baseline gap range across seeds | W/T/L | Mean delta | Route regressions |
|---|---:|---:|---:|---:|
| `A-n60-k9` | `0.369%..3.840%` | `3/4/3` | `-1.7` | `0` |
| `B-n66-k9` | `1.064%..5.927%` | `5/0/5` | `0.4` | `0` |
| `E-n76-k10` | `5.181%..12.892%` | `2/1/7` | `13.8` | `0` |
| `M-n151-k12` | `8.670%..13.300%` | `3/3/4` | `-0.5` | `0` |
| `P-n70-k10` | `4.716%..13.301%` | `2/3/5` | `6.6` | `0` |
| `X-n120-k6` | `5.686%..6.886%` | `3/5/2` | `-25.1` | `0` |
| `X-n143-k7` | `8.599%..11.720%` | `2/7/1` | `-34.8` | `0` |
| `X-n204-k19` | `6.348%..7.350%` | `1/8/1` | `5.6` | `0` |

The most important observation is that high residual BKS gap did not predict
candidate improvement. `E-n76-k10` had substantial baseline gaps, but regret4
lost 7 of 10 seeds. `P-n70-k10` also had high gaps and lost 5 of 10. `M-n151-k12`
had large gaps but ended `3/3/4`. The X family retained positive mean distance
because a few seeds had large wins, but 20 of 30 X rows tied and the median was
0.0. This is not a broad robust improvement; it is a family/slice diagnostic.

Why the smoke signal failed:

- Case-slice overfit: Phase K tested A/M/X only; broader validation added B/E/P
  and exposed E/P regressions.
- Seed sensitivity: the original X wins were often one-seed effects. With
  seeds `0..9`, many rows became ties or losses.
- Repair-operator interaction: regret4 competes with greedy/regret2/regret3 in
  an adaptive pool. Short runs may not learn the correct operator mix, and
  adding a similar repair can perturb the trajectory without improving the
  incumbent.
- Objective gap mismatch: BKS gap may come from construction choice, route
  count, acceptance, destroy selection, large-neighborhood diversification,
  runtime budget, or large-instance fallback. A repair-order tweak only
  addresses one narrow mechanism.
- Measurement noise and budget pressure: many 1s runs complete only a small
  number of ALNS iterations. A local perturbation can change the random path
  enough to win or lose without a stable mechanism advantage.
- Constraint preservation is necessary but weak: route and feasibility
  regressions were zero, yet overall W-L was negative. The candidate is safe
  in constraints but not broadly quality-improving.

## Why Gap To BKS Did Not Translate Into Easy Improvement

Both ALNS-only and canonical ALNS+VNS have measurable BKS gap, but that does
not imply a simple local operator improves the incumbent under the actual
budget and protocol.

Current supporting docs:

- `/home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/v04-cvrp-baseline-strength-phaseA-20260613.md`
  shows ALNS-only has more BKS headroom but worse solver quality. In paired
  characterization, ALNS-only won only `7/64`, lost `56/64`, tied `1/64`
  against ALNS+VNS, with mean BKS gap `6.50%` for ALNS-only versus `4.20%`
  for ALNS+VNS.
- The same Phase A report shows ALNS+VNS has higher A/A measurement floor
  (`MDE=9.6`) than ALNS-only (`MDE=4.65`), meaning small local changes can be
  invisible or noisy against the canonical baseline.
- `/home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/v04-cvrp-baseline-strength-phaseC-postrun-20260615.md`
  shows the repaired protocol can reach validation/frozen under ALNS-only, but
  no champion promotion occurred. ALNS-only validation positives collapsed at
  frozen, and canonical ALNS+VNS did not produce a row above its own MDE.
- `/home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/v04-cvrp-size70-fixed-validation-postrun-20260615.md`
  shows a mechanically active two-opt size70 fixed candidate completed 48/48
  validation pairs, preserved feasibility/fleet/routes, and still failed
  validation with `VALIDATION_FAIL_NO_HIERARCHICAL_GAIN`.

The right distinction is:

- BKS gap means the solver is not globally optimal or not at best-known
  quality on the tested instance.
- A paired candidate improvement means the candidate beats the current
  champion on the same case/seed/budget under the protocol objective.
- A robust improvement means that paired gain survives family split, seed
  expansion, route/feasibility guards, validation/frozen exposure limits, and
  the measurement noise floor.

The independent agents repeatedly found headroom, but their candidates did not
systematically convert that headroom into paired gains.

## Independent Agent Research Quality

Strengths:

- Usable process records: K/L and most G-J phases kept logs, JSONL ledgers,
  raw rows, candidate summaries, and either patches or explicit rejection.
- Bounded experiments: agents generally used paired case/seed/budget matrices
  rather than unsupported qualitative claims.
- Some stopping discipline: Newton rejected Or-opt after an outside-case sanity
  check; Russell retained no patch after neutral/negative X-focused screens;
  Helmholtz explicitly requested broader validation before merge.
- Feasibility discipline: candidates were mostly tested with feasibility and
  route-count checks, and retained candidates were not applied to the main
  checkout.

Weaknesses:

- Hypothesis diversity is shallow. Most candidates are parameter knobs
  (`narrow_destroy_ratio`, `cooler_sa`, `destroy160`, `vns_threshold0`,
  `max_destroy_160`), small insertion/local-search variants (`regret4`,
  intra-route Or-opt), or construction tweaks (`multi_construction`,
  `rotated_sweep8`).
- Mechanism novelty is low. Regret4 extends an existing regret-k family;
  Or-opt adds local neighborhood work to a VNS/local-search-heavy solver;
  no-VNS and VNS threshold tests mostly rediscover that local search is
  expensive but valuable.
- Baseline understanding is partial. Several records notice that VNS/local
  search can dominate wall time and that route-count/benchmark feasibility
  differs from CVRP feasibility, but few candidates directly exploit instance
  features, runtime phase traces, or family-specific failure modes.
- Experiment design is good enough for screening but weak for mechanism
  diagnosis. There are small paired matrices, but little systematic ablation:
  no operator scheduling ablation, no destroy/repair interaction grid, no
  budget tier ladder before candidate selection, no instance-feature stratified
  acceptance rule, and limited separation of construction-only, ALNS-only,
  ALNS+VNS, and large-X surfaces.
- Stopping discipline is mixed. Some candidates were correctly stopped; others
  were passed forward as "weak seeds" despite known caveats. This is acceptable
  as external-control seed generation, but not enough for adoption.
- The agents tend to search around the solver rather than diagnose the residual
  gap. They see "BKS gap exists" and try a small operator/parameter. The
  evidence says the residual gap is often located in budget allocation,
  construction/family behavior, adaptive operator scheduling, or large-X
  runtime dynamics, not in one universally missing local move.

Prior phase patterns:

- Phase G Tesla retained `narrow_destroy_ratio`, changing destroy ratio
  `(0.10,0.40)` to `(0.05,0.25)`. Its evidence was only 7 cases x 2 seeds x
  nominal 0.4s: W/T/L `5/7/2`, mean gap delta `-0.2904` pp. It also had
  negative signals on `X-n143-k7` and `tai150a`, and `X-n513-k21` did not
  activate ALNS under the short budget.
- Phase H retained `c02_cooler_sa`, a two-constant simulated annealing patch:
  W/T/L `11/42/1`, total distance delta `-236`, mean gap delta `-0.1403` pp
  over 54 paired comparisons. Useful but tiny, with many ties and explicit
  need for 10+ seeds, more X cases, and longer budgets.
- Phase I retained `rotated_sweep8`, which improved AGS large construction
  fallback (`7/3/0` on 10 AGS rows, total distance delta `-61,847`) but did
  not address the main X-subset ALNS gap. It is a large-construction diagnostic,
  not a broad VRP improvement.
- Phase J retained no candidate. No-VNS lost `0/0/15` with mean cost delta
  `+240.73`; rotated sweep initial and max-destroy-160 were `0/15/0` ties.

These prior phases show the same pattern as K/L: the independent lane can
produce auditable bounded probes, but it mostly explores nearby knobs and
operators. Positive seeds are narrow and need no-LLM validation; negative
results often reveal budget/operator interactions rather than absence of BKS
headroom.

## Implications For Scion CVRP/VRP

1. Scion should not treat independent positive smoke as solver evidence.
   Phase K was a useful hypothesis seed, and the broader replay correctly
   rejected it as a broad fixed candidate.

2. The external lane is valuable as a process control. It shows that plain
   Codex without Scion governance also struggles to convert BKS gap into robust
   improvement. This weakens the hypothesis that Scion governance alone is the
   bottleneck.

3. The useful problem is now VRP mechanism research quality. Current agents can
   log and test, but they are not yet diagnosing where residual gap arises:
   construction, route-count pressure, ALNS destroy/repair interaction,
   acceptance temperature, VNS runtime allocation, or large-X budget saturation.

4. Keep ALNS-only and ALNS+VNS separate. ALNS-only is a weaker, more measurable
   research surface; ALNS+VNS is the stronger canonical quality baseline. A
   candidate that improves ALNS-only does not automatically improve ALNS+VNS.

5. Keep BKS/gap out of DecisionFeatures. It is useful for human/problem-owned
   targeting and postrun diagnosis, but it should not drive deterministic
   promotion unless converted through the existing protocol metrics.

## Concrete Next Experiment Recommendations

The next VRP research task should be less "try another local operator" and
more "identify the slice-specific mechanism that creates or fails to close the
gap."

Recommended next task:

1. Run a targeted family/slice mechanism diagnostic, not a broad candidate
   patch. Split at least A/B/E/P/M/X and construction-only large/AGS surfaces.
   For each slice, record construction cost, post-initial-local-search cost,
   ALNS iterations, selected destroy/repair pairs, accepted moves, best-update
   count, route-count status, and final BKS gap.

2. Separate research surfaces:
   - ALNS-only for lower measurement floor and faster exploratory diagnosis.
   - ALNS+VNS for canonical quality confirmation.
   - Construction-only/large fallback for AGS/large cases.
   - X-family runtime curve for large-X where ALNS iteration density is low.

3. Test instance-feature-conditioned operator scheduling. Regret4 should not
   return as a global repair-pool addition. If revisited, it should be gated
   by family/feature signals such as route slack, customer count, route-count
   pressure, removal size, or insertion candidate dispersion.

4. Pre-register budget tiers before candidate selection: 1s, 2s/3s, and one
   longer diagnostic tier. A candidate that wins only at 1s by trajectory noise
   or loses when VNS gets time should be classified differently from a
   mechanism that scales with budget.

5. Do a destroy/repair interaction ablation before new repair operators:
   compare greedy/regret2/regret3/regret4 individually and in pools, with and
   without adaptive weights, across the same seeds. This directly tests whether
   regret4 has independent value or only perturbs adaptive sampling.

6. For local-search additions, measure opportunity cost explicitly:
   iterations, wall time spent before/inside ALNS, best-update count, and local
   improvement count. Newton's Or-opt result suggests "more local search" can
   reduce ALNS exploration under short budgets.

7. Require a process record template for future independent agents:
   hypothesis, mechanism target, expected gap source, patch summary, case
   rationale, seeds, budget, raw paths, W/T/L, family split, route/feasibility
   checks, budget/iteration diagnostics, rejection/retention decision, and the
   next no-LLM validation tier.

Acceptance for the next independent/research task should not be "find a
candidate with positive W/T/L on a smoke set." It should be either:

- a validated narrow mechanism claim for one pre-registered slice, or
- a diagnostic that explains why a slice has BKS gap but the current solver
  cannot exploit it under the tested budget.

That is the level of research needed before another candidate should be
considered for Scion fixed replay.
