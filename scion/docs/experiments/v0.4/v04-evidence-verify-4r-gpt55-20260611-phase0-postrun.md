# v0.4 Evidence Verification 4R Phase 0 Postrun

*Date: 2026-06-11*
*Branch: `codex/v04-evidence-repair-plan`*
*Commit: `0a6a2f5`*
*Model: `gpt-5.5` via local proxy*

This report freezes the Phase 0 evidence baseline for the paired CVRP and
warehouse verification runs launched after the v0.4 measurement/runtime/context
repair slice. It is a pre-repair postrun: do not treat it as evidence that the
remaining v0.4 closeout repairs are complete.

## Run Directories

- CVRP:
  `/home/clawd/research/scion-experiments/v04-evidence-verify-cvrp-4r-tl30-20260611-4r-gpt55-20260611T145506Z-claw`
- Warehouse:
  `/home/clawd/research/scion-experiments/v04-evidence-verify-warehouse-4r-defaultbudget-20260611-4r-gpt55-20260611T145506Z-claw`

Both wrappers exited cleanly with `WRAPPER_EXIT_STATUS:0`.

## Top-Level Outcome

| Problem | Started | Ended | Requested/effective rounds | Stage rows | Fresh runtime replays | Champion |
| --- | --- | --- | --- | --- | --- | --- |
| CVRP | 2026-06-11T14:55:07Z | 2026-06-11T16:26:59Z | 4/4 | screening 4, validation 0, frozen 0 | 0 | v1 |
| Warehouse | 2026-06-11T14:55:07Z | 2026-06-11T15:30:12Z | 4/4 | screening 2, validation 1, frozen 1 | 0 | v2 |

CVRP completed four formal candidates, all in screening. No candidate reached
validation or frozen. Warehouse completed a full promotion path for one
candidate, then screened and abandoned a follow-up modify candidate.

Both runs were valid clean-wrapper runs. CVRP stopped on
`max_rounds_exhausted`; campaign id was
`8524019b-972f-443a-b0f7-c4ab172fd81c`.

## CVRP Candidate Evidence

CVRP launched with:

```text
python -m scion.cli.main run
  --problem scion/problems/cvrp/problem.yaml
  --protocol scion/problems/cvrp/formal/protocol.yaml
  --split scion/problems/cvrp/formal/split_manifest.yaml
  --seeds scion/problems/cvrp/formal/seed_ledger.yaml
  --rounds 4
  --time-limit-sec 30
  --disable-early-stop
  --agentic-proposal
```

Each screening row used `8 cases x 4 seeds = 32` pairs.

Effective copied CVRP formal artifact hashes from
`campaign/champions/champion_v1/formal/`:

- `protocol.yaml`: `496fe3eaa333095624fca40beb5fd009defd488cdf6a36aa3e0d4b21e95447b6`
- `split_manifest.yaml`: `f6410f4bfae8d5078a8dfcc10e5d1ec8b0181b83ab1284ad6eabdfb4e1a177d4`
- `seed_ledger.yaml`: `32be9ccd6a77dc94ce8fc0154d1a0efbf859bf73e43f784254db8fda1b2bfaf0`
- `matrix.json`: `0ac78306b80ba5fc035465212191f3da2c7f26c5f404254c8cf0d5150b0c89b2`

Candidate accounting:

- Proposal attempts: 4.
- Agentic sessions: 8 = 4 partial hypothesis-only sessions plus 4 completed
  code sessions.
- Unique hypotheses: 4.
- Formal candidates: 4.
- Proposal quality blocks: 0.
- Verification-failure consumed candidates: 0.

| Hypothesis | Branch | Target | Pair W/L/T | Case-gate W/L/T | Gate win rate | Median delta | CI | Decision reasons |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ac615454` | `54ac43a9` | `local_search.py` | 9/14/9 | 0/3/5 | 0.000 | 0.0 | [-10.75, 1.5] | `SCREENING_FAIL_WIN_RATE`, archive loss-without-win |
| `b0335ef5` | `c9952e4e` | `destroy_repair.py` | 12/7/13 | 3/1/4 | 0.375 | 0.0 | [-2.0, 8.0] | `SCREENING_FAIL_WIN_RATE`, marginal signal continue |
| `8e8cadb8` | `c9952e4e` | `destroy_repair.py` | 5/1/26 | 0/0/8 | 0.000 | 0.0 | [0.0, 0.0] | active pair wins but case fail; runtime evidence incomplete |
| `9b994f51` | `374cdc2d` | `scheduler.py` | 5/0/27 | 0/0/8 | 0.000 | 0.0 | [0.0, 0.0] | active pair wins but case fail; runtime evidence incomplete |

Interpretation:

- The 6/11 audit's low-SNR failure mode is still reproduced: pair-level
  movement exists, but case-level gate evidence stays below the current
  screening threshold and validation/frozen are never reached.
- Branch `c9952e4e` did get a same-mechanism follow-up in `destroy_repair.py`,
  but the run still mostly creates shallow sibling branches. This is not yet
  the v3-style deep branch research loop.
- The current F-3 gap remains live: `win_rate < 0.5` still behaves as
  screening failure for trajectory-divergent CVRP instead of a measurement-aware
  low-signal expand path.

## CVRP Runtime Evidence

Per screening metric file:

| Metrics file | Runtime confidence | Runtime pairs | Runtime aggregate | Pair total seconds min/median/max/mean |
| --- | --- | --- | --- | --- |
| `b4a3b59d-5953-4d5b-a53a-69b2f42851d3.json` | high | 32 | median ratio 1.004, delta +98 ms | 48.936 / 50.071 / 89.197 / 55.608 |
| `2660a0c6-342b-41b5-97a3-a99297c6bb80.json` | low cached champion | 0 | excluded | 48.789 / 49.638 / 89.214 / 54.941 |
| `88df1af9-ac5e-4958-8b64-768ef5fdb61e.json` | low cached champion | 0 | excluded | 48.805 / 49.823 / 89.345 / 54.866 |
| `ae09444c-68e5-4da0-9b66-c88221ceaa78.json` | low cached champion | 0 | excluded | 48.844 / 49.959 / 89.181 / 54.938 |

Runtime governance status:

- `fresh_runtime_replay_protocol_results = 0`.
- `fresh_champion_required_count = 0`.
- `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED` did not consume rounds.
- Cached champion runtime is excluded from aggregate speed claims and exposed
  as proposal guidance only.
- Saturation/runtime-budget language is still visible in prompt/status
  diagnostics, but no longer appears to be consuming fresh replay rows.
- `SCREENING_RUNTIME_BUDGET_SATURATION` appears for all four CVRP screenings
  with info-level severity and saturation ratios around 0.990-0.995.

This supports the F-2 repair direction, while showing that runtime feedback
still needs cleaner problem-owned interpretation in prompt context.

## Warehouse Candidate Evidence

Warehouse launched with the problem default budget:

```text
python -m scion.cli.main run
  --problem problems/warehouse_delivery/problem.yaml
  --protocol problems/warehouse_delivery/protocol.yaml
  --split problems/warehouse_delivery/split_manifest.yaml
  --seeds problems/warehouse_delivery/seed_ledger.yaml
  --rounds 4
  --disable-early-stop
  --agentic-proposal
```

| Hypothesis | Branch | Stage | Target | Pair W/L/T | Gate evidence | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| `3c0bbad2` | `bad3bcdf` | screening | create `operators/consolidate_subcategory.py` | 20/0/0 | win rate 1.0, median delta 3.0, CI [2.25, 7.5] | queue validation |
| `3c0bbad2` | `bad3bcdf` | validation | same | 18/0/0 | median delta 33.5, CI [12.0, 126.5] | queue frozen |
| `3c0bbad2` | `bad3bcdf` | frozen | same | 12/0/0 | median delta 62.5, CI [13.0, 174.0] | promote |
| `68be29f4` | `64df1e31` | screening | modify `operators/consolidate_subcategory.py` | 5/3/4 | case-gate win rate 0.167, median delta 0.25, CI [-0.5, 0.75] | abandon |

Candidate accounting:

- `3c0bbad2`: formal candidate `fece560e31af4ca5`, replay identity complete.
- `68be29f4`: formal candidate `d5720b4f9510d3e6`, replay identity complete.
- The run had 4 proposal attempts and 2 unique hypotheses. Agentic session
  accounting included 4 session outputs, with two `partial_hypothesis_only`
  sessions plus two completed code sessions. Trace-level LLM accounting showed
  13 calls: 3 hypothesis, 2 code, and 8 tool-selection calls.

Warehouse remains a healthy control for the full Scion path:
screening -> validation -> frozen -> promotion. It also shows a plausible
post-promotion plateau/follow-up failure that should be studied with repeated
campaigns, not a single promotion anecdote.

## Warehouse Runtime Evidence

Configured solver budget is 300s, but actual pairs finish much faster:

| Metrics file | Stage | Pairs | Pair total seconds min/median/max/mean | Runtime ratio |
| --- | --- | --- | --- | --- |
| `c3dfad27-3707-4598-9530-ac2908b7ef88.json` | screening create | 20 | 1.760 / 9.081 / 21.645 / 9.644 | 0.682 |
| `6923d6a6-9793-4333-8161-061818b9d435.json` | validation | 18 | 14.402 / 41.769 / 158.085 / 48.317 | 0.649 |
| `8e85eb16-f8d0-4489-a89f-2ceafb1b7bf4.json` | frozen | 12 | 13.998 / 41.317 / 163.513 / 59.853 | 0.676 |
| `17c76f39-a20d-42e5-ad06-f14a469cbedf.json` | screening modify | 12 | 0.613 / 4.245 / 11.527 / 5.334 | 1.194 |

The 300s cap is not the typical realized runtime because the warehouse solver
also has iteration limits and many instances terminate earlier. Warehouse still
needs A/A runtime/budget calibration, but not because it is slow.

## Prompt And Context Evidence

Manifest counts:

- CVRP: 28 `api_visible_prompt_manifest_*.json` files.
- Warehouse: 13 `api_visible_prompt_manifest_*.json` files.

Block-family character totals across visible prompt sections:

| Problem | General | Governance | Research signal | Source context | Tool observation | Active facts | Tool selection |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CVRP | 380,206 | 35,395 | 228,081 | 315,796 | 262,985 | 271,528 | 891,626 |
| Warehouse | 200,075 | 17,386 | 26,154 | 422 | 27,945 | 0 | 244,518 |

CVRP prompt sizes remain much larger:

- CVRP hypothesis prompts observed around 118k-186k chars, with some
  `Compact Research Signals` sections truncated.
- The CVRP subagent audit estimated medians around 148.8k chars for hypothesis,
  110.6k chars for target-intent, and 112.3k chars for code prompts.
- CVRP code prompts observed around 109k-130k chars and did include source
  context / current champion research code / current branch code sections.
- All four CVRP code sessions had full target-file source visibility and
  integration-file visibility.
- Cross-branch research map sections remain visible in the 5k-18k char range.
- Runtime feedback sections remain visible in the 2.8k-8.6k char range.
- Target-intent prompts still lack compact research signals.
- Warehouse hypothesis prompts were smaller, around 39k-48k chars, and code
  prompts were around 54k-72k chars. Code-stage source visibility was adequate:
  create code prompts included champion code and reference files, while modify
  code prompts included full target-file source.

Context conclusion:

- Source visibility is not absent and should not be compressed away.
- The remaining issue is signal density: CVRP still lacks a compact
  problem-owned diagnostics layer that puts per-case residual opportunity,
  noise/MDE facts, and mechanism-effect ranking ahead of generic governance
  and broad cross-branch material.
- Target-intent and hypothesis prompts should not rely on generic
  `research_signal_ratio` alone; cross-branch map and real problem-domain
  diagnostics need separate accounting.

## Phase 0 Conclusions

1. The experiments are complete and valid as a Phase 0 evidence baseline.
2. Warehouse confirms the generic Scion promotion path still works after the
   measurement/runtime/context repair slice.
3. CVRP still reproduces the audit's low-SNR screening failure: useful pair
   movement is present, but case-level win-rate evidence does not pass and no
   validation/frozen evidence is produced.
4. F-2 runtime governance appears improved: no fresh runtime replay rows were
   consumed, and cached runtime aggregates were excluded from speed claims.
5. F-3, lifecycle depth, and problem-domain context remain unresolved.
6. The next phase should be formal A/A calibration for CVRP and warehouse
   before any further gate/lifecycle tuning or campaign budget expansion.

## Branch Research Notes

- CVRP produced one same-mechanism `destroy_repair.py` follow-up on branch
  `c9952e4e`, but the overall shape remained shallow: max branch depth was 2
  with distribution `{1: 2, 2: 1}`. The run included one abandoned
  `local_search.py` branch, one two-screening destroy/repair branch, and one
  new `scheduler.py` branch.
- CVRP cross-branch plumbing existed but transfer was weak: cross-branch map
  seen count 4, branch lesson records 7, lesson usage present 4, usage
  satisfied 1, semantic mismatches 2, weak-positive transfer 0.
- Warehouse branch depth distribution was `{1: 1, 3: 1}`. Branch `bad3bcdf`
  carried the same subcategory-consolidation mechanism through screening,
  validation, frozen, and promotion. Branch `64df1e31` was a one-step modify
  follow-up that was abandoned after marginal quality and runtime slowdown.
- Warehouse cross-branch observability was present but not yet strong transfer
  evidence: branch lessons were recorded, but borrowed/weak-positive transfer
  counts were zero in the subagent audit.

## Required Next Step

Proceed to Phase 1 from `scion/TASK.md`: run formal champion-vs-champion A/A
calibration for both CVRP and warehouse, producing MDE, false-positive win-rate,
case/seed noise, practical-delta detectability, and runtime-profile reports.
