# -*- coding: utf-8 -*-
"""CLI main entry rejects legacy CN/HK symbols."""

import os
import subprocess
import sys
import unittest


class MainCliAssetScopeTestCase(unittest.TestCase):
    def test_main_py_rejects_a_share_symbol(self) -> None:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        env = {
            **os.environ,
            "MARKET_REVIEW_REGION": "us",
            "RUN_IMMEDIATELY": "true",
            "SCHEDULE_ENABLED": "false",
        }
        proc = subprocess.run(
            [
                sys.executable,
                "main.py",
                "--stocks",
                "600519",
                "--dry-run",
                "--no-notify",
                "--no-market-review",
                "--force-run",
            ],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertNotEqual(proc.returncode, 0)
        combined = (proc.stdout or "") + (proc.stderr or "")
        self.assertIn("不再接受", combined)


if __name__ == "__main__":
    unittest.main()
