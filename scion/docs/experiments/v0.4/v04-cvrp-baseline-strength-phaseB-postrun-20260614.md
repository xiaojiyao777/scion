# CVRP Baseline-Strength Phase B Postrun

*Date: 2026-06-14*
*Branch: `codex/v04-evidence-repair-plan`*
*Scope: report-only postrun analysis; no campaign, scheduler, Decision, lifecycle, or promotion state was mutated.*

## V3 Boundary

This analysis follows `scion/design/scion-architecture-v3.md`: LLM output,
prompt/context artifacts, branch lessons, MDE/BKS/headroom facts, VNS telemetry,
and runtime diagnostics are postrun and proposal-diagnostic material only. They
must not enter `DecisionFeatures` and must not become promotion or abandonment
inputs. Formal outcomes remain owned by Contract, Verification, Protocol, safe
feature extraction, and deterministic Decision.

## Artifacts

Pre-registration and launch:

- `scion/docs/planning/v0.4/v0.4-cvrp-baseline-strength-phaseB-20260614.md`
- `scion/docs/experiments/v0.4/v04-cvrp-baseline-strength-phaseB-launch-20260614.md`

Execution roots:

- Server `rep01`:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseB-matched-20260614T024206Z-claw`
- WSL `rep02`/`rep03`:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseB-matched-20260614T024206Z-wsl`
- WSL handoff/status:
  `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z`
- Postrun report-only artifacts:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseB-analysis-20260614`

Phase A calibration anchor:

- `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseA-20260613T171611Z-claw`
- ALNS+VNS A/A MDE: `9.6` raw `total_distance`, recommended seeds `16`
- ALNS-only A/A MDE: `4.65` raw `total_distance`, recommended seeds `8`

## Sync And Completeness

The WSL status file reports `finished_clean_all_four` at
`2026-06-14T16:57:58Z`, with all WSL cells exit `0`, `8/8` effective rounds,
and `failed_pairs=0`. The full WSL group was synced to the server as a separate
`*-wsl` root rather than merged into the server `*-claw` root.

The synced server copy contains `138M` and `6889` regular files. Each WSL cell
has `run_status.json`, `campaign/campaign_summary.json`, `campaign/scion.db`,
agentic session artifacts, and `artifacts/formal_candidates/index.jsonl`.

Caveats:

- The server `*-claw` root contains rep02/rep03 placeholder directories from
  the original sequential matrix setup. The accepted matrix uses only server
  `rep01` plus WSL `rep02`/`rep03`.
- WSL artifacts still contain WSL-origin absolute paths under
  `/home/xjy-ubuntu/...`; local replay on the server would need path remapping.
- `artifacts/formal_candidates/index.jsonl` is the replayable patch subset, not
  the complete 8-row protocol event list. Protocol rows are in
  `campaign_summary.json` and `campaign/scion.db`.
- `rep01` ran before the WSL data-root fallback commit and `rep02`/`rep03` ran
  from `2a7e1e4`. Each repeat is internally matched across baselines, but the
  full 3-repeat matrix is not a single-commit execution.

## Cell Outcomes

All six accepted cells are valid and complete. All formal evidence remained in
screening; no validation row, frozen row, promotion, fresh-runtime replay, infra
failure, non-infra failure, telemetry failed experiment, or failed pair occurred.

| Cell | Baseline | Formal Artifacts / Unique Hypotheses | Protocol Rows | Screening E/C/A/Q | Validation / Frozen / Promotion |
|---|---|---:|---:|---:|---:|
| server rep01 | `alns_vns` | 4 / 4 | 8/8 | 4 / 3 / 1 / 0 | 0 / 0 / 0 |
| server rep01 | `alns_only` | 4 / 4 | 8/8 | 4 / 4 / 0 / 0 | 0 / 0 / 0 |
| WSL rep02 | `alns_vns` | 6 / 6 | 8/8 | 2 / 4 / 2 / 0 | 0 / 0 / 0 |
| WSL rep02 | `alns_only` | 5 / 5 | 8/8 | 3 / 3 / 1 / 1 | 0 / 0 / 0 |
| WSL rep03 | `alns_vns` | 8 / 8 | 8/8 | 0 / 5 / 3 / 0 | 0 / 0 / 0 |
| WSL rep03 | `alns_only` | 6 / 6 | 8/8 | 2 / 1 / 5 / 0 | 0 / 0 / 0 |

`E/C/A/Q` means `expand_screening`, `continue_explore`, `abandon`, and
`queue_validate`.

## Baseline Comparison

Across three repeats per baseline:

| Baseline | Rows | E/C/A/Q | Case W/L/T | Case-Row +/-/= | Pair W/L/T | Pair-Row +/-/= | Median Delta +/0/- | Rows With CI Low > 0 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `alns_vns` | 24 | 6/12/6/0 | 45/51/128 | 5/8/11 | 513/548/731 | 8/14/2 | 4/18/2 | 0 |
| `alns_only` | 24 | 9/8/6/1 | 47/36/149 | 10/6/8 | 508/334/1014 | 15/7/2 | 7/15/2 | 1 |

The ALNS-only surface produced stronger research signals than the ALNS+VNS
surface in this matrix, but not a validated improvement:

- ALNS-only had the only `SCREENING_PASS -> queue_validate` row.
- ALNS-only had more case-row and pair-row positive evidence.
- ALNS-only had the only row whose CI lower bound was positive.
- Neither baseline reached validation/frozen under the 8-round budget.

The strongest row was WSL `rep02/alns_only`, branch
`dd95dbf3-4c84-40b5-be54-5ab5aa5de348`
(`route_count_aware_repair_selection`):

- Decision: `queue_validate`
- Case-level gate W/L/T: `5/1/2`
- Pair W/L/T: `46/12/6`
- Median delta: `16.75`
- CI: `[3.25, 36.5]`
- MDE interpretation: `16.75 > 4.65` ALNS-only Phase A MDE

This is evidence that the ALNS-only research surface can expose a measurable
candidate signal. It is not promotion evidence because no validation/frozen row
was executed. The `queue_validate` row occurred as the last protocol row, so
`max_rounds_exhausted` stopped the cell before validation could run.

For ALNS+VNS, the best final screening median delta was `0.75`, far below the
ALNS+VNS MDE `9.6`. The strong ALNS+VNS baseline still appears too low-headroom
for the current 8-round, screening-first CVRP campaign to produce formal
acceptance evidence.

## Branch Research

Eight rounds were not enough to fully evaluate branch-local depth. Screening
expand consumes extra protocol rows, so one or two active branches can exhaust
the whole budget before validation or deeper within-branch iteration occurs.

Branch summary:

| Baseline | Branches | Active At Stop | Abandoned | Max Depth | Mean Depth | Unique Hypotheses | Formal Artifacts |
|---|---:|---:|---:|---:|---:|---:|---:|
| `alns_vns` | 9 | 3 | 6 | 5 | 2.67 | 18 | 18 |
| `alns_only` | 10 | 4 | 6 | 6 | 2.50 | 15 | 15 |

Notable branch patterns:

- `alns_only` rep01 `route_preserving_repair_bias` reached depth `6`, three
  unique hypotheses, and repeated marginal pair/case signal, but stayed in
  screening.
- `alns_only` rep02 `route_count_aware_repair_selection` reached
  `ready_validate` / `queue_validate` at the final row and was censored by the
  round budget.
- `alns_vns` rep03 `cross_route_2opt_reconnect` reached a four-hypothesis
  same-mechanism chain, but final evidence regressed and the branch was
  abandoned.
- Multiple cells ended with active weak/marginal branches. These are censored
  research states, not hard mechanism failures.

Therefore, `validation=0` is not by itself a failure diagnosis. In this matrix
it means the current screening-first budget and gate policy did not leave enough
room to verify active or borderline research signals.

## Prompt And Context

The launched context arm was `compact-measurement-diagnostics` in all six
cells. Report-only proposal trajectory manifests were generated under:

`/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseB-analysis-20260614/postrun_acceptance/proposal_trajectory_manifests`

They confirm:

- `raw_prompt_excluded=true`
- `raw_response_excluded=true`
- `patch_body_excluded=true`
- `decision_features_excluded=true`
- `proposal_context_ablation=compact-measurement-diagnostics`

The compact measurement mode worked in the sense that standalone measurement
diagnostics were not rendered as a large hypothesis prompt section. However,
the prompt-density problem remains:

- In hypothesis prompts, average token share was approximately:
  `source_context 22.0%`, `active_facts 20.0%`, `general 17.5%`,
  `tool_observation 15.3%`, `research_signal 15.0%`,
  `feedback 5.5%`, `governance 4.7%`.
- `compact_research_signals` was present but truncated in all sampled
  hypothesis prompts.
- `branch_lesson_usage_context` was truncated in most hypothesis prompts.
- `experiment_history_this_branch` was effectively negligible.
- The large remaining space consumers are not only governance rules; they are
  repeated solver/source maps, active facts, tool observations, and code-stage
  general instructions.

Code-stage source visibility did hold:

- 33 code manifests were inspected.
- 30 modify-target prompts had full target source visible.
- 3 create-new prompts correctly had no prior target body.
- No code manifest missed the required protected source guarantee.

This means context compression did not hide the direct research object code in
Phase B. The remaining weakness is that champion/current/target identity is not
prominent enough when the branch workspace has diverged from champion source.

## Interpretation

Phase B answers three questions:

1. **Were WSL results synced and usable?** Yes. The synced WSL group is complete
   and all four WSL cells are valid 8/8 runs.
2. **Does ALNS-only improve the CVRP research surface?** Partially. ALNS-only
   produced the only validation-ready signal and more positive pair/case rows,
   but the result is not stable enough to replace ALNS+VNS or claim production
   solver quality.
3. **Is 8 rounds enough to judge branch-local deep research?** No. At least one
   validation-ready candidate was cut off by `max_rounds_exhausted`, and several
   weak/marginal branches remained active at the end.

## Phase B Closeout Decision

Accepted as valid Phase B research-surface evidence, not as a promotion result
and not as a final CVRP governance-value conclusion.

The evidence supports two v0.4 follow-ups before broad v0.5 experimentation:

1. Add a CVRP staged gate policy: high-recall screening, diagnostic validation
   for borderline but measurable pair-level signal, and stricter validation /
   frozen gates for promotion.
2. Pre-register a longer CVRP follow-up, preferably 12 or 16 rounds, treating
   active branches at round exhaustion as censored rather than failed. The
   follow-up should either run after the staged gate repair or explicitly test
   the old vs repaired gate policy.

The long-run experiment should preserve:

- Same champion snapshots and baseline labels.
- Same formal split/seeds/protocol-time runtime policy unless pre-registered.
- Same model and provider settings.
- `measurement_governance=on`.
- `compact-measurement-diagnostics` or a repaired compact context that protects
  branch lessons and compact research signals from truncation.
- Postrun analysis by branch depth, same-mechanism parent-chain length,
  validation/frozen reach, pair-level signal, failure taxonomy, prompt/context
  visibility, and MDE interpretation.

The ALNS-only arm remains a copied research-surface ablation. Any future
ALNS-only promotion must be interpreted against its weaker baseline and lower
MDE, not as a win over the canonical ALNS+VNS champion.
