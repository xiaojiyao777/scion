# Campaign Reopen Active-Branch Restore Repair

Date: 2026-06-18
Branch: `codex/v04-evidence-repair-plan`

## Purpose

The next CVRP checkpoint needs a real same-mechanism follow-up on the active
`demand_slack_regret_insertion` branch. Reopening or copying an existing
campaign must therefore preserve the persisted current champion, active branch
state, mechanism/evidence summary, and branch workspace.

Before this repair, `scion.cli.main run --campaign-dir <existing>` could open
the existing `scion.db`, but campaign composition rebuilt only fresh in-memory
branch/controller state. It also skipped installing the persisted current
champion into the reopened manager. A copied/resumed campaign could therefore
look operational while silently losing the branch trajectory needed for
evidence-backed continuation.

## Change

- Campaign composition now restores all persisted active branches into the
  in-memory `BranchController` when a campaign directory is reopened.
- If an active branch uses `branch_workspace` and its workspace directory still
  exists, the reopened manager restores that workspace mapping.
- For each restored active branch, campaign composition restores the latest
  durable `status=active` hypothesis record and reconstructs the in-memory
  hypothesis proposal view needed by evaluation and continuation steps.
- When a prior screening artifact exists, campaign composition restores the
  in-memory patch proposal from `candidate.patch.json` so resumed evaluation
  can preserve formal candidate replay identity instead of emitting a
  `missing_patch` artifact omission.
- If a current champion already exists in `ChampionStore`, the reopened manager
  installs that persisted champion instead of keeping a freshly constructed v1
  in memory.
- When a campaign directory has been copied, the reopened manager re-anchors
  the in-memory current champion path to the copied local
  `champions/champion_vN` snapshot only when the local snapshot exists and its
  hash matches the persisted champion hash.

This repair does not change Decision, Protocol, promotion policy, lifecycle
gates, generic budgets, or problem semantics.

## Field Smoke

The first copied-campaign WSL resume smoke after branch/workspace restoration
was invalid: the restored branch reached scheduling, but eval failed closed with
`no hypothesis for eval step - abandoning`. That run produced no Protocol rows
and is not CVRP evidence. It exposed the active-hypothesis restore gap covered
by this repair.

The next valid copied-campaign WSL resume completed formal screening, but its
reconciled candidate artifact was omitted with `missing_patch` /
`missing_replay_identity`, because the patch object had not been restored into
memory. That run remains valid screening evidence, but it exposed the
patch-recovery gap covered by this repair.

## Acceptance

- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_campaign_basics_continue.py::TestCampaignBasics::test_reopened_campaign_restores_champion_active_branch_and_workspace`
  - Result: `1 passed`.
- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_campaign_basics_continue.py scion/scion/tests/test_lineage_sprint3.py scion/scion/tests/test_campaign_control_boundaries.py`
  - Result: `53 passed`.
- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion python -m py_compile scion/scion/core/branch.py scion/scion/core/campaign_composition.py scion/scion/tests/test_campaign_basics_continue.py`
  - Result: passed.
- `git diff --check`
  - Result: passed.

## Next Field Check

Copy the latest WSL CVRP pivot campaign to a new run directory and run one more
agentic round against the copied `campaign` directory. Acceptance is that the
follow-up continues from the active `demand_slack_regret_insertion` evidence
surface, targets the `CMT2`/`CMT4` losses, and keeps A/E/P plus M/X behavior
visible in the resulting artifact.
