from __future__ import annotations

from pathlib import Path

from scion.core.models import (
    AcceptedFileBeforeSource,
    PatchFileChange,
    PatchProposal,
)
from scion.problems.cvrp.mechanism_attribution import (
    summarize_cvrp_mechanism_attribution,
)
from scion.problems.cvrp.proposal_mechanism_evidence import (
    CvrpProposalMechanismEvidenceProvider,
)
from scion.protocol.experiment import proposal_evidence


def _subject(path: str, before: str, after: str) -> dict:
    return {
        "schema_version": "scion.problem_proposal_subject.v1",
        "changes": [
            {
                "file_path": path,
                "action": "modify",
                "before_source": before,
                "after_source": after,
            }
        ],
    }


def _runtime(*, initial_distance: float, vns_accepted: int = 0) -> dict:
    return {
        "solver_algorithm_solution_progress": {
            "initial_total_distance": initial_distance,
            "initial_route_count": 3,
            "final_total_distance": initial_distance - vns_accepted,
        },
        "solver_algorithm_phase_move_attempts": {
            "vns": 10,
            "alns": 4,
        },
        "solver_algorithm_phase_accepted_moves": {"vns": vns_accepted},
        "solver_algorithm_phase_improvement_counts": {"vns": vns_accepted},
        "solver_algorithm_phase_delta_sum": {"vns": float(vns_accepted)},
        "solver_algorithm_phase_runtime_ms": {
            "construction": 2,
            "vns_initial": 3,
            "vns_embedded": 5,
        },
    }


def test_initial_portfolio_equal_state_is_family_observable_unchanged() -> None:
    subject = _subject(
        "policies/baseline_modules/scheduler.py",
        "class _ALNSVNSSolver:\n    def _initial_solution(self):\n        return 1\n",
        (
            "class _ALNSVNSSolver:\n"
            "    def _initial_solution(self):\n"
            "        return min(1, 2)\n"
        ),
    )
    pairs = [
        {
            "candidate_runtime": _runtime(initial_distance=100.0),
            "champion_runtime": _runtime(initial_distance=100.0),
        },
        {
            "candidate_runtime": _runtime(initial_distance=200.0),
            "champion_runtime": _runtime(initial_distance=200.0),
        },
    ]

    result = summarize_cvrp_mechanism_attribution(
        proposal_subject=subject,
        runtime_pairs=pairs,
    )

    assert result["attribution_status"] == "family_observable_unchanged"
    assert result["attribution_resolution"] == "family_association"
    assert result["exact_mechanism_activation"] is False
    assert result["mechanism_families"] == ["initial_solution_selection"]
    assert result["changed_source_roles"] == ["scheduler"]
    assert result["changed_symbol_names"] == ["_ALNSVNSSolver._initial_solution"]
    assert all(
        probe["different_pairs"] == 0 for probe in result["activation_observations"]
    )


def test_construction_change_uses_initial_state_family_observations() -> None:
    subject = _subject(
        "policies/baseline_modules/construction.py",
        "def build_initial_solution():\n    return first()\n",
        "def build_initial_solution():\n    return min(first(), second())\n",
    )
    result = summarize_cvrp_mechanism_attribution(
        proposal_subject=subject,
        runtime_pairs=[
            {
                "candidate_runtime": _runtime(initial_distance=100.0),
                "champion_runtime": _runtime(initial_distance=100.0),
            }
        ],
    )

    assert result["attribution_status"] == "family_observable_unchanged"
    assert result["mechanism_families"] == ["initial_solution_selection"]
    assert result["changed_source_roles"] == ["construction"]
    assert result["changed_symbol_names"] == ["build_initial_solution"]


def test_new_vns_neighborhood_reports_only_family_observable_change() -> None:
    subject = _subject(
        "policies/baseline_modules/local_search.py",
        "def _default_vns_operators():\n    return ('swap',)\n",
        (
            "def _exchange_2_for_2():\n    return True\n\n"
            "def _default_vns_operators():\n"
            "    return ('swap', _exchange_2_for_2)\n"
        ),
    )
    pairs = [
        {
            "candidate_runtime": _runtime(
                initial_distance=90.0,
                vns_accepted=2,
            ),
            "champion_runtime": _runtime(initial_distance=100.0),
        }
    ]

    result = summarize_cvrp_mechanism_attribution(
        proposal_subject=subject,
        runtime_pairs=pairs,
    )

    assert result["attribution_status"] == "family_observable_changed"
    assert result["attribution_resolution"] == "family_association"
    assert result["exact_mechanism_activation"] is False
    assert result["mechanism_families"] == ["vns_neighborhood"]
    assert result["changed_source_roles"] == ["local_search"]
    assert result["changed_symbol_names"] == [
        "_default_vns_operators",
        "_exchange_2_for_2",
    ]
    by_id = {item["signal"]: item for item in result["activation_observations"]}
    assert "initial_solution_selected_distance" not in by_id
    assert by_id["vns_move_attempts"]["observed_pairs"] == 1
    assert by_id["vns_accepted_moves"]["different_pairs"] == 1


def test_absent_before_after_subject_is_explicitly_unavailable_legacy() -> None:
    result = summarize_cvrp_mechanism_attribution(
        proposal_subject=None,
        runtime_pairs=[
            {
                "candidate_runtime": _runtime(initial_distance=90.0),
                "champion_runtime": _runtime(initial_distance=100.0),
            }
        ],
    )

    assert result["attribution_status"] == "unavailable_legacy"
    assert result["changed_source_roles"] == []
    assert result["activation_observations"] == []


def test_incomplete_runtime_pairs_never_claim_family_change_or_unchanged() -> None:
    subject = _subject(
        "policies/baseline_modules/local_search.py",
        "def _default_vns_operators():\n    return ()\n",
        "def _default_vns_operators():\n    return ('swap',)\n",
    )

    result = summarize_cvrp_mechanism_attribution(
        proposal_subject=subject,
        runtime_pairs=[
            {
                "candidate_runtime": _runtime(initial_distance=90.0),
                "champion_runtime": _runtime(initial_distance=100.0),
            }
        ],
        runtime_pairs_complete=False,
    )

    assert result["attribution_status"] == "unavailable_incomplete"
    assert result["activation_observations"] == []
    assert result["exact_mechanism_activation"] is False


def test_provider_keeps_incomplete_pair_evidence_unavailable() -> None:
    subject = _subject(
        "policies/baseline_modules/local_search.py",
        "def _default_vns_operators():\n    return ()\n",
        "def _default_vns_operators():\n    return ('swap',)\n",
    )
    provider = CvrpProposalMechanismEvidenceProvider()

    result = provider.summarize_proposal_mechanism_evidence(
        stage="screening",
        selected_surface="solver_design",
        proposal_subject=subject,
        runtime_pairs=[
            {
                "candidate_runtime": _runtime(initial_distance=90.0),
                "champion_runtime": _runtime(initial_distance=100.0),
            }
        ],
        runtime_pairs_complete=False,
    )

    assert result["mechanism_attribution"]["attribution_status"] == (
        "unavailable_incomplete"
    )
    assert result["hypothesis_attribution"] not in {
        "family_observable_changed",
        "family_observable_unchanged",
    }


def test_expansion_with_already_applied_source_is_explicitly_unavailable() -> None:
    source = "def _default_vns_operators():\n    return ('swap',)\n"
    subject = _subject(
        "policies/baseline_modules/local_search.py",
        source,
        source,
    )

    result = summarize_cvrp_mechanism_attribution(
        proposal_subject=subject,
        runtime_pairs=[
            {
                "candidate_runtime": _runtime(initial_distance=90.0),
                "champion_runtime": _runtime(initial_distance=100.0),
            }
        ],
    )

    assert result["attribution_status"] == "unavailable_current_source"
    assert result["mechanism_families"] == []
    assert result["activation_observations"] == []
    assert result["changed_source_roles"] == []
    assert result["changed_symbol_names"] == []


def test_unmapped_scheduler_symbol_is_explicitly_unsupported() -> None:
    subject = _subject(
        "policies/baseline_modules/scheduler.py",
        "def solve():\n    return 1\n",
        "def solve():\n    return 2\n",
    )

    result = summarize_cvrp_mechanism_attribution(
        proposal_subject=subject,
        runtime_pairs=[
            {
                "candidate_runtime": _runtime(initial_distance=90.0),
                "champion_runtime": _runtime(initial_distance=100.0),
            }
        ],
    )

    assert result["attribution_status"] == "unavailable_unsupported"
    assert result["mechanism_families"] == []
    assert result["activation_observations"] == []


def test_non_vns_polish_change_is_not_attributed_to_vns() -> None:
    subject = _subject(
        "policies/baseline_modules/local_search.py",
        "def _two_opt_intra_polish():\n    return 1\n",
        "def _two_opt_intra_polish():\n    return 2\n",
    )

    result = summarize_cvrp_mechanism_attribution(
        proposal_subject=subject,
        runtime_pairs=[
            {
                "candidate_runtime": _runtime(initial_distance=90.0),
                "champion_runtime": _runtime(initial_distance=100.0),
            }
        ],
    )

    assert result["attribution_status"] == "unavailable_unsupported"
    assert result["mechanism_families"] == []
    assert result["activation_observations"] == []


def test_vns_family_requires_a_vns_owned_runtime_observation() -> None:
    subject = _subject(
        "policies/baseline_modules/local_search.py",
        "def _default_vns_operators():\n    return ()\n",
        "def _default_vns_operators():\n    return ('swap',)\n",
    )

    result = summarize_cvrp_mechanism_attribution(
        proposal_subject=subject,
        runtime_pairs=[
            {
                "candidate_runtime": {
                    "solver_algorithm_solution_progress": {
                        "initial_total_distance": 90.0,
                    }
                },
                "champion_runtime": {
                    "solver_algorithm_solution_progress": {
                        "initial_total_distance": 100.0,
                    }
                },
            }
        ],
    )

    assert result["attribution_status"] == "unavailable_legacy"
    assert all(
        observation["observed_pairs"] == 0
        for observation in result["activation_observations"]
    )


def test_proposal_subject_has_aggregate_utf8_source_hard_cap(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(proposal_evidence, "_MAX_SUBJECT_SOURCE_BYTES", 8)
    (tmp_path / "first.py").write_text("é", encoding="utf-8")
    (tmp_path / "second.py").write_text("a", encoding="utf-8")

    at_limit = PatchProposal(
        file_path="first.py",
        action="modify",
        code_content="é",
        additional_changes=(
            PatchFileChange(
                file_path="second.py",
                action="modify",
                code_content="bbb",
            ),
        ),
    )
    over_limit = PatchProposal(
        file_path="first.py",
        action="modify",
        code_content="é",
        additional_changes=(
            PatchFileChange(
                file_path="second.py",
                action="modify",
                code_content="bbbb",
            ),
        ),
    )

    assert (
        proposal_evidence.build_problem_proposal_subject(
            patch=at_limit,
            base_workspace=str(tmp_path),
        )["schema_version"]
        == "scion.problem_proposal_subject.v1"
    )
    assert (
        proposal_evidence.build_problem_proposal_subject(
            patch=over_limit,
            base_workspace=str(tmp_path),
        )
        == {}
    )

    (tmp_path / "oversized.py").write_text("123456789", encoding="utf-8")
    assert (
        proposal_evidence.build_problem_proposal_subject(
            patch=PatchProposal(
                file_path="oversized.py",
                action="modify",
                code_content="",
            ),
            base_workspace=str(tmp_path),
        )
        == {}
    )


def test_proposal_subject_prefers_plain_before_sources_without_metadata() -> None:
    patch = PatchProposal(
        file_path="solver.py",
        action="modify",
        code_content="def solve():\n    return 'after'\n",
    )

    subject = proposal_evidence.build_problem_proposal_subject(
        patch=patch,
        base_workspace=None,
        before_sources=(
            AcceptedFileBeforeSource(
                file_path="solver.py",
                source="def solve():\n    return 'before'\n",
            ),
        ),
    )

    assert subject == {
        "schema_version": "scion.problem_proposal_subject.v1",
        "changes": [
            {
                "file_path": "solver.py",
                "action": "modify",
                "before_source": "def solve():\n    return 'before'\n",
                "after_source": "def solve():\n    return 'after'\n",
            }
        ],
    }
    subject_keys = set(subject) | set(subject["changes"][0])
    assert subject_keys.isdisjoint(
        {"digest", "hash", "identity", "lease", "receipt", "registry", "signature"}
    )


def test_provider_projects_attribution_without_search_allocation_fields() -> None:
    subject = _subject(
        "policies/baseline_modules/scheduler.py",
        "class _ALNSVNSSolver:\n    def _initial_solution(self):\n        return 1\n",
        "class _ALNSVNSSolver:\n    def _initial_solution(self):\n        return 2\n",
    )

    provider = CvrpProposalMechanismEvidenceProvider()
    result = provider.summarize_proposal_mechanism_evidence(
        stage="screening",
        selected_surface="solver_design",
        proposal_subject=subject,
        runtime_pairs=[
            {
                "candidate_runtime": {
                    "solver_algorithm_solution_progress": {
                        "initial_total_distance": 9.0,
                        "initial_route_count": 2,
                    }
                },
                "champion_runtime": {
                    "solver_algorithm_solution_progress": {
                        "initial_total_distance": 10.0,
                        "initial_route_count": 2,
                    }
                },
            }
        ],
    )

    assert result["hypothesis_attribution"] == "family_observable_changed"
    assert result["mechanism_attribution"]["attribution_status"] == (
        "family_observable_changed"
    )
