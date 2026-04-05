# -*- coding: utf-8 -*-
"""
共享的数据解析与字段归一化工具。

面向 ``context_snapshot`` / ``fundamental_context`` 等 JSON 或混类型字段，
提供模型名占位符过滤、JSON 字符串解析、板块与行业榜结构清洗等函数。
"""

import json
from typing import Any, Dict, List, Optional


# 模型名中的占位或无效字面量（大小写不敏感比较），归一化为 None
_MODEL_PLACEHOLDER_VALUES = {"unknown", "error", "none", "null", "n/a"}


def normalize_model_used(value: Any) -> Optional[str]:
    """将占位或空的模型名规范为 None。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in _MODEL_PLACEHOLDER_VALUES:
        return None
    return text


def parse_json_field(value: Any) -> Any:
    """对字符串做尽力而为的 JSON 解析；非字符串则原样返回。"""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError, ValueError):
            return value
    return value


def _non_empty_dict(value: Any) -> Optional[Dict[str, Any]]:
    """若 value 为非空 dict 则返回副本语义下的自身，否则 None。"""
    if not isinstance(value, dict):
        return None
    return value if value else None


def _normalize_belong_boards(value: Any) -> List[Dict[str, Any]]:
    """
    将 ``belong_boards`` 规范为字典列表：每项至少含 ``name``，可选 ``code``、``type``。
    跳过非 dict、缺 name 或 name 为空的项。
    """
    if not isinstance(value, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if name is None:
            continue
        name_text = str(name).strip()
        if not name_text:
            continue
        board = {"name": name_text}
        if item.get("code") is not None:
            code_text = str(item.get("code")).strip()
            if code_text:
                board["code"] = code_text
        if item.get("type") is not None:
            type_text = str(item.get("type")).strip()
            if type_text:
                board["type"] = type_text
        normalized.append(board)
    return normalized


def _safe_float(value: Any) -> Optional[float]:
    """从 str/int/float 安全解析浮点数；字符串末尾 ``%`` 会先去掉再解析。无法解析则 None。"""
    if value is None:
        return None
    try:
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            if text.endswith("%"):
                text = text[:-1].strip()
            return float(text)
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_sector_ranking_items(value: Any) -> List[Dict[str, Any]]:
    """
    规范板块涨跌榜中的条目列表：每项含 ``name``，若有 ``change_pct`` 则转为 float。
    """
    if not isinstance(value, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if name is None:
            continue
        name_text = str(name).strip()
        if not name_text:
            continue
        ranking_item: Dict[str, Any] = {"name": name_text}
        change_pct = _safe_float(item.get("change_pct"))
        if change_pct is not None:
            ranking_item["change_pct"] = change_pct
        normalized.append(ranking_item)
    return normalized


def _normalize_sector_rankings(value: Any) -> Optional[Dict[str, List[Dict[str, Any]]]]:
    """
    将 ``sector_rankings`` 规范为 ``{"top": [...], "bottom": [...]}``；输入非 dict 则 None。
    """
    if not isinstance(value, dict):
        return None

    return {
        "top": _normalize_sector_ranking_items(value.get("top")),
        "bottom": _normalize_sector_ranking_items(value.get("bottom")),
    }


def extract_fundamental_context(
    context_snapshot: Any,
    fallback_fundamental_payload: Any = None,
) -> Optional[Dict[str, Any]]:
    """
    从 context 快照中解析 ``fundamental_context``，可选用兜底载荷。

    优先路径：``snapshot.enhanced_context.fundamental_context``；
    否则使用 ``fallback_fundamental_payload`` 解析后的 dict（若存在）。
    """
    snapshot_obj = parse_json_field(context_snapshot)
    if isinstance(snapshot_obj, dict):
        enhanced = snapshot_obj.get("enhanced_context")
        if isinstance(enhanced, dict):
            fundamental = enhanced.get("fundamental_context")
            if isinstance(fundamental, dict):
                return fundamental

    fallback_obj = parse_json_field(fallback_fundamental_payload)
    if isinstance(fallback_obj, dict):
        return fallback_obj
    return None


def extract_fundamental_detail_fields(
    context_snapshot: Any,
    fallback_fundamental_payload: Any = None,
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    从 ``fundamental_context`` 中提取对外稳定的财报与分红块。

    返回键：``financial_report``、``dividend_metrics``（缺失或非 dict 时为 None）。
    """
    fundamental_ctx = extract_fundamental_context(
        context_snapshot=context_snapshot,
        fallback_fundamental_payload=fallback_fundamental_payload,
    )
    if not isinstance(fundamental_ctx, dict):
        return {"financial_report": None, "dividend_metrics": None}

    earnings_block = fundamental_ctx.get("earnings")
    earnings_data = earnings_block.get("data") if isinstance(earnings_block, dict) else None
    if not isinstance(earnings_data, dict):
        return {"financial_report": None, "dividend_metrics": None}

    financial_report = _non_empty_dict(earnings_data.get("financial_report"))
    dividend_metrics = _non_empty_dict(earnings_data.get("dividend"))
    return {
        "financial_report": financial_report,
        "dividend_metrics": dividend_metrics,
    }


def extract_board_detail_fields(
    context_snapshot: Any,
    fallback_fundamental_payload: Any = None,
) -> Dict[str, Any]:
    """
    从 ``fundamental_context`` 中提取板块相关稳定字段。

    - ``belong_boards``：归属板块列表（经 ``_normalize_belong_boards``）
    - ``sector_rankings``：当 ``boards.status`` 为 ok/partial 或未设时，取 ``boards.data`` 并规范结构
    """
    fundamental_ctx = extract_fundamental_context(
        context_snapshot=context_snapshot,
        fallback_fundamental_payload=fallback_fundamental_payload,
    )
    if not isinstance(fundamental_ctx, dict):
        return {"belong_boards": [], "sector_rankings": None}

    boards_block = fundamental_ctx.get("boards")
    sector_rankings = None
    if isinstance(boards_block, dict):
        boards_status = boards_block.get("status")
        if boards_status in {"ok", "partial"} or boards_status is None:
            sector_rankings = boards_block.get("data")
    return {
        "belong_boards": _normalize_belong_boards(fundamental_ctx.get("belong_boards")),
        "sector_rankings": _normalize_sector_rankings(sector_rankings),
    }
