# -*- coding: utf-8 -*-
"""Fundamental context: A-share pipeline removed; expect not_supported-style payloads."""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_provider.base import DataFetcherManager


class TestFundamentalContext(unittest.TestCase):
    def test_symbols_return_not_supported_payload(self) -> None:
        manager = DataFetcherManager(fetchers=[])
        cfg = SimpleNamespace(enable_fundamental_pipeline=True)
        with patch("src.config.get_config", return_value=cfg):
            for sym in ("AAPL", "600519", "HK00700"):
                ctx = manager.get_fundamental_context(sym)
                self.assertIn(ctx["status"], ("not_supported", "partial"))
                self.assertEqual(ctx["coverage"].get("growth"), "not_supported")
                self.assertEqual(ctx["coverage"].get("capital_flow"), "not_supported")

    def test_disabled_pipeline(self) -> None:
        manager = DataFetcherManager(fetchers=[])
        cfg = SimpleNamespace(enable_fundamental_pipeline=False)
        with patch("src.config.get_config", return_value=cfg):
            ctx = manager.get_fundamental_context("AAPL")
            self.assertEqual(ctx["status"], "not_supported")


if __name__ == "__main__":
    unittest.main()
