# -*- coding: utf-8 -*-
"""
分析请求相关的共享元数据常量。

用于 API / 校验：标的来源（手工、补全、导入、图片识别等）。
"""

from __future__ import annotations


# 允许的 selection_source 取值，与 Analyze 请求里「选股来源」一致
SELECTION_SOURCES: tuple[str, ...] = ("manual", "autocomplete", "import", "image")
# 供 Pydantic / 正则校验用的模式串（manual|autocomplete|import|image）
SELECTION_SOURCE_PATTERN = "^(" + "|".join(SELECTION_SOURCES) + ")$"
