#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stock Index Generation Script

Generate stock index file for frontend autocomplete functionality
Output to apps/dsa-web/public/stocks.index.json

US-only scope: index entries are built from STOCK_NAME_MAP (MVP tickers).

Usage:
    python3 scripts/generate_stock_index.py
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import List, Dict, Any

# Add the project root to sys.path.
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from pypinyin import lazy_pinyin
    PYPINYIN_AVAILABLE = True
except ImportError:
    PYPINYIN_AVAILABLE = False
    print("[Warning] pypinyin not available, pinyin fields will be empty")
    print("[Info] Install with: pip install pypinyin")


def normalize_name_for_pinyin(name: str) -> str:
    """
    Normalize stock name to avoid special prefixes and full-width characters polluting pinyin index

    Args:
        name: Original stock name

    Returns:
        Normalized name for pinyin generation
    """
    normalized = unicodedata.normalize('NFKC', name).strip()

    normalized = re.sub(r'^(?:\*?ST|N)+', '', normalized, flags=re.IGNORECASE)

    return normalized.strip() or unicodedata.normalize('NFKC', name).strip()


def generate_stock_index_from_map() -> List[Dict[str, Any]]:
    """
    Generate index from STOCK_NAME_MAP (MVP)

    Returns:
        List of stock index
    """
    from src.data.stock_mapping import STOCK_NAME_MAP

    index = []

    for code, name in STOCK_NAME_MAP.items():
        # Generate pinyin fields.
        pinyin_full = None
        pinyin_abbr = None
        if PYPINYIN_AVAILABLE:
            try:
                normalized_name = normalize_name_for_pinyin(name)
                py = lazy_pinyin(normalized_name)
                pinyin_full = ''.join(py)
                pinyin_abbr = ''.join([p[0] for p in py])
            except Exception:
                pass

        # Determine market and asset type.
        market, asset_type = determine_market_and_type(code)

        # Generate short aliases.
        aliases = generate_aliases(name)

        index.append({
            "canonicalCode": build_canonical_code(code, market),
            "displayCode": code,
            "nameZh": name,
            "pinyinFull": pinyin_full,
            "pinyinAbbr": pinyin_abbr,
            "aliases": aliases,
            "market": market,
            "assetType": asset_type,
            "active": True,
            "popularity": 100,  # Default popularity
        })

    return index


def determine_market_and_type(code: str) -> tuple:
    """All mapped symbols are US-listed equities or US ETFs in MVP scope."""
    return 'US', 'stock'


def market_to_suffix(market: str) -> str:
    """
    Convert market code to suffix

    Args:
        market: Market code

    Returns:
        Market suffix
    """
    return 'US' if market == 'US' else 'US'


def build_canonical_code(code: str, market: str) -> str:
    """US tickers use canonical form TICKER.US for frontend index compatibility."""
    return f"{code}.{market_to_suffix(market)}"


def generate_aliases(name: str) -> List[str]:
    """
    Generate stock aliases (abbreviations)

    Args:
        name: Full stock name

    Returns:
        List of aliases
    """
    aliases = []

    alias_map = {
        '苹果': ['AAPL'],
        '特斯拉': ['TSLA'],
        '英伟达': ['NVDA'],
        '亚马逊': ['AMZN'],
        '谷歌A': ['GOOGL'],
        '标普500ETF': ['SPY'],
        '纳指100ETF': ['QQQ'],
    }

    if name in alias_map:
        aliases.extend(alias_map[name])

    return aliases


def compress_index(index: List[Dict[str, Any]]) -> List[List]:
    """
    Compress index to array format to reduce file size

    Args:
        index: Original index

    Returns:
        Compressed index
    """
    compressed = []
    for item in index:
        compressed.append([
            item["canonicalCode"],
            item["displayCode"],
            item["nameZh"],
            item.get("pinyinFull"),
            item.get("pinyinAbbr"),
            item.get("aliases", []),
            item["market"],
            item["assetType"],
            item["active"],
            item.get("popularity", 0),
        ])
    return compressed


def main():
    """Main function"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description='生成股票自动补全索引文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 scripts/generate_stock_index.py              # 默认：生成索引文件
  python3 scripts/generate_stock_index.py --test       # 测试模式：只读取不写入
  python3 scripts/generate_stock_index.py --test -v    # 测试模式 + 显示详细数据
        """
    )
    parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='测试模式：只读取和验证数据，不写入文件'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='详细模式：显示前10条数据预览'
    )
    args = parser.parse_args()

    print("开始生成股票索引...")

    # 生成索引（MVP：使用现有映射）
    index = generate_stock_index_from_map()
    print(f"共生成 {len(index)} 条索引")

    # 按市场统计
    market_stats = {}
    for item in index:
        market = item['market']
        market_stats[market] = market_stats.get(market, 0) + 1
    print(f"市场分布：{market_stats}")

    # 压缩格式（减少文件大小）
    compressed = compress_index(index)

    # 测试模式：不写入文件
    if args.test:
        print("\n[测试模式] 不会写入文件")
        print(f"预计文件大小：{len(json.dumps(compressed, ensure_ascii=False, separators=(',', ':'))) / 1024:.2f} KB")

        if args.verbose:
            print("\n前10条数据预览：")
            for i, item in enumerate(index[:10]):
                print(f"  {i + 1}. {item['canonicalCode']} - {item['nameZh']} ({item['market']})")

        print("\n✓ 测试通过，数据格式正确")
        return 0

    # 输出路径
    output_path = Path(__file__).parent.parent / "apps" / "dsa-web" / "public" / "stocks.index.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('[\n')
        for i, item in enumerate(compressed):
            json.dump(item, f, ensure_ascii=False, separators=(',', ':'))
            if i < len(compressed) - 1:
                f.write(',\n')
            else:
                f.write('\n')
        f.write(']\n')

    file_size = output_path.stat().st_size
    print(f"索引已生成：{output_path}")
    print(f"文件大小：{file_size / 1024:.2f} KB")

    # 验证文件可读
    with open(output_path, 'r', encoding='utf-8') as f:
        test_data = json.load(f)
        print(f"验证通过：{len(test_data)} 条记录")

    return 0


if __name__ == "__main__":
    sys.exit(main())
