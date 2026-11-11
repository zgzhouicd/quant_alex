interface ValidationResult {
  valid: boolean;
  message?: string;
  normalized: string;
}

const SUPPORTED_QUERY_CHARACTERS = /^[A-Z0-9.\-\s\u3400-\u9FFF]+$/;

// US equities, US futures (Yahoo-style), common crypto perpetual tickers
const STOCK_CODE_PATTERNS = [
  /^[A-Z][A-Z0-9.\-]{0,9}$/, // US ticker, e.g. AAPL, BRK.B
  /^[A-Z0-9.\-]+=?F$/i, // US futures, e.g. ES=F
  /^[A-Z0-9]{2,20}(?:USDT|USDC|USD|BTC|ETH)$/i, // crypto pairs
  /^[A-Z0-9._\-]+(?:[-_/]PERP|PERP)$/i, // perpetual suffix
];

const LEGACY_CN_HK_PATTERN =
  /^(\d{5,6}|(SH|SZ|BJ)\d{6}|\d{6}\.(SH|SZ|SS|BJ)|HK\d{1,5}|\d{1,5}\.HK)$/i;

/**
 * Check whether the input looks like a stock code.
 */
export const looksLikeStockCode = (value: string): boolean => {
  const normalized = value.trim().toUpperCase();
  if (LEGACY_CN_HK_PATTERN.test(normalized)) {
    return false;
  }
  return STOCK_CODE_PATTERNS.some((regex) => regex.test(normalized));
};

/**
 * Validate US-focused ticker / derivative symbol formats.
 */
export const validateStockCode = (value: string): ValidationResult => {
  const normalized = value.trim().toUpperCase();

  if (!normalized) {
    return { valid: false, message: '请输入股票代码', normalized };
  }

  if (LEGACY_CN_HK_PATTERN.test(normalized)) {
    return {
      valid: false,
      message: '本产品仅支持美股等美国上市标的，不支持 A 股 / 港股代码',
      normalized,
    };
  }

  const valid = looksLikeStockCode(normalized);

  return {
    valid,
    message: valid ? undefined : '股票代码格式不正确（示例: AAPL、MSFT、ES=F）',
    normalized,
  };
};

/**
 * Reject obviously invalid free-text queries before they reach the backend.
 */
export const isObviouslyInvalidStockQuery = (value: string): boolean => {
  const normalized = value.trim().toUpperCase();

  if (!normalized || looksLikeStockCode(normalized)) {
    return false;
  }

  if (!SUPPORTED_QUERY_CHARACTERS.test(normalized)) {
    return true;
  }

  const hasLetters = /[A-Z]/.test(normalized);
  const hasDigits = /\d/.test(normalized);

  return hasLetters && hasDigits;
};
