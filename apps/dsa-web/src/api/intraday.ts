import apiClient from './index';
import { toCamelCase } from './utils';
import type { IntradayInterval, IntradaySignalBatchResponse, IntradaySignalResponse } from '../types/intraday';
import {
  DEFAULT_INTRADAY_INTERVAL,
  DEFAULT_LOOKBACK_MINUTES,
} from '../constants/intradayDefaults';

type LatestSignalParams = {
  code: string;
  interval?: IntradayInterval | string;
};

const LONG_TIMEOUT_MS = 120_000;

export const intradayApi = {
  async getSignalBatch(params: {
    symbols: string[];
    interval?: IntradayInterval | string;
    lookbackMinutes?: number;
    refresh?: boolean;
  }): Promise<IntradaySignalBatchResponse> {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/intraday/signals/batch',
      undefined,
      {
        params: {
          symbols: params.symbols.map((s) => s.trim()).filter(Boolean),
          interval: params.interval ?? DEFAULT_INTRADAY_INTERVAL,
          lookback_minutes: params.lookbackMinutes ?? DEFAULT_LOOKBACK_MINUTES,
          refresh: params.refresh ?? true,
        },
        timeout: LONG_TIMEOUT_MS,
      },
    );
    return toCamelCase<IntradaySignalBatchResponse>(response.data);
  },

  async getLatestSignal(params: LatestSignalParams): Promise<IntradaySignalResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/intraday/signal/latest', {
      params: {
        code: params.code.trim(),
        interval: params.interval ?? DEFAULT_INTRADAY_INTERVAL,
      },
    });
    return toCamelCase<IntradaySignalResponse>(response.data);
  },
};
