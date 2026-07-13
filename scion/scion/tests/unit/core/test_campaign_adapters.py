from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

from scion.config.problem import ProtocolConfig
from scion.core.campaign_adapters import _evaluation_orchestrator_for
from scion.core.decision_coordinator import DecisionCoordinator


def test_lazy_evaluation_orchestrator_reuses_production_owner_fields() -> None:
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
        _require_experiment_protocol=True,
    )

    orchestrator = _evaluation_orchestrator_for(owner)

    assert orchestrator.require_experiment_protocol is True
    assert orchestrator.decision_coordinator is owner._decision_coordinator
