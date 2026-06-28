from __future__ import annotations

import json
from pathlib import Path

from scion.core.protocol_case_delta_projection import protocol_case_level_deltas


def test_protocol_case_level_deltas_projects_public_metric_pairs(
    tmp_path: Path,
) -> None:
    campaign = tmp_path / "campaign"
    metrics_dir = campaign / "metrics"
    metrics_dir.mkdir(parents=True)
    (metrics_dir / "screening.json").write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "case": "cvrplib/CMT/CMT2.vrp",
                        "seed": 11,
                        "comparison": "loss",
                        "delta": -20.0,
                        "metric_deltas": {
                            "fleet_violation": 0.0,
                            "total_distance": -20.0,
                        },
                    },
                    {
                        "case": "cvrplib/CMT/CMT2.vrp",
                        "seed": 29,
                        "comparison": "win",
                        "delta": 8.0,
                        "metric_deltas": {
                            "fleet_violation": 0.0,
                            "total_distance": 8.0,
                        },
                    },
                    {
                        "case": "cvrplib/CMT/CMT4.vrp",
                        "seed": 11,
                        "comparison": "tie",
                        "delta": 0.0,
                        "metric_deltas": {
                            "fleet_violation": 0.0,
                            "total_distance": 0.0,
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    projection = protocol_case_level_deltas(
        {
            "raw_metrics_public_ref": "metrics/screening.json",
            "raw_metrics_ref": "/private/internal.json",
        },
        campaign_path=campaign,
    )

    assert projection["cvrplib/CMT/CMT2.vrp"]["metric_delta_medians"][
        "total_distance"
    ] == -6.0
    assert projection["cvrplib/CMT/CMT2.vrp"]["comparison_counts"] == {
        "loss": 1,
        "win": 1,
    }
    assert projection["cvrplib/CMT/CMT2.vrp"]["sample_pairs"][0] == {
        "seed": 11,
        "comparison": "loss",
        "delta": -20.0,
        "metric_deltas": {
            "fleet_violation": 0.0,
            "total_distance": -20.0,
        },
    }
    assert projection["cvrplib/CMT/CMT4.vrp"]["metric_delta_medians"][
        "total_distance"
    ] == 0.0


def test_protocol_case_level_deltas_ignores_private_or_unsafe_refs(
    tmp_path: Path,
) -> None:
    campaign = tmp_path / "campaign"
    campaign.mkdir()

    assert (
        protocol_case_level_deltas(
            {"raw_metrics_ref": "/tmp/private-screening.json"},
            campaign_path=campaign,
        )
        == {}
    )
    assert (
        protocol_case_level_deltas(
            {"raw_metrics_public_ref": "../outside.json"},
            campaign_path=campaign,
        )
        == {}
    )
