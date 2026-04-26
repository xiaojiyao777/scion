from types import SimpleNamespace

from scion.proposal.context_manager import _build_objective_steering


def test_objective_steering_prefers_lower_priority_when_higher_priority_is_stable():
    objectives = [
        SimpleNamespace(name="splits", priority=1),
        SimpleNamespace(name="cost", priority=2),
    ]
    stats = {
        "splits": {
            "n": 20,
            "pos": 0,
            "neg": 0,
            "tie": 20,
            "decisive_wins": 0,
            "decisive_losses": 0,
        },
        "cost": {
            "n": 20,
            "pos": 8,
            "neg": 5,
            "tie": 7,
            "decisive_wins": 8,
            "decisive_losses": 5,
        },
    }

    text = _build_objective_steering(
        objective_specs=objectives,
        objective_stats=stats,
        mode="lexicographic",
    )

    assert "targeting cost" in text
    assert "preserving splits" in text


def test_objective_steering_keeps_high_priority_when_it_still_moves():
    objectives = [
        SimpleNamespace(name="splits", priority=1),
        SimpleNamespace(name="cost", priority=2),
    ]
    stats = {
        "splits": {
            "n": 20,
            "pos": 4,
            "neg": 3,
            "tie": 13,
            "decisive_wins": 4,
            "decisive_losses": 3,
        },
        "cost": {
            "n": 20,
            "pos": 8,
            "neg": 5,
            "tie": 7,
            "decisive_wins": 8,
            "decisive_losses": 5,
        },
    }

    text = _build_objective_steering(
        objective_specs=objectives,
        objective_stats=stats,
        mode="lexicographic",
    )

    assert text == ""
