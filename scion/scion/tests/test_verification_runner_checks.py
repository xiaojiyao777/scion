"""Focused tests split from test_verification.py."""

from .verification_test_support import *  # noqa: F401,F403

class TestUnitTestsCheck:
    def test_skipped_when_no_test_file(self, tmp_path):
        """Returns passed=True with 'skipped' detail when no test file found."""
        spec = _make_spec()
        r = check_unit_tests(spec, None, str(tmp_path))
        assert r.passed is True
        assert "skipped" in r.detail
        assert r.name == "V3_unit_tests"
        assert r.severity == "light"

    def test_passes_on_valid_test_file(self, tmp_path):
        """Passing pytest file → check passes."""
        test_file = tmp_path / "test_dummy.py"
        test_file.write_text("def test_pass(): assert True\n")
        spec = _make_spec()
        spec = spec.model_copy(update={"unit_test_path": str(test_file)})
        r = check_unit_tests(spec, None, str(tmp_path))
        assert r.passed is True
        assert r.name == "V3_unit_tests"

    def test_fails_on_failing_test_file(self, tmp_path):
        """Failing pytest file → check fails."""
        test_file = tmp_path / "test_dummy.py"
        test_file.write_text("def test_fail(): assert False, 'intentional failure'\n")
        spec = _make_spec()
        spec = spec.model_copy(update={"unit_test_path": str(test_file)})
        r = check_unit_tests(spec, None, str(tmp_path))
        assert r.passed is False
        assert r.severity == "light"

    def test_uses_fallback_path_when_not_configured(self, tmp_path):
        """Falls back to tests/test_operators.py relative to root_dir."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_operators.py").write_text("def test_ok(): pass\n")
        spec = _make_spec()
        spec = spec.model_copy(update={"root_dir": str(tmp_path)})
        r = check_unit_tests(spec, None, str(tmp_path))
        assert r.passed is True


class TestRegressionTestsCheck:
    def test_skipped_when_no_test_file(self, tmp_path):
        """Returns passed=True with 'skipped' detail when no test file found."""
        spec = _make_spec()
        r = check_regression_tests(spec, None, str(tmp_path))
        assert r.passed is True
        assert "skipped" in r.detail
        assert r.name == "V4_regression_tests"
        assert r.severity == "light"

    def test_passes_on_valid_test_file(self, tmp_path):
        """Passing pytest regression file → check passes."""
        test_file = tmp_path / "test_regression.py"
        test_file.write_text("def test_pass(): assert 1 + 1 == 2\n")
        spec = _make_spec()
        spec = spec.model_copy(update={"regression_test_path": str(test_file)})
        r = check_regression_tests(spec, None, str(tmp_path))
        assert r.passed is True
        assert r.name == "V4_regression_tests"

    def test_fails_on_failing_test_file(self, tmp_path):
        """Failing regression test → check fails with light severity."""
        test_file = tmp_path / "test_regression.py"
        test_file.write_text("def test_fail(): raise AssertionError('regression')\n")
        spec = _make_spec()
        spec = spec.model_copy(update={"regression_test_path": str(test_file)})
        r = check_regression_tests(spec, None, str(tmp_path))
        assert r.passed is False
        assert r.severity == "light"

    def test_uses_fallback_path_when_not_configured(self, tmp_path):
        """Falls back to tests/test_solver.py relative to root_dir."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_solver.py").write_text("def test_noop(): pass\n")
        spec = _make_spec()
        spec = spec.model_copy(update={"root_dir": str(tmp_path)})
        r = check_regression_tests(spec, None, str(tmp_path))
        assert r.passed is True


class TestVerificationGateTestChecks:
    def test_unit_tests_in_gate_with_spec_and_runner(self, tmp_path):
        """V3_unit_tests and V4_regression_tests appear when runner+spec set."""
        spec = _make_spec()
        runner = _mock_runner()
        gate = VerificationGate(problem_spec=spec, runner=runner)
        patch = _make_patch(_VALID_CODE)
        result = gate.run(str(tmp_path), str(tmp_path), patch)
        check_names = [c.name for c in result.checks]
        assert "V3_unit_tests" in check_names
        assert "V4_regression_tests" in check_names

    def test_test_checks_absent_when_no_runner(self, tmp_path):
        """V3_unit_tests and V4_regression_tests not included without runner."""
        gate = VerificationGate()
        patch = _make_patch(_VALID_CODE)
        result = gate.run(str(tmp_path), str(tmp_path), patch)
        check_names = [c.name for c in result.checks]
        assert "V3_unit_tests" not in check_names
        assert "V4_regression_tests" not in check_names

    def test_failing_unit_test_has_light_severity(self, tmp_path):
        """Unit test failure → VerificationResult has light severity."""
        test_file = tmp_path / "test_fail.py"
        test_file.write_text("def test_fail(): assert False\n")
        spec = _make_spec()
        spec = spec.model_copy(update={"unit_test_path": str(test_file)})
        runner = _mock_runner()
        gate = VerificationGate(problem_spec=spec, runner=runner)
        patch = _make_patch(_VALID_CODE)
        result = gate.run(str(tmp_path), str(tmp_path), patch)
        assert result.passed is False
        assert result.failure_severity == "light"
        assert result.first_failure == "V3_unit_tests"
