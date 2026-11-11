# -*- coding: utf-8 -*-
"""
Binance 现货公共 REST（无需 API Key）：加密货币分钟 / 小时 K 线。

用于 intraday 链路，在判定为加密货币合约代码时由 DataFetcherManager 优先于 Yahoo 尝试。
文档：https://binance-docs.github.io/apidocs/spot/en/#kline-candlestick-data
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from .base import BaseFetcher, DataFetchError
from .yfinance_fetcher import (
    _CRYPTO_PAIR_RE,
    _US_FUTURE_YAHOO_RE,
    _YF_CRYPTO_DASH_RE,
    _strip_perp_suffix,
)

logger = logging.getLogger(__name__)

_DEFAULT_SPOT_BASE = "https://api.binance.com"
_BINANCE_INTERVAL_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "8h": 28_800_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
}


def _yahoo_dash_to_binance_spot(code: str) -> Optional[str]:
    if not _YF_CRYPTO_DASH_RE.fullmatch(code):
        return None
    base, quote = code.split("-", 1)
    if quote in ("USD", "USDT"):
        return f"{base}USDT"
    if quote == "USDC":
        return f"{base}USDC"
    return f"{base}{quote}"


def _compact_to_binance_spot(code: str) -> Optional[str]:
    stem = _strip_perp_suffix(code).upper()
    if not _CRYPTO_PAIR_RE.fullmatch(stem):
        return None
    if stem.endswith("USDT") or stem.endswith("USDC"):
        return stem
    if stem.endswith("USD"):
        return f"{stem[:-3]}USDT"
    if stem.endswith("BTC") or stem.endswith("ETH"):
        return stem
    return None


def binance_spot_symbol_for_intraday(stock_code: str) -> Optional[str]:
    """
    将 STOCK_LIST / 前端输入（BTCUSDT、BTC-USD 等）映射为 Binance 现货 symbol。
    若非加密货币合约形态则返回 None（由调用方改走 Yahoo）。
    """
    c = (stock_code or "").strip().upper()
    stem = _strip_perp_suffix(c)
    if _US_FUTURE_YAHOO_RE.fullmatch(c) or _US_FUTURE_YAHOO_RE.fullmatch(stem):
        return None
    y = _yahoo_dash_to_binance_spot(c)
    if y:
        return y
    return _compact_to_binance_spot(c)


def should_prefer_binance_intraday(stock_code: str) -> bool:
    return binance_spot_symbol_for_intraday(stock_code) is not None


class BinancePublicFetcher(BaseFetcher):
    """Binance 现货 K 线（公共接口）。日线分析主链未实现，仅作 intraday 补充。"""

    name = "BinancePublicFetcher"
    priority = int(os.getenv("BINANCE_PUBLIC_PRIORITY", "3"))

    def _spot_base_url(self) -> str:
        return (os.getenv("BINANCE_SPOT_API_BASE") or _DEFAULT_SPOT_BASE).rstrip("/")

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        raise DataFetchError(
            f"[{self.name}] 未实现日线拉取；{stock_code} 请使用 Yahoo / Longbridge"
        )

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        return df

    def get_intraday_data(
        self,
        stock_code: str,
        interval: str = "1m",
        lookback_minutes: int = 390,
    ) -> pd.DataFrame:
        symbol = binance_spot_symbol_for_intraday(stock_code)
        if not symbol:
            raise DataFetchError(
                f"[{self.name}] 非加密货币现货符号（期望如 BTCUSDT、BTC-USD）: {stock_code}"
            )

        interval_key = (interval or "1m").strip().lower()
        if interval_key == "60m":
            interval_key = "1h"
        if interval_key not in _BINANCE_INTERVAL_MS:
            raise DataFetchError(
                f"[{self.name}] 不支持的 interval={interval}，"
                f"Binance 现货支持的 intraday 间隔请见官方文档"
            )

        lookback = max(int(lookback_minutes or 390), 1)
        span_ms = int(lookback * 60_000)
        step_ms = _BINANCE_INTERVAL_MS[interval_key]
        est_bars = max(10, span_ms // step_ms + 5)
        limit = min(1000, est_bars)

        end_ms = int(time.time() * 1000)
        start_ms = end_ms - span_ms - step_ms

        q = urlencode(
            {
                "symbol": symbol,
                "interval": interval_key,
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": limit,
            }
        )
        url = f"{self._spot_base_url()}/api/v3/klines?{q}"
        logger.debug("[%s] GET klines symbol=%s interval=%s", self.name, symbol, interval_key)

        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; quant-dsa/1.0)"})
            with urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            raise DataFetchError(
                f"[{self.name}] Binance HTTP {exc.code}: {body[:500]}"
            ) from exc
        except URLError as exc:
            raise DataFetchError(f"[{self.name}] Binance 网络错误: {exc}") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DataFetchError(f"[{self.name}] Binance 响应非 JSON: {raw[:200]}") from exc

        if not isinstance(data, list) or not data:
            raise DataFetchError(f"[{self.name}] Binance 未返回 K 线: {symbol}")

        rows = []
        for k in data:
            if not isinstance(k, (list, tuple)) or len(k) < 6:
                continue
            o_t = int(k[0])
            o, h, low, c = float(k[1]), float(k[2]), float(k[3]), float(k[4])
            vol = float(k[5])
            rows.append(
                {
                    "timestamp": o_t,
                    "open": o,
                    "high": h,
                    "low": low,
                    "close": c,
                    "volume": vol,
                }
            )

        df = pd.DataFrame(rows)
        if df.empty:
            raise DataFetchError(f"[{self.name}] Binance K 线解析为空: {symbol}")

        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df["pct_chg"] = df["close"].pct_change() * 100
        df["pct_chg"] = df["pct_chg"].fillna(0.0).round(4)
        df["amount"] = (df["close"] * df["volume"]).fillna(0.0)
        df["interval"] = interval_key

        anchor = df["timestamp"].max()
        cutoff = anchor - pd.Timedelta(minutes=lookback)
        df = df[df["timestamp"] >= cutoff].reset_index(drop=True)
        if df.empty:
            raise DataFetchError(f"[{self.name}] Binance K 线在回看窗口内为空: {symbol}")

        return df
