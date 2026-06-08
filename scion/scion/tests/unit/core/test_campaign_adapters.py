from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

from scion.config.problem import ProtocolConfig
from scion.core.campaign_adapters import _evaluation_orchestrator_for
from scion.core.decision_coordinator import DecisionCoordinator
from scion.core.features import BudgetState


def test_lazy_evaluation_orchestrator_reuses_production_owner_fields() -> None:
    frozen_budget_ledger = SimpleNamespace()
    zero_win_streaks = {"branch-a": 2}
    telemetry_diagnostic_streaks = {"branch-b": 1}

    owner = SimpleNamespace(
        _evaluation_orchestrator=None,
        _branch_ctrl=SimpleNamespace(),
        _champion_lock=nullcontext(),
        _champion=SimpleNamespace(code_snapshot_path="/tmp/champion"),
        _branch_patches={},
        _branch_workspaces={},
        _branch_hypotheses={},
        _branch_current_hypothesis={},
        _experiment_protocol=None,
        _budget=BudgetState(total=10, used=0),
        _decision_coordinator=DecisionCoordinator(config=ProtocolConfig()),
        _decision_reason_codes={},
        _campaign_id="campaign",
        _registry=None,
        _materializer=None,
        _hyp_store=None,
        _persist_branch_state=lambda _branch_id: None,
        _begin_status_progress=lambda **_kwargs: None,
        _end_status_progress=lambda: None,
        _handle_failure=lambda _branch, _failure: None,
        _n_experiments=0,
        _telemetry_failed_experiments=0,
        _soft_abandon_streak=0,
        _decision_lifecycle_actions={},
        _branch_zero_win_streaks=zero_win_streaks,
        _branch_telemetry_diagnostic_streaks=telemetry_diagnostic_streaks,
        _frozen_budget_ledger=frozen_budget_ledger,
        _require_experiment_protocol=True,
    )

    orchestrator = _evaluation_orchestrator_for(owner)

    assert orchestrator.frozen_budget_ledger is frozen_budget_ledger
    assert orchestrator.require_experiment_protocol is True
    assert orchestrator.branch_zero_win_streaks is zero_win_streaks
    assert (
        orchestrator.branch_telemetry_diagnostic_streaks
        is telemetry_diagnostic_streaks
    )
