from __future__ import annotations

import re
from pathlib import Path
import unittest

from gim.runtime import REPO_ROOT
from gim.core.transitions import ALLOWED_LEGACY_WRITER_MODULES


CRITICAL_ASSIGNMENT_PATTERNS = (
    re.compile(r"\.economy\.gdp\s*[\+\-\*/]?="),
    re.compile(r"\.economy\.capital\s*[\+\-\*/]?="),
    re.compile(r"\.economy\.public_debt\s*[\+\-\*/]?="),
    re.compile(r"\.society\.trust_gov\s*[\+\-\*/]?="),
    re.compile(r"\.society\.social_tension\s*[\+\-\*/]?="),
)

# Contract: only centralized transition modules may write critical fields.
ALLOWED_LEGACY_WRITERS = set(ALLOWED_LEGACY_WRITER_MODULES)


class CriticalWriteAuditTests(unittest.TestCase):
    def test_no_unexpected_critical_field_writers(self) -> None:
        core_dir = REPO_ROOT / "gim" / "core"
        offenders: dict[str, int] = {}

        for path in core_dir.rglob("*.py"):
            rel = str(path.relative_to(REPO_ROOT))
            text = path.read_text(encoding="utf-8")
            count = 0
            for pattern in CRITICAL_ASSIGNMENT_PATTERNS:
                count += len(pattern.findall(text))
            if count > 0:
                offenders[rel] = count

        unexpected = sorted(set(offenders) - ALLOWED_LEGACY_WRITERS)
        self.assertFalse(
            unexpected,
            f"Unexpected critical-field writer modules: {unexpected}. "
            f"Current offenders: {offenders}",
        )
        self.assertIn("gim/core/transitions/reconcile.py", offenders)


if __name__ == "__main__":
    unittest.main()
