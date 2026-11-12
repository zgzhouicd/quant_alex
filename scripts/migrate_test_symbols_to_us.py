#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-shot / idempotent bulk replace legacy CN/HK fixture symbols in tests."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "tests"

SKIP_FILES = frozenset(
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
    }
)

REPLACEMENTS = [
    ("600519.SH", "AAPL"),
    ("600519", "AAPL"),
    ("000858", "NVDA"),
    ("300750", "TSLA"),
    ("000001", "MSFT"),
    ("00700.HK", "MSFT"),
    ("HK00700", "MSFT"),
    ("00700", "MSFT"),
    ("贵州茅台", "苹果公司"),
    ("腾讯控股", "微软"),
    ("宁德时代", "英伟达"),
    ("Analyze 贵州茅台", "Analyze AAPL"),
    ("茅台", "苹果"),
]


def main() -> None:
    changed = 0
    for path in sorted(ROOT.rglob("*.py")):
        if path.name in SKIP_FILES:
            continue
        if path.parts[-2:] == ("fixtures", "us_symbols.py"):
            continue
        text = path.read_text(encoding="utf-8")
        original = text
        for old, new in REPLACEMENTS:
            text = text.replace(old, new)
        if text != original:
            path.write_text(text, encoding="utf-8")
            changed += 1
            print(f"updated {path.relative_to(ROOT.parent)}")
    print(f"done, {changed} files")


if __name__ == "__main__":
    main()
