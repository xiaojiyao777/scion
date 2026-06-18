#!/usr/bin/env python3
"""Write report-only launcher status for failed completion preflight."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "outer-wrapper.v1"


def build_status(*, exit_code: int, detail_path: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "finished",
        "wrapper_exit_status": int(exit_code),
        "pre_campaign_completion_preflight": "failed",
        "pre_campaign_completion_preflight_detail_file": detail_path.name,
        "pre_campaign_completion_preflight_detail_path": str(detail_path),
    }
    try:
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        payload["pre_campaign_completion_preflight_detail_error"] = str(exc)
        return payload
    if not isinstance(detail, dict):
        payload["pre_campaign_completion_preflight_detail_error"] = (
            "detail artifact is not a JSON object"
        )
        return payload

    chat = detail.get("chat")
    if isinstance(chat, dict):
        _copy_if_present(
            payload,
            chat,
            "classification",
            "pre_campaign_completion_preflight_classification",
        )
        _copy_if_present(
            payload,
            chat,
            "http_status",
            "pre_campaign_completion_preflight_http_status",
        )
        _copy_if_present(
            payload,
            chat,
            "code",
            "pre_campaign_completion_preflight_code",
        )

    auth_status = detail.get("auth_status")
    if isinstance(auth_status, dict):
        _copy_if_present(
            payload,
            auth_status,
            "authenticated",
            "pre_campaign_completion_preflight_authenticated",
        )
        pool = auth_status.get("pool")
        if isinstance(pool, dict):
            _copy_if_present(
                payload,
                pool,
                "active",
                "pre_campaign_completion_preflight_active_accounts",
            )
            _copy_if_present(
                payload,
                pool,
                "refreshing",
                "pre_campaign_completion_preflight_refreshing_accounts",
            )

    login_url = str(detail.get("login_url") or "")
    payload["pre_campaign_completion_preflight_login_url_present"] = bool(login_url)
    action = _operator_action(str(payload.get("pre_campaign_completion_preflight_classification") or ""))
    if action:
        payload["pre_campaign_completion_preflight_operator_action"] = action
    return payload


def write_status(*, output_path: Path, exit_code: int, detail_path: Path) -> None:
    payload = build_status(exit_code=exit_code, detail_path=detail_path)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--exit-code", required=True, type=int)
    parser.add_argument("--detail", required=True, type=Path)
    args = parser.parse_args(argv)
    write_status(
        output_path=args.output,
        exit_code=args.exit_code,
        detail_path=args.detail,
    )
    return 0


def _copy_if_present(
    target: dict[str, Any],
    source: dict[str, Any],
    source_key: str,
    target_key: str,
) -> None:
    if source_key in source:
        target[target_key] = source[source_key]


def _operator_action(classification: str) -> str:
    if classification in {"auth_token_invalidated", "not_authenticated", "unauthorized"}:
        return (
            "Refresh the local proxy login, then rerun launch readiness until "
            "launch_ready=true."
        )
    if classification == "no_available_accounts":
        return (
            "Wait for an active GPT-5.5 account or refresh the proxy account pool, "
            "then rerun launch readiness."
        )
    if classification == "rate_limited":
        return "Wait for the rate limit window to clear, then rerun launch readiness."
    if classification == "transport_error":
        return (
            "Start or repair the local GPT-5.5 proxy endpoint, then rerun launch readiness."
        )
    if classification:
        return (
            "Inspect the completion preflight detail artifact, repair the proxy or "
            "model route, then rerun launch readiness."
        )
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
