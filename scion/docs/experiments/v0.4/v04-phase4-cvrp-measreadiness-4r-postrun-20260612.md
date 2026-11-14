# Scion v0.4 Phase 4 CVRP Measurement-Readiness 4R Postrun Audit

*Date: 2026-06-12*
*Branch: `codex/v04-evidence-repair-plan`*
*Run root: `/home/clawd/research/scion-experiments/v04-phase4-focused-cvrp-measreadiness-20260611-4r-gpt55-20260611T224916Z-claw`*
*Run commit: `32ab596`*
*Governing boundary: `scion/design/scion-architecture-v3.md`*

## 0. Boundary Used For This Audit

This audit uses the v3 boundary as the primary interpretation rule:

- LLM output, hypothesis text, target intent, code proposals, branch-lesson
  text, and prompt diagnostics are tainted proposal material.
- The evidence path is Contract -> Verification -> Protocol metrics -> safe
  `DecisionFeatures` -> deterministic Decision.
- CVRP, ALNS, VNS, BKS, case hardness, MDE, and runtime-model semantics are
  problem-owned diagnostics. They may guide proposals and readiness decisions,
  but they are not generic framework decision inputs.
- The report below therefore treats proposal/context artifacts as "what the
  agent saw and tried", not as proof. Proof for the 4R outcome comes from
  copied config, formal candidate artifacts, metric rows, verification records,
  and deterministic decisions.

## 1. Effective Launch Configuration

The wrapper completed successfully:

- Outer `exit.txt`: `WRAPPER_EXIT_STATUS:0`, ended `2026-06-12T00:43:50Z`.
- `campaign/run_status.json`: `run_validity_status=valid`,
  `run_completeness_status=complete`, `completed_requested_rounds=true`,
  `last_stop_reason=max_rounds_exhausted`.
- Started at `2026-06-11T22:49:16Z` in
  `/home/clawd/research/or-autoresearch-agent/scion`.

Resolved launch environment:

```text
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion
SCION_MODEL=gpt-5.5
SCION_BASE_URL=http://127.0.0.1:8080
SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp
PROBLEM=scion/problems/cvrp/problem.yaml
PROTOCOL=scion/problems/cvrp/formal/protocol.yaml
SPLIT=scion/problems/cvrp/formal/split_manifest.yaml
SEEDS=scion/problems/cvrp/formal/seed_ledger.yaml
ROUNDS=4
TIME_LIMIT_SEC=30
AGENTIC_SESSION_TIMEOUT_SEC=900
DISABLE_EARLY_STOP=1
AGENTIC_PROPOSAL=1
GIT_COMMIT=32ab596
```

Important config trap: `campaign/champions/champion_v1/protocol.yaml`,
`split_manifest.yaml`, and `seed_ledger.yaml` are smoke copies, but the
effective formal files are under `campaign/champions/champion_v1/formal/`.
The metric rows and replay identity agree with the formal copies, not the
smoke top-level copies.

Effective formal screening config:

- Protocol version: `0.4-cvrp-formal-readiness`.
- `n_cases_modify=8`, `n_seeds=4`, `expand_to_modify=12`.
- Screening seeds: `11`, `29`, `43`, `59`.
- Screening split: 16 formal CVRPLIB cases, from which modify screening selected
  8 cases first and 12 after expansion.
- Runtime limits: default screening `30s`; screening dimension 150-250 -> `45s`;
  screening dimension >=251 -> `60s`.
- Problem measurement declaration: `runtime_model=budget_exhausting`,
  `practical_delta_screen=2.0` raw `total_distance`,
  `practical_delta_validate=1.0`.
- Copied Phase 1 calibration:
  `formal/calibration/aa_noise_floor.json`, `mde_at_power_80=9.9`,
  `false_pass_rate_at_current_gate=0.0`, `recommended_min_seeds=8`,
  `n_pairs=96`, `decision_features_excluded=true`.

Interpretation: this was a formal CVRP measurement-readiness run using the
new formal split/seeds and problem-owned measurement diagnostics. It was not
an old two-seed or smoke-config CVRP run.

## 2. Count Reconciliation

`status.json` and `campaign_summary.json` reconcile cleanly:

| Counter | Value |
|---|---:|
| requested rounds | 4 |
| proposal attempts total | 4 |
| quality blocks | 0 |
| verification-consumed candidates | 4 |
| effective protocol rounds | 4 |
| protocol metric results | 4 |
| screening protocol results | 4 |
| validation protocol results | 0 |
| frozen protocol results | 0 |
| champion version | 1 |
| promotions | 0 |
| fresh runtime replay protocol results | 0 |
| formal screened candidates | 4 |
| formal candidate artifact index rows | 2 |

The apparent mismatch between `formal_screened_candidates=4` and
`artifacts/formal_candidates/index.jsonl` having 2 rows is expected and is
explicitly recorded by `formal_candidate_count_reconciliation`:

- The 4 formal screened candidates are 4 protocol-evaluated screening rows.
- The 2 index rows are replayable patch artifacts.
- Each branch had one replayable patch/hypothesis, then an expanded screening
  row reused that same patch and hypothesis:
  - Branch `05770185...`, hypothesis `36727956...`, patch digest
    `d9be840c...`, metrics `0657b9ef...` then `1f89b5bd...`.
  - Branch `1e4159eb...`, hypothesis `19bc6883...`, patch digest
    `fd33c0b7...`, metrics `de63e526...` then `16d06247...`.
- The status payload says formal candidate artifacts are a replayable patch
  subset of screening rows, not a complete metric-row count.

Evidence integrity was complete:

- `evidence_integrity.status=complete`, no warnings.
- `lineage_integrity.status=complete`, `recorded_outcome_count=4`.
- Both formal patch artifacts have `replay_identity_status=complete` and no
  missing replay identity keys.

## 3. Candidate / Decision Audit

All four candidates passed Contract and Verification. Verification includes
syntax/interface checks, solution consistency, feasibility, objective oracle,
double-run canonical signature, and V9 budget compliance. The V9 guard used
the new `budget_exhausting` semantics: it checked budget compliance rather
than treating equal wall time as a speed regression.

### Round 1: route-limit-aware repair, initial screening

| Field | Value |
|---|---|
| branch | `05770185-2e4a-4463-bfe5-ee83b6bf85e7` |
| hypothesis | `36727956-232e-48f9-89ab-dd4998035c24` |
| target | `policies/baseline_modules/destroy_repair.py` plus scheduler integration |
| mechanism | `route_limit_aware_repair` |
| raw metrics | `metrics/0657b9ef-13e2-499a-9e1a-f32cf3b4f73c.json` |
| pairs | 32 attempted / 32 valid / 0 failed |
| case result | 0 W / 0 L / 8 T |
| pair result | 1 W / 1 L / 30 T |
| median delta | `0.0` raw `total_distance` |
| CI | `[0.0, 0.0]` |
| runtime evidence | high/sufficient, 32 fresh champion pairs |
| decision | `expand_screening` |
| decision reason | `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT` |

The patch made greedy/regret repair route-limit aware and passed `max_routes`
from scheduler into repair. Telemetry showed activation, but objective effect
was essentially zero: only CMT2 had non-tie pair deltas (`-9`, `+17`) and
still tied at case level.

Against Phase 1 CVRP MDE `9.9`, the protocol-level effect is `0.0 / 9.9 = 0`.
The largest single pair delta in this row was `17`, but that did not survive
case-level aggregation and had an opposing loss in the same case.

### Round 2: same patch, expanded screening

| Field | Value |
|---|---|
| branch | `05770185-2e4a-4463-bfe5-ee83b6bf85e7` |
| target | same route-limit-aware repair patch |
| raw metrics | `metrics/1f89b5bd-1294-4056-b533-356c53ee2577.json` |
| pairs | 48 attempted / 48 valid / 0 failed |
| case result for DecisionFeatures | 0 W / 0 L / 12 T |
| pair result | 0 W / 1 L / 47 T |
| median delta | `0.0` |
| CI | `[0.0, 0.0]` |
| runtime evidence | `low_cached_champion`, 16 cached champion runtime pairs |
| decision | `continue_explore` |
| decision reasons | `SCREENING_FAIL_WIN_RATE`, `SCREENING_ZERO_WIN_STREAK_CONTINUE`, `SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE` |

The expansion added 4 formal cases. It confirmed the mechanism was active but
not useful: 47 of 48 pairs tied and the only non-tie was a loss on
`E-n101-k14.vrp` with raw delta `-4`.

The deterministic decision did not promote. It kept the branch in `explore`
with same-mechanism-only follow-up allowed, but the candidate code was
discarded and evidence retained.

Against MDE, this is again `0.0 / 9.9 = 0`.

### Round 3: double-bridge relink VNS, initial screening

| Field | Value |
|---|---|
| branch | `1e4159eb-7f98-4a21-9a86-ff91946868e5` |
| hypothesis | `19bc6883-3149-484a-9af6-1ce760709292` |
| target | `policies/baseline_modules/local_search.py` |
| mechanism | `double_bridge_relink_vns` |
| raw metrics | `metrics/de63e526-e51c-4984-9a20-64517ebf40e2.json` |
| pairs | 32 attempted / 32 valid / 0 failed |
| case result | 4 W / 2 L / 2 T |
| pair result | 17 W / 9 L / 6 T |
| median delta | `0.75` |
| CI | `[-9.0, 21.0]` |
| runtime evidence | `low_cached_champion`, aggregate runtime excluded/insufficient |
| decision | `expand_screening` |
| decision reason | `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT` |

This was the most research-informative row. It was not VNS absorption or a
pure tie: the candidate changed search behavior and produced case-level wins:

- `A-n64-k9`: win, median `+7.5`, pair 4/0/0.
- `B-n63-k10`: win, median `+21.0`, pair 3/1/0.
- `P-n65-k10`: win, median `+1.5`, pair 2/1/1.
- `X-n110-k13`: win, median `+82.0`, pair 4/0/0.

It also lost cases:

- `CMT2`: loss, median `-9.0`, pair 1/3/0.
- `E-n101-k14`: loss, median `-2.5`, pair 1/2/1.

Two cases tied (`CMT4`, `M-n200-k17`). The median `0.75` is below both the
declared practical screening delta `2.0` and the Phase 1 MDE `9.9`. The CI
crosses zero widely. The `X-n110-k13` case-level win (`+82.0`) is above MDE
on one case, but protocol evidence is not one-case evidence; cross-case median
and CI remained below readiness.

### Round 4: same double-bridge patch, expanded screening

| Field | Value |
|---|---|
| branch | `1e4159eb-7f98-4a21-9a86-ff91946868e5` |
| target | same double-bridge relink VNS patch |
| raw metrics | `metrics/16d06247-6540-491b-9296-91a84997a2b9.json` |
| pairs | 48 attempted / 48 valid / 0 failed |
| case result | 4 W / 5 L / 3 T |
| pair result | 22 W / 19 L / 7 T |
| median delta | `-1.25` |
| CI | `[-5.75, 7.25]` |
| runtime evidence | `low_cached_champion`, 48 cached champion runtime pairs, aggregate runtime excluded |
| decision | `abandon` |
| decision reasons | `SCREENING_FAIL_WIN_RATE`, `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`, `SCREENING_SOFT_ABANDON_NEGATIVE_DELTA` |

Expanded screening preserved several real positive case signals:

- `A-n64-k9`: win, median `+7.5`, pair 4/0/0.
- `A-n80-k10`: win, median `+12.0`, pair 3/1/0.
- `M-n151-k12`: win, median `+7.0`, pair 3/1/0.
- `X-n110-k13`: win, median `+82.0`, pair 4/0/0.

But losses grew and dominated case-level gate outcome:

- `E-n101-k14`: loss, median `-2.5`, pair 1/2/1.
- `E-n101-k8`: loss, median `-2.5`, pair 1/2/1.
- `P-n76-k4`: loss, median `-12.0`, pair 1/3/0.
- `P-n101-k4`: loss, median `-9.0`, pair 0/4/0.
- `CMT3`: loss, median `-2.5`, pair 1/2/1.

Three cases tied (`B-n67-k10`, `CMT4`, `tai150c`). The final median is
negative and the high CI bound `7.25` is below the Phase 1 MDE `9.9`.
Therefore the deterministic abandon is justified as a screening failure and
soft lifecycle archive, not as proof that the mechanism is intrinsically bad.

## 4. Runtime Evidence

The run shows Phase 2/3 runtime repairs helped:

- `fresh_runtime_replay_protocol_results=0`.
- `fresh_champion_required_count=0`.
- Runtime evidence policy explicitly marks low/cached runtime as proposal or
  audit guidance only and `decision_features_excluded=true`.
- V9 perf guard was budget-compliance based for `runtime_model=budget_exhausting`.

Residual runtime evidence:

- All four screening rows have `SCREENING_RUNTIME_BUDGET_SATURATION` info
  diagnostics, with saturation ratios around `0.9873` to `0.9966`.
- The severity is `info`, not a gate veto.
- Three of four rows used cached champion runtime evidence at least partly:
  - Round 2: 16 cached champion runtime pairs, runtime evidence pressure.
  - Round 3: 32 cached champion runtime pairs, runtime aggregate excluded.
  - Round 4: 48 cached champion runtime pairs, runtime aggregate excluded.

Interpretation: the earlier pathological "fresh replay drains round budget"
is fixed for this run. Runtime is still noisy as proposal feedback because
budget-exhausting ALNS/VNS naturally saturates the time budget, but it no
longer drives promotion or replay behavior.

## 5. Branch Research Shape

The run used two branches:

| Branch | Mechanism | Depth | Final status |
|---|---|---:|---|
| `05770185...` | `route_limit_aware_repair` | 2 | active `explore`, code discarded, evidence retained |
| `1e4159eb...` | `double_bridge_relink_vns` | 2 | abandoned, soft lifecycle archive |

Branch behavior:

- Both branches received same-mechanism follow-up through screening expansion.
- Clean fork behavior worked: the second branch changed mechanism family and
  target file after the route-limit branch failed to produce quality signal.
- Cross-branch transfer was advisory only:
  `cross_branch_research_observability.policy=proposal_observability_only`,
  `decision_input_policy=excluded_from_decision_features`.
- Prompt/output artifacts show the second hypothesis explicitly contrasted
  against the prior destroy/repair route-limit attempt and moved to
  `local_search.py`.

Compared with previous shallow CVRP runs:

- The 6/11 review reported a prior CVRP 8R shape of 4 branches with depths
  `3/3/1/1`. This 4R run is shorter but cleaner: both branches got one
  same-mechanism expansion, so there were no one-shot branches.
- It did not get deeper than earlier CVRP work in absolute depth; max depth is
  only 2. It therefore improves the *consistency* of branch-internal follow-up
  under a 4R budget, but it does not yet prove deep CVRP research.
- The useful research signal came from the second branch's positive case
  clusters, not from a promotion path.

## 6. Prompt / Context Audit

The run had 16 LLM traces, all `gpt-5.5`:

- 2 `hypothesis_target_intent`
- 2 `hypothesis`
- 10 `tool_selection`
- 2 `code`

Total LLM accounting:

- input/prompt tokens: `310,828`
- output tokens: `8,707`
- total tokens: `319,535`
- cache reads: `0`

Agentic session structure:

- Each mechanism has one partial hypothesis session ending at
  `hypothesis_awaiting_approval`, then one completed code session using the
  same idempotency key. This is segmented recording, not duplicate hypothesis
  generation.
- Hypothesis sessions are tainted (`tainted=true`); their outputs are proposal
  material.

Prompt block accounting for hypothesis generation:

| Session | Total chars | Research signal | Governance | Source context | Active facts | Tool observations | Feedback |
|---|---:|---:|---:|---:|---:|---:|---:|
| route-limit hypothesis | 127,613 | 11,137 (8.7%) | 7,294 (5.7%) | 32,339 (25.3%) | 34,548 (27.1%) | 24,170 (18.9%) | 0 |
| double-bridge hypothesis | 148,742 | 26,827 (18.0%) | 7,290 (4.9%) | 32,339 (21.7%) | 29,801 (20.0%) | 23,980 (16.1%) | 4,731 (3.2%) |

Context improvements over the 6/11 review:

- The prompt now includes `problem_measurement_diagnostics`, and the run copied
  the formal A/A artifact with MDE `9.9`.
- The second hypothesis prompt includes `runtime_feedback`,
  `agentic_research_diagnosis`, `objective_opportunity_profile_screening_only`,
  `campaign_search_memory`, `exploration_coverage`, and sibling/branch context.
- Governance share is much lower than the earlier reported CVRP prompt problem
  (about 5%, not tens of thousands of dominant compliance text).

Remaining context issues:

- Research signal is still not dominant. Source + active facts + tool
  observations are roughly 58-71% of hypothesis prompt chars, while distilled
  research signal is 9-18%.
- `experiment_history_this_branch` was only 81 chars in both hypothesis
  manifests. The richer branch evidence exists in status/branch cards, but
  the branch-local history section itself remains thin.
- Raw prompts are not saved (`raw_prompt_saved=false`), so this audit can
  verify visibility/accounting and output behavior, but cannot quote the exact
  full prompt.

Interpretation: Phase 4 context is materially better than the prior "governance
drowns research" pattern, but it is not yet a dense research cockpit. The agent
received enough source and measurement/readiness signal to propose real solver
mechanisms, and it did use branch lessons. The remaining weakness is signal
distillation, not v3 boundary leakage.

## 7. Framework vs Problem / Research Findings

What v0.4 repairs helped:

- Evidence closure: replay identity complete; metric rows complete; status
  reconciliation explicitly explains counter differences.
- Measurement readiness: copied formal A/A MDE is visible and problem-owned.
- Runtime semantics: `budget_exhausting` prevented runtime replay drain and
  made runtime aggregate exclusion explicit.
- Branch governance: same-mechanism expansion happened, and clean fork moved
  from destroy/repair to local-search VNS.
- Prompt profile: measurement diagnostics and compact research sections are
  present; governance no longer dominates by raw char share.

What remains before governance on/off conclusions:

- The CVRP screening instrument is still underpowered for `practical_delta=2.0`:
  Phase 1 MDE is `9.9`, almost 5x larger, and this run still used 4 seeds
  while calibration recommends 8.
- The strongest row had real case clusters but a cross-case median of `0.75`
  or `-1.25` after expansion. This is below both practical delta and MDE.
- Branch depth is still shallow. A 4R run can validate mechanics, not deep
  algorithmic search.
- Runtime feedback remains mostly low/cached for expanded rows; it is now
  correctly excluded from standalone decision, but still needs better proposal
  rendering.
- The report cannot infer "Scion governance is valuable" from this run alone.
  That requires the planned v0.5 governance ablation on an effect-measurable
  problem.

## 8. Conclusion

This is valid Phase 4 evidence.

It supports a narrower and more useful conclusion than "CVRP is ready":

1. The formal CVRP v0.4 run path is now auditable: launch config, copied formal
   config, A/A calibration, replayable patch artifacts, protocol metrics,
   verification, and decisions reconcile.
2. Runtime semantics are materially repaired for budget-exhausting CVRP:
   no fresh replay drain, no runtime promotion leakage, no runtime-only
   optimization claim.
3. The agent can propose and implement real CVRP/ALNS/VNS mechanisms under
   problem-owned surfaces:
   `route_limit_aware_repair` and `double_bridge_relink_vns`.
4. The best research signal is the double-bridge branch: it produced 17/9/6
   pair results initially and 22/19/7 after expansion, with stable wins on
   `A-n64-k9`, `A-n80-k10`, `M-n151-k12`, and `X-n110-k13`.
5. The same evidence also says CVRP quality-improvement readiness is not yet
   sufficient under this protocol: final median `-1.25`, CI `[-5.75, 7.25]`,
   win rate `4/12`, and high CI below MDE `9.9`.

Bottom line:

> Phase 4 shows that v0.4 repairs made CVRP evidence and branch mechanics
> healthier, but the run did not produce promotion-grade or validation-ready
> CVRP quality evidence. CVRP remains a measurement-readiness and runtime
> semantics pressure test, not yet a reliable quality-improvement target under
> 4 seeds / 30-45s screening.

## 9. Recommended Next Actions

1. Do not run another long CVRP quality campaign with the same 4-seed screening
   protocol expecting promotion. The measured MDE/readiness mismatch is still
   present.
2. Run a focused CVRP measurement configuration check with 8 screening seeds
   or a power-adjusted protocol, using the same formal split, before any
   40R+ campaign.
3. Preserve and analyze the `double_bridge_relink_vns` signal as a problem-owned
   research lead, especially the positive cluster on `A-n64-k9`, `A-n80-k10`,
   `M-n151-k12`, and `X-n110-k13`, and the negative cluster on `P-*` / `E-*`.
4. Improve proposal rendering for branch-local history and runtime evidence:
   make the 4W/5L/3T case table and MDE comparison first-class prompt signal,
   not something hidden in branch cards or raw metrics.
5. Keep CVRP/ALNS/VNS semantics inside the CVRP problem package and measurement
   layer. Do not move BKS, MDE, or mechanism-family conclusions into generic
   `DecisionFeatures`.
6. Use warehouse or another effect-measurable problem for governance on/off
   ablation. This CVRP 4R run is not an appropriate governance-value test.

## Appendix A. Files And Commands Used

Primary reference files read:

```bash
sed -n '1,520p' scion/design/scion-architecture-v3.md
sed -n '1,430p' scion/reports/v04-audit-agent-experiment-guide-20260609.md
sed -n '1,520p' scion/reports/v04-core-framework-review-20260611.md
sed -n '1,230p' scion/reports/v04-core-framework-code-review-20260611.md
sed -n '1,460p' scion/design/v0.5-evidence-uplift-roadmap.md
sed -n '1,380p' scion/docs/experiments/v0.4/v04-phase1-aa-calibration-20260611.md
```

Run-artifact inspection commands:

```bash
sed -n '1,240p' <run_root>/launch.env
sed -n '1,220p' <run_root>/run.sh
cat <run_root>/exit.txt <run_root>/run_status.json
jq . <run_root>/campaign/run_status.json
jq . <run_root>/campaign/status.json
jq . <run_root>/campaign/campaign_summary.json
find <run_root>/campaign -maxdepth 3 -type f | sort
sed -n '1,120p' <run_root>/campaign/artifacts/formal_candidates/index.jsonl
```

Config and calibration checks:

```bash
sed -n '1,220p' <run_root>/campaign/champions/champion_v1/formal/protocol.yaml
sed -n '1,220p' <run_root>/campaign/champions/champion_v1/formal/seed_ledger.yaml
sed -n '1,260p' <run_root>/campaign/champions/champion_v1/formal/split_manifest.yaml
jq '{mde:.protocol_power.mde_at_power_80,false_pass:.protocol_power.false_pass_rate_at_current_gate,recommended_min_seeds:.protocol_power.recommended_min_seeds,n_pairs,decision_features_excluded,policy}' \
  <run_root>/campaign/champions/champion_v1/formal/calibration/aa_noise_floor.json
```

Metric and DB extraction used lightweight Python/SQLite queries over:

```text
<run_root>/campaign/metrics/*.json
<run_root>/campaign/scion.db
<run_root>/campaign/artifacts/formal_candidates/*/*/candidate.diff
<run_root>/campaign/agentic_sessions/agentic_session_index.json
<run_root>/campaign/agentic_sessions/agentic_session_trace_index.json
<run_root>/campaign/agentic_sessions/*/scratch/api_visible_prompt_manifest_*.json
<run_root>/campaign/llm_traces/*.json
```

No new experiments were started.
