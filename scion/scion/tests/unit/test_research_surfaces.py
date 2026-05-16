from __future__ import annotations

from pathlib import Path

import pytest

from scion.problem.bridge import legacy_problem_spec_from_v1
from scion.problem.spec import ProblemSpecV1
from scion.tests.unit.research_surface_helpers import _problem_payload


def test_problem_spec_accepts_optional_research_surfaces_and_bridge_maps_loci(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "local",
            "kind": "operator",
            "description": "Local operators",
            "target_files": ["operators/*.py"],
        },
        {
            "name": "search_policy",
            "kind": "policy",
            "description": "Budget policy",
            "target_files": ["policies/search_policy.py"],
            "create_new_allowed": False,
            "remove_allowed": False,
        },
    ]

    spec = ProblemSpecV1(**payload)
    legacy = legacy_problem_spec_from_v1(spec)

    assert [surface.name for surface in spec.research_surfaces or []] == [
        "local",
        "search_policy",
    ]
    assert legacy.operator_categories == ["local", "search_policy"]
    assert [surface.name for surface in legacy.research_surfaces] == [
        "local",
        "search_policy",
    ]
    assert legacy.research_surfaces[1].required_functions == []
    assert legacy.research_surfaces[1].targets.files == [
        "policies/search_policy.py"
    ]
    assert legacy.research_surfaces[1].interface.required_functions == []


def test_problem_spec_accepts_v2_research_surface_and_exposes_legacy_fields(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["search_space"]["editable"] = ["operators/*.py", "policies/*.py"]
    payload["research_surfaces"] = [
        {
            "name": "search_policy",
            "kind": "policy",
            "description": "Budget policy",
            "algorithm": {
                "role": "search_budget_policy",
                "invocation_point": "before_main_search",
                "description": "Controls bounded search budget choices.",
            },
            "targets": {
                "files": ["policies/search_policy.py"],
                "create_new_allowed": False,
                "modify_allowed": True,
                "remove_allowed": False,
                "singleton": True,
            },
            "interface": {
                "required_functions": [
                    "baseline_time_fraction",
                    "max_operator_rounds",
                ],
                "function_signatures": {
                    "baseline_time_fraction": ["instance", "time_limit_sec"],
                    "max_operator_rounds": "max_operator_rounds(instance, time_limit_sec)",
                },
                "return_contract": "problem-defined scalar policy values",
            },
            "bounds": {
                "allowed_components": ["baseline_budget", "round_limit"],
                "numeric_ranges": {
                    "baseline_time_fraction": [0.05, 0.95],
                    "max_operator_rounds": [0, 50],
                },
                "complexity_scale_terms": ["problem_size", "time_limit_sec"],
            },
            "evidence": {
                "required_runtime_fields": [
                    "policy_loaded",
                    "policy_errors",
                ],
            },
            "novelty": {
                "strategy": "semantic_signature",
                "signature_fields": ["budget_pattern", "round_limit_pattern"],
            },
            "prompt": {
                "hypothesis_guidance": "Explain expected budget tradeoff.",
                "implementation_guidance": "Keep policy deterministic.",
                "anti_patterns": "Do not read external result files.",
            },
        },
    ]

    spec = ProblemSpecV1(**payload)
    surface = (spec.research_surfaces or [])[0]

    assert surface.algorithm is not None
    assert surface.algorithm.role == "search_budget_policy"
    assert surface.targets is not None
    assert surface.targets.files == ["policies/search_policy.py"]
    assert surface.targets.singleton is True
    assert surface.interface is not None
    assert surface.interface.required_functions == [
        "baseline_time_fraction",
        "max_operator_rounds",
    ]
    assert surface.interface.function_signatures == {
        "baseline_time_fraction": ["instance", "time_limit_sec"],
        "max_operator_rounds": ["instance", "time_limit_sec"],
    }
    assert surface.interface.return_contract == "problem-defined scalar policy values"
    assert surface.bounds is not None
    assert surface.bounds.allowed_components == ["baseline_budget", "round_limit"]
    assert surface.bounds.numeric_ranges["baseline_time_fraction"] == (0.05, 0.95)
    assert surface.evidence is not None
    assert surface.evidence.required_runtime_fields == [
        "policy_loaded",
        "policy_errors",
    ]
    assert surface.novelty is not None
    assert surface.novelty.strategy == "semantic_signature"
    assert surface.prompt is not None
    assert surface.prompt.anti_patterns == "Do not read external result files."

    assert surface.target_files == ["policies/search_policy.py"]
    assert surface.required_functions == [
        "baseline_time_fraction",
        "max_operator_rounds",
    ]
    assert surface.create_new_allowed is False
    assert surface.modify_allowed is True
    assert surface.remove_allowed is False

    legacy = legacy_problem_spec_from_v1(spec)
    legacy_surface = legacy.research_surfaces[0]
    assert legacy.operator_categories == ["search_policy"]
    assert legacy_surface.target_files == ["policies/search_policy.py"]
    assert legacy_surface.required_functions == [
        "baseline_time_fraction",
        "max_operator_rounds",
    ]
    assert legacy_surface.bounds.allowed_components == [
        "baseline_budget",
        "round_limit",
    ]


def test_v2_research_surface_metadata_is_problem_owned(tmp_path: Path) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "abstract_surface",
            "kind": "portfolio",
            "algorithm": {
                "role": "problem_defined_role",
                "invocation_point": "problem_defined_hook",
            },
            "targets": {"files": ["operators/*.py"]},
            "bounds": {
                "allowed_components": ["problem_component_a"],
                "numeric_ranges": {"problem_knob": [1, 3]},
                "complexity_scale_terms": ["problem_scale_term"],
            },
        },
    ]

    spec = ProblemSpecV1(**payload)
    surface = (spec.research_surfaces or [])[0]

    assert surface.kind == "portfolio"
    assert surface.bounds is not None
    assert surface.bounds.allowed_components == ["problem_component_a"]
    assert surface.bounds.complexity_scale_terms == ["problem_scale_term"]


def test_problem_spec_rejects_duplicate_research_surface_names(tmp_path: Path) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "search_policy",
            "kind": "policy",
            "description": "Budget policy",
            "target_files": ["policies/search_policy.py"],
        },
        {
            "name": "search_policy",
            "kind": "policy",
            "description": "Duplicate",
            "target_files": ["policies/other.py"],
        },
    ]

    with pytest.raises(ValueError, match="research surface names must be unique"):
        ProblemSpecV1(**payload)


def test_problem_spec_rejects_legacy_v2_surface_target_conflict(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "policy",
            "kind": "policy",
            "targets": {"files": ["policies/policy.py"]},
            "target_files": ["policies/other.py"],
        },
    ]

    with pytest.raises(ValueError, match="target_files conflicts"):
        ProblemSpecV1(**payload)


def test_problem_spec_rejects_legacy_v2_surface_action_conflict(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "policy",
            "kind": "policy",
            "targets": {
                "files": ["policies/policy.py"],
                "remove_allowed": False,
            },
            "target_files": ["policies/policy.py"],
            "remove_allowed": True,
        },
    ]

    with pytest.raises(ValueError, match="remove_allowed conflicts"):
        ProblemSpecV1(**payload)


def test_problem_spec_rejects_legacy_v2_surface_interface_conflict(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "policy",
            "kind": "policy",
            "targets": {"files": ["policies/policy.py"]},
            "interface": {"required_functions": ["choose_limit"]},
            "target_files": ["policies/policy.py"],
            "required_functions": ["choose_mode"],
        },
    ]

    with pytest.raises(ValueError, match="required_functions conflicts"):
        ProblemSpecV1(**payload)


def test_problem_spec_without_research_surfaces_keeps_legacy_categories(
    tmp_path: Path,
) -> None:
    spec = ProblemSpecV1(**_problem_payload(str(tmp_path)))
    legacy = legacy_problem_spec_from_v1(spec)

    assert spec.research_surfaces is None
    assert legacy.operator_categories == ["local"]
    assert legacy.research_surfaces == []


def test_problem_spec_rejects_unknown_research_surface_kind(tmp_path: Path) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "local",
            "kind": "oprator",
            "description": "Typo should not load.",
            "target_files": ["operators/*.py"],
        },
    ]

    with pytest.raises(ValueError, match="unsupported research surface kind"):
        ProblemSpecV1(**payload)
