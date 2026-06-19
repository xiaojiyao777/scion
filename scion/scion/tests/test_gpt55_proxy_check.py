import importlib.util
import subprocess
import sys
from pathlib import Path


SCION_DIR = Path(__file__).resolve().parents[2]
TOOL = SCION_DIR / "tools" / "check_gpt55_proxy.py"


def _load_tool_module():
    spec = importlib.util.spec_from_file_location("check_gpt55_proxy", TOOL)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_normalize_base_url_adds_v1_suffix() -> None:
    tool = _load_tool_module()

    assert tool.normalize_base_url("http://127.0.0.1:8080") == (
        "http://127.0.0.1:8080/v1"
    )
    assert tool.normalize_base_url("http://127.0.0.1:8080/v1") == (
        "http://127.0.0.1:8080/v1"
    )


def test_classify_token_invalidated_failure() -> None:
    tool = _load_tool_module()
    body = (
        '{"error":{"message":"All accounts exhausted (1 expired). '
        'Codex API error (401): Your authentication token has been invalidated. '
        'Please try signing in again.","code":"codex_api_error"}}'
    )

    code, message, classification = tool.classify_failure(401, body)

    assert code == "codex_api_error"
    assert "token has been invalidated" in message
    assert classification == "auth_token_invalidated"


def test_classify_not_authenticated_failure() -> None:
    tool = _load_tool_module()
    body = (
        '{"error":{"message":"Not authenticated. Please login first at /",'
        '"code":"invalid_api_key"}}'
    )

    code, _, classification = tool.classify_failure(401, body)

    assert code == "invalid_api_key"
    assert classification == "not_authenticated"


def test_parse_chat_success_requires_non_empty_content() -> None:
    tool = _load_tool_module()

    ok = tool.parse_chat_success(
        200,
        '{"choices":[{"message":{"content":"OK"},"finish_reason":"stop"}]}',
    )
    empty = tool.parse_chat_success(
        200,
        '{"choices":[{"message":{"content":""},"finish_reason":"stop"}]}',
    )

    assert ok.ok is True
    assert ok.content_len == 2
    assert ok.finish_reason == "stop"
    assert empty.ok is False
    assert empty.classification == "empty_completion"


def test_tool_help_and_api_key_env_guard() -> None:
    help_result = subprocess.run(
        [sys.executable, str(TOOL), "--help"],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "--login-url-on-failure" in help_result.stdout
    assert "--format" in help_result.stdout

    bad_result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--api-key",
            "explicit",
            "--api-key-env",
            "SCION_API_KEY",
        ],
        cwd=SCION_DIR,
        text=True,
        capture_output=True,
    )
    assert bad_result.returncode != 0
    assert "--api-key and --api-key-env are mutually exclusive" in bad_result.stderr
