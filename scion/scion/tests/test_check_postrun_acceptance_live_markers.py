from __future__ import annotations

import importlib.util
from pathlib import Path


SCION_DIR = Path(__file__).parents[2]
CHECK_PATH = SCION_DIR / "tools" / "check_postrun_acceptance.py"

CHECK_SPEC = importlib.util.spec_from_file_location(
    "check_postrun_acceptance",
    CHECK_PATH,
)
assert CHECK_SPEC is not None
check_tool = importlib.util.module_from_spec(CHECK_SPEC)
assert CHECK_SPEC.loader is not None
CHECK_SPEC.loader.exec_module(check_tool)


def test_live_postrun_marker_counts_overlay_stale_inventory(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-root"
    run_root.mkdir()
    (run_root / "run.log").write_text(
        "\n".join(
            [
                "POSTRUN_REPORTS_EXIT_STATUS:0",
                "POSTRUN_READINESS_EXIT_STATUS:0",
                "POSTRUN_REPORTS_FINISHED_AT:2026-06-29T00:01:00Z",
                "",
            ]
        ),
        encoding="utf-8",
    )
    inventory = {
        "launcher": {
            "run_log_markers": {
                "POSTRUN_REPORTS_STARTED_AT": 1,
                "POSTRUN_REPORT_DIR": 1,
            },
            "exit_markers": {},
        }
    }

    updated = check_tool._with_live_launcher_markers(run_root, inventory)

    assert updated is not inventory
    markers = updated["launcher"]["run_log_markers"]
    assert markers["POSTRUN_REPORTS_STARTED_AT"] == 1
    assert markers["POSTRUN_REPORT_DIR"] == 1
    assert markers["POSTRUN_REPORTS_EXIT_STATUS"] == 1
    assert markers["POSTRUN_REPORTS_FINISHED_AT"] == 1
    assert markers["POSTRUN_READINESS_EXIT_STATUS"] == 1
