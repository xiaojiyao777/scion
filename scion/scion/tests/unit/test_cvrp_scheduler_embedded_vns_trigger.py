from __future__ import annotations

from types import SimpleNamespace

from scion.problems.cvrp.policies.baseline_modules import scheduler


def _solver() -> scheduler._ALNSVNSSolver:
    return scheduler._ALNSVNSSolver(
        time_limit=30,
        destroy_ratio=(0.1, 0.4),
        segment_length=100,
        reaction_factor=0.1,
        vns_max_no_improve=5000,
        use_vns=True,
        cw_threshold=1500,
        vns_threshold=1200,
        alns_threshold=2000,
        max_destroy_customers=200,
        max_routes=None,
        context=SimpleNamespace(),
    )


def test_embedded_vns_early_protect_then_cadence2(monkeypatch) -> None:
    monkeypatch.setattr(scheduler, "ENABLE_EMBEDDED_VNS", True)
    monkeypatch.setattr(scheduler, "EMBEDDED_VNS_CADENCE", 2)
    monkeypatch.setattr(scheduler, "EMBEDDED_VNS_EARLY_ALWAYS_ITERATIONS", 8)
    monkeypatch.setattr(scheduler, "EMBEDDED_VNS_RUN_ON_REPAIR_IMPROVEMENT", True)
    solver = _solver()
    instance = SimpleNamespace(customer_count=151)
    current = SimpleNamespace(total_cost=1000.0)
    best = SimpleNamespace(total_cost=995.0)

    assert solver._should_run_embedded_vns(
        instance,
        iteration=1,
        candidate_after_repair_distance=1010.0,
        current=current,
        best=best,
    )
    assert not solver._should_run_embedded_vns(
        instance,
        iteration=9,
        candidate_after_repair_distance=1010.0,
        current=current,
        best=best,
    )
    assert solver._should_run_embedded_vns(
        instance,
        iteration=10,
        candidate_after_repair_distance=1010.0,
        current=current,
        best=best,
    )
    assert solver._should_run_embedded_vns(
        instance,
        iteration=9,
        candidate_after_repair_distance=990.0,
        current=current,
        best=best,
    )
