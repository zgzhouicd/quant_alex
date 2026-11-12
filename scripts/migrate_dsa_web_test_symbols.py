#!/usr/bin/env python3
"""Replace legacy CN/HK fixture codes in dsa-web Vitest files with US examples.

Deprecated: blind replace breaks mixed assertions — prefer editing tests file-by-file.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "apps" / "dsa-web" / "src"

REPLACEMENTS = [
    ("600519.SH", "AAPL.US"),
    ("600519", "AAPL"),
    ("000001", "MSFT"),
    ("300750", "TSLA"),
    ("00700.HK", "MSFT"),
    ("HK00700", "MSFT"),
    ("贵州茅台", "苹果"),
    ("腾讯控股", "微软"),
    ("茅台", "苹果"),
]


def main() -> None:
    changed = 0
    for path in sorted(ROOT.rglob("__tests__/*")):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        text = path.read_text(encoding="utf-8")
        orig = text
        for old, new in REPLACEMENTS:
            text = text.replace(old, new)
        if text != orig:
            path.write_text(text, encoding="utf-8")
            print(f"updated {path.relative_to(ROOT.parent)}")
            changed += 1
    print(f"done: {changed} files")


if __name__ == "__main__":
    main()
