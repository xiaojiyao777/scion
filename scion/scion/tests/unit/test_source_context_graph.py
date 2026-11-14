from __future__ import annotations

import pytest
from scion.proposal.context_manager.source_graph import (
    ordered_source_paths,
    source_graph_roles,
)


def test_graph_uses_independent_dependency_and_caller_closures() -> None:
    sources = {
        "pkg/target.py": "from .dep import helper\n",
        "pkg/dep.py": "from .leaf import VALUE\ndef helper(): return VALUE\n",
        "pkg/leaf.py": "VALUE = 1\n",
        "pkg/caller.py": "from .target import target\n",
        "entry.py": "from pkg.caller import run\n",
        "pkg/caller_only_dep.py": "VALUE = 2\n",
        "pkg/peer.py": "VALUE = 3\n",
    }

    roles = source_graph_roles(sources, target="pkg/target.py")

    assert roles["pkg/target.py"] == ("target",)
    assert roles["pkg/dep.py"] == ("dependency",)
    assert roles["pkg/leaf.py"] == ("dependency",)
    assert roles["pkg/caller.py"] == ("caller",)
    assert roles["entry.py"] == ("caller",)
    assert roles["pkg/caller_only_dep.py"] == ("peer",)
    assert roles["pkg/peer.py"] == ("peer",)
    assert ordered_source_paths(roles)[:3] == (
        "pkg/target.py",
        "pkg/dep.py",
        "pkg/leaf.py",
    )


def test_graph_resolves_declared_fully_qualified_problem_package_prefix() -> None:
    sources = {
        "policies/target.py": (
            "from scion.problems.generic_subject.policies.dep import helper\n"
        ),
        "policies/dep.py": "def helper(): return 1\n",
        "policies/caller.py": (
            "from scion.problems.generic_subject.policies.target import target\n"
        ),
    }

    roles = source_graph_roles(
        sources,
        target="policies/target.py",
        qualified_prefixes=("scion.problems.generic_subject.",),
    )

    assert roles["policies/dep.py"] == ("dependency",)
    assert roles["policies/caller.py"] == ("caller",)


def test_graph_does_not_guess_external_suffix_modules() -> None:
    roles = source_graph_roles(
        {
            "models.py": "VALUE = 1\n",
            "target.py": "from unrelated.vendor.models import VALUE\n",
        },
        target="target.py",
        qualified_prefixes=("scion.problems.generic_subject.",),
    )

    assert roles["models.py"] == ("peer",)


@pytest.mark.parametrize(
    "sources",
    [
        {"target.py": "def broken(:\n"},
        {"target.py": "from ..outside import value\n"},
        {"pkg.py": "VALUE = 1\n", "pkg/__init__.py": "VALUE = 2\n"},
    ],
)
def test_graph_fails_closed_on_invalid_current_source(sources) -> None:
    target = "target.py" if "target.py" in sources else "pkg.py"

    with pytest.raises(ValueError):
        source_graph_roles(sources, target=target)
