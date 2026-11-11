#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
列出当前 FastAPI 应用 OpenAPI 中的 HTTP 路径与方法（只读）。

用法：
  python scripts/list_openapi_paths.py
  python scripts/list_openapi_paths.py --json

用于维护 docs/api-v1-surface.md 时与 OpenAPI 真源对齐。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 项目根目录
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="List OpenAPI paths from create_app()")
    parser.add_argument("--json", action="store_true", help="Print JSON array of {method, path, tags}")
    args = parser.parse_args()

    from api.app import create_app

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(static_dir=Path(tmp))
        schema = app.openapi()
        paths = schema.get("paths") or {}
        rows: list[dict] = []
        for path, path_item in sorted(paths.items()):
            for method, op in sorted(path_item.items()):
                if method.upper() not in (
                    "GET",
                    "POST",
                    "PUT",
                    "DELETE",
                    "PATCH",
                    "HEAD",
                    "OPTIONS",
                ):
                    continue
                tags = op.get("tags") or []
                summary = (op.get("summary") or "").replace("\n", " ")
                rows.append(
                    {
                        "method": method.upper(),
                        "path": path,
                        "tags": tags,
                        "summary": summary,
                    }
                )

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    for r in rows:
        tag = ",".join(r["tags"]) if r["tags"] else "-"
        print(f"{r['method']:7} {r['path']:55} [{tag}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
