# -*- coding: utf-8 -*-
"""
StockAnalysisPipeline 的重量级、进程级共享依赖（API 热路径复用）。

CLI 批处理每次调用仍会新建 pipeline；异步 API 任务在同一个 Config 单例下
共享一份运行时，避免每个请求都重建 fetcher、GeminiAnalyzer、SearchService 等。
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from data_provider import DataFetcherManager
from src.analyzer import GeminiAnalyzer
from src.search_service import SearchService
from src.services.capability_router import MarketCapabilityRouter
from src.services.social_sentiment_service import SocialSentimentService

if TYPE_CHECKING:
    from src.config import Config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineSharedRuntime:
    """管线子系统的不可变打包（构造过程保证线程安全）。"""

    fetcher_manager: DataFetcherManager
    capability_router: MarketCapabilityRouter
    analyzer: GeminiAnalyzer
    search_service: Optional[SearchService]
    social_sentiment_service: Optional[SocialSentimentService]


_runtime_lock = threading.Lock()
_runtime: Optional[PipelineSharedRuntime] = None
_runtime_config_id: Optional[int] = None


def get_pipeline_shared_runtime(config: "Config") -> PipelineSharedRuntime:
    """
    Return shared runtime for the given Config instance.

    Invalidates automatically when ``config`` is not the same object as the
    one used to build the cache (e.g. after ``Config.reset_instance()``).
    """
    global _runtime, _runtime_config_id

    cfg_id = id(config)
    with _runtime_lock:
        if _runtime is not None and _runtime_config_id == cfg_id:
            return _runtime

        fetcher_manager = DataFetcherManager()
        capability_router = MarketCapabilityRouter(fetcher_manager)
        analyzer = GeminiAnalyzer(config=config)

        search_service: Optional[SearchService] = None
        try:
            search_service = SearchService(
                bocha_keys=config.bocha_api_keys,
                tavily_keys=config.tavily_api_keys,
                brave_keys=config.brave_api_keys,
                serpapi_keys=config.serpapi_keys,
                minimax_keys=config.minimax_api_keys,
                searxng_base_urls=config.searxng_base_urls,
                searxng_public_instances_enabled=config.searxng_public_instances_enabled,
                news_max_age_days=config.news_max_age_days,
                news_strategy_profile=getattr(config, "news_strategy_profile", "short"),
            )
        except Exception as exc:
            logger.warning(
                "搜索服务初始化失败（共享运行时），将以无搜索模式运行: %s",
                exc,
                exc_info=True,
            )
            search_service = None

        social_sentiment_service: Optional[SocialSentimentService] = None
        try:
            social_sentiment_service = SocialSentimentService(
                api_key=config.social_sentiment_api_key,
                api_url=config.social_sentiment_api_url,
            )
            if social_sentiment_service.is_available:
                logger.info(
                    "Social sentiment service enabled (shared runtime, Reddit/X/Polymarket, US stocks only)"
                )
        except Exception as exc:
            logger.warning(
                "社交舆情服务初始化失败（共享运行时），将跳过舆情分析: %s",
                exc,
                exc_info=True,
            )
            social_sentiment_service = None

        _runtime = PipelineSharedRuntime(
            fetcher_manager=fetcher_manager,
            capability_router=capability_router,
            analyzer=analyzer,
            search_service=search_service,
            social_sentiment_service=social_sentiment_service,
        )
        _runtime_config_id = cfg_id
        logger.info("Pipeline shared runtime initialized for config id=%s", cfg_id)
        return _runtime


def reset_pipeline_shared_runtime() -> None:
    """Drop cached runtime (config reload / tests)."""
    global _runtime, _runtime_config_id
    with _runtime_lock:
        _runtime = None
        _runtime_config_id = None
