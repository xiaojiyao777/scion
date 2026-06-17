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
    monkeypatch.setattr(scheduler, "EMBEDDED_VNS_MIN_RUNTIME_SHARE", 0.0)
    monkeypatch.setattr(scheduler, "EMBEDDED_VNS_RUN_ON_REPAIR_IMPROVEMENT", True)
    solver = _solver()
    instance = SimpleNamespace(customer_count=151)
    current = SimpleNamespace(total_cost=1000.0)
    best = SimpleNamespace(total_cost=995.0)

    assert solver._should_run_embedded_vns(
        instance,
        iteration=1,
        alns_elapsed_ms_before=0,
        embedded_vns_runtime_ms=0,
        candidate_after_repair_distance=1010.0,
        current=current,
        best=best,
    )
    assert not solver._should_run_embedded_vns(
        instance,
        iteration=9,
        alns_elapsed_ms_before=1000,
        embedded_vns_runtime_ms=800,
        candidate_after_repair_distance=1010.0,
        current=current,
        best=best,
    )
    assert solver._should_run_embedded_vns(
        instance,
        iteration=10,
        alns_elapsed_ms_before=1000,
        embedded_vns_runtime_ms=800,
        candidate_after_repair_distance=1010.0,
        current=current,
        best=best,
    )
    assert solver._should_run_embedded_vns(
        instance,
        iteration=9,
        alns_elapsed_ms_before=1000,
        embedded_vns_runtime_ms=800,
        candidate_after_repair_distance=990.0,
        current=current,
        best=best,
    )


def test_embedded_vns_runtime_share_floor_precedes_cadence(monkeypatch) -> None:
    monkeypatch.setattr(scheduler, "ENABLE_EMBEDDED_VNS", True)
    monkeypatch.setattr(scheduler, "EMBEDDED_VNS_CADENCE", 2)
    monkeypatch.setattr(scheduler, "EMBEDDED_VNS_EARLY_ALWAYS_ITERATIONS", 0)
    monkeypatch.setattr(scheduler, "EMBEDDED_VNS_MIN_RUNTIME_SHARE", 0.60)
    monkeypatch.setattr(scheduler, "EMBEDDED_VNS_RUN_ON_REPAIR_IMPROVEMENT", True)
    solver = _solver()
    instance = SimpleNamespace(customer_count=151)
    current = SimpleNamespace(total_cost=1000.0)
    best = SimpleNamespace(total_cost=995.0)

    assert solver._should_run_embedded_vns(
        instance,
        iteration=1,
        alns_elapsed_ms_before=0,
        embedded_vns_runtime_ms=0,
        candidate_after_repair_distance=1010.0,
        current=current,
        best=best,
    )
    assert solver._should_run_embedded_vns(
        instance,
        iteration=9,
        alns_elapsed_ms_before=1000,
        embedded_vns_runtime_ms=500,
        candidate_after_repair_distance=1010.0,
        current=current,
        best=best,
    )
    assert not solver._should_run_embedded_vns(
        instance,
        iteration=9,
        alns_elapsed_ms_before=1000,
        embedded_vns_runtime_ms=700,
        candidate_after_repair_distance=1010.0,
        current=current,
        best=best,
    )


def test_embedded_vns_runtime_share_cap_blocks_non_rescued_triggers(
    monkeypatch,
) -> None:
    monkeypatch.setattr(scheduler, "ENABLE_EMBEDDED_VNS", True)
    monkeypatch.setattr(scheduler, "EMBEDDED_VNS_CADENCE", 2)
    monkeypatch.setattr(scheduler, "EMBEDDED_VNS_EARLY_ALWAYS_ITERATIONS", 0)
    monkeypatch.setattr(scheduler, "EMBEDDED_VNS_MIN_RUNTIME_SHARE", 0.70)
    monkeypatch.setattr(scheduler, "EMBEDDED_VNS_MAX_RUNTIME_SHARE", 0.70)
    monkeypatch.setattr(
        scheduler,
        "EMBEDDED_VNS_CAP_REPAIR_IMPROVEMENT_RESCUE",
        False,
    )
    monkeypatch.setattr(scheduler, "EMBEDDED_VNS_RUN_ON_REPAIR_IMPROVEMENT", True)
    solver = _solver()
    instance = SimpleNamespace(customer_count=151)
    current = SimpleNamespace(total_cost=1000.0)
    best = SimpleNamespace(total_cost=995.0)

    assert solver._should_run_embedded_vns(
        instance,
        iteration=9,
        alns_elapsed_ms_before=1000,
        embedded_vns_runtime_ms=500,
        candidate_after_repair_distance=1010.0,
        current=current,
        best=best,
    )
    assert not solver._should_run_embedded_vns(
        instance,
        iteration=10,
        alns_elapsed_ms_before=1000,
        embedded_vns_runtime_ms=700,
        candidate_after_repair_distance=990.0,
        current=current,
        best=best,
    )


def test_embedded_vns_runtime_share_cap_allows_repair_improvement_rescue(
    monkeypatch,
) -> None:
    monkeypatch.setattr(scheduler, "ENABLE_EMBEDDED_VNS", True)
    monkeypatch.setattr(scheduler, "EMBEDDED_VNS_CADENCE", 2)
    monkeypatch.setattr(scheduler, "EMBEDDED_VNS_EARLY_ALWAYS_ITERATIONS", 0)
    monkeypatch.setattr(scheduler, "EMBEDDED_VNS_MIN_RUNTIME_SHARE", 0.70)
    monkeypatch.setattr(scheduler, "EMBEDDED_VNS_MAX_RUNTIME_SHARE", 0.70)
    monkeypatch.setattr(
        scheduler,
        "EMBEDDED_VNS_CAP_REPAIR_IMPROVEMENT_RESCUE",
        True,
    )
    monkeypatch.setattr(scheduler, "EMBEDDED_VNS_RUN_ON_REPAIR_IMPROVEMENT", True)
    solver = _solver()
    instance = SimpleNamespace(customer_count=151)
    current = SimpleNamespace(total_cost=1000.0)
    best = SimpleNamespace(total_cost=995.0)

    assert solver._should_run_embedded_vns(
        instance,
        iteration=9,
        alns_elapsed_ms_before=1000,
        embedded_vns_runtime_ms=700,
        candidate_after_repair_distance=990.0,
        current=current,
        best=best,
    )
    assert not solver._should_run_embedded_vns(
        instance,
        iteration=10,
        alns_elapsed_ms_before=1000,
        embedded_vns_runtime_ms=700,
        candidate_after_repair_distance=1010.0,
        current=current,
        best=best,
    )


def test_embedded_vns_diagnostic_records_direct_effect() -> None:
    records = []

    class Context:
        def record_phase(self, phase, elapsed_ms):
            records.append(("phase", phase, elapsed_ms))

        def record_move(self, phase, **kwargs):
            records.append(("move", phase, kwargs))

    solver = _solver()
    solver.context = Context()

    solver._record_embedded_vns_diagnostic(
        "adaptive_embedded_vns_share70_trigger",
        phase_elapsed_ms=123,
        before_vns_distance=1000.0,
        after_vns_distance=990.0,
        best=SimpleNamespace(total_cost=995.0),
    )

    assert records == [
        ("phase", "adaptive_embedded_vns_share70_trigger", 123),
        (
            "move",
            "adaptive_embedded_vns_share70_trigger",
            {
                "attempted": 1,
                "accepted": 1,
                "delta": 10.0,
                "best_improved": 1,
            },
        ),
    ]
