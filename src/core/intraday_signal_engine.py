"""日线级指标与信号引擎。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass
class IntradaySignalResult:
    code: str
    interval: str
    bar_start: datetime
    signal: str
    confidence: float
    setup: str
    invalidation: Optional[float]
    last_price: float
    vwap_session: float
    ema_fast: float
    ema_slow: float
    macd: float
    macd_signal: float
    rsi: float
    volume_ratio: float
    opening_range_high: float
    opening_range_low: float
    recent_high: float
    recent_low: float
    reasons: List[str] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_record_payload(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "interval": self.interval,
            "bar_start": self.bar_start,
            "signal": self.signal,
            "confidence": self.confidence,
            "setup": self.setup,
            "invalidation": self.invalidation,
            "last_price": self.last_price,
            "vwap_session": self.vwap_session,
            "ema_fast": self.ema_fast,
            "ema_slow": self.ema_slow,
            "macd": self.macd,
            "macd_signal": self.macd_signal,
            "rsi": self.rsi,
            "volume_ratio": self.volume_ratio,
            "opening_range_high": self.opening_range_high,
            "opening_range_low": self.opening_range_low,
            "recent_high": self.recent_high,
            "recent_low": self.recent_low,
            "reasons": self.reasons,
            "payload": self.payload,
        }

    def to_api_dict(self) -> Dict[str, Any]:
        return {
            **self.to_record_payload(),
            "bar_start": self.bar_start.isoformat(),
        }


class IntradaySignalEngine:
    """基于 OHLCV 计算 VWAP / EMA / MACD / RSI 与结构化信号。"""

    EMA_FAST = 9
    EMA_SLOW = 21
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9
    RSI_PERIOD = 14
    VOLUME_WINDOW = 20
    RECENT_WINDOW = 20

    def analyze(self, df: pd.DataFrame, *, code: str, interval: str) -> IntradaySignalResult:
        if df is None or df.empty:
            raise ValueError("intraday dataframe is empty")

        frame = self._prepare_frame(df, code=code, interval=interval)
        latest = frame.iloc[-1]

        is_daily = self._is_daily_interval(interval)
        signal, setup, reasons = self._decide_signal(frame, is_daily=is_daily)
        score = min(1.0, max(0.0, len(reasons) / 5.0))
        if signal == "neutral":
            score = min(score, 0.55)

        invalidation = None
        if signal == "long":
            invalidation = min(float(latest["vwap_session"]), float(latest["recent_low"]))
        elif signal == "short":
            invalidation = max(float(latest["vwap_session"]), float(latest["recent_high"]))

        payload = {
            "session_date": str(latest["session_date"]),
            "price_vs_vwap_pct": round((latest["close"] - latest["vwap_session"]) / latest["vwap_session"] * 100, 3)
            if latest["vwap_session"] else None,
            "ema_fast_name": f"ema_{self.EMA_FAST}",
            "ema_slow_name": f"ema_{self.EMA_SLOW}",
            "macd_hist": round(float(latest["macd_hist"]), 4),
            "session_vwap_ready": bool(latest["session_volume_cum"] > 0),
            "signal_timeframe": "daily" if is_daily else "intraday",
        }

        return IntradaySignalResult(
            code=code,
            interval=interval,
            bar_start=latest["timestamp"].to_pydatetime(),
            signal=signal,
            confidence=round(score, 3),
            setup=setup,
            invalidation=round(float(invalidation), 4) if invalidation is not None else None,
            last_price=round(float(latest["close"]), 4),
            vwap_session=round(float(latest["vwap_session"]), 4),
            ema_fast=round(float(latest["ema_fast"]), 4),
            ema_slow=round(float(latest["ema_slow"]), 4),
            macd=round(float(latest["macd"]), 4),
            macd_signal=round(float(latest["macd_signal"]), 4),
            rsi=round(float(latest["rsi"]), 3),
            volume_ratio=round(float(latest["volume_ratio"]), 3),
            opening_range_high=round(float(latest["opening_range_high"]), 4),
            opening_range_low=round(float(latest["opening_range_low"]), 4),
            recent_high=round(float(latest["recent_high"]), 4),
            recent_low=round(float(latest["recent_low"]), 4),
            reasons=reasons,
            payload=payload,
        )

    def _prepare_frame(self, df: pd.DataFrame, *, code: str, interval: str) -> pd.DataFrame:
        frame = df.copy()
        if "bar_start" in frame.columns and "timestamp" not in frame.columns:
            frame["timestamp"] = frame["bar_start"]
        if "timestamp" not in frame.columns:
            raise ValueError("intraday dataframe missing timestamp column")

        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        numeric_cols = ["open", "high", "low", "close", "volume", "amount"]
        for col in numeric_cols:
            frame[col] = pd.to_numeric(frame.get(col), errors="coerce")
        frame = frame.dropna(subset=["timestamp", "close", "high", "low"]).sort_values("timestamp").reset_index(drop=True)
        if frame.empty:
            raise ValueError("intraday dataframe has no usable rows")

        interval_minutes = self._interval_to_minutes(interval)
        is_daily = self._is_daily_interval(interval)
        session_tz = self._infer_session_timezone(code)
        frame["session_date"] = frame["timestamp"].dt.tz_convert(session_tz).dt.date
        typical_price = (frame["high"] + frame["low"] + frame["close"]) / 3.0
        volume = frame["volume"].fillna(0.0)
        pv = typical_price * volume
        if is_daily:
            frame["session_volume_cum"] = volume.rolling(window=self.VOLUME_WINDOW, min_periods=1).sum()
            frame["session_pv_cum"] = pv.rolling(window=self.VOLUME_WINDOW, min_periods=1).sum()
        else:
            frame["session_volume_cum"] = frame.groupby("session_date")["volume"].transform(lambda s: s.fillna(0.0).cumsum())
            frame["session_pv_cum"] = pv.groupby(frame["session_date"]).cumsum()
        frame["vwap_session"] = frame["session_pv_cum"] / frame["session_volume_cum"].replace(0, pd.NA)
        frame["vwap_session"] = frame["vwap_session"].ffill().fillna(frame["close"])

        frame["ema_fast"] = frame["close"].ewm(span=self.EMA_FAST, adjust=False).mean()
        frame["ema_slow"] = frame["close"].ewm(span=self.EMA_SLOW, adjust=False).mean()
        ema12 = frame["close"].ewm(span=self.MACD_FAST, adjust=False).mean()
        ema26 = frame["close"].ewm(span=self.MACD_SLOW, adjust=False).mean()
        frame["macd"] = ema12 - ema26
        frame["macd_signal"] = frame["macd"].ewm(span=self.MACD_SIGNAL, adjust=False).mean()
        frame["macd_hist"] = frame["macd"] - frame["macd_signal"]

        delta = frame["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=self.RSI_PERIOD, min_periods=self.RSI_PERIOD).mean()
        avg_loss = loss.rolling(window=self.RSI_PERIOD, min_periods=self.RSI_PERIOD).mean()
        rs = avg_gain / avg_loss.replace(0, pd.NA)
        frame["rsi"] = (100 - (100 / (1 + rs))).fillna(50.0)

        if is_daily:
            frame["opening_range_high"] = frame["high"].rolling(window=self.RECENT_WINDOW, min_periods=1).max()
            frame["opening_range_low"] = frame["low"].rolling(window=self.RECENT_WINDOW, min_periods=1).min()
        else:
            opening_bars = max(1, int(30 / max(interval_minutes, 1)))
            frame["opening_range_high"] = frame.groupby("session_date")["high"].transform(
                lambda s: s.iloc[:opening_bars].max()
            )
            frame["opening_range_low"] = frame.groupby("session_date")["low"].transform(
                lambda s: s.iloc[:opening_bars].min()
            )
        frame["recent_high"] = frame["high"].rolling(window=self.RECENT_WINDOW, min_periods=1).max()
        frame["recent_low"] = frame["low"].rolling(window=self.RECENT_WINDOW, min_periods=1).min()
        avg_vol = frame["volume"].rolling(window=self.VOLUME_WINDOW, min_periods=1).mean()
        frame["volume_ratio"] = (frame["volume"] / avg_vol.replace(0, pd.NA)).fillna(1.0)
        return frame

    def _decide_signal(self, frame: pd.DataFrame, *, is_daily: bool = False) -> tuple[str, str, List[str]]:
        latest = frame.iloc[-1]
        reasons: List[str] = []
        bearish_reasons: List[str] = []
        vwap_label = "20日量价均衡线" if is_daily else "会话 VWAP"
        breakout_high_label = "突破近20日高点" if is_daily else "突破开盘区间高点"
        breakout_low_label = "跌破近20日低点" if is_daily else "跌破开盘区间低点"

        if latest["close"] > latest["vwap_session"]:
            reasons.append(f"价格位于{vwap_label}上方")
        else:
            bearish_reasons.append(f"价格位于{vwap_label}下方")

        if latest["ema_fast"] > latest["ema_slow"]:
            reasons.append(f"EMA{self.EMA_FAST} 高于 EMA{self.EMA_SLOW}")
        else:
            bearish_reasons.append(f"EMA{self.EMA_FAST} 低于 EMA{self.EMA_SLOW}")

        if latest["macd"] > latest["macd_signal"]:
            reasons.append("MACD 快线在信号线上方")
        else:
            bearish_reasons.append("MACD 快线在信号线下方")

        if 50 <= latest["rsi"] <= 75:
            reasons.append("RSI 位于多头动量区间")
        elif latest["rsi"] < 45:
            bearish_reasons.append("RSI 偏弱")

        if latest["volume_ratio"] >= 1.1:
            reasons.append("量能高于近期均值")
        elif latest["volume_ratio"] <= 0.9:
            bearish_reasons.append("量能低于近期均值")

        if latest["close"] >= latest["opening_range_high"]:
            reasons.append(breakout_high_label)
        elif latest["close"] <= latest["opening_range_low"]:
            bearish_reasons.append(breakout_low_label)

        if len(reasons) >= 4:
            return "long", "daily_momentum_long" if is_daily else "intraday_momentum_long", reasons
        if len(bearish_reasons) >= 4:
            return "short", "daily_momentum_short" if is_daily else "intraday_momentum_short", bearish_reasons
        if len(reasons) >= len(bearish_reasons):
            merged = reasons or ["信号分歧，维持观望"]
            return "neutral", "mixed_daily_conditions" if is_daily else "mixed_intraday_conditions", merged
        merged = bearish_reasons or ["信号分歧，维持观望"]
        return "neutral", "mixed_daily_conditions" if is_daily else "mixed_intraday_conditions", merged

    @staticmethod
    def _interval_to_minutes(interval: str) -> int:
        text = (interval or "1m").strip().lower()
        if text in {"1d", "d", "day", "daily"}:
            return 1440
        if text.endswith("m") and text[:-1].isdigit():
            return max(1, int(text[:-1]))
        if text.endswith("h") and text[:-1].isdigit():
            return max(1, int(text[:-1]) * 60)
        return 1

    @staticmethod
    def _is_daily_interval(interval: str) -> bool:
        return (interval or "").strip().lower() in {"1d", "d", "day", "daily"}

    @staticmethod
    def _infer_session_timezone(code: str) -> str:
        code_text = (code or "").strip().upper()
        if code_text.endswith(("USDT", "USDC", "USD", "BTC", "ETH")) or code_text.endswith("PERP"):
            return "UTC"
        return "America/New_York"
