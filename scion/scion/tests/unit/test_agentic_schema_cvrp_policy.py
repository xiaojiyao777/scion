"""Focused tests split from test_agentic_proposal_tools_schema.py."""

from .agentic_schema_test_support import *  # noqa: F401,F403

def test_cvrp_policy_preview_good_defaults_pass(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)

    patches = [
        {
            "file_path": "policies/construction_policy.py",
            "action": "modify",
            "code_content": (
                _CVRP_ROOT / "policies" / "construction_policy.py"
            ).read_text(encoding="utf-8"),
        },
        {
            "file_path": "policies/search_policy.py",
            "action": "modify",
            "code_content": (_CVRP_ROOT / "policies" / "search_policy.py").read_text(
                encoding="utf-8"
            ),
        },
        {
            "file_path": "policies/neighborhood_portfolio.py",
            "action": "modify",
            "code_content": (
                _CVRP_ROOT / "policies" / "neighborhood_portfolio.py"
            ).read_text(encoding="utf-8"),
        },
    ]

    for patch in patches:
        observation = registry.call("proposal.interface_preview", patch, context)
        assert observation.is_error is False
        assert observation.structured_payload["passed"] is True
        assert observation.structured_payload["problem_preview"]["passed"] is True


def test_cvrp_construction_policy_preview_fails_bad_dynamic_mode_and_bias(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)

    observation = registry.call(
        "proposal.interface_preview",
        {
            "file_path": "policies/construction_policy.py",
            "action": "modify",
            "code_content": (
                "def construction_mode(instance, time_limit_sec):\n"
                "    mode = 'savings'\n"
                "    return mode\n\n"
                "def construction_bias(instance, time_limit_sec):\n"
                "    bias = 2.0\n"
                "    return bias\n"
            ),
        },
        context,
    )

    preview = observation.structured_payload["problem_preview"]
    assert observation.structured_payload["passed"] is False
    assert preview["passed"] is False
    assert "unknown mode" in json.dumps(preview)
    assert "construction_bias" in json.dumps(preview)


def test_cvrp_search_and_portfolio_preview_fail_bad_limits_and_components(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)

    bad_search = registry.call(
        "proposal.interface_preview",
        {
            "file_path": "policies/search_policy.py",
            "action": "modify",
            "code_content": (
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    return 0.8\n\n"
                "def max_operator_rounds(instance, time_limit_sec):\n"
                "    rounds = 99\n"
                "    return rounds\n\n"
                "def enable_post_baseline_operators(instance, time_limit_sec):\n"
                "    return True\n"
            ),
        },
        context,
    )
    bad_portfolio = registry.call(
        "proposal.interface_preview",
        {
            "file_path": "policies/neighborhood_portfolio.py",
            "action": "modify",
            "code_content": (
                "def enabled_components(instance, time_limit_sec):\n"
                "    component = 'not_registered'\n"
                "    return [component]\n\n"
                "def component_weights(instance, time_limit_sec):\n"
                "    return {'route_local': float('inf')}\n\n"
                "def candidate_limits(instance, time_limit_sec):\n"
                "    limit = 999\n"
                "    return {'top_k': limit}\n"
            ),
        },
        context,
    )

    assert bad_search.structured_payload["passed"] is False
    assert "max_operator_rounds" in json.dumps(
        bad_search.structured_payload["problem_preview"]
    )
    assert bad_portfolio.structured_payload["passed"] is False
    rendered = json.dumps(bad_portfolio.structured_payload["problem_preview"])
    assert "unknown components" in rendered
    assert "non-finite" in rendered
    assert "top_k" in rendered


def test_cvrp_interface_preview_skips_problem_preview_after_contract_failure(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)

    observation = registry.call(
        "proposal.interface_preview",
        {
            "file_path": "policies/search_policy.py",
            "action": "modify",
            "code_content": (
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    return open('/definitely/not/present/scion_secret.json').read()\n\n"
                "def max_operator_rounds(instance, time_limit_sec):\n"
                "    return 20\n\n"
                "def enable_post_baseline_operators(instance, time_limit_sec):\n"
                "    return True\n"
            ),
        },
        context,
    )

    payload = observation.structured_payload
    rendered_checks = json.dumps(payload["checks"])
    assert payload["passed"] is False
    assert payload["problem_preview"] is None
    assert "C9_sensitive_api" in rendered_checks
    assert "open" in rendered_checks


def test_cvrp_contract_preview_records_problem_preview_failure_without_raw_refs(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)

    observation = registry.call(
        "proposal.contract_preview",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="construction_policy",
                target_file="policies/construction_policy.py",
                target_objectives=["total_distance"],
                protected_objectives=["fleet_violation"],
            ),
            "patch": {
                "file_path": "policies/construction_policy.py",
                "action": "modify",
                "code_content": (
                    "def construction_mode(instance, time_limit_sec):\n"
                    "    mode = 'savings'\n"
                    "    return mode\n\n"
                    "def construction_bias(instance, time_limit_sec):\n"
                    "    return 0.5\n"
                ),
            },
        },
        context,
    )

    rendered = json.dumps(observation.structured_payload, sort_keys=True)
    assert observation.is_error is False
    assert observation.structured_payload["passed"] is False
    assert observation.structured_payload["patch"]["problem_preview"]["passed"] is False
    assert "issues" in observation.structured_payload["patch"]["problem_preview"]
    assert "synthetic_instance" not in rendered
    assert "code_content" not in rendered
    assert "raw_metrics_ref" not in rendered
    assert "SECRET_RAW" not in rendered
