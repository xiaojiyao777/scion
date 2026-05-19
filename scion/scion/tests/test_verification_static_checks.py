"""Focused tests split from test_verification.py."""

from .verification_test_support import *  # noqa: F401,F403

class TestSyntaxCheck:
    def test_valid_code_passes(self):
        r = check_syntax(_make_patch(_VALID_CODE))
        assert r.passed is True
        assert r.name == "V1_syntax"
        assert r.severity == "light"

    def test_bad_syntax_fails(self):
        r = check_syntax(_make_patch(_BAD_SYNTAX))
        assert r.passed is False
        assert r.severity == "light"
        assert "SyntaxError" in r.detail

    def test_delete_action_skipped(self):
        r = check_syntax(_make_patch(action="delete"))
        assert r.passed is True
        assert "delete" in r.detail


class TestInterfaceCheck:
    def test_valid_class_passes_ast(self, tmp_path):
        r = check_interface(_make_patch(_VALID_CODE), str(tmp_path))
        assert r.passed is True
        assert r.name == "V2_interface"

    def test_missing_execute_fails_ast(self, tmp_path):
        r = check_interface(_make_patch(_NO_EXECUTE), str(tmp_path))
        assert r.passed is False
        assert r.severity == "light"

    def test_wrong_args_fails_ast(self, tmp_path):
        r = check_interface(_make_patch(_WRONG_ARGS), str(tmp_path))
        assert r.passed is False

    def test_problem_defined_signature_passes(self, tmp_path):
        code = """\
class MyOp:
    def execute(self, solution, instance, rng):
        return solution
"""
        r = check_interface(
            _make_patch(code),
            str(tmp_path),
            operator_execute_signature="execute(self, solution, instance, rng) -> TspSolution",
        )
        assert r.passed is True

    def test_problem_defined_signature_rejects_legacy_args(self, tmp_path):
        r = check_interface(
            _make_patch(_VALID_CODE),
            str(tmp_path),
            operator_execute_signature="execute(self, solution, instance, rng) -> TspSolution",
        )
        assert r.passed is False
        assert "instance" in r.detail

    def test_delete_action_skipped(self, tmp_path):
        r = check_interface(_make_patch(action="delete"), str(tmp_path))
        assert r.passed is True

    def test_no_class_skipped(self, tmp_path):
        code = "x = 1\ndef foo(): pass\n"
        r = check_interface(_make_patch(code), str(tmp_path))
        assert r.passed is True

    def test_runtime_check_with_real_file(self, tmp_path):
        """When operator file exists in workspace, runtime check is used."""
        op_dir = tmp_path / "operators"
        op_dir.mkdir()
        op_file = op_dir / "my_op.py"
        op_file.write_text(_VALID_CODE)

        patch = _make_patch(_VALID_CODE)
        r = check_interface(patch, str(tmp_path))
        assert r.passed is True

    def test_runtime_check_fails_no_execute(self, tmp_path):
        op_dir = tmp_path / "operators"
        op_dir.mkdir()
        op_file = op_dir / "my_op.py"
        op_file.write_text(_NO_EXECUTE)

        patch = _make_patch(_NO_EXECUTE)
        r = check_interface(patch, str(tmp_path))
        assert r.passed is False

    def test_interface_check_does_not_execute_top_level_code(self, tmp_path):
        op_dir = tmp_path / "operators"
        op_dir.mkdir()
        marker = tmp_path / "executed.txt"
        code = f"""\
from pathlib import Path
Path({str(marker)!r}).write_text("executed")

class MyOp:
    def execute(self, solution, rng):
        return solution
"""
        (op_dir / "my_op.py").write_text(code)

        patch = _make_patch(code)
        r = check_interface(patch, str(tmp_path))
        assert r.passed is True
        assert not marker.exists()

    def test_interface_check_rejects_invalid_patch_path(self, tmp_path):
        patch = PatchProposal(
            file_path="operators/../../outside.py",
            action="modify",
            code_content=_VALID_CODE,
        )
        r = check_interface(patch, str(tmp_path))
        assert r.passed is False
        assert "path segment" in r.detail

    def test_surface_policy_missing_required_function_fails_ast(self, tmp_path):
        patch = PatchProposal(
            file_path="policies/search_policy.py",
            action="modify",
            code_content=(
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    return 0.5\n"
            ),
        )

        r = check_interface(
            patch,
            str(tmp_path),
            problem_spec=_make_policy_interface_spec(),
            selected_surface="search_policy",
        )

        assert r.passed is False
        assert r.name == "V2_interface"
        assert "missing required functions ['max_operator_rounds']" in r.detail

    def test_surface_policy_declared_signature_fails_ast(self, tmp_path):
        patch = PatchProposal(
            file_path="policies/search_policy.py",
            action="modify",
            code_content=(
                "def baseline_time_fraction(instance):\n"
                "    return 0.5\n\n"
                "def max_operator_rounds(instance, time_limit_sec):\n"
                "    return 10\n"
            ),
        )

        r = check_interface(
            patch,
            str(tmp_path),
            problem_spec=_make_policy_interface_spec(),
            selected_surface="search_policy",
        )

        assert r.passed is False
        assert "do not match declared prefix" in r.detail

    def test_surface_policy_static_return_constraint_fails_ast(self, tmp_path):
        patch = PatchProposal(
            file_path="policies/search_policy.py",
            action="modify",
            code_content=(
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    return 1.5\n\n"
                "def max_operator_rounds(instance, time_limit_sec):\n"
                "    return 10\n"
            ),
        )

        r = check_interface(
            patch,
            str(tmp_path),
            problem_spec=_make_policy_interface_spec(),
            selected_surface="search_policy",
        )

        assert r.passed is False
        assert "outside declared range" in r.detail

    def test_valid_surface_policy_module_without_class_passes_ast(self, tmp_path):
        patch = PatchProposal(
            file_path="policies/search_policy.py",
            action="modify",
            code_content=(
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    return 0.5\n\n"
                "def max_operator_rounds(instance, time_limit_sec):\n"
                "    return 10\n"
            ),
        )

        r = check_interface(
            patch,
            str(tmp_path),
            problem_spec=_make_policy_interface_spec(),
            selected_surface="search_policy",
        )

        assert r.passed is True
        assert r.name == "V2_interface"

    def test_selected_surface_target_mismatch_fails_ast(self, tmp_path):
        spec = _make_policy_interface_spec()
        patch = _make_patch(_VALID_CODE)

        r = check_interface(
            patch,
            str(tmp_path),
            problem_spec=spec,
            selected_surface="search_policy",
        )

        assert r.passed is False
        assert "is not in target files" in r.detail
