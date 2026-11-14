"""Tests for the remaining Sprint Q0 technical-debt cleanup."""
from __future__ import annotations

import os


# ---------------------------------------------------------------------------
# W14: Tech debt cleanup
# ---------------------------------------------------------------------------

class TestTechDebtCleanup:
    def test_state_leak_removed(self) -> None:
        state_leak_path = os.path.join(
            os.path.dirname(__file__), os.pardir, "verification", "state_leak.py"
        )
        assert not os.path.exists(state_leak_path), "state_leak.py should be removed"

    def test_splits_weight_deprecated(self) -> None:
        import inspect
        from scion.protocol.evaluation import compute_delta
        src = inspect.getsource(compute_delta)
        assert "DEPRECATED" in src
