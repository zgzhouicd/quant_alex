# -*- coding: utf-8 -*-
"""Regression tests for TickFlow market-review manager fallback."""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_provider.base import DataFetcherManager


class _DummyFetcher:
    def __init__(self, name, indices=None, stats=None, indices_error=None):
        self.name = name
        self.priority = 1
        self.indices = indices
        self.stats = stats
        self.indices_error = indices_error
        self.index_calls = 0
        self.stats_calls = 0
        self.last_region = None

    def get_main_indices(self, region="cn"):
        self.index_calls += 1
        self.last_region = region
        if self.indices_error is not None:
            raise self.indices_error
        return self.indices

    def get_market_stats(self):
        self.stats_calls += 1
        return self.stats


class _DummyTickFlowFetcher:
    def __init__(self, indices=None, stats=None, error=None):
        self.indices = indices
        self.stats = stats
        self.error = error
        self.closed = False

    def get_main_indices(self, region="cn"):
        if self.error is not None:
            raise self.error
        return self.indices

    def get_market_stats(self):
        if self.error is not None:
            raise self.error
        return self.stats

    def close(self):
        self.closed = True


class TestTickFlowMarketReviewFallback(unittest.TestCase):
    def test_legacy_cn_region_maps_to_us_for_indices(self):
        """region=cn is deprecated; index fetch uses the normal chain with region=us."""
        manager = DataFetcherManager.__new__(DataFetcherManager)
        primary = _DummyFetcher("YfinanceFetcher", indices=[{"code": "^GSPC"}])
        manager._fetchers = [primary]
        manager._get_tickflow_fetcher = Mock(
            side_effect=AssertionError("TickFlow is not used for get_main_indices"),
        )

        data = DataFetcherManager.get_main_indices(manager, region="cn")

        self.assertEqual(data, [{"code": "^GSPC"}])
        self.assertEqual(primary.index_calls, 1)
        self.assertEqual(primary.last_region, "us")

    def test_indices_try_next_fetcher_when_first_raises(self):
        manager = DataFetcherManager.__new__(DataFetcherManager)
        broken = _DummyFetcher(
            "BrokenFetcher",
            indices_error=RuntimeError("upstream failure"),
            indices=[{"code": "ignored"}],
        )
        backup = _DummyFetcher("YfinanceFetcher", indices=[{"code": "^GSPC"}])
        manager._fetchers = [broken, backup]

        data = DataFetcherManager.get_main_indices(manager, region="us")

        self.assertEqual(data, [{"code": "^GSPC"}])
        self.assertEqual(broken.index_calls, 1)
        self.assertEqual(backup.index_calls, 1)

    def test_indices_try_next_fetcher_when_first_returns_empty(self):
        manager = DataFetcherManager.__new__(DataFetcherManager)
        empty_first = _DummyFetcher("EmptyFetcher", indices=[])
        backup = _DummyFetcher("YfinanceFetcher", indices=[{"code": "^IXIC"}])
        manager._fetchers = [empty_first, backup]

        data = DataFetcherManager.get_main_indices(manager, region="us")

        self.assertEqual(data, [{"code": "^IXIC"}])
        self.assertEqual(empty_first.index_calls, 1)
        self.assertEqual(backup.index_calls, 1)

    def test_us_region_uses_primary_fetcher_for_indices(self):
        manager = DataFetcherManager.__new__(DataFetcherManager)
        primary = _DummyFetcher("YfinanceFetcher", indices=[{"code": "^GSPC"}])
        manager._fetchers = [primary]
        manager._get_tickflow_fetcher = Mock(
            side_effect=AssertionError("TickFlow is not used for get_main_indices"),
        )

        data = DataFetcherManager.get_main_indices(manager, region="us")

        self.assertEqual(data, [{"code": "^GSPC"}])
        self.assertEqual(primary.index_calls, 1)

    def test_manager_falls_back_when_tickflow_market_stats_fails(self):
        manager = DataFetcherManager.__new__(DataFetcherManager)
        fallback = _DummyFetcher(
            "AkshareFetcher",
            stats={"up_count": 1, "down_count": 2, "flat_count": 3},
        )
        manager._fetchers = [fallback]
        manager._get_tickflow_fetcher = lambda: _DummyTickFlowFetcher(
            error=RuntimeError("tickflow down")
        )

        data = DataFetcherManager.get_market_stats(manager)

        self.assertEqual(data["up_count"], 1)
        self.assertEqual(fallback.stats_calls, 1)

    @patch("src.config.get_config")
    def test_manager_skips_tickflow_without_api_key(self, mock_get_config):
        mock_get_config.return_value = SimpleNamespace(tickflow_api_key=None)

        manager = DataFetcherManager.__new__(DataFetcherManager)
        fallback = _DummyFetcher(
            "AkshareFetcher",
            stats={"up_count": 2, "down_count": 1, "flat_count": 0},
        )
        manager._fetchers = [fallback]

        data = DataFetcherManager.get_market_stats(manager)

        self.assertEqual(data["up_count"], 2)
        self.assertEqual(fallback.stats_calls, 1)

    def test_manager_close_releases_tickflow_fetcher(self):
        manager = DataFetcherManager.__new__(DataFetcherManager)
        tickflow_fetcher = _DummyTickFlowFetcher(indices=[{"code": "000001"}])
        manager._tickflow_fetcher = tickflow_fetcher
        manager._tickflow_api_key = "tf-secret"
        manager._tickflow_lock = None

        DataFetcherManager.close(manager)

        self.assertTrue(tickflow_fetcher.closed)
        self.assertIsNone(manager._tickflow_fetcher)
        self.assertIsNone(manager._tickflow_api_key)


if __name__ == "__main__":
    unittest.main()
