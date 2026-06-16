# Scion v0.4 Warehouse Longrun Rep02 Branch Analysis - 2026-06-16

## Boundary

This report preserves the Scion v3 boundary from
`/home/clawd/research/or-autoresearch-agent/scion/design/scion-architecture-v3.md`.
Prompt, context, transcript, branch-card, branch-lesson, and LLM output
artifacts are report-only explanatory material. They are useful for diagnosing
research quality and information transfer, but they are not Decision inputs.
Promotion interpretation below is based on deterministic Contract,
Verification, Protocol, and DecisionFeatures-derived outputs persisted by the
campaign.

Scope is limited to rep02:

- Cell root:
  `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep02/on_compact`
- Campaign DB:
  `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep02/on_compact/campaign/scion.db`
- Campaign summary:
  `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep02/on_compact/campaign/campaign_summary.json`
- Agentic session index:
  `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep02/on_compact/campaign/agentic_sessions/agentic_session_index.json`
- Agentic trace index:
  `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep02/on_compact/campaign/agentic_sessions/agentic_session_trace_index.json`
- Postrun:
  `/home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/v04-warehouse-longrun-regression-3x24r-postrun-20260616.md`
- Acceptance artifacts:
  `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/postrun_acceptance/`

No source code was modified for this analysis.

## Cell Summary

Rep02 was a valid 24-round campaign, not a launch or pre-Protocol failure.
`postrun_acceptance/research_efficiency/rep02_on_compact.research_efficiency.v1.json`
reports:

- `campaign_exit_status=complete`
- `run_validity.status=valid`
- `requested_rounds=24`
- `effective_rounds_completed=24`
- `protocol_metric_results=24`
- stage rows: `screening=21`, `validation=2`, `frozen=1`,
  `fresh_runtime_replay=0`
- final champion stayed `v1`; `champion_promotions=0`

The decisive branch was `345a246c-3d1e-4eb4-aede-dcf1eec27af7`,
hypothesis `497f5537-d6da-48fa-9ffb-05e6a194417c`, target
`operators/swap_orders.py`, mechanism `slack_balanced_swap`. It reached
frozen and then failed:

- screening: `4/1/1` case W/L/T, case win rate `0.6667`, median delta `450`,
  CI `[-600, 1825]`, decision `queue_validate`, metric
  `campaign/metrics/8b47b9a2-f97c-46a4-9b72-941149084c9f.json`
- validation first run: metric
  `campaign/metrics/f47bc81c-298e-4cce-9640-dddd6dc28da9.json`,
  pair W/L `9/6`, median delta `0`, CI `[0, 1]`, high fresh runtime,
  decision `expand_validation`
- validation expanded/exhausted run: metric
  `campaign/metrics/932a742e-09fd-4096-9508-3442d6ecf333.json`,
  same pair W/L `9/6`, median delta `0`, CI `[0, 1]`, low cached champion
  runtime, decision `queue_frozen`
- frozen: metric
  `campaign/metrics/773eb845-c6d5-44d7-af4d-4835f363fbc0.json`,
  pair W/L `6/6`, median delta `-400`, CI `[-4100, 3500]`,
  pair sum delta `-2300`, runtime confidence `high`, decision `abandon`,
  reason `FROZEN_PROTOCOL_GATE_NOT_PASS`

The frozen failure was therefore a real objective-gate failure on fresh
champion evidence, not a cached-runtime artifact. Runtime was favorable for
the candidate at frozen (`runtime_ratio_median=0.904`, regression rate `0.0`),
but v3/v0.4 correctly treats runtime as a supporting/tie-break signal, not as
promotion evidence when the objective gate fails.

Research efficiency was poor. The run consumed `38` proposal attempts for
`24` Protocol metric rows. `14` attempts were pre-Protocol proposal-quality
blocks, all in the `branch_lesson_usage_*` family. Two code generation
attempts failed with `old_string_not_found in operators/merge_vehicles.py`.
No heavy verification failures, tool timeouts, or fatal acceptance failures
were reported for rep02.

## Branch Evolution Map

The branch path below is reconstructed from `branches`, `hypotheses`, and
`experiment_events` in `campaign/scion.db`, plus final branch cards in
`campaign_summary.json`.

### Branch `e0b22a0b-0ca9-464f-bef7-2e8182b1b123`

Direction: vehicle-level `subcategory_bucket_repack` via
`operators/subcategory_consolidate.py`.

Terminal state: `parked_lineage`, next action `clean_fork`.
Final current-head evidence was no-effect: `0/0/6` case W/L/T, median delta
`0`, CI `[0, 0]`, runtime confidence `low_cached_champion`, fresh runtime
required.

Evolution:

| Step | Hypothesis/session | Action and target | Mechanism | Stage/gate | Outcome |
|---|---|---|---|---|---|
| 1 | `919fa7c7-a175-4f06-b5a9-63c8ba86b4aa` then `8c9cea99-ff8d-4ae0-8aca-305051dcf1a4`; hyp `1e0e3dfa-d6cc-478b-b0b4-da2d1967ea4a` | create `operators/subcategory_consolidate.py` | `subcategory_bucket_repack` | screening | initial `5/1/4`, md `475`, CI `[0,1200]`, decision `expand_screening`, metric `5ebb6039-2963-4f76-b49a-5deb05332cdf.json`; expanded `6/2/8`, md `25`, CI `[-100,600]`, decision `continue_explore`, metric `d639f93e-1c1a-4c71-b55f-2dd0e396f7c6.json` |
| 2 | `0874e8ce-dba7-418d-bbc9-2ba6a0e83bb6`; hyp `1efff80d-0f97-4d8c-8739-7661870245ee` | modify same file | same mechanism | proposal | quality block at loop step 3, `branch_lesson_usage_semantic_mismatch`, missing `target_file,action` linkage; no Protocol metric |
| 3 | `11071bc7-c828-408c-ba0d-db92a2a375f0` then `62b50863-e3e3-4485-adeb-cf9841a8cb62`; hyp `568180e2-bda5-4384-85a1-752faed6a721` | modify same file | same mechanism | screening | `0/0/6`, all ties, md `0`, decision `continue_explore`, reason `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`, metric `b79a90f9-6e0c-40c6-bf65-65cbf2f2dae6.json` |
| 4 | `e03d877c-f07b-4e2d-9f9a-fa75aeeeceda` then `3f832845-a694-40bd-9ea7-6e1c295c2684`; hyp `cb7a0929-36ba-4fd2-95e2-f3f534740196` | modify same file | same mechanism | screening | `0/0/6`, all ties, md `0`, decision `continue_explore`, reason `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`, metric `594863bd-d6f0-420a-a4e1-6630fdfa2eab.json` |

Classification: same-mechanism depth after an initial weak/marginal signal.
The first candidate had some case-level signal but failed expanded screening.
Later same-mechanism refinements became all-tie no-effect loops under cached
champion runtime. Branch lessons were present in sessions, but the first
refinement was blocked because the structured lesson linkage was not semantic
enough for the quality gate. The branch was later parked by active-slot
reclaim after its current head was no-effect.

Agent context/output evidence:

- Session `919fa7c7...` hypothesis prompt traces
  `20260616T153101289151_hypothesis_d6e612600f_0a69c0d0` and
  `20260616T153131343329_hypothesis_f8335e28ca_b05faa8a` had
  `compact_research_signals` truncated; research-signal token shares were
  only `0.224` and `0.172`. Output proposed creating a bounded bucket repack
  operator.
- Code session `8c9cea99...` completed and produced the candidate patch.
  Its code prompt was mostly generic context (`general` token share `0.925`).
- Quality block ledger sequence `1`, loop step `3`, recorded
  `2026-06-16T15:37:19.618428`, says the same-branch/sibling proposal used
  branch_lesson_usage but missed `target_file,action` linkage for
  `operators/subcategory_consolidate.py/modify/subcategory_bucket_repack`.

Interpretation: this branch shows branch-local depth, but the depth did not
become semantic learning. The branch retained the mechanism name, yet later
outputs either failed lesson-linkage validation or produced no objective
effect. Fresh-runtime pressure was noted, but the actual screening signals
after expansion were too weak to justify validation.

### Branch `86efd5b6-b97c-4f60-b5f6-e13098816487`

Direction: order-level replacement of `operators/move_order.py` with
`evacuate_low_fill_vehicle`.

Terminal state: `abandoned`, code status `discarded`.

Evolution:

| Step | Hypothesis/session | Action and target | Mechanism | Stage/gate | Outcome |
|---|---|---|---|---|---|
| 1 | `bc0c9e4b-d84e-436a-8087-2507cfb87520` then `e65becd3-9990-4299-b470-dff76d9df584`; hyp `238fe186-d9a9-4763-a72a-99841113703a` | modify `operators/move_order.py` | `evacuate_low_fill_vehicle` | screening | `0/1/5`, md `0`, CI `[-1625,800]`, decision `abandon`, reason `SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN`, metric `bc0304ed-13c1-438d-ad7d-600b9696100e.json` |

Classification: clean fork from earlier vehicle-level bucket repack. It tried
an order-level evacuation mechanism. Branch lessons were present semantically
in the proposal manifest, but the mechanism did not transfer into useful
evidence.

Agent context/output evidence:

- Hypothesis session `bc0c9e4...` had compact research signals truncated,
  research-signal shares `0.415/0.357`, and proposed replacing random
  `MoveOrder` with bounded low-fill vehicle evacuation.
- Code session `e65becd3...` completed. Its code prompt was mostly generic
  context (`general` token share `0.872`).

Interpretation: not a measurement-noise casualty. It had high runtime
confidence in the metric file, but objective evidence had no case wins and one
case loss. The deterministic abandon was appropriate.

### Branch `603928ba-7c8e-4091-8e3b-3ce030ef0c2b`

Direction: vehicle-level `guarded_cost_merge` in
`operators/merge_vehicles.py`.

Terminal state: `abandoned`, code status `discarded`.

Evolution:

| Step | Hypothesis/session | Action and target | Mechanism | Stage/gate | Outcome |
|---|---|---|---|---|---|
| 1 | `ee293fd2-4f5f-4935-9d8c-9dcc5d91123a` then `8054cff6-c411-4733-ba02-bb5333cd8fa1`; hyp `36a038f6-d9a9-4763-a72a-99841113703a` | modify `operators/merge_vehicles.py` | `guarded_cost_merge` | screening | `0/3/3`, md `-875`, CI `[-8150,0]`, decision `abandon`, metric `4a893ef5-a097-4920-89da-4259a4abead7.json` |

Classification: clean fork. It targeted a new vehicle-level guarded merge, but
screening produced clear quality regression.

Agent context/output evidence:

- Hypothesis session `ee293fd2...` had compact research signals truncated and
  research-signal token share `0.445`. It proposed replacing random merge with
  bounded split-neutral cost merge.
- Code session `8054cff6...` completed with code prompt `general` share
  `0.891`.

Interpretation: the branch generated a semantically plausible clean fork but
lost strongly. Its negative screening later influenced other proposals:
`345a...` contrasted lesson `lesson:39d1175b038bcf26` as an avoided guarded
cost pattern; `e9278...` later also referenced this lesson when attempting
`split_neutral_best_merge`.

### Branch `345a246c-3d1e-4eb4-aede-dcf1eec27af7` (frozen-failed path)

Direction: order-level `slack_balanced_swap` in `operators/swap_orders.py`.

Terminal state: `abandoned`, branch code status `quality_regression`.

Evolution:

| Step | Hypothesis/session | Action and target | Mechanism | Stage/gate | Outcome |
|---|---|---|---|---|---|
| 1 | `f086e37d-ea60-45c9-ad6e-1f98832ed7af`; hyp draft for `497f5537-d6da-48fa-9ffb-05e6a194417c` | modify `operators/swap_orders.py` | `slack_balanced_swap` | proposal | hypothesis accepted after preview; branch_lesson_usage had `avoided_lessons=1`, `contrasted_lessons=2`, `rejected_weak_positive_lessons=1` |
| 2 | `f4eff904-9e80-4825-81b5-e99b728bf4e9`; hyp `497f5537-d6da-48fa-9ffb-05e6a194417c` | modify `operators/swap_orders.py` | `slack_balanced_swap` | code/verification | code completed; Contract and Verification passed |
| 3 | same hypothesis | same | same | screening | `4/1/1`, win rate `0.6667`, md `450`, CI `[-600,1825]`, decision `queue_validate`, metric `8b47b9a2-f97c-46a4-9b72-941149084c9f.json` |
| 4 | same hypothesis | same | same | validation | pair W/L `9/6`, md `0`, CI `[0,1]`, high runtime confidence, decision `expand_validation`, metric `f47bc81c-298e-4cce-9640-dddd6dc28da9.json` |
| 5 | same hypothesis | same | same | validation expanded | pair W/L `9/6`, md `0`, CI `[0,1]`, low cached runtime, decision `queue_frozen` with `VALIDATION_EXPAND_EXHAUSTED_MARGINAL_PASS`, metric `932a742e-09fd-4096-9508-3442d6ecf333.json` |
| 6 | same hypothesis | same | same | frozen | pair W/L `6/6`, md `-400`, CI `[-4100,3500]`, high runtime confidence, decision `abandon`, reason `FROZEN_PROTOCOL_GATE_NOT_PASS`, metric `773eb845-c6d5-44d7-af4d-4835f363fbc0.json` |

Classification: clean fork with weak-positive transfer rejection, not
same-mechanism depth. It deliberately moved away from earlier
`subcategory_bucket_repack`, `evacuate_low_fill_vehicle`, and
`guarded_cost_merge` lessons. The branch_lesson_usage was semantically present
and machine-recognized; this is one of the healthier information-transfer
examples in rep02.

What the agent saw:

- Hypothesis session `f086e37d...` prompt manifests:
  - `agentic_sessions/f086e37d-ea60-45c9-ad6e-1f98832ed7af/scratch/api_visible_prompt_manifest_0001_hypothesis.json`
  - `agentic_sessions/f086e37d-ea60-45c9-ad6e-1f98832ed7af/scratch/api_visible_prompt_manifest_0002_hypothesis_preview_retry.json`
- Trace IDs:
  - `20260616T154746514704_hypothesis_0879eddb31_046bb685`
  - `20260616T154818205116_hypothesis_2c1ef66f24_97459840`
- Both hypothesis traces truncated `compact_research_signals` and
  `branch_lesson_usage_context`.
- Research-signal token share was high for this branch (`0.499` then
  `0.439`), so the agent saw more research context than early branches, but
  still saw truncated lesson context.
- Code session `f4eff904...` prompt manifests:
  - `api_visible_prompt_manifest_0001_tool_selection.json`
  - `api_visible_prompt_manifest_0002_tool_selection.json`
  - `api_visible_prompt_manifest_0003_code.json`
- Code trace IDs:
  - `20260616T154848981015_tool_selection_c79eabecbe_a50fe81f`
  - `20260616T154853826550_tool_selection_44c2c9ee94_c475b8c8`
  - `20260616T154856648756_code_d8135c87a1_c2595806`

What the agent produced:

- Hypothesis output in
  `campaign/agentic_sessions/f4eff904-9e80-4825-81b5-e99b728bf4e9/output.json`
  proposed replacing random two-order swaps with bounded, feasibility-screened
  swaps. It claimed:
  - preserve `subcategory_splits`
  - target `total_cost`
  - cap search at at most `12` vehicle pairs and `8` order-pair combinations
  - no-op if no split-preserving, capacity-safe, non-worsening proxy swap is
    found
- The output explicitly contrasted earlier lessons:
  - avoided `lesson:6faa36454e64393e` from `operators/move_order.py`
  - contrasted `lesson:643bbe413d1c8fc3` from subcategory bucket repack
  - contrasted `lesson:39d1175b038bcf26` from guarded cost merge
  - rejected weak-positive `lesson:3ce250b7711f3384` as not reused
- The patch output modified `operators/swap_orders.py`; patch body was
  omitted in the output for compactness, but repair attribution shows
  canonical full-content normalization and composition of duplicate same-file
  changes. The final composed patch had digest
  `9f1dbf34ccb48defab99a05fd163d3741396a6502e5fd04fd3289b50965a1d98`
  and derived diff `typed-edit-diff:e3a25face4ed5fe2`.

Noise and measurement:

- Screening passed despite `low_cached_champion` runtime, but the objective
  gate, not runtime, drove `SCREENING_PASS`.
- Validation was marginal: pair W/L `9/6`, median delta `0`, CI `[0,1]`.
  It reached frozen through `VALIDATION_EXPAND_EXHAUSTED_MARGINAL_PASS`, not a
  strong validation pass.
- Frozen used high fresh runtime and had no failed pairs. Its pair split was
  exactly `6` wins and `6` losses, md `-400`, CI crossing zero. This is
  consistent with a real plateau/noise-sensitive candidate whose screening and
  validation positives did not generalize, not with a framework artifact.

Interpretation: this was rep02's best research path, but it was overfit or
underpowered. The mechanism produced speedups and occasional cost wins, but the
cost effect changed sign across frozen seeds/cases. Because `subcategory_splits`
were unchanged in frozen pairs, the failure reduced to unstable lower-priority
`total_cost`, not a high-priority split regression.

### Branch `034bc9ca-ced3-447e-9a88-bd4c8d3e9334`

Direction: order-level `cost_guarded_swap` in `operators/swap_orders.py`.

Terminal state: `abandoned`, code status `discarded`.

Evolution:

| Step | Hypothesis/session | Action and target | Mechanism | Stage/gate | Outcome |
|---|---|---|---|---|---|
| 1 | `44aa21da-8bfd-482c-97c9-931a7221fffb` then `cb493136-a100-4c8f-9002-6514bf7df789`; hyp `becf7df8-c1fe-4438-81e3-a9e06ba0a466` | modify `operators/swap_orders.py` | `cost_guarded_swap` | screening | `1/1/4`, md `75`, CI `[-1650,800]`, decision `continue_explore`, metric `b61b481d-fb86-489e-991d-4396e0e500b3.json` |
| 2 | `603e80e8-0dc3-4cee-9999-75339b2d2112`; hyp `97ec1e84-c867-4211-85de-2fb395b6e76d` | modify same file | same | proposal | quality block sequence `2`, loop step `13`, semantic mismatch, corrected fields `operators/swap_orders.py/modify/cost_guarded_swap`, missing `mechanism` |
| 3 | `644dd5f4-89c7-442c-b31d-5e026d83191c` then `630dd700-9ff0-4ab3-8c61-2e9104a977b1`; hyp `a1fb3d37-414b-40a7-a694-5cff739058f9` | modify same file | same | screening | `1/1/4`, md `-50`, CI `[-2525,325]`, decision `abandon`, metric `eb6fe112-b1b1-424f-ab75-15c470b90d30.json` |

Classification: sibling-nearby to frozen branch because it also worked on
`swap_orders.py`, but it used a different swap mechanism. Same-mechanism depth
was attempted after a marginal first screen.

Context/output:

- Hypothesis prompt sessions had both `compact_research_signals` and
  `branch_lesson_usage_context` truncated. Research-signal shares were high:
  `0.514/0.455`, then `0.483/0.434`, then `0.468/0.421`.
- The agent saw enough prior-branch signal to name `cost_guarded_swap`, but the
  refinement failed branch_lesson_usage semantic linkage.

Interpretation: this branch was a near sibling to `slack_balanced_swap`, but it
did not produce a robust cost signal. It also demonstrates the core
information-transfer defect: branch lessons were visible enough to be present,
but not encoded with the target/action/mechanism fields the gate required.

### Branch `e7ee4097-1db4-4b1a-8b64-79810c0ffa76`

Direction: vehicle-level `locked_anchor_packdown`.

Terminal state: `parked_lineage`, next action `clean_fork`. Current head was
no-effect with fresh runtime required; best checkpoint was weak-positive:
`3/0/7`, md `500`, CI `[125,3075]`.

Evolution:

| Step | Hypothesis/session | Action and target | Mechanism | Stage/gate | Outcome |
|---|---|---|---|---|---|
| 1 | `872eeb55-bd14-4621-aa5f-e54245c3821c`; hyp `3417f9d4-bd3b-46ce-b4ec-1065dc3e6199` | remove `operators/split_vehicle.py` | `destructive_split_prune` | proposal | quality block sequence `3`, loop step `15`, linkage unrecognized; missing `target_file,action,recognized_linkage_fields` |
| 2 | `1154698e-9be4-4b6d-a5b3-4f769ddc4087` then `6ecf6387-364d-4b6e-9978-eaf61bec8095`; hyp `05eecc1d-395c-4954-bbed-b3c2ef1d9dac` | create `operators/locked_anchor_packdown.py` | `locked_anchor_packdown` | screening | `3/0/7`, md `500`, CI `[125,3075]`, decision `continue_explore` as weak signal, metric `edb4f146-6602-4f6f-af12-67a7fc264861.json` |
| 3 | `df785140-67df-418b-8215-5a0d43e55678`; hyp `8a4362d5-31c5-4523-9fac-3e55ab17faa1` | modify same file | same | proposal | quality block sequence `4`, semantic mismatch, missing `target_file,action` |
| 4 | `e3247ae7-9db1-4977-aadc-e5c21a5a19dd` then `8440676d-d8b9-4020-8c4c-399b975a3655`; hyp `d5f23dd1-7650-4aba-94d9-de39bedca6a7` | modify same file | same | screening | `0/0/6`, all ties, decision `continue_explore`, metric `09ae31c8-0722-4122-89da-4259a4abead7.json` |
| 5 | `5e72d5ca-4702-4946-ae10-845ecd882a42` then `1ac69ebb-0ea4-4541-bed3-d4a742686629`; hyp `8adccc52-0c7d-402e-b955-7d6b11583df9` | modify same file | same | screening | `0/0/6`, all ties, decision `continue_explore`, metric `469ee166-eeaa-49f3-9f6e-860b411f1420.json` |

Classification: same-mechanism depth after a weak-positive first candidate.
This branch had one real weak-positive signal but refinements regressed to
no-effect. It is a clean example of weak-positive transfer failing to become
semantic improvement: later prompts preserved or referenced the same mechanism,
but either failed linkage or produced all ties.

Context/output:

- Hypothesis traces for this branch consistently truncated both compact
  research signals and branch lesson usage context.
- Research-signal token shares were high (`0.527/0.469`,
  `0.503/0.455`, `0.483/0.437`, `0.473/0.431`), suggesting that context
  volume was not absent; the problem was usable structure and linkage.
- Code sessions completed with mostly generic code prompts (`general` token
  shares around `0.86-0.89`).

Measurement:

- The weak-positive metric `edb4f146...` had low cached champion runtime and
  pair W/T `11/9`, no losses, but failed the case-level screening win-rate
  gate (`3/0/7`, win rate `0.3`). That is evidence of a possible local signal,
  not validation-grade evidence.
- Later all-tie metrics had `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`, but no
  objective effect.

Interpretation: this branch should have produced either a targeted
same-mechanism refinement or a deliberate clean fork. Instead it burned
proposal attempts on linkage failures and then generated stricter variants that
turned into no-effect.

### Branch `b5e19c66-7450-4c30-b4be-3fc90360a17a`

Direction: order-level `fill_dominant_slack`.

Terminal state: `explore`, `active_no_effect`, required follow-up. Best
checkpoint was marginal (`3/1/6`, md `200`, CI `[-175,775]`); current head was
no-effect (`0/0/6`).

Evolution:

| Step | Hypothesis/session | Action and target | Mechanism | Stage/gate | Outcome |
|---|---|---|---|---|---|
| 1 | `119291c4-c074-4942-a1a4-a1fab7ce2da7`; hyp `cf795c2d-3a09-4497-ba4f-fe0699d18f9c` | create `operators/cross_subcat_cost_coload.py` | `cross_subcat_cost_coload` | proposal | quality block sequence `5`, linkage unrecognized; missing `target_file,action,recognized_linkage_fields` |
| 2 | `290be7eb-7b4c-4a4f-a503-3fc9350075a7` then `93fae911-5aee-42d8-b352-5cf4e06a3448`; hyp `d0bbf994-28b2-41df-b4e7-cd3c84bcd033` | create `operators/fill_dominant_subcategory_slack.py` | `fill_dominant_slack` | screening | `3/1/6`, md `200`, CI `[-175,775]`, decision `continue_explore`, metric `e36b738a-7eee-4118-a2a9-2c4f3ee320a0.json` |
| 3 | `a27878e3-2e5d-4312-a1b8-b875e5c92b12`; hyp `6289f8a6-6da6-4769-8009-907f1addcaf5` | modify same file | same | proposal | quality block sequence `6`, semantic mismatch for same mechanism |
| 4 | `1b5c661c-0a72-4567-a3e4-9f4ac8977ded`; hyp `89c216f8-78ea-40e4-ba4a-d44cca0b73b0` | modify same file | same | proposal | quality block sequence `7`, semantic mismatch for same mechanism |
| 5 | `b9fb78aa-28da-465d-b9d3-1afc67b8a9cb` then `bbb59ace-5ff6-4c10-98ab-4b16200c802c`; hyp `17383413-2234-4fcd-bb52-b0df7c2e6f31` | modify same file | same | screening | `0/0/6`, all ties, decision `continue_explore`, metric `7ae66e61-75ed-4b99-a11d-1040721475a6.json` |

Classification: sibling-nearby/clean-fork followed by same-mechanism depth. The
branch lessons were present, but the two refinement attempts were blocked by
semantic mismatch before code. The successful refinement then no-oped.

Context/output:

- Hypothesis sessions had research-signal token shares around `0.56/0.50` for
  clean-fork attempts and `0.51/0.46`, `0.50/0.46`, `0.49/0.45` for
  same-mechanism refinements. `branch_lesson_usage_context` and
  `compact_research_signals` were truncated in those hypothesis prompts.
- Code sessions completed with code prompt `general` shares `0.871` and
  `0.821`.

Measurement:

- Best checkpoint `e36b738a...` had low cached champion runtime but did include
  12 runtime pairs and `runtime_ratio_median=0.921`; objective evidence was
  still weak (`3/1/6`, CI crossing zero).
- Current head `7ae66e...` was all ties with cached runtime pressure.
- Fresh-runtime replay drain later listed this branch as materializable but not
  schedulable because `fresh_champion_runtime_replay_pending_missing`.

Interpretation: this branch did not fail because it lacked a signal entirely;
it failed because the signal was marginal, refinement quality was blocked, and
the eventual refinement collapsed into no-effect. The fresh-runtime machinery
also left open replay pressure but did not schedule closure.

### Branch `f45ed5e5-91dc-42c5-ba33-34ed50f8d64c`

Direction: vehicle-level `best_saving_downsize` after an attempted
`evacuate_redundant_vehicle` clean fork.

Terminal state: `abandoned`, code status `discarded`.

Evolution:

| Step | Hypothesis/session | Action and target | Mechanism | Stage/gate | Outcome |
|---|---|---|---|---|---|
| 1 | `c6520bbf-1786-4c81-b5fd-5861a13bd4c5`; hyp `71f350e3-6aac-430f-a05b-bea95b171bc8` | create `operators/evacuate_redundant_vehicle.py` | `evacuate_redundant_vehicle` | proposal | quality block sequence `8`, linkage unrecognized; missing `target_file,action,recognized_linkage_fields` |
| 2 | `9010baf9-7fb3-4a4e-aa31-d57359b359fd` then `ef8f6772-8e5a-4e3b-9b66-1fb91dba2692`; hyp `c4c45c51-62e5-44a6-bf5f-6beb681ead76` | modify `operators/change_vehicle_type.py` | `best_saving_downsize` | screening | `0/0/6`, md `-225`, CI `[-1375,0]`, decision `abandon`, metric `903df7e6-2bda-4a9b-bd52-2f7148c6ffcf.json` |

Classification: clean fork after blocked proposal. It did not become
same-mechanism depth.

Context/output:

- Hypothesis sessions had research-signal token shares `0.561/0.503` and
  `0.559/0.503`, with both compact research signals and branch lesson context
  truncated.
- Code prompt `general` share was `0.888`.

Interpretation: the branch was abandoned correctly. It had no wins and
non-positive CI. The first clean-fork attempt never reached code due to lesson
linkage failure, so the eventual branch tested a different downsize mechanism
without evidence that the earlier lesson was semantically resolved.

### Branch `5fee024e-85f9-425c-9056-23839f251ad7`

Direction: order-level `guarded_evacuate_tail` in `operators/move_order.py`.

Terminal state: `parked_lineage`, next action `clean_fork`. Final evidence was
marginal but losing: current and repeated screens `1/2/3`, md `0`, CI
`[-2800,1375]`.

Evolution:

| Step | Hypothesis/session | Action and target | Mechanism | Stage/gate | Outcome |
|---|---|---|---|---|---|
| 1 | `bb82e639-b2d6-404b-809d-3a649dd3d292`; hyp `8d41f3dc-a164-4c1e-82f5-24da365fad66` | create `operators/evacuate_same_subcategory_tail.py` | `evacuate_same_subcategory_tail` | proposal | quality block sequence `9`, linkage unrecognized |
| 2 | `5cc32794-c4ff-4678-80a4-f6f28b0584bc` then `893737b5-95d2-45ee-ac89-c2dda08bbc5e`; hyp `0ff9eb5f-8bc9-4e86-b35c-0b4a792a9662` | modify `operators/move_order.py` | `guarded_evacuate_tail` | screening | `1/2/3`, md `0`, CI `[-2800,1375]`, decision `continue_explore`, metric `6fd837da-46d0-4907-8556-e4ab6b7e4e0a.json` |
| 3 | `70cdbc54-1f06-42da-8111-068d23813aab` then `5a8cbed3-16fe-4793-a61c-421b9a27b62f`; hyp `8e8eeab5-a3eb-4f42-9179-872f0a661260` | modify same file | same | screening | repeated `1/2/3`, md `0`, CI `[-2800,1375]`, decision `continue_explore`, metric `d09db40a-4108-49d5-9d52-68f60c18a197.json` |

Classification: same-mechanism depth after clean-fork blockage. It is a
deepest plateau branch, but the plateau was negative/marginal, not promising.

Context/output:

- Hypothesis traces were truncated for compact research signals and branch
  lessons; research-signal share was `0.562/0.503` for the blocked clean fork,
  `0.560/0.503` for the first guarded tail proposal, and `0.513` for the
  later refinement.
- Code session `893737b5...` had three code traces with general shares
  `0.874/0.844/0.744`, suggesting repeated code-phase attempts but no code
  failure.

Interpretation: the branch repeated essentially the same weak result. It did
not show learning from the first `1/2/3` outcome. Parking and clean-fork
recommendation were appropriate.

### Branch `e9278cc3-a751-4366-bce4-6f05ae833942`

Direction: order-level `locked_anchor_packdown`, but this branch consumed many
attempts and contains the rep02 old-string/code-edit failures.

Terminal state: `explore`, `active_no_effect`, required follow-up. Best
checkpoint was marginal (`2/1/7`, md `0`, CI `[-450,1250]`); current head was
no-effect (`0/0/6`).

Evolution:

| Step | Hypothesis/session | Action and target | Mechanism | Stage/gate | Outcome |
|---|---|---|---|---|---|
| 1 | `747d65dc-c5fe-47e8-adb9-8a37015ff395`; hyp `43104ee5-15af-4e0e-a68c-532c6e69eba0` | create `operators/evacuate_costly_leaf_vehicle.py` | `costly_leaf_evacuation` | proposal | quality block sequence `10`, linkage unrecognized |
| 2 | `93fed61c-4152-4388-b517-5b4937b604b1`; hyp `24f4788a-5d7a-4dd3-9183-5a7c8c29cf52` | remove `operators/split_vehicle.py` | `destructive_split_removal` | proposal | quality block sequence `11`, linkage unrecognized |
| 3 | `cefa8b28-3f14-4f6e-94a0-9750385ee348`; hyp `5ca7ad06-6260-44f4-a0ee-93d985dba828` | modify `operators/merge_vehicles.py` | `split_neutral_best_merge` | proposal | hypothesis was generated, then code attempts failed |
| 4 | `0447e983-9ce0-4ece-aa90-de76efb4e52c` | same file/mechanism | same | code | `code_generation_failed`; failure ledger had `exact_replace_not_serializable` then `old_string_not_found in operators/merge_vehicles.py`; no patch |
| 5 | `d6f55508-9705-48a2-9887-14f9e5f01e50` | same file/mechanism | same | code retry | same failure pattern; no patch |
| 6 | `e67828b8-dbdf-442f-a1bf-b122b3071a79` then `1081c59a-b22a-4e60-bfcc-ea839cc81692`; hyp `795b84f8-64cc-4c91-9f33-7988907ecbe1` | create `operators/locked_anchor_packdown.py` | `locked_anchor_packdown` | screening | `2/1/7`, md `0`, CI `[-450,1250]`, decision `continue_explore`, metric `554a356f-6a29-4dd9-8ddf-4e07216954f4.json` |
| 7 | `98cf0d2f-8de0-484c-9eff-4adbbc4d11b9` then `2b7ff70c-4e49-4f14-8c2a-63bdfe7d58f9`; hyp `1be0464d-6d57-4659-9703-761a90b1348b` | modify same file | same | screening | `0/0/6`, all ties, decision `continue_explore`, metric `06af1556-b621-4dff-9edd-c1b9a18d9398.json` |

Classification: a weak-positive transfer/sibling-nearby branch that churned
through multiple clean forks before settling into same-mechanism depth. It is
also the clearest edit-protocol failure branch.

What the agent saw and produced:

- For the failed `split_neutral_best_merge` path, hypothesis session
  `cefa8b28...` saw compact research signals and branch lessons, both
  truncated; research-signal shares were `0.575/0.519`.
- The output proposed replacing `MergeVehicles` with a split-neutral best-merge
  selector, contrasting earlier `costly_leaf`, `guarded_cost`, and
  `slack_balanced` lessons.
- Code session `0447e983...` used trace IDs:
  - `20260616T164511134194_tool_selection_ce02f1ede1_3f338545`
  - `20260616T164513620101_code_20ccbef99a_d0efeea5`
  - `20260616T164602221644_code_13da223b9b_8bbe4a4e`
- Code session `d6f55508...` used trace IDs:
  - `20260616T164649559542_tool_selection_2c0b1d0d06_f9202dac`
  - `20260616T164651912384_code_3f41fe32db_ba45a1b7`
  - `20260616T164744062841_code_1abd59c766_f86e7899`
- Both output files,
  `campaign/agentic_sessions/0447e983-9ce0-4ece-aa90-de76efb4e52c/output.json`
  and
  `campaign/agentic_sessions/d6f55508-9705-48a2-9887-14f9e5f01e50/output.json`,
  record:
  - first failure: `exact_replace old_string does not match the content after
    prior same-file edits`, reason `exact_replace_not_serializable`,
    JSON pointer `/additional_changes/0`
  - second failure: `/: old_string_not_found in operators/merge_vehicles.py`
  - `patch=null`
- The code prompt was dominated by generic context (`general` shares
  `0.909/0.881` and `0.883/0.855` in the failed code attempts).

Measurement:

- The successful later `locked_anchor_packdown` screen had pair W/L/T
  `9/6/5` but only case `2/1/7`, md `0`, CI crossing zero.
- The refinement became all ties (`0/0/6`, pair ties `12`).
- Fresh-runtime replay drain listed this branch as materializable but not
  schedulable due to missing `fresh_champion_runtime_replay_pending` marker.

Interpretation: this branch spent too much of the budget on proposal and code
format failures before reaching a runnable candidate. The useful semantic
lesson transfer was partial: the agent named and contrasted prior lessons, but
the actual research path bounced among mechanisms. When it finally produced
code, the effect was marginal/no-effect.

### Branch `bc56f528-ec4b-4556-b7f0-c953fbc35636`

Direction: order-level `retire_split_neutral_vehicle`.

Terminal state: `explore`, `active_no_effect`, required follow-up. Best
checkpoint was marginal (`1/1/8`, md `0`, CI `[-750,250]`); current head was
no-effect (`0/0/6`).

Evolution:

| Step | Hypothesis/session | Action and target | Mechanism | Stage/gate | Outcome |
|---|---|---|---|---|---|
| 1 | `95b2f5b5-5890-4d0d-89b9-615a9324d015` then `51ff015d-506c-4c75-9cb4-6dae2a07d9f1`; hyp `f72b0c27-0c75-4f14-8516-4c8a3a33047d` | create `operators/retire_split_neutral_vehicle.py` | `retire_split_neutral_vehicle` | screening | `1/1/8`, md `0`, CI `[-750,250]`, decision `continue_explore`, metric `c5d7b062-a5ec-45ae-8a44-7a6c5a9d105e.json` |
| 2 | `2bfc06aa-6466-45ae-aef7-a2a7e753e26c`; hyp `f7a5d973-5eb4-4eed-87c5-3df35b8f8c4c` | modify same file | same | proposal | quality block sequence `14`, semantic mismatch, missing `target_file,action` |
| 3 | `dcd9ea63-052b-48f4-80c4-3a9e329c5a41` then `b2e0a7d2-ee21-40ca-80ac-0cebafab9e1f`; hyp `5ff0792c-fad6-4180-be3d-561f1d7e5768` | modify same file | same | screening | `0/0/6`, all ties, decision `continue_explore`, metric `34f543b8-2f55-49e3-8cba-14740f764a93.json` |

Classification: late clean fork followed by same-mechanism refinement. It was
not abandoned before max rounds, but it was no-effect at the terminal state.

Context/output:

- Hypothesis research-signal shares were high (`0.585/0.526`, then `0.543`,
  then `0.531/0.483`), and branch lesson context was truncated.
- Code sessions completed with general shares `0.871` and `0.846`.

Measurement:

- Both metrics used cached champion runtime and had no decisive objective
  signal.
- Fresh-runtime replay drain's final skipped attempt was on this branch:
  `action=skip`, `scheduler_reason=pending_retry_diagnostic_followup`,
  `pressure_no_schedulable_replay_candidate`.

Interpretation: this branch was late-budget exploration. It left unresolved
fresh-runtime pressure but no objective evidence worth promotion.

## Context And Output Audit

Rep02 had `55` agentic sessions and `120` traces. The proposal trajectory
manifest reports `prompt_manifest_loaded_count=120`,
`session_count=55`, and `trace_count=120`.

Context composition:

- All known traces used `compact-measurement-diagnostics`.
- Branch lesson usage was present in all `55` sessions, with semantic
  projection present in all `55`.
- Branch lesson context was truncated in `51` traces.
- The prompt family aggregate in the postrun for rep02 was roughly:
  `general=35.7%`, `research_signal=34.0%`, `tool_selection=11.8%`,
  `tool_observation=7.7%`, `feedback=6.1%`, `governance=4.6%`.

What this means at branch level:

- The agent usually saw research/lesson material, but often in truncated form.
- Hypothesis prompts for later branches often assigned 45-58% token share to
  research signals, yet machine quality still rejected branch_lesson_usage
  linkage. This means the failure is not simply "no context"; it is a mismatch
  between visible report-style lesson text and the strict structured linkage
  expected by the quality gate.
- Code prompts were often dominated by generic context: many completed code
  phases had `general` token share `0.84-0.92`. The code phase therefore
  mostly had target/source/generic instructions, while research lessons were
  a hypothesis-phase burden.

Critical inspected outputs:

- Frozen branch output:
  `campaign/agentic_sessions/f4eff904-9e80-4825-81b5-e99b728bf4e9/output.json`
  generated `slack_balanced_swap`, with explicit branch_lesson_usage and
  canonical patch repair attribution.
- Old-string failures:
  `campaign/agentic_sessions/0447e983-9ce0-4ece-aa90-de76efb4e52c/output.json`
  and
  `campaign/agentic_sessions/d6f55508-9705-48a2-9887-14f9e5f01e50/output.json`
  show repeated `exact_replace_not_serializable` followed by
  `old_string_not_found in operators/merge_vehicles.py`.
- Deep plateau branch outputs:
  `campaign/agentic_sessions/2b7ff70c-4e49-4f14-8516-4c8a3a33047d/output.json`
  generated stricter `locked_anchor_packdown`, but the metric became all ties.
  `campaign/agentic_sessions/bbb59ace-5ff6-4c10-98ab-4b16200c802c/output.json`
  generated a stricter `fill_dominant_slack`, also all ties.

## Information Transfer Between Branches

Branch lessons were present in every session, but transfer quality was mixed.

Successful or partially successful semantic transfer:

- Frozen branch `345a...` used structured branch_lesson_usage with:
  - `avoided_lessons=1`
  - `contrasted_lessons=2`
  - `rejected_weak_positive_lessons=1`
  It explicitly avoided earlier `MoveOrder` evacuation losses, contrasted
  bucket repack, contrasted guarded cost merge, and rejected a weak-positive
  bucket lesson as not reusable. This is semantic clean-fork behavior.
- `e9278...` later borrowed/preserved the weak `locked_anchor_packdown` lesson
  when refining the same mechanism, but the result was all ties.

Failed transfer / present but not semantically usable:

- Quality block ledger sequence `1` (`e0b22...`), `2` (`034bc...`), `3-4`
  (`e7ee...`), `5-7` (`b5e...`), `8-9` (`f45...`/`5fee...`), `10-13`
  (`e927...`), and `14` (`bc56...`) all show branch_lesson_usage was present
  but failed semantic or target/action/mechanism linkage rules.
- The most common machine reject was not "no lesson"; it was "lesson present
  but linkage unrecognized" or "semantic mismatch."
- Proposal attempts often included broad family names or lesson prose, but the
  quality gate required compact lesson IDs plus concrete `target_file`,
  `action`, and `mechanism` linkage.

Did prior evidence influence later proposals?

- Yes, at the proposal-text level. Later proposals repeatedly contrasted
  earlier failures: guarded cost merge, low-fill evacuation, bucket repack, and
  destructive split removal.
- The influence was often report-only rather than operationally useful. It did
  not reliably guide the next candidate to a stronger Protocol outcome.
- The best example of semantic influence was `345a...`, but even that
  semantically clean fork only reached frozen as a marginal candidate and then
  failed.

## Noise And Measurement

Screening vs validation/frozen:

- Many screening rows used cached champion runtime and low runtime confidence.
  This was handled correctly as proposal/audit guidance only; deterministic
  gates still used objective Protocol outputs.
- The frozen failure did not use cached champion runtime. It had
  `champion_cache_hits=0`, `champion_cache_misses=12`, `champion_cache_writes=12`,
  `runtime_confidence=high`, and no failed pairs.
- Validation for `345a...` was borderline: `9/6` pair W/L, median delta `0`,
  CI `[0,1]`. The expanded validation row was cached-runtime but objective
  evidence was unchanged, so it queued frozen under an exhausted marginal-pass
  rule rather than a strong pass.

No-effect/tie rows:

- All-tie screening appeared repeatedly:
  - `e0b22...` metrics `b79a90...`, `594863...`
  - `e7ee...` metrics `09ae31...`, `469ee...`
  - `b5e...` metric `7ae66...`
  - `e927...` metric `06af15...`
  - `bc56...` metric `34f543...`
- These rows often carried `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`, but the
  objective effect was also zero. They are not evidence for promotion; they are
  evidence of no-effect loops.

Fresh replay pressure:

- `campaign_summary.json` reports fresh-runtime replay drain status
  `pressure_no_schedulable_replay_candidate`.
- Pressure candidates were `b5e19...`, `e9278...`, and `bc56...`; all were
  materializable but not schedulable because the
  `fresh_champion_runtime_replay_pending` marker was missing.
- This affected terminal diagnosis of no-effect active branches, not the frozen
  failure. The frozen failure already used fresh high-confidence evidence.

Was the frozen failure a real plateau or measurement artifact?

- It was a real frozen failure against the active champion under the available
  Protocol evidence.
- It may still be noise-sensitive in the scientific sense: frozen W/L was
  exactly `6/6`, CI crossed zero, and screening/validation were marginal.
  However, under v3/v0.4 governance that is precisely why it must not promote.

## Failure/Quality Taxonomy

Observed low-quality causes in rep02:

1. Proposal quality blocks:
   - Count: `14`
   - Cause: `branch_lesson_usage_semantic_mismatch` or
     `branch_lesson_usage_linkage_unrecognized`
   - Examples:
     - `e0b22...`, loop step `3`, missing `target_file,action`
     - `034bc...`, loop step `13`, missing `mechanism`
     - `e7ee...`, loop steps `15` and `17`, missing linkage or
       `target_file,action`
     - `b5e...`, loop steps `20`, `22`, `23`
     - `e927...`, loop steps `30-33`
     - `bc56...`, loop step `37`

2. Code/edit failures:
   - Count: `2` code-generation failures in the research efficiency taxonomy;
     both on branch `e9278...`
   - Sessions:
     - `0447e983-9ce0-4ece-aa90-de76efb4e52c`
     - `d6f55508-9705-48a2-9887-14f9e5f01e50`
   - Failure path:
     `exact_replace_not_serializable` -> `old_string_not_found in operators/merge_vehicles.py`
   - Impact: no formal candidate patch for `split_neutral_best_merge`, budget
     drain, and reroute to a different mechanism.

3. Verification failures:
   - None reported in rep02 (`verification_failure_breakdown={}`,
     `verification_heavy.count=0`).
   - Contract/Verification passed for all Protocol rows in DB.

4. Tool timeouts:
   - None reported (`tool_timeout.count=0`).

5. No-effect loops:
   - Multiple same-mechanism refinements ended all ties:
     `subcategory_bucket_repack`, `locked_anchor_packdown`,
     `fill_dominant_slack`, `retire_split_neutral_vehicle`.
   - These were often stricter guards that no-oped rather than producing
     robust positive movement.

6. Fresh-runtime replay pressure:
   - Present for terminal active branches but unresolved due to scheduler marker
     mismatch. It did not invalidate frozen; it reduced closure quality for
     active no-effect branches.

## Interpretation

Rep02 failed to promote because its only validation/frozen candidate was
marginal before frozen and non-positive at frozen. The strongest branch
(`345a...`) was not blocked by Contract, Verification, prompt absence, or
runtime regression. It failed because the objective signal was unstable:
screening passed, validation barely queued frozen, and frozen split 6/6 with
negative median delta.

The broader cell underperformed because it combined three drains:

- Research-quality drain: many ideas were semantically plausible but weakly
  grounded. Branches often added stricter cost guards and no-op conditions,
  which protected feasibility but collapsed into ties.
- Context/lesson-linkage drain: branch lessons were visible, but the model
  frequently failed to express them in the exact structured linkage required
  by the proposal quality gate. This consumed 14 attempts before Protocol.
- Edit-protocol drain: the `e9278...` merge-vehicles fork lost two code
  attempts to non-serializable same-file exact replacements and stale
  `old_string` edits.

Branch governance mostly behaved conservatively: weak/no-effect branches were
continued briefly, abandoned, or parked; frozen did not promote a marginal
candidate. The governance weakness is more about wasted attempts and unresolved
fresh-runtime replay pressure than about unsafe promotion.

Compared with the v0.3 reference, rep02 is much weaker:

- v0.3 production Sonnet reference promoted `3/3` after fixes.
- Strongest v0.3 synthetic reached four continuous promotions.
- Rep02 produced zero promotions, despite reaching frozen once.

The likely reason is not that v0.4 cannot run production warehouse Protocol:
rep01 and rep03 in the same postrun promoted once. Rep02 specifically failed
because its search path was dominated by marginal/no-effect guarded local
moves, branch-lesson linkage blocks, and one frozen candidate whose apparent
screening/validation edge did not generalize.

## Concrete Repair Hypotheses

1. Make branch_lesson_usage easier to satisfy semantically.
   - Current failure mode is "present but not machine-usable."
   - Provide a compact schema skeleton in the hypothesis prompt with required
     fields filled from the branch card: `lesson_id`, `target_file`, `action`,
     `mechanism`, `changed_dimensions`, and `reject_reason_code`.
   - Acceptance criterion: proposal-quality blocks for
     `branch_lesson_usage_*` fall below 10% of proposal attempts in a 24-round
     warehouse run.

2. Separate weak-positive refinement from clean-fork contrast.
   - Branches like `e7ee...` and `b5e...` had weak-positive/marginal signals
     but refinement prompts also carried clean-fork/sibling constraints.
   - Use a deterministic mode label in prompts: `same_mechanism_refine`,
     `clean_fork`, `sibling_nearby`, or `weak_positive_transfer`, and show only
     the required lesson structure for that mode.
   - Acceptance criterion: same-mechanism refinements preserve the parent
     mechanism and produce fewer all-tie no-effect rows.

3. Improve code edit protocol for same-file multi-edit outputs.
   - The `e9278...` failures show duplicate exact-replace edits over the same
     file can become non-serializable.
   - For code-generation prompts, prefer full-file replacement or a single
     canonical same-file patch body, not multiple `additional_changes` entries
     with dependent `old_string` values.
   - Acceptance criterion: zero `exact_replace_not_serializable` and
     `old_string_not_found` failures in repeated warehouse longrun cells.

4. Treat all-tie refinements as a branch-local stop signal sooner.
   - Repeated all-tie rows consumed rounds in `e0b22...`, `e7ee...`,
     `b5e...`, `e927...`, and `bc56...`.
   - After one same-mechanism all-tie refinement following a marginal parent,
     force either telemetry/activation diagnosis or clean fork instead of
     another stricter no-op guard.
   - Acceptance criterion: fewer repeated all-tie rows per branch without
     reducing promotion rate.

5. Close fresh-runtime replay pressure deterministically.
   - Rep02 had materializable replay candidates but none schedulable because
     the pending marker was missing.
   - Repair scheduler/branch-card consistency so materializable candidates with
     `fresh_runtime_required=true` can be replayed or explicitly closed.
   - Acceptance criterion: `fresh_runtime_replay_drain.status` is either
     `executed` or a deterministic non-replayable reason with no
     `pressure_no_schedulable_replay_candidate` terminal state.

6. Add frozen-candidate preflight diagnosis for marginal validation passes.
   - `345a...` queued frozen on exhausted marginal validation with md `0` and
     CI `[0,1]`.
   - Before consuming frozen budget, emit report-only diagnosis showing whether
     validation wins are high-priority objective improvements or lower-priority
     cost swings across seeds. Keep Decision deterministic.
   - Acceptance criterion: humans can audit why a marginal validation candidate
     entered frozen without reading all pair rows manually.
