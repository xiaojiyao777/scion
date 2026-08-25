from __future__ import annotations

import json
from pathlib import Path

import pytest

from scion.cli.commands.init_run import _load_code_research_limits
from scion.core.code_research_limits import (
    CodeResearchLimits,
    load_code_research_limits,
    normalize_code_research_limits,
    write_code_research_limits,
)

_SCION_ROOT = Path(__file__).resolve().parents[4]
_LEGACY_INPUT_ROOT = _SCION_ROOT / "docs" / "experiments" / "v0.4" / "inputs"


def test_missing_and_explicit_one_preserve_the_fixed_k1_configuration() -> None:
    missing = normalize_code_research_limits({"max_turns": 2})
    explicit = normalize_code_research_limits(
        {"max_turns": 2, "max_hypothesis_candidates": 1}
    )

    assert missing == explicit
    assert missing.max_hypothesis_candidates == 1
    assert missing.to_primitive()["max_hypothesis_candidates"] == 1


def test_existing_positional_max_turns_call_keeps_its_meaning() -> None:
    limits = CodeResearchLimits(3)

    assert limits.max_turns == 3
    assert limits.max_hypothesis_candidates == 1


@pytest.mark.parametrize(
    ("value", "error_type"),
    (
        (0, ValueError),
        (2, ValueError),
        (3, ValueError),
        (True, TypeError),
        ("1", TypeError),
    ),
)
def test_non_k1_candidate_counts_fail_closed_in_constructor_and_mapping(
    value: object,
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type, match="max_hypothesis_candidates"):
        CodeResearchLimits(max_hypothesis_candidates=value)  # type: ignore[arg-type]
    with pytest.raises(error_type, match="max_hypothesis_candidates"):
        normalize_code_research_limits({"max_hypothesis_candidates": value})


def test_candidate_count_has_no_alias() -> None:
    with pytest.raises(ValueError, match="unsupported code research limits field"):
        normalize_code_research_limits({"hypothesis_candidates": 1})


def test_write_and_load_roundtrip_persists_effective_k1(tmp_path: Path) -> None:
    expected = CodeResearchLimits(max_turns=2)

    path = write_code_research_limits(str(tmp_path), expected)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["max_hypothesis_candidates"] == 1
    assert load_code_research_limits(path) == expected


@pytest.mark.parametrize(
    "filename",
    (
        "v04-cvrp-m10-code-research-limits.json",
        "v04-cvrp-m11-code-research-limits.json",
    ),
)
def test_tracked_legacy_limits_without_candidate_field_load_as_k1(
    filename: str,
) -> None:
    path = _LEGACY_INPUT_ROOT / filename
    raw = json.loads(path.read_text(encoding="utf-8"))

    assert "max_hypothesis_candidates" not in raw
    assert load_code_research_limits(path).max_hypothesis_candidates == 1


def test_cli_limits_loader_accepts_k1_and_rejects_k2(tmp_path: Path) -> None:
    accepted = tmp_path / "accepted.json"
    accepted.write_text(
        '{"max_hypothesis_candidates":1,"max_turns":2}',
        encoding="utf-8",
    )
    rejected = tmp_path / "rejected.json"
    rejected.write_text(
        '{"max_hypothesis_candidates":2,"max_turns":2}',
        encoding="utf-8",
    )

    assert _load_code_research_limits(accepted).max_hypothesis_candidates == 1
    with pytest.raises(ValueError, match="max_hypothesis_candidates"):
        _load_code_research_limits(rejected)
