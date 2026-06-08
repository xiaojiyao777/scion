# Explore Step Pipeline

## Scope

Current source reviewed:

- `scion/scion/core/explore_step/pipeline.py`
- `scion/scion/core/explore_step/verification.py`
- `scion/scion/core/explore_step/common.py`
- `scion/scion/core/explore_step/events.py`
- `scion/scion/core/explore_step/material_difference.py`
- `scion/scion/core/explore_step_pipeline.py`
- selected call sites in `campaign_composition.py` and `campaign_adapters.py`
- selected helper source in `proposal/context/branch_followup.py`

## Current Understanding

`ExploreStepPipeline` owns the new-candidate path:

```text
pending hypothesis retry or new hypothesis
  -> hypothesis Contract
  -> material_difference pre-code guard
  -> code generation
  -> branch continuation / repair-focus policy
  -> patch Contract
  -> workspace setup
  -> apply patch
  -> VerificationGate
  -> screening/evaluation dispatch
  -> DecisionFinalizer
  -> StepRecord
```

The old `scion/scion/core/explore_step_pipeline.py` is now a compatibility
facade that re-exports the package implementation.

## Positive Boundary Observations

- Proposal/code/contract/workspace/verification early exits record `StepRecord`
  entries with `decision=None`, so pre-Decision failures remain distinguishable
  from deterministic Decision outcomes.
- `material_difference` is enforced before code generation when branch/session
  metadata requires it. This keeps cross-branch novelty pressure in tainted
  proposal guidance rather than Decision features.
- Heavy verification failures under top-level `solver_design` style surfaces
  are candidate-scoped. A single invalid solver implementation rejects that
  candidate without globally blacklisting the entire research boundary.

## Risks And Findings

### F-EXPLORE-001 [P1] `step_history` is not wired into `ExploreStepPipeline`

`ExploreStepPipeline` calls `getattr(self, "step_history", ())` in at least two
important places:

- branch continuation / repair-focused patch policy;
- `branch_current_file_sources(...)` passed as `base_file_overrides` to patch
  Contract.

The production construction in `campaign_composition.py` does not pass
`step_history` into `ExploreStepPipeline`. The compatibility construction in
`campaign_adapters.py` also does not pass it.

Evidence:

- `scion/scion/core/explore_step/pipeline.py:678`
- `scion/scion/core/explore_step/pipeline.py:755`
- `scion/scion/core/campaign_composition.py:459`
- `scion/scion/core/campaign_adapters.py:221`
- `scion/scion/proposal/context/branch_followup.py:288`

Impact:

- Patch-level continuation policy may miss same-branch prior mechanism ids,
  touched files, or branch-created files.
- Patch Contract may not see branch-current file content for files created or
  modified earlier on the same branch.
- This is most likely to matter for non-clean branches, weak-positive follow-up,
  same-mechanism repair, and multi-file `solver_design` edits.

Suggested fix direction:

- Add `step_history: Sequence[StepRecord]` or a `get_step_history` callback to
  `ExploreStepPipeline`.
- Wire it from `owner._step_history` in both `campaign_composition.py` and the
  compatibility adapter.
- Add a regression test that runs through the production-style construction and
  proves `base_file_overrides` contains branch-current file content.

### F-EXPLORE-002 [P2] Patch Contract failure may consume an effective round

When patch Contract fails, the returned `StepResult` uses
`counts_toward_max_rounds=not retry_attempt` and `attempt_kind="screening"` for
ordinary non-repeated failures.

Evidence:

- `scion/scion/core/explore_step/pipeline.py:813`

Why this needs confirmation:

- In the v3/v0.4 control model, pre-protocol Contract failure is not formal
  screening evidence and should normally not count as an effective screened
  round.
- Other proposal/code quality failures often use `counts_toward_max_rounds=False`.

Impact:

- A campaign can spend effective round budget before any candidate reaches
  Verification/Protocol.
- Run summaries may overstate screened progress if these failures are counted
  as effective rounds.

Follow-up:

- Check `CampaignLoop` accounting tests around patch Contract failures.
- Decide whether this is intentional budget pressure for bad patch generation
  or a drift from formal screened-round semantics.

## Open Questions

- Should `ExploreStepPipeline` expose `step_history` directly, or should it take
  small provider callbacks such as `branch_current_file_sources_for(branch)` and
  `branch_continuation_history_for(branch)`?
- Should repeated patch Contract failures be separated from ordinary Contract
  failures in loop accounting and status?
- Does `attempt_fix` for light verification failure need the same branch-current
  base-file override semantics as primary patch Contract?
