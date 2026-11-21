"""Pure public-observation contracts; this module grants no execution capability.

Filesystem closure validation and sandbox execution belong to P1b/P2. Merely
resolving a provider or validating a descriptor does not make it runnable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

JsonObject = dict[str, Any]


class PublicObservationConfigurationError(ValueError):
    """A requested capability cannot be composed (no scientific outcome)."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True)
class PublicObservationSpec:
    schema_version: int
    fixture_paths: tuple[str, ...]
    subject_workspace_paths: tuple[str, ...]
    subject_optional_workspace_paths: tuple[str, ...]
    subject_package_paths: tuple[str, ...]
    checker_package_paths: tuple[str, ...]
    neutral_support_paths: tuple[str, ...]
    checker_neutral_support_paths: tuple[str, ...]
    runner_module: str
    checker_module: str
    input_description: str
    args_description: str
    subject_dependencies: tuple[str, ...] = ()
    checker_dependencies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise PublicObservationConfigurationError("OBS_DESCRIPTOR_INVALID")
        for paths in (
            self.fixture_paths, self.subject_workspace_paths,
            self.subject_optional_workspace_paths,
            self.subject_package_paths, self.checker_package_paths,
            self.neutral_support_paths, self.checker_neutral_support_paths,
            self.subject_dependencies, self.checker_dependencies,
        ):
            if type(paths) is not tuple:
                raise PublicObservationConfigurationError("OBS_DESCRIPTOR_INVALID")
            for path in paths:
                if (type(path) is not str or not path
                        or any(c in path for c in "\\\x00*?[]:")
                        or any(part in ("", ".", "..") for part in path.split("/"))):
                    raise PublicObservationConfigurationError("OBS_DESCRIPTOR_INVALID")
            if len(set(paths)) != len(paths):
                raise PublicObservationConfigurationError("OBS_DESCRIPTOR_INVALID")
        for module in (self.runner_module, self.checker_module):
            if (type(module) is not str or not module
                    or not all(part.isidentifier() for part in module.split("."))):
                raise PublicObservationConfigurationError("OBS_DESCRIPTOR_INVALID")
        for description in (self.input_description, self.args_description):
            if type(description) is not str or not description.strip():
                raise PublicObservationConfigurationError("OBS_DESCRIPTOR_INVALID")


class PublicObservationProvider(Protocol):
    def describe(self) -> PublicObservationSpec: ...

    def validate_input(self, value: JsonObject) -> JsonObject: ...

    def validate_args(self, value: JsonObject) -> JsonObject: ...

    def source_config(self, available_files: tuple[str, ...], *, initial: bool) -> JsonObject: ...

    def validate_source_config(self, value: JsonObject, available_files: tuple[str, ...]) -> JsonObject: ...


def resolve_public_observation_provider(
    adapter: Any, *, enabled: bool = False,
) -> PublicObservationProvider | None:
    """Resolve only on explicit opt-in, without altering ProblemAdapter.

    No imports, attribute lookup, or factory calls occur when disabled. The
    caller must still validate the actual filesystem closure before execution.
    """
    if type(enabled) is not bool:
        raise PublicObservationConfigurationError("OBS_CONFIG_INVALID")
    if not enabled:
        return None
    try:
        factory = getattr(adapter, "public_observation_provider", None)
        if factory is None:
            raise PublicObservationConfigurationError("OBS_CAPABILITY_UNAVAILABLE")
        if not callable(factory):
            raise PublicObservationConfigurationError("OBS_PROVIDER_INVALID")
        provider = factory()
        if not all(callable(getattr(provider, name, None)) for name in (
            "describe", "validate_input", "validate_args", "validate_source_config",
        )):
            raise PublicObservationConfigurationError("OBS_PROVIDER_INVALID")
        if type(provider.describe()) is not PublicObservationSpec:
            raise PublicObservationConfigurationError("OBS_DESCRIPTOR_INVALID")
        return provider
    except PublicObservationConfigurationError:
        raise
    except Exception:
        raise PublicObservationConfigurationError("OBS_PROVIDER_INVALID") from None
