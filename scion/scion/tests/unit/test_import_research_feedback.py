"""C8 guidance and draft locations must agree with unchanged import checks."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from scion.config.problem import ProblemSpec, SearchSpace
from scion.contract.checks.security import (
    check_import_whitelist,
    effective_import_whitelist,
)
from scion.contract.patch_graph import PatchSetGraph
from scion.core.models import PatchFileChange, PatchProposal
from scion.proposal.code_research_session import _bounded_test_projection
from scion.proposal.engine import ProposalValidationError
from scion.verification.development import development_safety_preflight_failure


def _spec():
    spec = ProblemSpec(
        name="generic",
        root_dir=".",
        operator_categories=["generic"],
        search_space=SearchSpace(
            editable=["pkg/*.py"], frozen=[], import_whitelist=["random"]
        ),
    )
    object.__setattr__(
        spec,
        "runtime_dependencies",
        SimpleNamespace(required_python_modules=["numpy.linalg"]),
    )
    return spec


def test_effective_roots_are_the_actual_checker_policy():
    spec = _spec()
    allowed = effective_import_whitelist(spec)
    assert {"random", "math", "collections", "numpy"} <= allowed
    assert "oracle" not in allowed
    for module in (*sorted(allowed), "oracle"):
        result = check_import_whitelist(
            PatchProposal("pkg/main.py", "modify", f"import {module}\n"),
            problem_spec=spec,
        )
        assert result.passed == (module in allowed)


@pytest.mark.parametrize(
    "statement",
    [
        "import oracle",
        "from oracle import check_feasibility",
        "import numpy, oracle as checker",
    ],
)
def test_first_rejected_import_line_is_from_draft_not_raw_detail(
    statement, tmp_path: Path
):
    # A nested later import is encountered before the top-level rejection in
    # some AST traversal orders; return the earliest source line regardless.
    source = "import math\n" + statement + "\ndef f():\n    import another_forbidden\n"
    patch = PatchProposal("pkg/main.py", "modify", source)
    check = check_import_whitelist(patch, problem_spec=_spec())
    assert not check.passed
    assert check.metadata == {"source_line": 2}
    hint = development_safety_preflight_failure(
        patch=patch, problem_spec=_spec(), candidate_workspace=str(tmp_path)
    )
    assert hint.source_line == 2
    assert hint.file_path == "pkg/main.py"


def test_missing_relative_symbol_points_to_import_without_weakening_graph():
    patch = PatchProposal(
        "pkg/main.py", "modify", "# draft\nfrom .helper import absent\n"
    )
    patch.additional_changes = (
        PatchFileChange("pkg/helper.py", "create", "present = 1\n"),
    )
    result = check_import_whitelist(
        patch,
        problem_spec=_spec(),
        patch_graph=PatchSetGraph.from_patch(patch),
        is_editable_solver_file=lambda path: path.startswith("pkg/"),
    )
    assert not result.passed
    assert result.metadata == {"source_line": 2}
    patch.code_content = "from .helper import present\n"
    result = check_import_whitelist(
        patch,
        problem_spec=_spec(),
        patch_graph=PatchSetGraph.from_patch(patch),
        is_editable_solver_file=lambda path: path.startswith("pkg/"),
    )
    assert result.passed
    assert result.metadata == {}


@pytest.mark.parametrize(
    "line", [None, True, False, 0, -1, 4, 1.5, "2", [], {}, "/private/SECRET"]
)
def test_projection_rejects_invalid_or_out_of_draft_line(line):
    with pytest.raises(ProposalValidationError, match="development check"):
        _project(line)


def _project(line, **updates):
    return _bounded_test_projection(
        {
            "outcome": "preflight_rejected",
            "checks": [
                {
                    "name": "C8_import_whitelist",
                    "outcome": "preflight_rejected",
                    "reason_code": "import_whitelist_rejected",
                    "file_path": "pkg/main.py",
                    "source_line": line,
                    **updates,
                }
            ],
        },
        draft_revision=1,
        patch_paths=frozenset({"pkg/main.py"}),
        patch_line_counts={"pkg/main.py": 3},
    )


def test_projection_keeps_only_c8_editable_draft_location():
    assert _project(2)["checks"][0]["source_line"] == 2
    for updates in (
        {"name": "C9_sensitive_api", "reason_code": "sensitive_api_rejected"},
        {"file_path": None},
        {"file_path": "private.py"},
        {"detail": "PRIVATE_SENTINEL"},
    ):
        with pytest.raises(ProposalValidationError, match="development check"):
            _project(2, **updates)
