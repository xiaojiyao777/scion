"""Problem-owned defaults for postrun inventory loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scion.postrun.inventory.loader import (
    PostrunArtifactInventoryLoader,
    build_inventory,
)

PROBLEM_LAUNCHER_STATUS_KEYS = ("warehouse_data_root_missing",)
PROBLEM_PRE_CAMPAIGN_INFRA_FAILURE_KEYS = ("warehouse_data_root_missing",)


def default_prepared_handoff_ports_by_family() -> dict[str, Any]:
    from scion.problems.cvrp.postrun_handoff import CvrpPreparedHandoffReviewPort
    from scion.problems.warehouse_delivery.postrun_handoff import (
        WarehousePreparedHandoffReviewPort,
    )

    return {
        "cvrp": CvrpPreparedHandoffReviewPort(),
        "warehouse_delivery": WarehousePreparedHandoffReviewPort(),
    }


def default_postrun_inventory_loader() -> PostrunArtifactInventoryLoader:
    return PostrunArtifactInventoryLoader(
        prepared_handoff_ports=default_prepared_handoff_ports_by_family(),
        extra_launcher_status_keys=PROBLEM_LAUNCHER_STATUS_KEYS,
        extra_pre_campaign_infra_failure_keys=PROBLEM_PRE_CAMPAIGN_INFRA_FAILURE_KEYS,
    )


def build_problem_inventory(run_root: Path | str) -> dict[str, Any]:
    return build_inventory(
        run_root,
        prepared_handoff_ports=default_prepared_handoff_ports_by_family(),
        extra_launcher_status_keys=PROBLEM_LAUNCHER_STATUS_KEYS,
        extra_pre_campaign_infra_failure_keys=PROBLEM_PRE_CAMPAIGN_INFRA_FAILURE_KEYS,
    )
