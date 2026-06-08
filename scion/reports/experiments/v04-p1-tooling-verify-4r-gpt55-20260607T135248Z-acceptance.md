# v0.4 P1 Tooling Verify 4R Acceptance Addendum

Date: 2026-06-07

Run root: `/home/clawd/research/scion-experiments/v04-p1-tooling-verify-4r-gpt55-20260607T135248Z-claw`

Source reports:

- Research-quality analysis: `scion/reports/experiments/v04-p1-tooling-verify-4r-gpt55-20260607T135248Z-analysis.md`
- Tooling audit: `scion/reports/experiments/v04-p1-tooling-verify-4r-gpt55-20260607T135248Z-tooling-audit.md`

## Acceptance Principle

This 4R run is not accepted on the basis of lower token use. Lower
`tool_selection` calls and input tokens are only secondary health indicators.
The real acceptance question is whether Scion preserved enough research context
for the agent to do algorithmic research while wasting less LLM planner capacity
on deterministic control flow.

The post-4R gate is therefore:

1. The run must be valid and complete.
2. Tooling changes must not remove required research context or introduce
   quality/repair blockers.
3. Hypothesis and code phases must still see problem mechanics, active solver
   facts, target files, relevant source, screening/runtime feedback, and
   cross-branch lessons.
4. Agent research quality must remain credible: hypotheses should use prior
   failures or weak signals, create mechanism-level differences, and produce
   auditable evidence/lifecycle behavior.

If context is insufficient, lower calls/tokens are a failure. If context is
sufficient but research remains weak, the next optimization target is
evidence/lifecycle/branch-follow-up, not more token reduction.

## Gate Results

| Gate | Result | Evidence |
| --- | --- | --- |
| Run validity | PASS | `run_complete=true`, `run_validity_status=valid`, `completed_requested_rounds=true`, 4 effective screening rounds. |
| Proposal accounting | PASS | 4 proposal attempts, 4 formal screened candidates, 4 protocol-evaluated candidates. No retries inflated the run. |
| Quality/repair blockers | PASS | `quality_blocks=0`, model repair=0, telemetry failed/repairable attempts=0. |
| Tooling overhead path | PASS with audit caveat | `tool_selection` dropped from 47 to 18 calls; skipped `stop` entries dropped from 12 to 0; all 8 sessions had non-empty deterministic prefetch plan ids. |
| Final prompt context visibility | PASS | Beauvoir found deterministic prefetch result ids in `compact_transcript`, `evidence_used`, prompt manifests, and final prompt visibility. Source/surface visibility remained available for target files and integration files. |
| Observation-ledger persistence | FAIL for formal audit | Deterministic prefetch observations reached final prompts but were not persisted in `observation_ledger.observations` or `observation_ledger.read_receipts`. This is an audit persistence gap, not a prompt visibility loss. |
| Agent research quality | PARTIAL | The agent used prior no-effect and weak signals, changed mechanism families, and produced a Round 4 pair-level weak positive. But there was no validation/frozen/promotion, Round 3 had a pair-level loss, and Round 4 runtime evidence was excluded by fresh-champion policy. |
| Evidence/lifecycle support for next scale | FAIL for formal 8R | Discarded candidates do not retain canonical patch artifacts, weak-positive code/evidence retention is ambiguous, and fresh champion runtime replay is not automatically queued when weak-positive or diagnostic evidence appears. |

## Research-Quality Finding

Tesla's report supports a cautious but important conclusion: Scion's agent is
not merely producing random edits. Across the four rounds it used prior evidence:

- Round 1 tried VNS whole-route absorption.
- Round 2 reacted to Round 1 no-effect/runtime saturation by moving route
  absorption into post-repair compaction.
- Round 3 reacted to repeated compaction no-effect by changing repair scoring.
- Round 4 reacted to local-search/repair weakness by changing acceptance
  dynamics and produced one pair-level win with no pair-level losses.

This means the context/tooling optimization did not obviously blind the agent.
The research path is coherent and mechanism-level. The problem is that Scion's
evidence and lifecycle machinery does not yet make the best weak signal easy to
follow up:

- Round 3 had phase-level telemetry positives but a final pair-level loss.
- Round 4 had a pair-level weak positive but case-level ties and excluded
  runtime aggregate due `fresh_champion_required` / `low_cached_champion`.
- Round 4 was marked `weak_positive_followup=true`, but current head was still
  `discarded`, which is easy to misread unless code retention and evidence
  retention are explicitly separated.

Therefore, the bottleneck exposed by this 4R is not primarily LLM tool-choice
cost. The bottleneck is evidence retention, weak-positive follow-up, fresh
runtime replay, and lifecycle/status semantics.

## Tooling Finding

Beauvoir's tooling audit validates the intended P1 control-flow change:

- `tool_selection` calls fell from 47 to 18.
- `tool_selection` input tokens fell from 688,585 to 232,381.
- All 8 sessions had non-empty deterministic prefetch plan ids.
- Current artifacts had 0 `stop` entries and 0 skipped entries.
- Proposal attempts and formal screened candidates did not regress.

This should not be interpreted as "lower token use is success." The correct
interpretation is narrower: default deterministic prefetches no longer burn LLM
planner calls, while prompt visibility was preserved. Keep this behavior.

The remaining tooling issue is audit persistence: deterministic prefetch entries
must become first-class `observation_ledger` observations/read receipts, matching
their existing presence in prompt manifests and `evidence_used`.

## 8R Decision

Do not run a formal 8R yet.

The run is valid, and P1 tooling did not show major negative side effects, but
the formal 8R gate is not satisfied because:

1. deterministic prefetch visibility has an observation-ledger persistence gap;
2. weak-positive evidence is not cleanly connected to code/evidence retention;
3. fresh champion runtime replay is not queued for weak-positive or diagnostic
   candidates;
4. discarded formally screened candidates do not preserve canonical patch/diff
   artifacts for branch-level audit.

An exploratory 8R could be run with an explicit waiver, but it should not be
used as a formal readiness signal. The next formal step should be another 4R
after the mechanism fixes below.

## Required Next Fixes Before Formal 8R

1. Persist deterministic prefetch observations into
   `observation_ledger.observations` and `observation_ledger.read_receipts`.
2. Retain canonical patch/diff artifacts for every formally screened candidate,
   including discarded heads.
3. Make weak-positive branch cards/status separate code retention, evidence
   retention, and follow-up policy.
4. Queue fresh champion runtime replay when screening produces pair-level
   win/no-loss or actionable loss diagnostics.
5. Add phase-level causal summaries to proposal feedback, for example local
   phase positive but final objective loss, or acceptance phase positive with
   pair-level win but case-level tie.
6. Adjust smoke activation diagnostics so "smoke coverage weak" is not mistaken
   for "mechanism did not activate" when formal screening later observes
   activation.

After these fixes, rerun 4R first. Only move to 8R if the new 4R is valid,
keeps context visibility, has no quality/repair blockers, and shows that branch
research quality has not degraded.
