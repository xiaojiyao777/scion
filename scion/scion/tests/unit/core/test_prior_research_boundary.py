from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import pytest
from scion.config.problem import ProblemSpec, SearchSpace
from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    HypothesisProposal,
)
from scion.proposal.context_manager import ContextManager
from scion.proposal.context_snapshot import freeze_proposal_context
from scion.proposal.engine import build_prompt_turn_snapshot

_PACKAGE_ROOT = Path(__file__).resolve().parents[3]


class _ShapeProjector:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def project_prior_research_observation(
        self,
        *,
        observation: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        copied = dict(observation)
        self.calls.append(copied)
        shape = copied["shape"]
        if shape == "omit":
            return None
        if shape == "nested-sequence":
            return {
                "projected_kind": "sequence",
                "public_facts": copied["evidence"]["items"],
            }
        if shape == "scalar-map":
            return {
                "projected_kind": "scalar",
                "public_score": copied["score"],
            }
        raise AssertionError(f"unexpected fake observation shape: {shape}")


class _ProjectingAdapter:
    def __init__(self, projector: Any) -> None:
        self.projector = projector

    def prior_research_observation_provider(self) -> Any:
        return self.projector

    def research_question_payload(self) -> Mapping[str, Any]:
        raise AssertionError("the removed adapter-static campaign question was called")


class _LegacyOnlyAdapter:
    def research_question_payload(self) -> Mapping[str, Any]:
        raise AssertionError("the removed adapter-static campaign question was called")


class _UnsafeProjector:
    def __init__(self, key: str) -> None:
        self.key = key

    def project_prior_research_observation(
        self,
        *,
        observation: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        return {"public_wrapper": {self.key: observation["value"]}}


def _research_objects(tmp_path: Path) -> tuple[ProblemSpec, ChampionState, Branch]:
    operators = tmp_path / "operators"
    operators.mkdir()
    (operators / "existing.py").write_text(
        "def improve(value):\n    return value\n",
        encoding="utf-8",
    )
    surface = SimpleNamespace(
        name="generic_search",
        kind="operator",
        description="A declared synthetic research surface.",
        target_files=["operators/*.py"],
        create_new_allowed=True,
        modify_allowed=True,
        remove_allowed=False,
        required_functions=[],
    )
    spec = ProblemSpec(
        name="synthetic-boundary",
        root_dir=str(tmp_path),
        operator_categories=[surface.name],
        research_surfaces=[surface],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=["solver.py"],
            import_whitelist=[],
        ),
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        code_snapshot_path=str(tmp_path),
    )
    branch = Branch(
        branch_id="generic-prior-boundary",
        state=BranchState.EXPLORE,
        base_champion_id=1,
    )
    return spec, champion, branch


def _hypothesis_context(
    tmp_path: Path,
    *,
    adapter: Any | None = None,
    research_input: Mapping[str, Any] | None = None,
) -> tuple[ContextManager, dict[str, Any], ProblemSpec, ChampionState, Branch]:
    spec, champion, branch = _research_objects(tmp_path)
    manager = ContextManager(adapter=adapter, research_input=research_input)
    context = manager.build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=spec,
    )
    return manager, context, spec, champion, branch


@pytest.mark.parametrize(
    ("observation", "expected"),
    [
        (
            {
                "shape": "nested-sequence",
                "evidence": {"items": ["ALPHA_PUBLIC", {"delta": 3}]},
                "internal_payload": "ALPHA_RAW_ONLY",
            },
            {
                "projected_kind": "sequence",
                "public_facts": ["ALPHA_PUBLIC", {"delta": 3}],
            },
        ),
        (
            {
                "shape": "scalar-map",
                "score": 7.5,
                "internal_payload": "BETA_RAW_ONLY",
            },
            {"projected_kind": "scalar", "public_score": 7.5},
        ),
    ],
)
def test_differently_shaped_problem_observations_use_one_generic_projection_path(
    tmp_path: Path,
    observation: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    projector = _ShapeProjector()
    _manager, context, _spec, _champion, _branch = _hypothesis_context(
        tmp_path,
        adapter=_ProjectingAdapter(projector),
        research_input={
            "current_question": "Can the agent improve the synthetic subject?",
            "observations": [observation],
        },
    )

    snapshot = freeze_proposal_context("hypothesis", context)

    assert snapshot.provider_context()["prior_research_observations"] == [expected]
    assert projector.calls == [observation]
    assert observation["internal_payload"] not in json.dumps(
        snapshot.provider_context(),
        sort_keys=True,
    )


def test_no_input_and_no_provider_preserve_the_preexisting_hypothesis_context(
    tmp_path: Path,
) -> None:
    _manager, context, spec, champion, branch = _hypothesis_context(
        tmp_path,
        adapter=_LegacyOnlyAdapter(),
    )
    baseline = ContextManager().build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=spec,
    )

    assert context == baseline
    assert "research_question" not in context
    assert "prior_research_observations" not in context
    freeze_proposal_context("hypothesis", context)


def test_input_owned_question_is_visible_without_observations_or_provider(
    tmp_path: Path,
) -> None:
    question = "Can an autonomous agent improve this problem object?"
    _manager, context, _spec, _champion, _branch = _hypothesis_context(
        tmp_path,
        adapter=_LegacyOnlyAdapter(),
        research_input={
            "current_question": question,
            "observations": [],
        },
    )

    assert context["research_question"] == {"current_question": question}
    assert "prior_research_observations" not in context


def test_nonempty_observations_without_problem_projector_fail_closed(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="provider"):
        _hypothesis_context(
            tmp_path,
            adapter=_LegacyOnlyAdapter(),
            research_input={
                "current_question": "Do not expose opaque observations.",
                "observations": [{"raw_domain_fact": "MUST_NOT_REACH_H"}],
            },
        )


def test_projected_observations_reach_h_once_in_input_order_and_never_reach_c(
    tmp_path: Path,
) -> None:
    projector = _ShapeProjector()
    adapter = _ProjectingAdapter(projector)
    research_input = {
        "current_question": "QUESTION_MARKER",
        "observations": [
            {
                "shape": "nested-sequence",
                "evidence": {"items": ["FIRST_PUBLIC_MARKER"]},
                "internal_payload": "FIRST_RAW_MARKER",
            },
            {"shape": "omit", "internal_payload": "OMITTED_RAW_MARKER"},
            {
                "shape": "scalar-map",
                "score": 11,
                "internal_payload": "SECOND_RAW_MARKER",
            },
        ],
    }
    manager, context, spec, champion, branch = _hypothesis_context(
        tmp_path,
        adapter=adapter,
        research_input=research_input,
    )

    h_snapshot = build_prompt_turn_snapshot("hypothesis", context)
    rendered_h = "\n".join(
        [
            *(str(block["text"]) for block in h_snapshot.system_blocks),
            h_snapshot.user_prompt,
        ]
    )
    projected = h_snapshot.structured_context["prior_research_observations"]
    assert [item["projected_kind"] for item in projected] == [
        "sequence",
        "scalar",
    ]
    assert len(projector.calls) == 3
    for marker in ("QUESTION_MARKER", "FIRST_PUBLIC_MARKER"):
        assert rendered_h.count(marker) == 1
    for marker in (
        "FIRST_RAW_MARKER",
        "OMITTED_RAW_MARKER",
        "SECOND_RAW_MARKER",
    ):
        assert marker not in rendered_h

    hypothesis = HypothesisProposal(
        hypothesis_text="Try one generic local improvement.",
        change_locus="generic_search",
        action="modify",
        target_file="operators/existing.py",
        predicted_direction="improve",
        target_weakness="The declared local behavior is weak.",
        expected_effect="Improve the declared objective.",
    )
    code_context = manager.build_code_context(
        branch=branch,
        hypothesis=hypothesis,
        champion=champion,
        problem_spec=spec,
    )
    code_snapshot = freeze_proposal_context("code", code_context)
    serialized_c = json.dumps(code_snapshot.provider_context(), sort_keys=True)
    assert "prior_research_observations" not in code_context
    assert "research_question" not in code_context
    for marker in (
        "QUESTION_MARKER",
        "FIRST_PUBLIC_MARKER",
        "FIRST_RAW_MARKER",
        "OMITTED_RAW_MARKER",
        "SECOND_RAW_MARKER",
    ):
        assert marker not in serialized_c
    assert len(projector.calls) == 3


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "raw",
        "validation",
        "frozen",
        "holdout",
        "private",
        "secret",
        "token",
        "api_key",
        "credential",
        "password",
        "access_token",
        "auth_token",
    ],
)
def test_unsafe_projected_evidence_fields_fail_closed_before_h_provider_call(
    tmp_path: Path,
    forbidden_key: str,
) -> None:
    with pytest.raises(ValueError, match="forbidden"):
        _manager, context, _spec, _champion, _branch = _hypothesis_context(
            tmp_path,
            adapter=_ProjectingAdapter(_UnsafeProjector(forbidden_key)),
            research_input={
                "current_question": "Keep current evaluation details private.",
                "observations": [{"value": "SECRET_MARKER"}],
            },
        )
        freeze_proposal_context("hypothesis", context)


def test_prior_input_cannot_change_declared_research_authority(
    tmp_path: Path,
) -> None:
    spec, champion, branch = _research_objects(tmp_path)
    projector = _ShapeProjector()
    adapter = _ProjectingAdapter(projector)
    control = ContextManager(adapter=adapter).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=spec,
    )
    treated = ContextManager(
        adapter=adapter,
        research_input={
            "current_question": "Try a new direction.",
            "observations": [
                {
                    "shape": "scalar-map",
                    "score": 5,
                    "surfaces": ["forbidden_surface"],
                    "actions": ["forbidden_action"],
                    "targets": ["outside.py"],
                    "protocol": {"cases": ["secret-case"]},
                    "decision": "promote",
                }
            ],
        },
    ).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=spec,
    )

    for key in (
        "research_surfaces",
        "available_actions",
        "existing_target_files",
        "create_path_patterns",
        "champion_operators_code",
        "champion_stats",
    ):
        assert treated[key] == control[key]
    projected_text = json.dumps(
        treated["prior_research_observations"],
        sort_keys=True,
    )
    for forbidden_value in (
        "forbidden_surface",
        "forbidden_action",
        "outside.py",
        "secret-case",
        "promote",
    ):
        assert forbidden_value not in projected_text


def test_prior_transport_is_absent_from_protocol_and_decision_modules() -> None:
    isolated_paths = [
        _PACKAGE_ROOT / "protocol",
        _PACKAGE_ROOT / "core" / "decision_coordinator.py",
        _PACKAGE_ROOT / "core" / "decision_finalizer.py",
        _PACKAGE_ROOT / "core" / "features.py",
    ]
    forbidden_tokens = ("research_input", "prior_research_observations")
    for path in isolated_paths:
        files = path.rglob("*.py") if path.is_dir() else (path,)
        for source_file in files:
            source = source_file.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                assert token not in source, f"{token} leaked into {source_file}"


def test_generic_prior_transport_contains_no_problem_specific_branch() -> None:
    generic_roots = (
        _PACKAGE_ROOT / "core",
        _PACKAGE_ROOT / "problem",
        _PACKAGE_ROOT / "proposal",
    )
    forbidden_tokens = ("cvrp", "warehouse", "x-n200", "m7-fc1")
    for root in generic_roots:
        for source_file in root.rglob("*.py"):
            source = source_file.read_text(encoding="utf-8").casefold()
            for token in forbidden_tokens:
                assert token not in source, (
                    f"problem-specific token {token!r} leaked into {source_file}"
                )
