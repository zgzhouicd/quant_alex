/**
 * searchStocks unit tests (US index fixtures).
 */

import { searchStocks } from '../searchStocks';
import type { StockIndexItem } from '../../types/stockIndex';
import { describe, expect, test } from 'vitest';

const mockIndex: StockIndexItem[] = [
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
    canonicalCode: 'BRK.B.US',
    displayCode: 'BRK.B',
    nameZh: '伯克希尔B',
    pinyinFull: 'baikexiereb',
    pinyinAbbr: 'bkxe',
    aliases: [],
    market: 'US',
    assetType: 'stock',
    active: true,
    popularity: 92,
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

describe('searchStocks', () => {
  test('精确匹配代码', () => {
    const results = searchStocks('AAPL', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('AAPL.US');
    expect(results[0].matchType).toBe('exact');
    expect(results[0].matchField).toBe('code');
  });

  test('精确匹配中文名称', () => {
    const results = searchStocks('苹果', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('AAPL.US');
    expect(results[0].matchType).toBe('exact');
    expect(results[0].matchField).toBe('name');
  });

  test('拼音首字母匹配', () => {
    const results = searchStocks('pg', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('AAPL.US');
    expect(results[0].matchType).toBe('exact');
  });

  test('别名匹配', () => {
    const results = searchStocks('NVIDIA', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('NVDA.US');
    expect(results[0].matchType).toBe('exact');
  });

  test('前缀匹配代码', () => {
    const results = searchStocks('AA', mockIndex);
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].matchType).toBe('prefix');
    expect(results[0].matchField).toBe('code');
  });

  test('前缀匹配名称', () => {
    const results = searchStocks('英伟', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].matchType).toBe('prefix');
    expect(results[0].matchField).toBe('name');
  });

  test('包含匹配拼音', () => {
    const results = searchStocks('yingwei', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('NVDA.US');
    expect(results[0].matchType).toBe('contains');
  });

  test('active 优先于 inactive', () => {
    const results = searchStocks('Z', mockIndex, { activeOnly: false });
    const activeResults = results.filter((r) => {
      const item = mockIndex.find((i) => i.canonicalCode === r.canonicalCode);
      return item?.active;
    });
    if (results.length > 1) {
      expect(activeResults.length).toBeGreaterThan(0);
    }
  });

  test('activeOnly 选项过滤不活跃股票', () => {
    const results = searchStocks('Z', mockIndex, { activeOnly: true });
    for (const result of results) {
      const item = mockIndex.find((i) => i.canonicalCode === result.canonicalCode);
      expect(item?.active).toBe(true);
    }
  });

  test('limit 选项限制返回数量', () => {
    const results = searchStocks('A', mockIndex, { limit: 1 });
    expect(results.length).toBeLessThanOrEqual(1);
  });

  test('无结果时返回空数组', () => {
    const results = searchStocks('NOTFOUND', mockIndex);
    expect(results).toHaveLength(0);
  });

  test('空查询返回空数组', () => {
    const results = searchStocks('', mockIndex);
    expect(results).toHaveLength(0);
  });

  test('大小写不敏感', () => {
    const results1 = searchStocks('aapl', mockIndex);
    const results2 = searchStocks('AAPL', mockIndex);
    expect(results1).toHaveLength(1);
    expect(results2).toHaveLength(1);
    expect(results1[0].canonicalCode).toBe(results2[0].canonicalCode);
  });

  test('sorts by popularity when scores are tied', () => {
    const results = searchStocks('A', mockIndex);
    if (results.length > 1) {
      for (let index = 0; index < results.length - 1; index++) {
        const currentItem = mockIndex.find((item) => item.canonicalCode === results[index].canonicalCode);
        const nextItem = mockIndex.find((item) => item.canonicalCode === results[index + 1].canonicalCode);
        if (results[index].score === results[index + 1].score) {
          expect(currentItem?.popularity || 0).toBeGreaterThanOrEqual(nextItem?.popularity || 0);
        }
      }
    }
  });

  test('美股代码匹配', () => {
    const results = searchStocks('AAPL', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('AAPL.US');
    expect(results[0].market).toBe('US');
  });

  test('supports dotted ticker display codes', () => {
    const results = searchStocks('BRK.B', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('BRK.B.US');
  });

  describe('Edge case tests', () => {
    test('special character query', () => {
      const results = searchStocks('@#$%', mockIndex);
      expect(results).toHaveLength(0);
    });

    test('pure space query', () => {
      const results = searchStocks('   ', mockIndex);
      expect(results).toHaveLength(0);
    });

    test('Unicode character query', () => {
      const results = searchStocks('股票🚀', mockIndex);
      expect(results).toHaveLength(0);
    });

    test('extra long query string', () => {
      const longQuery = 'a'.repeat(1000);
      const results = searchStocks(longQuery, mockIndex);
      expect(results).toHaveLength(0);
    });

    test('partial pinyin match', () => {
      const results = searchStocks('ping', mockIndex);
      expect(results.length).toBeGreaterThan(0);
      const hasApple = results.some((r) => r.canonicalCode === 'AAPL.US');
      expect(hasApple).toBe(true);
    });

    test('abbreviation prefix match', () => {
      const results = searchStocks('yw', mockIndex);
      expect(results.length).toBeGreaterThan(0);
      expect(results[0].matchType).toBe('prefix');
    });

    test('alias match partial', () => {
      const results = searchStocks('NVID', mockIndex);
      expect(results.length).toBeGreaterThan(0);
      expect(results[0].canonicalCode).toBe('NVDA.US');
    });
  });

  describe('Scoring system tests', () => {
    test('exact match has highest score', () => {
      const exactResults = searchStocks('AAPL', mockIndex);
      const prefixResults = searchStocks('AA', mockIndex);

      expect(exactResults[0].score).toBeGreaterThan(prefixResults[0].score);
    });

    test('code match prioritized over name match', () => {
      const codeResults = searchStocks('AAPL', mockIndex);
      const nameResults = searchStocks('苹果', mockIndex);

      expect(codeResults[0].score).toBe(99);
      expect(nameResults[0].score).toBeLessThan(99);
    });

    test('sorts by popularity when scores are equal', () => {
      const tieIndex: StockIndexItem[] = [
        {
          canonicalCode: 'TEST1.US',
          displayCode: 'TEST1',
          nameZh: '测试1',
          pinyinFull: 'test1',
          pinyinAbbr: 'ts1',
          aliases: [],
          market: 'US',
          assetType: 'stock',
          active: true,
          popularity: 50,
        },
        {
          canonicalCode: 'TEST2.US',
          displayCode: 'TEST2',
          nameZh: '测试2',
          pinyinFull: 'test2',
          pinyinAbbr: 'ts2',
          aliases: [],
          market: 'US',
          assetType: 'stock',
          active: true,
          popularity: 100,
        },
      ];

      const results = searchStocks('TEST', tieIndex);
      if (results.length > 1) {
        expect(results[0].canonicalCode).toBe('TEST2.US');
      }
    });
  });

  describe('Inactive stock tests', () => {
    test('filters out inactive stocks by default', () => {
      const results = searchStocks('ZZZZ', mockIndex);
      expect(results).toHaveLength(0);
    });

    test('shows inactive stocks when activeOnly=false', () => {
      const results = searchStocks('ZZZZ', mockIndex, { activeOnly: false });
      expect(results).toHaveLength(1);
      expect(results[0].canonicalCode).toBe('ZZZZ.US');
    });

    test('active stocks prioritized over inactive stocks', () => {
      const results = searchStocks('Z', mockIndex, { activeOnly: false });
      if (results.length > 1) {
        const firstItem = mockIndex.find((i) => i.canonicalCode === results[0].canonicalCode);
        expect(firstItem?.active).toBe(true);
      }
    });
  });

  describe('Performance tests', () => {
    test('large index search performance', () => {
      const largeIndex: StockIndexItem[] = Array.from({ length: 5000 }, (_, i) => ({
        canonicalCode: `S${i}.US`,
        displayCode: `S${i}`,
        nameZh: `股票${i}`,
        pinyinFull: `stock${i}`,
        pinyinAbbr: `s${i}`,
        aliases: [],
        market: 'US',
        assetType: 'stock',
        active: true,
        popularity: i % 100,
      }));

      const startTime = Date.now();
      const results = searchStocks('S1', largeIndex);
      const endTime = Date.now();

      expect(endTime - startTime).toBeLessThan(100);
      expect(results.length).toBeGreaterThan(0);
    });

    test('multiple search performance', () => {
      const iterations = 100;
      const startTime = Date.now();

      for (let i = 0; i < iterations; i++) {
        searchStocks('AA', mockIndex);
      }

      const endTime = Date.now();
      const avgTime = (endTime - startTime) / iterations;

      expect(avgTime).toBeLessThan(10);
    });
  });

  describe('Match type tests', () => {
    test('exact match type', () => {
      const results = searchStocks('AAPL', mockIndex);
      expect(results[0].matchType).toBe('exact');
    });

    test('prefix match type', () => {
      const results = searchStocks('AA', mockIndex);
      expect(results[0].matchType).toBe('prefix');
    });

    test('contains match type', () => {
      const results = searchStocks('yingwei', mockIndex);
      expect(results[0].matchType).toBe('contains');
    });
  });

  describe('Match field tests', () => {
    test('code field match', () => {
      const results = searchStocks('AAPL', mockIndex);
      expect(results[0].matchField).toBe('code');
    });

    test('name field match', () => {
      const results = searchStocks('微软', mockIndex);
      expect(results[0].matchField).toBe('name');
    });

    test('pinyin field match', () => {
      const results = searchStocks('pg', mockIndex);
      expect(results[0].matchField).toBe('pinyin');
    });

    test('alias field match', () => {
      const results = searchStocks('NVIDIA', mockIndex);
      expect(results.length).toBeGreaterThan(0);
    });
  });
});
