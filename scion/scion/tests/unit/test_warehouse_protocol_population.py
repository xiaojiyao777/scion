from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from scion.problems.warehouse_delivery.protocol_population import (
    SCHEMA_VERSION,
    WarehouseProtocolPopulationError,
    main,
    reconcile_warehouse_protocol_population_from_paths,
)


SCION_DIR = Path(__file__).resolve().parents[3]
WAREHOUSE_CONFIG_DIR = SCION_DIR / "problems" / "warehouse_delivery"
PROTOCOL = WAREHOUSE_CONFIG_DIR / "protocol_prod.yaml"
MANIFEST = WAREHOUSE_CONFIG_DIR / "split_manifest_prod.yaml"
EXPECTED_PROTOCOL_VERSION = "3.2-prod"
EXPECTED_MANIFEST_VERSION = "prod-1.1"


def _request_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["request_id"]): row for row in payload["requests"]}


def _small_protocol_payload() -> dict[str, Any]:
    payload = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    payload["screening"].update(
        {
            "n_cases_modify": 1,
            "n_cases_create": 1,
            "expand_to_modify": 1,
            "expand_to_create": 1,
        }
    )
    payload["validation"].update({"n_cases": 1, "expand_to": 1})
    payload["frozen"].update({"n_cases": 1})
    return payload


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )


def _write_small_assets(
    root: Path,
    *,
    screening_path: Path | None = None,
) -> tuple[Path, Path, dict[str, Path]]:
    root.mkdir(parents=True, exist_ok=True)
    cases = {
        "screening": screening_path or root / "screening.json",
        "validation": root / "validation.json",
        "frozen": root / "frozen.json",
        "canary": root / "canary.json",
    }
    for stage, path in cases.items():
        if path == screening_path and path.is_symlink():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(json.dumps({"stage": stage}).encode("utf-8"))
    protocol_path = root / "protocol.yaml"
    manifest_path = root / "manifest.yaml"
    _write_yaml(protocol_path, _small_protocol_payload())
    _write_yaml(
        manifest_path,
        {
            "version": "small-v1",
            "screening": [str(cases["screening"])],
            "validation": [str(cases["validation"])],
            "frozen": [str(cases["frozen"])],
            "canary": [str(cases["canary"])],
        },
    )
    return protocol_path, manifest_path, cases


def test_prod_population_reconcile_records_content_bound_selections() -> None:
    payload = reconcile_warehouse_protocol_population_from_paths(PROTOCOL, MANIFEST)
    requests = _request_map(payload)

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["status"] == "reconciled"
    assert payload["authority"] == "split_manifest_ordered_exact_case_content"
    assert payload["candidate_gate"] is False
    assert payload["decision_features_excluded"] is True
    assert payload["protocol_version"] == EXPECTED_PROTOCOL_VERSION
    assert payload["manifest_version"] == EXPECTED_MANIFEST_VERSION
    assert requests["screening.modify.initial"]["requested"] == 6
    assert requests["screening.create.initial"]["requested"] == 10
    assert requests["screening.modify.expanded"]["requested"] == 14
    assert requests["screening.create.expanded"]["requested"] == 16
    assert requests["screening.create.expanded"]["available"] == 16
    assert requests["screening.create.expanded"]["resolved"] == 16
    assert requests["validation.initial"]["requested"] == 5
    assert requests["validation.expanded"]["requested"] == 5
    assert requests["validation.initial"]["available"] == 5
    assert requests["validation.expanded"]["resolved"] == 5
    assert [
        Path(case["lexical_path"]).name
        for case in requests["frozen.initial"]["selected_case_identities"]
    ] == [
        "instance_prod_fro_x01.json",
        "instance_prod_fro_x04.json",
        "instance_prod_fro_xx03.json",
        "instance_prod_day2.json",
    ]
    for population in payload["populations"]:
        for case in population["cases"]:
            assert case["regular_file"] is True
            assert case["symlink_free"] is True
            assert Path(case["resolved_path"]).is_file()
    for request in payload["requests"]:
        assert request["requested"] == request["resolved"]
        assert request["requested"] == len(request["selected_case_identities"])


def test_reconcile_rejects_silent_protocol_shortfall(tmp_path: Path) -> None:
    protocol_payload = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    protocol_payload["screening"]["expand_to_create"] = 17
    protocol_path = tmp_path / "protocol.yaml"
    _write_yaml(protocol_path, protocol_payload)

    with pytest.raises(
        WarehouseProtocolPopulationError,
        match=(
            r"screening\.create\.expanded requests 17 cases but manifest has "
            r"16 distinct screening cases"
        ),
    ):
        reconcile_warehouse_protocol_population_from_paths(protocol_path, MANIFEST)


def test_reconcile_rejects_duplicate_manifest_identity(tmp_path: Path) -> None:
    protocol_path, manifest_path, cases = _write_small_assets(tmp_path)
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["screening"] = [
        str(cases["screening"]),
        str(cases["screening"]),
    ]
    _write_yaml(manifest_path, manifest)

    with pytest.raises(
        WarehouseProtocolPopulationError,
        match="screening manifest contains duplicate case ids",
    ):
        reconcile_warehouse_protocol_population_from_paths(
            protocol_path,
            manifest_path,
        )


def test_reconcile_rejects_expansion_that_shrinks_population(tmp_path: Path) -> None:
    protocol_payload = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    protocol_payload["screening"]["expand_to_modify"] = 5
    protocol_path = tmp_path / "protocol.yaml"
    _write_yaml(protocol_path, protocol_payload)

    with pytest.raises(
        WarehouseProtocolPopulationError,
        match=r"screening\.modify expansion cannot shrink population",
    ):
        reconcile_warehouse_protocol_population_from_paths(protocol_path, MANIFEST)


def test_reconcile_rejects_missing_case(tmp_path: Path) -> None:
    protocol_path, manifest_path, cases = _write_small_assets(tmp_path)
    cases["screening"].unlink()

    with pytest.raises(
        WarehouseProtocolPopulationError,
        match=r"screening case\[0\] missing",
    ):
        reconcile_warehouse_protocol_population_from_paths(
            protocol_path,
            manifest_path,
        )


def test_reconcile_rejects_symlink_case(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    symlink = tmp_path / "screening.json"
    symlink.symlink_to(target)
    protocol_path, manifest_path, _ = _write_small_assets(
        tmp_path / "assets",
        screening_path=symlink,
    )

    with pytest.raises(
        WarehouseProtocolPopulationError,
        match="must be symlink-free",
    ):
        reconcile_warehouse_protocol_population_from_paths(
            protocol_path,
            manifest_path,
        )


def test_no_llm_probe_writes_replayable_json(tmp_path: Path) -> None:
    output = tmp_path / "warehouse-w1-probe.json"

    assert main(
        [
            "--protocol",
            str(PROTOCOL),
            "--manifest",
            str(MANIFEST),
            "--output",
            str(output),
        ]
    ) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    replay = reconcile_warehouse_protocol_population_from_paths(PROTOCOL, MANIFEST)
    assert payload == replay
    assert payload["status"] == "reconciled"
