"""Problem-neutral resource limits for one direct campaign invocation."""

from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ProviderCallCapExhausted(RuntimeError):
    """Raised before a provider request that would exceed the declared cap."""

    def __init__(self, *, cap: int, used: int, request_kind: str) -> None:
        self.cap = cap
        self.used = used
        self.request_kind = str(request_kind)
        super().__init__(
            "provider call cap exhausted before "
            f"{self.request_kind}: used={self.used}, cap={self.cap}"
        )


@dataclass(frozen=True)
class ResourceEnvelope:
    """Optional operator-selected caps for one fresh normal run."""

    provider_call_cap: int | None = None
    outer_hardwall_sec: int | None = None

    def __post_init__(self) -> None:
        _validate_optional_positive_int(
            self.provider_call_cap,
            field="provider_call_cap",
        )
        _validate_optional_positive_int(
            self.outer_hardwall_sec,
            field="outer_hardwall_sec",
        )

    def to_primitive(self) -> dict[str, int]:
        value: dict[str, int] = {}
        if self.provider_call_cap is not None:
            value["provider_call_cap"] = self.provider_call_cap
        if self.outer_hardwall_sec is not None:
            value["outer_hardwall_sec"] = self.outer_hardwall_sec
        return value


def normalize_resource_envelope(value: Any | None) -> ResourceEnvelope:
    """Return one validated ordinary envelope without compatibility aliases."""

    if value is None:
        return ResourceEnvelope()
    if isinstance(value, ResourceEnvelope):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("resource envelope must be a mapping")
    allowed = {"provider_call_cap", "outer_hardwall_sec"}
    unknown = [key for key in value if key not in allowed]
    if unknown:
        raise ValueError(f"unsupported resource envelope field: {unknown[0]}")
    return ResourceEnvelope(
        provider_call_cap=value.get("provider_call_cap"),
        outer_hardwall_sec=value.get("outer_hardwall_sec"),
    )


def write_resource_envelope(campaign_dir: str, value: Any) -> Path | None:
    """Write one configured ordinary envelope in a fresh campaign root."""

    envelope = normalize_resource_envelope(value)
    payload = envelope.to_primitive()
    if not payload:
        return None
    path = Path(campaign_dir) / "resource_envelope.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as output:
        json.dump(payload, output, indent=2, sort_keys=True)
        output.write("\n")
    return path


class ProviderCallBudget:
    """One thread-safe counter shared by all H/C calls in an invocation."""

    def __init__(self, cap: int | None) -> None:
        _validate_optional_positive_int(cap, field="provider_call_cap")
        self._cap = cap
        self._used = 0
        self._lock = threading.Lock()

    @property
    def cap(self) -> int | None:
        return self._cap

    @property
    def used(self) -> int:
        with self._lock:
            return self._used

    def consume(self, *, request_kind: str) -> None:
        """Reserve one actual provider request or fail before client dispatch."""

        with self._lock:
            if self._cap is not None and self._used >= self._cap:
                raise ProviderCallCapExhausted(
                    cap=self._cap,
                    used=self._used,
                    request_kind=request_kind,
                )
            self._used += 1


def _validate_optional_positive_int(value: Any, *, field: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field} must be an integer or null")
    if value <= 0:
        raise ValueError(f"{field} must be greater than zero")


__all__ = [
    "ProviderCallBudget",
    "ProviderCallCapExhausted",
    "ResourceEnvelope",
    "normalize_resource_envelope",
    "write_resource_envelope",
]
