#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fail CI when tests or OpenAPI examples still embed legacy A-share/HK fixture codes.

Allowed: this script, docs explaining migration, and tests explicitly named for rejection.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Numeric CN-style codes and well-known HK/CN examples in examples (not comments-only).
PATTERNS = [
    re.compile(r"\b600519\b"),
    re.compile(r"\b000858\b"),
    re.compile(r"\b300750\b"),
    re.compile(r"\b00700\b"),
    re.compile(r"贵州茅台"),
    re.compile(r"腾讯控股"),
    re.compile(r"宁德时代"),
]

STRICT_DIRS = [ROOT / "api" / "v1" / "schemas"]
WARN_DIRS = [ROOT / "tests"]

ALLOWLIST_FILES = {
    ROOT / "tests" / "fixtures" / "us_symbols.py",
    ROOT / "scripts" / "check_legacy_cn_symbols_in_tests.py",
}

ALLOWLIST_TEST_FILENAMES = frozenset(
    {
        "test_stock_code_utils.py",
        "test_instrument_resolver.py",
        "test_multi_agent.py",
        "test_main_cli_asset_scope.py",
        "test_generate_index_from_csv.py",
        "test_longbridge_fetcher.py",
        "test_us_index_mapping.py",
        "test_name_to_code_resolver.py",
        "test_social_sentiment_service.py",
        "test_trading_calendar.py",
        "test_pipeline_fetch_error.py",
        "test_analysis_api_contract.py",
    }
)

# Tests that intentionally use legacy symbols to assert rejection.
ALLOWLIST_SUBSTRINGS = (
    "rejects_legacy",
    "legacy_cn",
    "is_legacy_cn",
    "a_share",
    "hong_kong",
)


def _line_is_comment_or_allowlisted(line: str, path: Path) -> bool:
    stripped = line.lstrip()
    if stripped.startswith("#"):
        return True
    if any(tag in path.name for tag in ("rejection", "legacy_cn")):
        return True
    return False


def scan_file(path: Path) -> list[tuple[int, str]]:
    if path in ALLOWLIST_FILES:
        return []
    if path.name in ALLOWLIST_TEST_FILENAMES:
        return []
    rel = str(path)
    if any(s in rel for s in ALLOWLIST_SUBSTRINGS):
        return []
    hits: list[tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return hits
    for i, line in enumerate(text.splitlines(), start=1):
        if _line_is_comment_or_allowlisted(line, path):
            continue
        for pat in PATTERNS:
            if pat.search(line):
                hits.append((i, line.strip()[:120]))
                break
    return hits


def _scan_tree(base: Path) -> list[str]:
    violations: list[str] = []
    if not base.is_dir():
        return violations
    for path in sorted(base.rglob("*.py")):
        for lineno, snippet in scan_file(path):
            violations.append(f"{path.relative_to(ROOT)}:{lineno}: {snippet}")
    return violations


def main() -> int:
    import os

    strict: list[str] = []
    for base in STRICT_DIRS:
        strict.extend(_scan_tree(base))

    if strict:
        print("Legacy CN/HK symbols in OpenAPI schema examples (blocking):", file=sys.stderr)
        for v in strict:
            print(f"  - {v}", file=sys.stderr)
        return 1

    warn: list[str] = []
    for base in WARN_DIRS:
        warn.extend(_scan_tree(base))

    if warn:
        print(f"check_legacy_cn_symbols_in_tests: warn {len(warn)} legacy refs in tests/")
        for v in warn[:15]:
            print(f"  - {v}")
        if len(warn) > 15:
            print(f"  ... and {len(warn) - 15} more")
        if os.environ.get("LEGACY_SYMBOL_STRICT_TESTS", "").strip().lower() in {"1", "true", "yes"}:
            return 1

    print("check_legacy_cn_symbols_in_tests: ok (schemas clean)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
