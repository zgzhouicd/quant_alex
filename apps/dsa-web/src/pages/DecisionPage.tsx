import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { intradayApi } from '../api/intraday';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import {
  ApiErrorAlert,
  Badge,
  Button,
  Card,
  PageHeader,
} from '../components/common';
import {
  DEFAULT_INTRADAY_INTERVAL,
  DEFAULT_LOOKBACK_MINUTES,
  INTRADAY_INTERVAL_OPTIONS,
} from '../constants/intradayDefaults';
import type { IntradayInterval, IntradaySignalResponse } from '../types/intraday';
import { cn } from '../utils/cn';
import {
  buildInboxOnChange,
  signalToDecisionLabel,
  sortSignalsByUrgency,
  type DecisionInboxItem,
} from '../utils/decisionPresentation';

const WATCHLIST_STORAGE_KEY = 'dsa.decision.watchlist';
const DEFAULT_WATCHLIST = 'AAPL,NVDA,MSFT';

function parseSymbolList(raw: string): string[] {
  return raw
    .split(/[\s,;]+/)
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean);
}

function formatNum(n: number | null | undefined, digits = 4): string {
  if (n == null || Number.isNaN(n)) return '—';
  return n.toFixed(digits);
}

const tonePanelClass: Record<string, string> = {
  long: 'border-l-4 border-l-emerald-500/80 bg-emerald-500/5',
  short: 'border-l-4 border-l-rose-500/80 bg-rose-500/5',
  neutral: 'border-l-4 border-l-amber-500/60 bg-amber-500/5',
  unknown: 'border-l-4 border-l-border bg-card/50',
};

const DecisionPage: React.FC = () => {
  const [watchlistRaw, setWatchlistRaw] = useState(() => {
    if (typeof window === 'undefined') return DEFAULT_WATCHLIST;
    return localStorage.getItem(WATCHLIST_STORAGE_KEY) ?? DEFAULT_WATCHLIST;
  });
  const [interval, setInterval] = useState<IntradayInterval>(DEFAULT_INTRADAY_INTERVAL);
  const [lookbackMinutes, setLookbackMinutes] = useState(DEFAULT_LOOKBACK_MINUTES);
  const [signals, setSignals] = useState<IntradaySignalResponse[]>([]);
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [inbox, setInbox] = useState<DecisionInboxItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const prevByCode = useRef<Record<string, IntradaySignalResponse>>({});

  const symbols = useMemo(() => parseSymbolList(watchlistRaw), [watchlistRaw]);

  const sortedSignals = useMemo(() => sortSignalsByUrgency(signals), [signals]);

  const selected = useMemo(() => {
    if (!sortedSignals.length) return null;
    const code = selectedCode ?? sortedSignals[0].code;
    return sortedSignals.find((s) => s.code === code) ?? sortedSignals[0];
  }, [selectedCode, sortedSignals]);

  useEffect(() => {
    document.title = '决策台 · DSA';
  }, []);

  useEffect(() => {
    localStorage.setItem(WATCHLIST_STORAGE_KEY, watchlistRaw);
  }, [watchlistRaw]);

  const mergeSignals = useCallback((items: IntradaySignalResponse[]) => {
    const nextInbox: DecisionInboxItem[] = [];
    for (const item of items) {
      const prev = prevByCode.current[item.code];
      const entry = buildInboxOnChange(prev, item);
      if (entry) nextInbox.push(entry);
      prevByCode.current[item.code] = item;
    }
    if (nextInbox.length) {
      setInbox((prev) => [...nextInbox, ...prev].slice(0, 50));
    }
    setSignals(items);
    if (!selectedCode && items.length) {
      setSelectedCode(items[0].code);
    }
  }, [selectedCode]);

  const runScan = useCallback(
    async (refresh: boolean) => {
      if (!symbols.length) return;
      setLoading(true);
      setError(null);
      try {
        const res = await intradayApi.getSignalBatch({
          symbols,
          interval,
          lookbackMinutes,
          refresh,
        });
        mergeSignals(res.items);
      } catch (e) {
        setError(getParsedApiError(e));
      } finally {
        setLoading(false);
      }
    },
    [interval, lookbackMinutes, mergeSignals, symbols],
  );

  const runLightRefresh = useCallback(async () => {
    if (!symbols.length) return;
    setError(null);
    try {
      const items = await Promise.all(
        symbols.map((code) =>
          intradayApi.getLatestSignal({ code, interval }).catch(() => null),
        ),
      );
      const valid = items.filter((x): x is IntradaySignalResponse => x != null);
      if (valid.length) {
        mergeSignals(valid);
      }
    } catch (e) {
      setError(getParsedApiError(e));
    }
  }, [interval, mergeSignals, symbols]);

  useEffect(() => {
    if (!autoRefresh || !symbols.length) return undefined;
    const id = window.setInterval(() => {
      void runLightRefresh();
    }, 60_000);
    return () => window.clearInterval(id);
  }, [autoRefresh, runLightRefresh, symbols.length]);

  const decision = selected ? signalToDecisionLabel(selected.signal, selected.setup) : null;

  return (
    <div className="mx-auto max-w-[1400px] space-y-5 px-4 pb-10 pt-4 md:px-6">
      <PageHeader
        eyebrow="导航 · 分钟级默认"
        title="决策台"
        description="观察名单 + 分钟结构信号（默认 5m）；变更记在右侧提醒流。结论仅在页面展示，不依赖外部 IM 推送。"
      />

      <Card className="p-4 md:p-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
          <label className="min-w-0 flex-1 space-y-1.5">
            <span className="text-xs text-muted-text">观察名单（逗号分隔）</span>
            <input
              className="input-surface input-focus-glow h-11 w-full rounded-xl border bg-transparent px-4 text-sm"
              value={watchlistRaw}
              onChange={(e) => setWatchlistRaw(e.target.value)}
              placeholder="AAPL, NVDA, …"
            />
          </label>
          <label className="w-full space-y-1.5 sm:w-24">
            <span className="text-xs text-muted-text">K 线周期</span>
            <select
              className="input-surface input-focus-glow h-11 w-full rounded-xl border bg-transparent px-3 text-sm"
              value={interval}
              onChange={(e) => setInterval(e.target.value as IntradayInterval)}
            >
              {INTRADAY_INTERVAL_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </label>
          <label className="w-full space-y-1.5 sm:w-32">
            <span className="text-xs text-muted-text">回溯（分钟）</span>
            <input
              type="number"
              min={30}
              max={10080}
              className="input-surface input-focus-glow h-11 w-full rounded-xl border bg-transparent px-4 text-sm"
              value={lookbackMinutes}
              onChange={(e) => setLookbackMinutes(Number(e.target.value) || DEFAULT_LOOKBACK_MINUTES)}
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="primary"
              disabled={loading || !symbols.length}
              isLoading={loading}
              loadingText="扫描中…"
              onClick={() => void runScan(true)}
            >
              <RefreshCw className="mr-1.5 h-4 w-4" />
              扫描信号
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={!symbols.length}
              onClick={() => void runLightRefresh()}
            >
              读库最新
            </Button>
            <Button
              type="button"
              variant={autoRefresh ? 'primary' : 'secondary'}
              onClick={() => setAutoRefresh((v) => !v)}
            >
              {autoRefresh ? '自动刷新：开' : '自动刷新：关'}
            </Button>
          </div>
        </div>
        {error ? (
          <div className="mt-3">
            <ApiErrorAlert error={error} />
          </div>
        ) : null}
        <p className="mt-3 text-[11px] leading-relaxed text-muted-text">
          展示词为分钟引擎的简化结论（偏多 / 偏空 / 不操作），基于最近一根已闭合 K 线与 session VWAP 等规则。
          <span className="text-foreground/80"> 结构参考，非委托。</span>
        </p>
      </Card>

      <div className="grid min-h-[420px] grid-cols-1 gap-4 lg:grid-cols-[minmax(200px,240px)_minmax(0,1fr)_minmax(240px,300px)]">
        <Card className="overflow-hidden p-0">
          <div className="border-b border-border/60 px-3 py-2 text-xs font-medium text-muted-text">
            观察 · 按关注度排序
          </div>
          <ul className="max-h-[520px] overflow-y-auto">
            {sortedSignals.length === 0 ? (
              <li className="px-3 py-6 text-center text-xs text-muted-text">扫描后显示列表</li>
            ) : (
              sortedSignals.map((row) => {
                const rowDecision = signalToDecisionLabel(row.signal, row.setup);
                const isOn = selected?.code === row.code;
                return (
                  <li key={row.code}>
                    <button
                      type="button"
                      className={cn(
                        'flex w-full flex-col gap-0.5 border-b border-border/40 px-3 py-2.5 text-left transition-colors',
                        isOn ? 'bg-primary/10' : 'hover:bg-card/80',
                        rowDecision.tone === 'neutral' && !isOn && 'opacity-70',
                      )}
                      onClick={() => setSelectedCode(row.code)}
                    >
                      <span className="text-sm font-semibold text-foreground">{row.code}</span>
                      <span className="text-[11px] text-muted-text">
                        {formatNum(row.lastPrice, 2)} · 置信 {formatNum(row.confidence, 2)}
                      </span>
                      <span
                        className={cn(
                          'text-xs font-semibold',
                          rowDecision.tone === 'long' && 'text-emerald-500',
                          rowDecision.tone === 'short' && 'text-rose-500',
                          rowDecision.tone === 'neutral' && 'text-amber-600',
                        )}
                      >
                        {rowDecision.label}
                      </span>
                    </button>
                  </li>
                );
              })
            )}
          </ul>
        </Card>

        <Card className="flex flex-col p-0">
          {!selected || !decision ? (
            <div className="flex flex-1 items-center justify-center p-8 text-sm text-muted-text">
              选择标的或先执行扫描
            </div>
          ) : (
            <>
              <div className="border-b border-border/60 px-4 py-3">
                <div className="flex flex-wrap items-baseline gap-2">
                  <h2 className="text-lg font-semibold text-foreground">{selected.code}</h2>
                  <Badge variant="default">{selected.interval}</Badge>
                  <span className="text-xs text-muted-text">bar {selected.barStart}</span>
                </div>
                <p className="mt-1 text-2xl font-bold tabular-nums text-foreground">
                  {formatNum(selected.lastPrice, 2)}
                </p>
              </div>
              <div className={cn('flex-1 px-4 py-5', tonePanelClass[decision.tone] ?? tonePanelClass.unknown)}>
                <p className="text-center text-3xl font-extrabold tracking-wide text-foreground">{decision.label}</p>
                <p className="mt-2 text-center text-xs text-muted-text">{decision.subtitle}</p>
                <p className="mt-4 rounded-lg bg-card/60 px-3 py-2 text-sm leading-relaxed text-secondary-text">
                  {selected.reasons[0] ?? '—'}
                </p>
                {selected.reasons.length > 1 ? (
                  <ul className="mt-2 list-inside list-disc text-xs text-muted-text">
                    {selected.reasons.slice(1, 5).map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                ) : null}
                <div className="mt-5 grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
                  <div className="rounded-lg border border-border/50 bg-card/40 px-2 py-1.5">
                    <span className="text-muted-text">作废参考</span>
                    <div className="font-mono text-foreground">
                      {selected.invalidation != null ? formatNum(selected.invalidation, 2) : '—'}
                    </div>
                  </div>
                  <div className="rounded-lg border border-border/50 bg-card/40 px-2 py-1.5">
                    <span className="text-muted-text">RSI</span>
                    <div className="font-mono text-foreground">{formatNum(selected.rsi, 2)}</div>
                  </div>
                  <div className="rounded-lg border border-border/50 bg-card/40 px-2 py-1.5">
                    <span className="text-muted-text">VWAP</span>
                    <div className="font-mono text-foreground">{formatNum(selected.vwapSession, 2)}</div>
                  </div>
                </div>
              </div>
            </>
          )}
        </Card>

        <Card className="flex flex-col overflow-hidden p-0">
          <div className="border-b border-border/60 px-3 py-2 text-xs font-medium text-muted-text">
            提醒流 <span className="text-[10px]">（信号或 bar 变化）</span>
          </div>
          <ul className="max-h-[520px] flex-1 overflow-y-auto">
            {inbox.length === 0 ? (
              <li className="px-3 py-6 text-center text-xs text-muted-text">暂无变更；扫描后会记录相对上次的变化</li>
            ) : (
              inbox.map((item) => (
                <li
                  key={item.id}
                  className="border-b border-border/40 px-3 py-2.5 text-left"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold">{item.code}</span>
                    <Badge variant="warning" size="sm">
                      {item.label}
                    </Badge>
                  </div>
                  <p className="mt-1 text-[11px] text-muted-text">{item.summary}</p>
                </li>
              ))
            )}
          </ul>
        </Card>
      </div>
    </div>
  );
};

export default DecisionPage;
