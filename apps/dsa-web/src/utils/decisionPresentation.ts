import type { IntradaySignalResponse } from '../types/intraday';

export type DecisionTone = 'long' | 'short' | 'neutral' | 'unknown';

export type DecisionLabel = {
  label: string;
  tone: DecisionTone;
  /** 越小越靠前（紧急/需关注优先）。 */
  rank: number;
  subtitle: string;
};

export function signalToDecisionLabel(signal: string, setup?: string): DecisionLabel {
  const s = signal.toLowerCase();
  const setupHint = setup?.trim() ? ` · ${setup}` : '';
  if (s === 'long') {
    return {
      label: '偏多',
      tone: 'long',
      rank: 0,
      subtitle: `日线结构偏多${setupHint}`,
    };
  }
  if (s === 'short') {
    return {
      label: '偏空',
      tone: 'short',
      rank: 1,
      subtitle: `日线结构偏空${setupHint}`,
    };
  }
  if (s === 'neutral') {
    return {
      label: '不操作',
      tone: 'neutral',
      rank: 2,
      subtitle: `暂无明确方向${setupHint}`,
    };
  }
  return {
    label: '观望',
    tone: 'unknown',
    rank: 3,
    subtitle: `信号未识别 (${signal})`,
  };
}

export type DecisionInboxItem = {
  id: string;
  at: string;
  code: string;
  label: string;
  summary: string;
};

export function buildInboxOnChange(
  prev: IntradaySignalResponse | undefined,
  next: IntradaySignalResponse,
): DecisionInboxItem | null {
  if (!prev) {
    return null;
  }
  if (prev.signal === next.signal && prev.barStart === next.barStart) {
    return null;
  }
  const { label } = signalToDecisionLabel(next.signal, next.setup);
  return {
    id: `${next.code}-${next.barStart}-${next.signal}-${Date.now()}`,
    at: new Date().toISOString(),
    code: next.code,
    label,
    summary: `${prev.signal.toUpperCase()} → ${next.signal.toUpperCase()} · bar ${next.barStart}`,
  };
}

export function sortSignalsByUrgency(items: IntradaySignalResponse[]): IntradaySignalResponse[] {
  return [...items].sort((a, b) => {
    const ra = signalToDecisionLabel(a.signal, a.setup).rank;
    const rb = signalToDecisionLabel(b.signal, b.setup).rank;
    if (ra !== rb) return ra - rb;
    return b.confidence - a.confidence;
  });
}
