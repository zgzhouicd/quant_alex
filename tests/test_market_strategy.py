# -*- coding: utf-8 -*-
"""Tests for market strategy blueprints."""

import unittest

from src.core.market_strategy import get_market_strategy_blueprint
from src.market_analyzer import MarketAnalyzer, MarketOverview


class TestMarketStrategyBlueprint(unittest.TestCase):
    """Validate US-only strategy blueprint (legacy region args map to US)."""

    def test_legacy_cn_region_returns_us_blueprint(self):
        cn = get_market_strategy_blueprint("cn")
        us = get_market_strategy_blueprint("us")
        self.assertIs(cn, us)
        block = cn.to_prompt_block()
        self.assertIn("US Market Regime Strategy", block)
        self.assertIn("Action Framework", block)
        self.assertIn("Risk-on", block)

    def test_us_blueprint_contains_regime_strategy(self):
        blueprint = get_market_strategy_blueprint("us")
        block = blueprint.to_prompt_block()

        self.assertIn("US Market Regime Strategy", block)
        self.assertIn("Risk-on", block)
        self.assertIn("Macro & Flows", block)


class TestMarketAnalyzerStrategyPrompt(unittest.TestCase):
    """Validate strategy section is injected into prompt/report."""

    def test_legacy_cn_region_uses_us_strategy_in_prompt(self):
        analyzer = MarketAnalyzer(region="cn")
        prompt = analyzer._build_review_prompt(MarketOverview(date="2026-02-24"), [])
        self.assertEqual(analyzer.region, "us")
        self.assertIn("Strategy Plan", prompt)
        self.assertIn("US Market Regime Strategy", prompt)

    def test_us_prompt_contains_strategy_plan_section(self):
        analyzer = MarketAnalyzer(region="us")
        prompt = analyzer._build_review_prompt(MarketOverview(date="2026-02-24"), [])

        self.assertIn("Strategy Plan", prompt)
        self.assertIn("US Market Regime Strategy", prompt)


if __name__ == "__main__":
    unittest.main()
