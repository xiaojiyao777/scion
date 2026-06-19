#!/usr/bin/env python3
"""Check the local gpt-5.5 proxy with a real chat completion."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8080"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_API_KEY = "pwd"
UNHEALTHY_EXIT = 64


@dataclass(frozen=True)
class ProbeResult:
    ok: bool
    http_status: int | None
    code: str
    message: str
    classification: str
    content_len: int = 0
    finish_reason: str | None = None


def normalize_base_url(base_url: str) -> str:
    value = base_url.strip().rstrip("/")
    if not value:
        raise ValueError("base URL must not be empty")
    if not value.endswith("/v1"):
        value += "/v1"
    return value


def classify_failure(http_status: int | None, body: str) -> tuple[str, str, str]:
    message = body.strip()
    code = ""
    try:
        payload = json.loads(body)
    except Exception:
        payload = None
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = str(error.get("message") or message)
            code = str(error.get("code") or "")

    lowered = f"{code} {message}".lower()
    if "refresh_token_invalidated" in lowered or "token has been invalidated" in lowered:
        return code or "auth_invalidated", message, "auth_token_invalidated"
    if "not authenticated" in lowered or "login first" in lowered:
        return code or "not_authenticated", message, "not_authenticated"
    if "no available accounts" in lowered or "all accounts exhausted" in lowered:
        return code or "no_available_accounts", message, "no_available_accounts"
    if http_status == 401:
        return code or "unauthorized", message, "unauthorized"
    if http_status == 429:
        return code or "rate_limited", message, "rate_limited"
    return code or "request_failed", message, "request_failed"


def parse_chat_success(http_status: int, body: str) -> ProbeResult:
    try:
        payload = json.loads(body)
    except Exception:
        return ProbeResult(
            ok=False,
            http_status=http_status,
            code="bad_json",
            message=body[:1000],
            classification="bad_json",
        )
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list) or not choices:
        return ProbeResult(
            ok=False,
            http_status=http_status,
            code="missing_choices",
            message="chat completion response has no choices",
            classification="empty_completion",
        )
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first, dict) else {}
    content = ""
    if isinstance(message, dict):
        content = str(message.get("content") or "").strip()
    finish_reason = first.get("finish_reason") if isinstance(first, dict) else None
    if not content:
        return ProbeResult(
            ok=False,
            http_status=http_status,
            code="empty_completion",
            message=f"empty completion; finish_reason={finish_reason}",
            classification="empty_completion",
            finish_reason=str(finish_reason) if finish_reason is not None else None,
        )
    return ProbeResult(
        ok=True,
        http_status=http_status,
        code="ok",
        message="chat completion returned non-empty content",
        classification="healthy",
        content_len=len(content),
        finish_reason=str(finish_reason) if finish_reason is not None else None,
    )


def post_json(url: str, payload: dict[str, Any], *, api_key: str | None, timeout: float) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key is not None:
        headers["Authorization"] = "Bearer " + api_key
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def get_text(url: str, *, timeout: float) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def probe_chat(base_url: str, model: str, api_key: str, timeout: float) -> ProbeResult:
    url = normalize_base_url(base_url) + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Reply exactly with the two letters OK and nothing else.",
            }
        ],
        "max_tokens": 16,
    }
    try:
        status, body = post_json(url, payload, api_key=api_key, timeout=timeout)
    except Exception as exc:
        return ProbeResult(
            ok=False,
            http_status=None,
            code=type(exc).__name__,
            message=str(exc),
            classification="transport_error",
        )
    if status == 200:
        return parse_chat_success(status, body)
    code, message, classification = classify_failure(status, body)
    return ProbeResult(
        ok=False,
        http_status=status,
        code=code,
        message=message,
        classification=classification,
    )


def fetch_auth_status(base_url: str, timeout: float) -> dict[str, Any] | None:
    root = base_url.strip().rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3].rstrip("/")
    try:
        status, body = get_text(root + "/auth/status", timeout=timeout)
    except Exception:
        return None
    if status != 200:
        return None
    try:
        payload = json.loads(body)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def fetch_login_url(base_url: str, timeout: float) -> str:
    root = base_url.strip().rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3].rstrip("/")
    status, body = post_json(root + "/auth/login-start", {}, api_key=None, timeout=timeout)
    if status != 200:
        return ""
    try:
        payload = json.loads(body)
    except Exception:
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("authUrl") or "")


def _resolve_api_key(args: argparse.Namespace) -> str:
    if args.api_key_env:
        value = os.environ.get(args.api_key_env, "")
        if not value:
            raise SystemExit(f"{args.api_key_env} is not set")
        return value
    return args.api_key


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Require a real chat completion from the local gpt-5.5 proxy."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    parser.add_argument("--api-key-env", default=None)
    parser.add_argument("--timeout-sec", type=float, default=60.0)
    parser.add_argument(
        "--login-url-on-failure",
        action="store_true",
        help="Print an OAuth login URL when chat completion is not healthy.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format. Use json for machine-readable readiness checks.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON only. Alias for --format json.",
    )
    args = parser.parse_args()
    if args.api_key_env and args.api_key != DEFAULT_API_KEY:
        raise SystemExit("--api-key and --api-key-env are mutually exclusive")
    if args.timeout_sec <= 0:
        raise SystemExit("--timeout-sec must be positive")
    if args.json:
        args.format = "json"
    return args


def main() -> None:
    args = parse_args()
    api_key = _resolve_api_key(args)
    auth_status = fetch_auth_status(args.base_url, args.timeout_sec)
    result = probe_chat(args.base_url, args.model, api_key, args.timeout_sec)
    login_url = ""
    if not result.ok and args.login_url_on_failure:
        login_url = fetch_login_url(args.base_url, args.timeout_sec)

    payload: dict[str, Any] = {
        "ok": result.ok,
        "chat": asdict(result),
        "auth_status": auth_status,
    }
    if login_url:
        payload["login_url"] = login_url

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if auth_status is not None:
            pool = auth_status.get("pool") if isinstance(auth_status, dict) else {}
            active = pool.get("active") if isinstance(pool, dict) else "?"
            refreshing = pool.get("refreshing") if isinstance(pool, dict) else "?"
            print(
                "AUTH_STATUS "
                f"authenticated={auth_status.get('authenticated')} "
                f"active={active} refreshing={refreshing}"
            )
        if result.ok:
            print(
                "CHAT_COMPLETION_OK "
                f"http={result.http_status} model={args.model} "
                f"content_len={result.content_len} "
                f"finish_reason={result.finish_reason}"
            )
        else:
            print(
                "CHAT_COMPLETION_FAILED "
                f"http={result.http_status} code={result.code} "
                f"classification={result.classification} "
                f"message={result.message[:800]}"
            )
            if login_url:
                print(f"LOGIN_URL={login_url}")

    raise SystemExit(0 if result.ok else UNHEALTHY_EXIT)


if __name__ == "__main__":
    main()
