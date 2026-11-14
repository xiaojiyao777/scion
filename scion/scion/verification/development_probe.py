"""Bounded, tainted hints from an isolated self-authored pytest probe.

The child has no private suites or framework mounted. Even so, its report is
untrusted: accept only fixed categories and a line in the submitted probe.
Never use these hints for readiness, Verification, or scientific decisions.
"""

from __future__ import annotations

from typing import Any

MAX_PROBE_REPORT_BYTES = 512


def bounded_probe_diagnostic(
    value: Any, *, max_probe_line: int
) -> dict[str, str | int] | None:
    if not isinstance(value, dict) or not {"phase", "exception_kind"} <= set(value):
        return None
    if set(value) - {"phase", "exception_kind", "probe_line"}:
        return None
    phase, kind = value["phase"], value["exception_kind"]
    if not isinstance(phase, str) or phase not in {
        "collection",
        "setup",
        "call",
        "teardown",
    }:
        return None
    if not isinstance(kind, str) or kind not in {
        "assertion_error",
        "attribute_error",
        "import_error",
        "name_error",
        "syntax_error",
        "type_error",
        "value_error",
        "other_exception",
    }:
        return None
    result: dict[str, str | int] = {"phase": phase, "exception_kind": kind}
    if "probe_line" in value:
        line = value["probe_line"]
        if type(line) is not int or not 1 <= line <= max_probe_line:
            return None
        result["probe_line"] = line
    return result


# Passed with Python -c, not imported from or mounted with the host framework.
# Pytest's normal stdout/stderr, including assertion explanations, is discarded.
# Low-level writes or a forged report can only suppress/spoof this bounded hint;
# they cannot supply a path/message or change the process exit-code outcome.
PROBE_RUNNER = r"""
import contextlib
import json
import os
import sys
import pytest

probe_path = sys.argv[1]
diagnostic = None
categories = (
    (AssertionError, "assertion_error"),
    (AttributeError, "attribute_error"),
    (ImportError, "import_error"),
    (NameError, "name_error"),
    (SyntaxError, "syntax_error"),
    (TypeError, "type_error"),
    (ValueError, "value_error"),
)

def observe(call, phase):
    global diagnostic
    if diagnostic is not None or call.excinfo is None:
        return
    error = call.excinfo.value
    # Pytest wraps import/syntax failures in CollectError. Inspect only the
    # bounded exception chain, never its formatted message/traceback/locals.
    if phase == "collection":
        for _ in range(8):
            if not isinstance(error, pytest.Collector.CollectError):
                break
            nested = error.__cause__ or error.__context__
            if nested is None or nested is error:
                break
            error = nested
    diagnostic = {
        "phase": phase,
        "exception_kind": next(
            (name for cls, name in categories if isinstance(error, cls)),
            "other_exception",
        ),
    }
    trace = error.__traceback__
    while trace is not None:
        if trace.tb_frame.f_code.co_filename == probe_path:
            diagnostic["probe_line"] = trace.tb_lineno
        trace = trace.tb_next
    if isinstance(error, SyntaxError) and error.filename == probe_path:
        diagnostic["probe_line"] = error.lineno

class ProbeHints:
    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        if outcome.get_result().failed:
            observe(call, call.when)

    def pytest_exception_interact(self, node, call, report):
        if report.failed:
            observe(call, "collection" if call.when == "collect" else call.when)

with open(os.devnull, "w") as sink:
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        result = pytest.main(sys.argv[1:], plugins=[ProbeHints()])
print(json.dumps(diagnostic, separators=(",", ":")))
sys.exit(int(result))
"""
