from __future__ import annotations

from collections import Counter
from contextlib import AbstractContextManager
import inspect
import os
from pathlib import Path
from typing import Any

from ..core import EconomyState, SocietyState


CRITICAL_ECONOMY_FIELDS = {"gdp", "capital", "public_debt"}
CRITICAL_SOCIETY_FIELDS = {"trust_gov", "social_tension"}

ALLOWED_LEGACY_WRITER_MODULES = {
    "gim/core/transitions/propagate.py",
    "gim/core/transitions/reconcile.py",
}


class CriticalWriteContractViolation(RuntimeError):
    pass


_ORIGINAL_ECONOMY_SETATTR = EconomyState.__setattr__
_ORIGINAL_SOCIETY_SETATTR = SocietyState.__setattr__
_ACTIVE_GUARD: "CriticalWriteGuard | None" = None
_PATCHED = False


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _rel_module_path(frame_filename: str) -> str:
    path = Path(frame_filename).resolve()
    try:
        return str(path.relative_to(_repo_root()))
    except ValueError:
        return str(path)


def _detect_writer_module() -> str:
    frame = inspect.currentframe()
    try:
        current = frame
        while current is not None:
            filename = current.f_code.co_filename
            rel = _rel_module_path(filename)
            if rel.startswith("gim/core/") and not rel.startswith("gim/core/transitions/write_guard.py"):
                return rel
            current = current.f_back
    finally:
        del frame
    return "unknown"


def _intercept_write(
    obj: Any,
    *,
    field_path: str,
    attr_name: str,
    value: Any,
    original_setattr,
) -> None:
    global _ACTIVE_GUARD
    guard = _ACTIVE_GUARD
    if guard is not None and guard.active:
        writer_module = _detect_writer_module()
        guard.record_write(writer_module=writer_module, field_name=field_path, value=value)
    original_setattr(obj, attr_name, value)


def _economy_setattr(obj: EconomyState, name: str, value: Any) -> None:
    if name in CRITICAL_ECONOMY_FIELDS:
        _intercept_write(
            obj,
            field_path=f"economy.{name}",
            attr_name=name,
            value=value,
            original_setattr=_ORIGINAL_ECONOMY_SETATTR,
        )
        return
    _ORIGINAL_ECONOMY_SETATTR(obj, name, value)


def _society_setattr(obj: SocietyState, name: str, value: Any) -> None:
    if name in CRITICAL_SOCIETY_FIELDS:
        _intercept_write(
            obj,
            field_path=f"society.{name}",
            attr_name=name,
            value=value,
            original_setattr=_ORIGINAL_SOCIETY_SETATTR,
        )
        return
    _ORIGINAL_SOCIETY_SETATTR(obj, name, value)


def _ensure_patched() -> None:
    global _PATCHED
    if _PATCHED:
        return
    EconomyState.__setattr__ = _economy_setattr  # type: ignore[assignment]
    SocietyState.__setattr__ = _society_setattr  # type: ignore[assignment]
    _PATCHED = True


class CriticalWriteGuard(AbstractContextManager):
    def __init__(
        self,
        *,
        mode: str = "off",
        allowed_writer_modules: set[str] | None = None,
    ) -> None:
        self.mode = mode
        self.active = mode != "off"
        self.phase = "pre"
        self.allowed_writer_modules = allowed_writer_modules or set(ALLOWED_LEGACY_WRITER_MODULES)
        self.records: list[dict[str, Any]] = []

    def set_phase(self, phase: str) -> None:
        self.phase = phase

    def record_write(self, *, writer_module: str, field_name: str, value: Any) -> None:
        record = {
            "phase": self.phase,
            "writer_module": writer_module,
            "field": field_name,
            "value": float(value) if isinstance(value, (int, float)) else value,
        }
        self.records.append(record)

        if self.mode == "strict" and writer_module not in self.allowed_writer_modules:
            raise CriticalWriteContractViolation(
                f"Critical write violation: {field_name} written by {writer_module} during phase={self.phase}"
            )

    def summary(self) -> dict[str, Any]:
        by_phase = Counter((record["phase"] for record in self.records))
        by_module = Counter((record["writer_module"] for record in self.records))
        by_field = Counter((record["field"] for record in self.records))
        return {
            "mode": self.mode,
            "record_count": len(self.records),
            "by_phase": dict(sorted(by_phase.items())),
            "by_module": dict(sorted(by_module.items())),
            "by_field": dict(sorted(by_field.items())),
        }

    def __enter__(self) -> "CriticalWriteGuard":
        global _ACTIVE_GUARD
        _ensure_patched()
        _ACTIVE_GUARD = self
        self.active = self.mode != "off"
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        global _ACTIVE_GUARD
        _ACTIVE_GUARD = None


def resolve_guard_mode(*, phase_trace_requested: bool) -> str:
    raw = os.getenv("GIM15_CRITICAL_WRITE_GUARD")
    if raw:
        return raw.strip().lower()
    return "observe" if phase_trace_requested else "off"


__all__ = [
    "ALLOWED_LEGACY_WRITER_MODULES",
    "CriticalWriteContractViolation",
    "CriticalWriteGuard",
    "resolve_guard_mode",
]
