from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from scion.proposal.code_research_session import _bounded_test_projection
from scion.verification.development import (
    BubblewrapDevelopmentSandbox,
    write_development_probe_source,
)
from scion.verification.development_probe import bounded_probe_diagnostic


def _probe(tmp_path, source, *, sandbox=None, timeout=10):
    runtime = tmp_path / "problem-runtime"
    runtime.mkdir(exist_ok=True)
    path = write_development_probe_source(
        source, tmp_path, max_chars=64000, max_bytes=100000
    )
    return (sandbox or BubblewrapDevelopmentSandbox()).run_probe(
        workspace=str(tmp_path),
        probe_path=path,
        timeout_sec=timeout,
        problem_runtime_root=str(runtime),
    )


@pytest.mark.parametrize(
    "source,outcome,phase,kind,line",
    [
        ("def test_ok(): assert True", "passed", None, None, None),
        (
            "def test_no():\n    assert False, '/private/SECRET'",
            "failed",
            "call",
            "assertion_error",
            2,
        ),
        (
            "def test_no():\n    object().missing",
            "failed",
            "call",
            "attribute_error",
            2,
        ),
        (
            "def test_no():\n    raise TypeError('/private/SECRET')",
            "failed",
            "call",
            "type_error",
            2,
        ),
        (
            "def test_no():\n    raise ValueError('/private/SECRET')",
            "failed",
            "call",
            "value_error",
            2,
        ),
        ("def test_no():\n    missing_name()", "failed", "call", "name_error", 2),
        (
            "def test_no():\n    raise RuntimeError('/private/SECRET')",
            "failed",
            "call",
            "other_exception",
            2,
        ),
        (
            "import missing_public_module",
            "inconclusive",
            "collection",
            "import_error",
            1,
        ),
        ("def test_broken(: pass", "inconclusive", "collection", "syntax_error", 1),
        (
            "import pytest\n@pytest.fixture\ndef fixture():\n    object().missing\ndef test_no(fixture): pass",
            "failed",
            "setup",
            "attribute_error",
            4,
        ),
        (
            "import pytest\n@pytest.fixture\ndef fixture():\n    yield\n    object().missing\ndef test_no(fixture): pass",
            "failed",
            "teardown",
            "attribute_error",
            5,
        ),
    ],
)
def test_real_probe_structural_failure_only(
    tmp_path, source, outcome, phase, kind, line
):
    result = _probe(tmp_path, source)
    assert result.outcome == outcome
    assert result.diagnostic == (
        {"phase": phase, "exception_kind": kind, "probe_line": line} if phase else None
    )
    assert "SECRET" not in repr(result)
    assert str(tmp_path) not in repr(result)


@pytest.mark.parametrize(
    "source,outcome",
    [
        ("import os\ndef test_exit(): os._exit(1)", "failed"),
        ("def test_hang():\n    while True: pass", "timeout"),
        ("def no_test(): pass", "inconclusive"),
    ],
)
def test_probe_without_diagnostic_keeps_exit_semantics(tmp_path, source, outcome):
    result = _probe(tmp_path, source, timeout=1)
    assert result.outcome == outcome
    assert result.diagnostic is None


def test_skips_and_expected_failures_do_not_mask_first_actual_failure(tmp_path):
    result = _probe(
        tmp_path,
        "import pytest\n"
        "def test_skip(): pytest.skip('SECRET')\n"
        "@pytest.mark.xfail\n"
        "def test_expected(): assert False\n"
        "def test_actual(): object().missing\n",
    )
    assert result.outcome == "failed"
    assert result.diagnostic == {
        "phase": "call",
        "exception_kind": "attribute_error",
        "probe_line": 5,
    }


@pytest.mark.parametrize(
    "raw",
    [
        b"SECRET",
        b"x" * 513,
        b'{"phase":"call","exception_kind":"SECRET"}',
        b'{"phase":"call","exception_kind":"assertion_error","path":"/private/SECRET"}',
        b'{"phase":"call","exception_kind":"assertion_error","probe_line":999}',
        b'{"phase":"call","exception_kind":"assertion_error","probe_line":true}',
        b"[]",
        b"null",
        b"\xff",
    ],
)
def test_child_report_is_bounded_and_untrusted(tmp_path, raw):
    class ForgedSandbox(BubblewrapDevelopmentSandbox):
        def _execute(self, argv, timeout_sec, *, stdout):
            stdout.write(raw)
            return "exited", 1

    result = _probe(tmp_path, "def test_one(): assert False", sandbox=ForgedSandbox())
    assert result.outcome == "failed"
    assert result.diagnostic is None


@pytest.mark.parametrize(
    "diagnostic",
    [
        {"phase": [], "exception_kind": "assertion_error"},
        {"phase": "call", "exception_kind": {}},
        {"phase": "call", "exception_kind": "assertion_error", "message": "SECRET"},
        {"phase": "call", "exception_kind": "assertion_error", "probe_line": -1},
        {"phase": "call", "exception_kind": "assertion_error", "probe_line": 3},
        {"phase": "call", "exception_kind": "assertion_error", "probe_line": 1.0},
    ],
)
def test_consumer_independently_drops_invalid_hints(diagnostic):
    assert bounded_probe_diagnostic(diagnostic, max_probe_line=2) is None
    projection = _bounded_test_projection(
        {
            "outcome": "passed",
            "checks": [],
            "falsifier_outcome": "failed",
            "falsifier_diagnostic": diagnostic,
        },
        draft_revision=1,
        patch_paths=frozenset(),
        max_probe_line=2,
    )
    assert "falsifier_diagnostic" not in projection
    assert projection["falsifier_outcome"] == "failed"
    assert "SECRET" not in json.dumps(projection)


@pytest.mark.parametrize(
    "outcome,lines,visible",
    [
        ("failed", 2, True),
        ("inconclusive", 2, True),
        ("passed", 2, False),
        ("timeout", 2, False),
        ("unavailable", 2, False),
        ("failed", 0, False),
    ],
)
def test_diagnostic_cannot_supply_or_override_an_outcome(outcome, lines, visible):
    hint = {"phase": "call", "exception_kind": "attribute_error", "probe_line": 2}
    projection = _bounded_test_projection(
        {
            "outcome": "failed",
            "checks": [],
            "falsifier_outcome": outcome,
            "falsifier_diagnostic": hint,
        },
        draft_revision=1,
        patch_paths=frozenset(),
        max_probe_line=lines,
    )
    assert ("falsifier_diagnostic" in projection) is visible
    assert projection["outcome"] == "failed"
    assert projection["falsifier_outcome"] == outcome


def test_public_cvrp_example_runs_real_source_without_framework(tmp_path):
    root = Path(__file__).resolve().parents[2] / "problems/cvrp"
    tree = ast.parse((root / "tests/test_solver.py").read_text())
    example = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(t, ast.Name) and t.id == "PUBLIC_PROBE_EXAMPLE"
            for t in node.targets
        )
    )
    for source in (root / "policies").rglob("*.py"):
        destination = tmp_path / source.relative_to(root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    runtime = tmp_path / "problem-runtime/cvrp"
    runtime.mkdir(parents=True)
    for name in ("__init__.py", "models.py"):
        (runtime / name).write_bytes((root / name).read_bytes())
    result = _probe(tmp_path, example)
    assert result.outcome == "passed", result
