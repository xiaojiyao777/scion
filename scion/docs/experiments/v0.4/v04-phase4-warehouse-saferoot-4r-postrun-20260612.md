# Scion v0.4 Phase 4 Warehouse Saferoot 4R Postrun Audit

Date: 2026-06-12

Run root:
`/home/clawd/research/scion-experiments/v04-phase4-focused-warehouse-saferoot-20260611-4r-gpt55-20260612T000035Z-claw`

Repository checkout:
`/home/clawd/research/or-autoresearch-agent`

Branch observed during audit: `codex/v04-evidence-repair-plan`

Commit recorded by launcher: `63f01d7`

Model recorded by launcher and LLM traces: `gpt-5.5`

## 1. Governing boundary

This audit uses `scion/design/scion-architecture-v3.md` as the architectural
source of truth.

The v3 boundary matters for this run:

- LLM hypothesis/code output is tainted proposal material.
- The evidence path is Contract -> Verification -> Protocol -> Decision.
- Decision may consume only structured `DecisionFeatures`, not free text.
- Warehouse facts such as A/A MDE, case readiness, objective deltas, and branch
  lessons are problem-owned diagnostics and proposal guidance. They must not be
  promoted into generic core decision features.
- This report therefore separates proposal/context observations from
  deterministic evidence and decision outcomes.

The required reference reports were read from their actual paths:

- `scion/reports/v04-audit-agent-experiment-guide-20260609.md`
- `scion/reports/v04-core-framework-review-20260611.md`
- `scion/reports/v04-core-framework-code-review-20260611.md`
- `scion/design/v0.5-evidence-uplift-roadmap.md`

Those reports frame this audit: v0.4 core boundaries were previously found
healthy, warehouse is the contrast case where the loop can produce evidence, and
v0.5 should focus on evidence uplift and controlled comparisons rather than
adding warehouse-specific semantics to generic core.

## 2. Run status and effective launch configuration

Wrapper and Scion run status are valid.

- `exit.txt`: `WRAPPER_EXIT_STATUS:0`, `CAMPAIGN_EXIT_STATUS:complete`,
  `RUN_VALIDITY_STATUS:valid`, `COMPLETED_REQUESTED_ROUNDS:True`,
  `LAST_STOP_REASON:max_rounds_exhausted`.
- `campaign/run_status.json`: `wrapper_exit_status=0`,
  `run_validity_status=valid`, `run_completeness_status=complete`,
  started `2026-06-12T00:00:43Z`, ended `2026-06-12T00:17:01Z`.
- `campaign/campaign_summary.json`: `stopped_reason=max_rounds_exhausted`,
  `champion_version=1`, `promotion_dossier_ref=null`.

The launcher resolved the run as:

- repo root: `/home/clawd/research/or-autoresearch-agent`
- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion`
- problem: `scion/problems/warehouse_delivery/problem.yaml`
- protocol: `scion/problems/warehouse_delivery/protocol_prod.yaml`
- split: `scion/problems/warehouse_delivery/split_manifest_prod.yaml`
- seeds: `scion/problems/warehouse_delivery/seed_ledger.yaml`
- rounds: `4`
- time limit: `30` seconds
- agentic session timeout: `900` seconds
- flags: `--disable-early-stop --agentic-proposal`

The formal replay identities recorded launch-time hashes:

- `problem_spec_hash=138b08aaae36da5adea3b610c8dc8e4f77d0f84a7dc53511d7eabcbd8f0545fa`
- `split_manifest_hash=c1d77b2b7ff729a863fe8162f7e38c5db544b2aab1cf6ec3ffc07aef85718d8b`
- `seed_ledger_hash=85a894693ad6eaad3f497dbac232522b41237544e9b9a40ad635d4efc4bb8ca3`
- `protocol_version=3.1-prod`

Important audit boundary: raw file SHA256 values in the current repository are
not identical to those formal replay identity hashes. The replay identity hashes
are generated from Scion's normalized problem/protocol artifacts, while the
following values are direct file-content hashes taken during audit:

- `problem.yaml`: `01359d67fa32e9c13a0cf7850403312cc65fc70d5c0f107fece48e273c1c8792`
- `protocol_prod.yaml`: `27ad59189a570f980994740dbd0064cb24009d15263fcafbcbfc70ab04fb4c71`
- `split_manifest_prod.yaml`: `e30d60236dd832bc552f14a4e4943654cfc654c18e5f839c2e29948ba556240a`
- `seed_ledger.yaml`: `5eca3cbeafcac1e8f0b98539f7b5022bd7ad074ec0bd8c47596edb7fbaaebb15`

So this audit treats `launch.env`, `run.sh`, metric files, DB rows, and formal
candidate replay identities as authoritative for the completed run. Current
source files are useful for human interpretation, but raw file hashes are not a
substitute for the normalized replay identities.

## 3. Count reconciliation

The headline counters are internally consistent once the fresh-runtime replay
closure is separated from formal candidates.

Campaign summary:

- `proposal_attempts=4`
- `proposal_attempts_consumed=4`
- `campaign_steps=4`
- `effective_rounds_completed=4`
- `counted_experiment_steps=4`
- `screened_rounds=5`
- `screened_experiments=5`
- `validation_protocol_results=0`
- `frozen_protocol_results=0`
- `promotion_dossier_ref=null`

Evidence scope reconciliation:

- `step_history_total=5`
- `protocol_step_count=5`
- `screening_protocol_step_count=5`
- `non_counted_step_count=1`
- `cross_branch_observable_step_count=4`

Formal candidate artifacts:

- `campaign/artifacts/formal_candidates/index.jsonl` has 4 rows.
- All 4 rows have `artifact_status=recorded`.
- All 4 rows have `replay_identity_status=complete`.
- The 4 formal candidates point to 4 distinct metric files:
  `258843de...`, `dd1d6430...`, `150eb4df...`, and `41ca9ad3...`.

The fifth screening protocol row is `metrics/e224e302...`, a non-counted
fresh-runtime replay closure for hypothesis `cc12fa9f...`. It has no new formal
candidate artifact and is marked in branch state as:

- `queue_intent=fresh_champion_runtime_replay`
- `counts_toward_max_rounds=false`
- `decision_features_excluded=true`
- `closure_status=fresh_evidence_recorded`

Decision rows reconcile as:

- 3 counted `continue_explore` decisions for the main branch.
- 1 counted `abandon` decision for the clean fork branch.
- 1 non-counted replay `continue_explore` closure.

No candidate reached validation or frozen because every counted candidate failed
screening.

## 4. Candidate evidence

All 4 formal candidates passed Contract and Verification according to
`experiment_events`; there were no verification failures in
`campaign_summary.verification_failure_breakdown`.

| Counted row | Branch | Hypothesis | Surface | Stage | Case W/L/T | Median delta | CI | Decision |
|---|---|---|---|---|---:|---:|---|---|
| 1 | `096e2acc` | `3a5b36cc` | create `operators/consolidate_subcategory.py` | screening | 2/2/6 of 10 | 50 | [-625, 700] | `continue_explore` |
| 2 | `096e2acc` | `4d0fddb3` | modify `operators/consolidate_subcategory.py` | screening | 0/0/6 of 6 | 0 | [0, 0] | `continue_explore` |
| 3 | `096e2acc` | `cc12fa9f` | modify `operators/consolidate_subcategory.py` | screening | 0/0/6 of 6 | 0 | [0, 0] | `continue_explore` with fresh runtime required |
| 4 | `8b939989` | `1de14ec0` | modify `operators/move_order.py` | screening | 1/3/2 of 6 | -125 | [-3000, 300] | `abandon` |

Fresh-runtime replay:

| Non-counted row | Branch | Hypothesis | Metric | Case W/L/T | Median delta | Decision |
|---|---|---|---|---:|---:|---|
| replay closure | `096e2acc` | `cc12fa9f` | `e224e302...` | 0/0/6 | 0 | `continue_explore`, replay closure |

Metric details:

- Candidate 1 generated real but weak objective signal. Pair-level deltas were
  mixed: positive on `instance_prod_scr_m03` and `instance_prod_scr_ms03`,
  negative on `instance_prod_scr_ml02` and `instance_prod_scr_s04`, mixed on
  several cases, and tied on micro cases. Case gate result was only 2 wins, 2
  losses, 6 ties.
- Candidate 2 had all six case-level ties and used cached champion evidence for
  most pairs. Runtime evidence was low/cached but sufficient for proposal
  guidance only.
- Candidate 3 had all six case-level ties and triggered
  `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED` because all champion runtime pairs were
  cached. Its formal metrics had runtime aggregate excluded; the replay reran
  fresh champion evidence and closed the diagnostic without changing the
  objective result.
- Candidate 4 was a clean fork with negative objective signal: one case win
  (`instance_prod_scr_s03`), three case losses (`instance_prod_scr_ms02`,
  `instance_prod_scr_m03`, `instance_prod_scr_ml02`), and two ties.

Warehouse A/A readiness:

The copied champion workspace includes
`champion_v1/calibration/aa_noise_floor.json`, marked
`decision_features_excluded=true`. It reports:

- measurement metric: `total_cost`
- unit: `raw_delta`
- stage: screening
- modify calibration MDE at 80 percent power: `577.5`
- related create-new MDE at 80 percent power: `1725.0`
- false pass rate at current gate: `0.0`

By that problem-owned readiness diagnostic, this run produced no candidate with
screening evidence ready for validation:

- Candidate 1 median delta was only `50`, below the modify MDE, and CI crossed
  zero.
- Candidate 2 and 3 had zero objective effect.
- Candidate 4 had negative median delta.

This is a valid no-promotion outcome, not a missing promotion.

## 5. Runtime evidence and fresh replay

Runtime evidence stayed outside DecisionFeatures, which is the correct v3
boundary.

Campaign summary runtime policy counts:

- `fresh_champion_required_count=1`
- `runtime_aggregate_excluded_count=1`
- `low_cached_champion_count=2`
- `runtime_budget_diagnostic_count=0`
- `decision_features_excluded_count=5`

The fresh replay was useful as an audit closure because it converted the current
head from cached/low-confidence runtime evidence into sufficient fresh evidence.
It was also noisy for campaign-level research accounting because it added a
fifth screening row after the requested 4 counted rounds, while contributing no
new formal candidate, no validation readiness, and no objective signal.

For Phase 5 governance design, this supports a narrow conclusion:

- Keep fresh-runtime replay as an audit/provenance repair path when runtime is
  truly part of the claim.
- Do not let fresh-runtime replay create ambiguity in requested-round counters.
- If the research claim is objective quality and runtime is only supporting
  tie-break evidence, a replay closure should be clearly out-of-band and should
  not be interpreted as a fifth candidate.
- This should remain generic runtime-governance behavior, not warehouse-specific
  core logic.

## 6. Branch-level research shape

The run explored two branches.

`campaign_summary.cross_branch_research_observability.research_shape_diagnostics`:

- branch depth distribution: `{1: 1, 4: 1}`
- max branch depth: `4`
- mean branch depth: `2.5`
- mechanism family breadth:
  - `consolidate_subcategory`: 5 observed rows including the replay closure and
    branch lessons
  - `split_neutral_evacuation`: 2 observed rows

Main branch `096e2acc`:

- Started as a clean fork because a new exploration slot was available.
- Created `ConsolidateSubcategory`, then followed the same mechanism twice.
- It used earlier evidence: the second hypothesis made accepted moves
  cost-nonworsening after the first candidate showed mixed cost deltas; the
  third hypothesis added a cost-aware bounded trigger after the second candidate
  collapsed to ties and had runtime evidence pressure.
- Best checkpoint was retained:
  `b2ea5b06-a82a-4499-8a50-486ac6facbb6`, with 2/2/6 and median delta 50.
- The current head was later parked after repeated zero-effect evidence:
  `BRANCH_LIFECYCLE_PARK_LINEAGE` and
  `SCREENING_NO_EFFECT_FOLLOWUP_EXHAUSTED`.
- Clean fork became required after lifecycle policy blocked further same-lineage
  consumption.

Clean fork branch `8b939989`:

- Opened after the main branch parked.
- Switched mechanism to order-level `split_neutral_evacuation` in
  `operators/move_order.py`.
- This was materially different from the vehicle-level consolidation line.
- It was abandoned after a loss-heavy screening result:
  `SCREENING_FAIL_WIN_RATE`,
  `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`,
  `SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP`,
  `SCREENING_SOFT_ABANDON_NEGATIVE_DELTA`.

The branch behavior matches v3's branch-governance intent more closely than the
earlier shallow CVRP runs: the system gave one mechanism a depth-4 same-branch
line before clean forking. The outcome says the specific consolidation line did
not survive screening under this production warehouse protocol; it does not say
warehouse research is exhausted.

## 7. Prompt and LLM context audit

The LLM sessions are tainted and are not decision evidence. They are still useful
to audit whether the agent had enough research context to propose meaningful
changes.

Session index:

- 8 hypothesis calls, 4 completed code calls, 14 tool-selection calls.
- 26 total LLM traces.
- total input tokens: `352964`
- total output tokens: `18531`
- total tokens: `371495`
- model counts: `gpt-5.5: 26`
- no proposal quality blocks and no code retry failures.

Hypothesis prompt manifests showed reasonable visibility:

- Sections included problem summary, research surfaces, objective policy,
  solver execution model, champion state/code, compact research signals,
  cross-branch research map, branch lesson usage context, measurement
  diagnostics, runtime feedback, experiment history, sibling branches, and tool
  observations.
- Raw prompts were not saved, but rendered prompt manifests were available.
- First hypothesis manifest:
  - total chars `41823`
  - research signal chars `11194`
  - governance chars `3537`
  - tool observation chars `4031`
  - only `compact_research_signals` truncated
- Later same-mechanism repair hypothesis manifests grew to `70760` and `90281`
  chars, adding branch code/status, recent objective feedback, objective
  opportunity profile, runtime feedback, and feedback-grounding sections.
- The clean-fork hypothesis manifest was `76074` chars and included
  `material_difference_requirement`, with that requirement visible once.

This is not a log-pile failure. Governance was present but not dominant in the
sampled hypothesis manifests; research signal plus feedback dominated governance
after branch evidence existed. Measurement/readiness and branch history were
visible as proposal guidance, and the model's follow-ups reflected earlier
screening evidence.

Code prompt manifests:

- The create-new `ConsolidateSubcategory` code prompt had a new-file placeholder
  for `operators/consolidate_subcategory.py`; for a create action, this is
  expected, though the source visibility ledger labels `target_file_create_mode`
  as false and `missing_required_source_paths` as the new file. That is a
  manifest clarity issue, not a demonstrated decision failure.
- The modify `ConsolidateSubcategory` code prompt had full current target source
  visible.
- The modify `MoveOrder` code prompt had full target source visible.

The prompt layer therefore looked adequate for Phase 4 evidence: it exposed the
right problem mechanics, source, branch-local evidence, measurement diagnostics,
and cross-branch context. The main limitation was not missing context; it was
that the measured candidates did not clear the problem-owned readiness and
screening gates.

## 8. Framework issues vs problem/research issues

Framework behavior that looks healthy:

- Contract and Verification passed for all 4 formal candidates.
- Formal replay identity was complete for all 4 candidate artifacts.
- Decision outcomes were deterministic and tied to structured screening
  features and reason codes.
- Runtime evidence policy explicitly marked runtime as proposal/audit guidance
  and excluded it from DecisionFeatures.
- Cross-branch research observability was marked advisory-only and excluded
  from DecisionFeatures.

Framework/observability issues worth fixing:

1. Fresh-runtime replay should be displayed more clearly in top-level counters.
   A non-counted replay closure is useful evidence hygiene, but it makes
   `screened_rounds=5` easy to misread as five candidates. This is a generic
   observability issue.
2. Code prompt source-visibility manifests should distinguish create-new
   placeholders from missing required target source. This is a prompt audit
   clarity issue.
3. Effective human-readable run configuration should be easier to inspect from a
   compact run config snapshot. Formal replay identity hashes are sufficient for
   replay, but auditors still need launch/config views that explain the
   normalized hashes without requiring a manual cross-walk through traces and
   metrics.

Problem/research issues:

1. This 4R run did not find a warehouse improvement above A/A readiness.
2. The dominant same-mechanism line had one weak mixed signal, then two
   zero-effect follow-ups.
3. The clean fork was materially different but negative.
4. No validation or frozen evidence was attempted because screening did its job.

No issue found here requires putting warehouse semantics into generic core.
Warehouse measurement diagnostics can remain problem-owned inputs to protocol
configuration, campaign readiness, and proposal context.

## 9. Phase 4 evidence conclusion

This is valid Phase 4 evidence.

It establishes:

- The Phase 4 warehouse saferoot launcher and wrapper produced a complete valid
  run.
- The production warehouse protocol/split/seeds path is replayable at the formal
  candidate level.
- The v3 evidence path worked for a no-promotion result: tainted proposals were
  gated by Contract/Verification, measured by Protocol, reduced to structured
  decision features, and deterministically rejected or continued.
- The run tested 4 formal candidate artifacts and one non-counted fresh-runtime
  closure.
- No candidate was ready for validation or promotion.

It does not establish:

- That warehouse research is globally exhausted.
- That the generic core should include warehouse-specific decision features.
- That fresh-runtime replay should count as a requested research round.
- That the Phase 4 warehouse measurement stack is broken.

The substantive research result is narrower: under this 4R, 30s, production
warehouse protocol, `consolidate_subcategory` did not produce robust evidence
above A/A readiness, and `split_neutral_evacuation` regressed.

## 10. Recommended next steps for the main session

1. Treat this run as a valid no-promotion Phase 4 artifact and include it in the
   closeout evidence set.
2. Keep the v3 boundary intact: use warehouse A/A/readiness only as
   problem-owned diagnostics and proposal guidance.
3. For the next warehouse run, do not spend Phase 5 design energy on making
   fresh-runtime replay a first-class research branch. Keep it as out-of-band
   evidence hygiene.
4. If the goal is to produce a warehouse promotion, run a longer focused
   campaign with the same saferoot setup but broaden mechanism families beyond
   subcategory consolidation after one weak/zero-effect lineage parks.
5. For v0.4 closeout, improve counter/report rendering so summaries separate
   formal candidates, counted protocol rows, and replay closure rows.
6. For Phase 5, use this run as one data point in the planned evidence uplift
   matrix: valid replay, healthy boundaries, no promotion, and a clear example
   of why controlled repetition matters more than adding governance features.

## 11. Commands run during audit

Representative lightweight commands:

```bash
sed -n '1,920p' scion/design/scion-architecture-v3.md
sed -n '1,620p' scion/reports/v04-audit-agent-experiment-guide-20260609.md
sed -n '1,620p' scion/reports/v04-core-framework-review-20260611.md
sed -n '1,620p' scion/reports/v04-core-framework-code-review-20260611.md
sed -n '1,320p' scion/design/v0.5-evidence-uplift-roadmap.md
sed -n '1,220p' <run_root>/launch.env
sed -n '1,220p' <run_root>/run.sh
jq . <run_root>/campaign/run_status.json
jq . <run_root>/campaign/campaign_summary.json
jq . <run_root>/campaign/status.json
sqlite3 <run_root>/campaign/scion.db '.tables'
sqlite3 <run_root>/campaign/scion.db 'select ... from hypotheses'
sqlite3 <run_root>/campaign/scion.db 'select ... from experiment_events'
sed -n '1,20p' <run_root>/campaign/artifacts/formal_candidates/index.jsonl
jq . <run_root>/campaign/champions/champion_v1/calibration/aa_noise_floor.json
jq ... <run_root>/campaign/metrics/*.json
jq ... <run_root>/campaign/agentic_sessions/*/scratch/api_visible_prompt_manifest*.json
sha256sum scion/problems/warehouse_delivery/{problem.yaml,protocol_prod.yaml,split_manifest_prod.yaml,seed_ledger.yaml}
git status --short
git branch --show-current
```

No long experiments were launched.
