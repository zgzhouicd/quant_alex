/** Types for intraday / daily signal API (camelCase after `toCamelCase`). */

export type IntradayInterval = '1d' | '1m' | '5m' | '15m';

export type IntradaySignalBatchResponse = {
  items: IntradaySignalResponse[];
};

export type IntradaySignalResponse = {
  code: string;
  interval: string;
  barStart: string;
  signal: string;
  confidence: number;
  setup: string;
  invalidation: number | null;
  lastPrice: number;
  vwapSession: number;
  emaFast: number;
  emaSlow: number;
  macd: number;
  macdSignal: number;
  rsi: number;
  volumeRatio: number;
  openingRangeHigh: number;
  openingRangeLow: number;
  recentHigh: number;
  recentLow: number;
  reasons: string[];
  payload: IntradaySignalPayload;
};

export type IntradaySignalPayload = {
  sessionDate?: string;
  priceVsVwapPct?: number | null;
  emaFastName?: string;
  emaSlowName?: string;
  macdHist?: number;
  sessionVwapReady?: boolean;
  [key: string]: unknown;
};
