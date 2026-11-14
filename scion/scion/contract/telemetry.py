"""Telemetry declaration helpers for contract checks."""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from scion.contract.schema import MECHANISM_ID_RE


def surface_mechanism_telemetry_declarations(
    surface: Any | None,
) -> tuple[str, ...]:
    evidence = getattr(surface, "evidence", None) if surface is not None else None
    declarations: list[str] = []
    telemetry = (
        getattr(evidence, "mechanism_telemetry", None)
        if evidence is not None
        else None
    )
    if isinstance(telemetry, Mapping):
        for raw_key, raw_value in telemetry.items():
            key = str(raw_key or "").strip()
            if not key:
                continue
            activation = getattr(raw_value, "activation_runtime_fields", None)
            effect = getattr(raw_value, "effect_probe_runtime_fields", None)
            if isinstance(raw_value, Mapping):
                activation = raw_value.get("activation_runtime_fields", activation)
                effect = raw_value.get("effect_probe_runtime_fields", effect)
            if activation or effect:
                declarations.append(mechanism_declaration_key(key))

    for field_name in (
        "mechanism_activation_runtime_fields",
        "mechanism_effect_probe_runtime_fields",
        "mechanism_effect_runtime_fields",
    ):
        raw_value = (
            getattr(evidence, field_name, None)
            if evidence is not None
            else None
        )
        declarations.extend(mechanism_declarations_from_probe_value(raw_value))

    return tuple(
        dict.fromkeys(declaration for declaration in declarations if declaration)
    )


def mechanism_id_matches_declaration(
    mechanism_id: str,
    declarations: tuple[str, ...],
) -> bool:
    for declaration in declarations:
        if declaration == mechanism_id:
            return True
        if "*" in declaration and mechanism_wildcard_match(mechanism_id, declaration):
            return True
    return False


def mechanism_wildcard_match(mechanism_id: str, declaration: str) -> bool:
    if declaration == "*":
        return True
    if not MECHANISM_ID_RE.fullmatch(mechanism_id):
        return False
    pattern = re.escape(declaration).replace(r"\*", "[a-z0-9_]*")
    return re.fullmatch(pattern, mechanism_id) is not None


def mechanism_declarations_from_probe_value(value: Any) -> list[str]:
    declarations: list[str] = []
    if value in (None, "", [], (), {}):
        return declarations
    if isinstance(value, Mapping):
        for raw_key, raw_value in value.items():
            key = mechanism_declaration_key(str(raw_key or "").strip())
            if key:
                declarations.append(key)
            declarations.extend(mechanism_declarations_from_probe_value(raw_value))
        return declarations
    if isinstance(value, str):
        if "{mechanism}" in value:
            declarations.append("*")
        return declarations
    try:
        iterator = iter(value)
    except TypeError:
        return declarations
    for item in iterator:
        declarations.extend(mechanism_declarations_from_probe_value(item))
    return declarations


def mechanism_declaration_key(key: str) -> str:
    if key in {"{mechanism}", "*", "default", "__default__", "all", "__all__"}:
        return "*"
    if MECHANISM_ID_RE.fullmatch(key):
        return key
    if "*" in key:
        return key
    return ""
