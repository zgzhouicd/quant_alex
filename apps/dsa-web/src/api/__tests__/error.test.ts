import { describe, it, expect } from 'vitest';
import { getParsedApiError } from '../error';

describe('parseApiError', () => {
  it('maps backend data_fetch_error (502) to a dedicated category and preserves message', () => {
    const err = {
      response: {
        status: 502,
        data: { error: 'data_fetch_error', message: 'No data for symbol' },
      },
    };
    const parsed = getParsedApiError(err);
    expect(parsed.category).toBe('data_fetch_error');
    expect(parsed.title).toContain('市场数据');
    expect(parsed.message).toContain('No data for symbol');
  });
});
