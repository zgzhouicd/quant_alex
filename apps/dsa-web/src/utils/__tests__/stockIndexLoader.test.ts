/**
 * stockIndexLoader Unit Tests
 *
 * Test stock index loading, parsing, compression, and other functions
 */

import {
  loadStockIndex,
  compressIndex,
  findStockInIndex,
  getPopularStocks,
  groupStocksByMarket,
} from '../stockIndexLoader';
import type { StockIndexItem } from '../../types/stockIndex';
import { beforeEach, describe, expect, test, vi } from 'vitest';

// Mock fetch
const mockFetch = vi.fn();
globalThis.fetch = mockFetch as unknown as typeof fetch;

describe('stockIndexLoader', () => {
  const mockIndexData: StockIndexItem[] = [
    {
      canonicalCode: 'AAPL.US',
      displayCode: 'AAPL',
      nameZh: '苹果',
      pinyinFull: 'pingguo',
      pinyinAbbr: 'pg',
      aliases: [],
      market: 'US',
      assetType: 'stock',
      active: true,
      popularity: 100,
    },
    {
      canonicalCode: 'NVDA.US',
      displayCode: 'NVDA',
      nameZh: '英伟达',
      pinyinFull: 'yingweida',
      pinyinAbbr: 'ywd',
      aliases: ['NVIDIA'],
      market: 'US',
      assetType: 'stock',
      active: true,
      popularity: 98,
    },
    {
      canonicalCode: 'MSFT.US',
      displayCode: 'MSFT',
      nameZh: '微软',
      pinyinFull: 'weiruan',
      pinyinAbbr: 'wr',
      aliases: [],
      market: 'US',
      assetType: 'stock',
      active: true,
      popularity: 95,
    },
    {
      canonicalCode: 'ZZZZ.US',
      displayCode: 'ZZZZ',
      nameZh: '下架标的',
      pinyinFull: 'xiajiabiaodi',
      pinyinAbbr: 'xjbd',
      aliases: [],
      market: 'US',
      assetType: 'stock',
      active: false,
      popularity: 80,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('loadStockIndex - Load stock index', () => {
    test('successfully loads object format index', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockIndexData,
      } as unknown as Response);

      const result = await loadStockIndex();

      expect(result.loaded).toBe(true);
      expect(result.fallback).toBe(false);
      expect(result.data).toEqual(mockIndexData);
      expect(result.error).toBeUndefined();
    });

    test('successfully loads compressed format index (tuple format)', async () => {
      const compressedData = [
        ['AAPL.US', 'AAPL', '苹果', 'pingguo', 'pg', [], 'US', 'stock', true, 100],
        ['NVDA.US', 'NVDA', '英伟达', 'yingweida', 'ywd', ['NVIDIA'], 'US', 'stock', true, 98],
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => compressedData,
      } as unknown as Response);

      const result = await loadStockIndex();

      expect(result.loaded).toBe(true);
      expect(result.fallback).toBe(false);
      expect(result.data).toHaveLength(2);
      expect(result.data[0].canonicalCode).toBe('AAPL.US');
      expect(result.data[0].nameZh).toBe('苹果');
    });

    test('returns fallback mode on network error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const result = await loadStockIndex();

      expect(result.loaded).toBe(false);
      expect(result.fallback).toBe(true);
      expect(result.data).toEqual([]);
      expect(result.error).toBeInstanceOf(Error);
    });

    test('returns fallback mode on HTTP error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
      } as unknown as Response);

      const result = await loadStockIndex();

      expect(result.loaded).toBe(false);
      expect(result.fallback).toBe(true);
      expect(result.data).toEqual([]);
      expect(result.error).toBeDefined();
    });

    test('returns fallback mode on JSON parse error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => {
          throw new Error('Invalid JSON');
        },
      } as unknown as Response);

      const result = await loadStockIndex();

      expect(result.loaded).toBe(false);
      expect(result.fallback).toBe(true);
      expect(result.data).toEqual([]);
      expect(result.error).toBeDefined();
    });

    test('handles empty array', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      } as unknown as Response);

      const result = await loadStockIndex();

      expect(result.loaded).toBe(true);
      expect(result.fallback).toBe(false);
      expect(result.data).toEqual([]);
    });

    test('fetch call includes cache-busting parameter', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockIndexData,
      } as unknown as Response);

      await loadStockIndex();

      const fetchCallArgs = mockFetch.mock.calls[0][0];
      expect(fetchCallArgs).toContain('?_t=');
    });
  });

  describe('compressIndex - Compress index', () => {
    test('converts object format to tuple format', () => {
      const compressed = compressIndex(mockIndexData);

      expect(compressed).toHaveLength(mockIndexData.length);
      expect(compressed[0]).toEqual([
        'AAPL.US',
        'AAPL',
        '苹果',
        'pingguo',
        'pg',
        [],
        'US',
        'stock',
        true,
        100,
      ]);
    });

    test('handles empty aliases array', () => {
      const itemWithoutAliases: StockIndexItem[] = [
        {
          canonicalCode: 'TEST.US',
          displayCode: 'TEST',
          nameZh: '测试',
          pinyinFull: 'test',
          pinyinAbbr: 'test',
          aliases: [],
          market: 'US',
          assetType: 'stock',
          active: true,
          popularity: 50,
        },
      ];

      const compressed = compressIndex(itemWithoutAliases);

      expect(compressed[0][5]).toEqual([]);
    });

    test('handles undefined aliases', () => {
      const itemWithUndefinedAliases: StockIndexItem[] = [
        {
          canonicalCode: 'TEST.US',
          displayCode: 'TEST',
          nameZh: '测试',
          pinyinFull: 'test',
          pinyinAbbr: 'test',
          aliases: undefined as unknown as string[],
          market: 'US',
          assetType: 'stock',
          active: true,
          popularity: 50,
        },
      ];

      const compressed = compressIndex(itemWithUndefinedAliases);

      expect(compressed[0][5]).toEqual([]);
    });

    test('handles empty array', () => {
      const compressed = compressIndex([]);
      expect(compressed).toEqual([]);
    });
  });

  describe('findStockInIndex - Find stock', () => {
    test('finds existing stock', () => {
      const result = findStockInIndex('AAPL.US', mockIndexData);
      expect(result).not.toBeNull();
      expect(result?.canonicalCode).toBe('AAPL.US');
      expect(result?.nameZh).toBe('苹果');
    });

    test('returns null for non-existent stock', () => {
      const result = findStockInIndex('NOTFOUND.US', mockIndexData);
      expect(result).toBeNull();
    });

    test('finds inactive stock', () => {
      const result = findStockInIndex('ZZZZ.US', mockIndexData);
      expect(result).not.toBeNull();
      expect(result?.active).toBe(false);
    });

    test('handles empty index', () => {
      const result = findStockInIndex('AAPL.US', []);
      expect(result).toBeNull();
    });

    test('case-sensitive search', () => {
      const result = findStockInIndex('aapl.us', mockIndexData);
      expect(result).toBeNull();
    });
  });

  describe('getPopularStocks - Get popular stocks', () => {
    test('sorts by popularity descending', () => {
      const result = getPopularStocks(mockIndexData, 3);

      expect(result).toHaveLength(3);
      expect(result[0].canonicalCode).toBe('AAPL.US'); // popularity: 100
      expect(result[1].canonicalCode).toBe('NVDA.US'); // popularity: 98
      expect(result[2].canonicalCode).toBe('MSFT.US'); // popularity: 95
    });

    test('filters out inactive stocks', () => {
      const result = getPopularStocks(mockIndexData, 10);

      // ZZZZ.US is inactive, should not appear
      const hasInactive = result.some(item => !item.active);
      expect(hasInactive).toBe(false);
    });

    test('limits return count', () => {
      const result = getPopularStocks(mockIndexData, 2);
      expect(result.length).toBeLessThanOrEqual(2);
    });

    test('defaults to limit of 20', () => {
      const result = getPopularStocks(mockIndexData);
      expect(result.length).toBeLessThanOrEqual(20);
    });

    test('handles empty index', () => {
      const result = getPopularStocks([]);
      expect(result).toEqual([]);
    });

    test('handles all inactive stocks', () => {
      const inactiveOnly: StockIndexItem[] = [
        {
          canonicalCode: 'TEST.US',
          displayCode: 'TEST',
          nameZh: '测试',
          pinyinFull: 'test',
          pinyinAbbr: 'test',
          aliases: [],
          market: 'US',
          assetType: 'stock',
          active: false,
          popularity: 100,
        },
      ];

      const result = getPopularStocks(inactiveOnly);
      expect(result).toEqual([]);
    });

    test('maintains stable sorting for same popularity', () => {
      const samePopularity: StockIndexItem[] = [
        {
          canonicalCode: 'A.US',
          displayCode: 'A',
          nameZh: 'A',
          pinyinFull: 'a',
          pinyinAbbr: 'a',
          aliases: [],
          market: 'US',
          assetType: 'stock',
          active: true,
          popularity: 100,
        },
        {
          canonicalCode: 'B.US',
          displayCode: 'B',
          nameZh: 'B',
          pinyinFull: 'b',
          pinyinAbbr: 'b',
          aliases: [],
          market: 'US',
          assetType: 'stock',
          active: true,
          popularity: 100,
        },
      ];

      const result = getPopularStocks(samePopularity, 2);
      expect(result).toHaveLength(2);
      expect(result[0].popularity).toBe(100);
      expect(result[1].popularity).toBe(100);
    });
  });

  describe('groupStocksByMarket - Group stocks by market', () => {
    test('groups different markets correctly', () => {
      const result = groupStocksByMarket(mockIndexData);

      expect(result.size).toBe(1); // US MVP index
      expect(result.get('US')).toHaveLength(3);
    });

    test('filters out inactive stocks', () => {
      const result = groupStocksByMarket(mockIndexData);

      const usStocks = result.get('US')!;
      const allActive = usStocks.every(item => item.active);
      expect(allActive).toBe(true);
    });

    test('handles empty index', () => {
      const result = groupStocksByMarket([]);
      expect(result.size).toBe(0);
    });

    test('handles all inactive stocks', () => {
      const inactiveOnly: StockIndexItem[] = [
        {
          canonicalCode: 'A.US',
          displayCode: 'A',
          nameZh: 'A',
          pinyinFull: 'a',
          pinyinAbbr: 'a',
          aliases: [],
          market: 'US',
          assetType: 'stock',
          active: false,
          popularity: 100,
        },
      ];

      const result = groupStocksByMarket(inactiveOnly);
      expect(result.size).toBe(0);
    });

    test('returns independent arrays for groups', () => {
      const result = groupStocksByMarket(mockIndexData);

      const usStocks = result.get('US')!;
      const originalLength = usStocks.length;

      // Modifying returned array should not affect original data
      usStocks.pop();

      const result2 = groupStocksByMarket(mockIndexData);
      const usStocks2 = result2.get('US')!;

      expect(usStocks2.length).toBe(originalLength);
    });

    test('maintains order within groups', () => {
      const result = groupStocksByMarket(mockIndexData);

      const usStocks = result.get('US')!;
      expect(usStocks[0].canonicalCode).toBe('AAPL.US');
      expect(usStocks[1].canonicalCode).toBe('NVDA.US');
    });
  });

  describe('Edge case comprehensive tests', () => {
    test('handles very large datasets', () => {
      const largeIndex: StockIndexItem[] = Array.from({ length: 10000 }, (_, i) => ({
        canonicalCode: `TEST${i}.US`,
        displayCode: `TEST${i}`,
        nameZh: `测试${i}`,
        pinyinFull: `test${i}`,
        pinyinAbbr: `t${i}`,
        aliases: [],
        market: 'US',
        assetType: 'stock',
        active: i % 2 === 0,
        popularity: i % 100,
      }));

      expect(() => compressIndex(largeIndex)).not.toThrow();
      expect(() => findStockInIndex('TEST5000.US', largeIndex)).not.toThrow();
      expect(() => getPopularStocks(largeIndex, 10)).not.toThrow();
    });

    test('handles special characters', () => {
      const specialChars: StockIndexItem[] = [
        {
          canonicalCode: 'TEST.US',
          displayCode: 'TEST',
          nameZh: '测试·公司',
          pinyinFull: 'test-gongsi',
          pinyinAbbr: 'test',
          aliases: ['测试(集团)'],
          market: 'US',
          assetType: 'stock',
          active: true,
          popularity: 50,
        },
      ];

      const compressed = compressIndex(specialChars);
      expect(compressed[0][2]).toBe('测试·公司');
      expect(compressed[0][5]).toEqual(['测试(集团)']);
    });
  });
});
