# -*- coding: utf-8 -*-
"""Regression tests for pipeline belong_boards field (legacy; always empty unless snapshot)."""

import unittest
from unittest.mock import MagicMock

from src.core.pipeline import StockAnalysisPipeline


class PipelineRelatedBoardsTestCase(unittest.TestCase):
    def test_shallow_copies_context_before_injecting_empty_boards(self) -> None:
        pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
        pipeline.fetcher_manager = MagicMock()

        cached_context = {
            "market": "us",
            "status": "ok",
            "coverage": {"boards": "ok"},
            "boards": {"status": "ok", "data": {"top": [], "bottom": []}},
        }

        enriched = pipeline._attach_belong_boards_to_fundamental_context("AAPL", cached_context)

        self.assertIsNot(enriched, cached_context)
        self.assertNotIn("belong_boards", cached_context)
        self.assertEqual(enriched["belong_boards"], [])
        pipeline.fetcher_manager.get_belong_boards.assert_not_called()

    def test_preserves_existing_board_list_from_snapshot(self) -> None:
        pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
        pipeline.fetcher_manager = MagicMock()

        existing_boards = [{"name": "legacy", "type": "行业"}]
        context = {
            "market": "us",
            "status": "ok",
            "belong_boards": existing_boards,
        }

        enriched = pipeline._attach_belong_boards_to_fundamental_context("AAPL", context)

        self.assertIsNot(enriched, context)
        self.assertEqual(enriched["belong_boards"], existing_boards)
        self.assertIsNot(enriched["belong_boards"], existing_boards)
        pipeline.fetcher_manager.get_belong_boards.assert_not_called()


if __name__ == "__main__":
    unittest.main()
