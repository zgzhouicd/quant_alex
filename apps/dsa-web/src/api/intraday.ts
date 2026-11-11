import apiClient from './index';
import { toCamelCase } from './utils';
import type { IntradaySignalBatchResponse, IntradaySignalResponse } from '../types/intraday';

type LatestSignalParams = {
  code: string;
  interval?: string;
};

const LONG_TIMEOUT_MS = 120_000;

export const intradayApi = {
  async getSignalBatch(params: {
    symbols: string[];
    interval?: string;
    lookbackDays?: number;
    refresh?: boolean;
  }): Promise<IntradaySignalBatchResponse> {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/intraday/signals/batch',
      undefined,
      {
        params: {
          symbols: params.symbols.map((s) => s.trim()).filter(Boolean),
          interval: params.interval ?? '1d',
          lookback_days: params.lookbackDays ?? 120,
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
        interval: params.interval ?? '1d',
      },
    });
    return toCamelCase<IntradaySignalResponse>(response.data);
  },
};
