from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest
from scion.cli.commands.init_run import _load_research_input
from scion.config.problem import ProblemSpec, SearchSpace
from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    HypothesisProposal,
)
from scion.core.problem_runtime import ProblemRuntime
from scion.core.research_input import (
    MAX_RESEARCH_OBSERVATIONS,
    normalize_research_input,
    write_research_input,
)
from scion.proposal.context_manager import ContextManager
from scion.proposal.context_snapshot import freeze_proposal_context
from scion.proposal.prompt_projection import project_prompt


def _research_objects(tmp_path: Path):
    source_root = tmp_path / "source"
    operator_dir = source_root / "operators"
    operator_dir.mkdir(parents=True)
    (operator_dir / "local_search.py").write_text(
        "def improve(solution, rng):\n    return solution\n",
        encoding="utf-8",
    )
    spec = ProblemSpec(
        name="generic-demo",
        root_dir=str(source_root),
        operator_categories=["local_search"],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=["solver.py"],
            import_whitelist=["math"],
        ),
    )
    branch = Branch(
        branch_id="branch-1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        code_snapshot_path=str(source_root),
    )
    return spec, branch, champion


class _ObservationProjector:
    def __init__(self) -> None:
        self.seen: list[dict[str, Any]] = []

    def project_prior_research_observation(
        self,
        *,
        observation: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        detached = dict(observation)
        self.seen.append(detached)
        if not detached.get("publish", True):
            return None
        if "finding" not in detached:
            return detached
        return {
            "finding": detached["finding"],
            "evidence": detached["evidence"],
        }


class _Adapter:
    def __init__(self, spec: Any | None = None) -> None:
        self.spec = spec
        self.projector = _ObservationProjector()

    def prior_research_observation_provider(self) -> _ObservationProjector:
        return self.projector


class _FixedProjectorAdapter:
    def __init__(self, projection: Any) -> None:
        self.projection = projection

    def prior_research_observation_provider(self) -> Any:
        projection = self.projection

        class _Projector:
            def project_prior_research_observation(
                self,
                *,
                observation: Mapping[str, Any],
            ) -> Any:
                return projection

        return _Projector()


def test_research_input_is_projected_in_order_to_h_only(tmp_path: Path) -> None:
    spec, branch, champion = _research_objects(tmp_path)
    adapter = _Adapter()
    research_input = {
        "current_question": "Which mechanism should be investigated next?",
        "observations": [
            {"publish": True, "finding": "first", "evidence": {"count": 3}},
            {"publish": False, "finding": "private", "evidence": {}},
            {"publish": True, "finding": "third", "evidence": {"count": 8}},
        ],
    }
    manager = ContextManager(adapter=adapter, research_input=research_input)

    h_context = manager.build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=spec,
    )
    h_snapshot = freeze_proposal_context("hypothesis", h_context)
    provider_context = project_prompt("hypothesis", h_snapshot).structured_context

    assert provider_context["research_question"] == {
        "current_question": "Which mechanism should be investigated next?"
    }
    assert [
        item["finding"] for item in provider_context["prior_research_observations"]
    ] == ["first", "third"]
    assert [item["finding"] for item in adapter.projector.seen] == [
        "first",
        "private",
        "third",
    ]
    baseline_context = ContextManager().build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=spec,
    )
    assert (
        provider_context["available_actions"] == baseline_context["available_actions"]
    )
    assert (
        provider_context["research_surfaces"] == baseline_context["research_surfaces"]
    )

    hypothesis = HypothesisProposal(
        hypothesis_text="Investigate a source-supported mechanism.",
        change_locus="local_search",
        action="modify",
        target_file="operators/local_search.py",
    )
    c_context = manager.build_code_context(
        branch=branch,
        hypothesis=hypothesis,
        champion=champion,
        problem_spec=spec,
    )
    assert "research_question" not in c_context
    assert "prior_research_observations" not in c_context


def test_question_is_external_and_nonempty_observations_require_projector(
    tmp_path: Path,
) -> None:
    spec, branch, champion = _research_objects(tmp_path)
    question_only = {
        "current_question": "Can the generic agent improve this object?",
        "observations": [],
    }
    context = ContextManager(research_input=question_only).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=spec,
    )

    assert context["research_question"] == {
        "current_question": "Can the generic agent improve this object?"
    }
    assert "prior_research_observations" not in context
    with pytest.raises(ValueError, match="require.*provider"):
        ContextManager(
            research_input={
                "current_question": "Can the generic agent improve this object?",
                "observations": [{"domain_evidence": "not projected"}],
            }
        )
    without_input = ContextManager().build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=spec,
    )
    assert "research_question" not in without_input
    assert "prior_research_observations" not in without_input


def test_research_input_is_bounded_without_truncation() -> None:
    observations = [{"sequence": index} for index in range(MAX_RESEARCH_OBSERVATIONS)]
    normalized = normalize_research_input(
        {"current_question": "  Continue?  ", "observations": observations}
    )
    assert normalized["current_question"] == "  Continue?  "
    assert normalized["observations"] == observations

    with pytest.raises(ValueError, match="too many observations"):
        normalize_research_input(
            {
                "current_question": "Continue?",
                "observations": observations + [{"sequence": len(observations)}],
            }
        )


@pytest.mark.parametrize(
    ("projection", "message"),
    [
        ({"expanded": "x" * (256 * 1024)}, "too large"),
        ({"non_json": ("tuple",)}, "unsupported value"),
    ],
)
def test_projected_observations_are_revalidated_without_truncation(
    projection: Any,
    message: str,
) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        ContextManager(
            adapter=_FixedProjectorAdapter(projection),
            research_input={
                "current_question": "Continue?",
                "observations": [{"opaque": "input"}],
            },
        )


@pytest.mark.parametrize(
    "key",
    ("api_key", "access-token", "secret", "password", "raw_prompt"),
)
def test_research_input_rejects_sensitive_fields_before_recording(
    key: str,
) -> None:
    with pytest.raises(ValueError, match="forbidden sensitive research input"):
        normalize_research_input(
            {
                "current_question": "Continue?",
                "observations": [{key: "must-not-be-recorded"}],
            }
        )


def test_cli_loader_requires_the_mapping_envelope(tmp_path: Path) -> None:
    valid_path = tmp_path / "research.json"
    valid_path.write_text(
        json.dumps(
            {
                "current_question": "Continue the research?",
                "observations": [{"result": "negative"}],
            }
        ),
        encoding="utf-8",
    )
    assert _load_research_input(valid_path)["observations"] == [{"result": "negative"}]

    invalid_path = tmp_path / "array.json"
    invalid_path.write_text("[]", encoding="utf-8")
    with pytest.raises(TypeError, match="JSON mapping"):
        _load_research_input(invalid_path)


def test_problem_runtime_keeps_one_detached_ordinary_input(tmp_path: Path) -> None:
    spec, _, _ = _research_objects(tmp_path)
    supplied = {
        "current_question": "Continue?",
        "observations": [{"result": ["failure"]}],
    }
    runtime = ProblemRuntime(
        adapter=_Adapter(spec),
        research_input=supplied,
    )
    supplied["observations"][0]["result"].append("mutated")

    first = runtime.research_input
    assert first == {
        "current_question": "Continue?",
        "observations": [{"result": ["failure"]}],
    }
    assert first is not None
    first["observations"].append({"result": ["local mutation"]})
    assert runtime.research_input == {
        "current_question": "Continue?",
        "observations": [{"result": ["failure"]}],
    }


def test_research_input_record_is_one_ordinary_json_file(tmp_path: Path) -> None:
    value = {"current_question": "Continue?", "observations": []}

    path = write_research_input(str(tmp_path), value)

    assert path.name == "research_input.json"
    assert json.loads(path.read_text(encoding="utf-8")) == value
    with pytest.raises(FileExistsError):
        write_research_input(str(tmp_path), value)
