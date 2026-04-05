# -*- coding: utf-8 -*-
"""
===================================
Markdown 转图片工具模块
===================================

将 Markdown 转为 PNG 图片（用于不支持 Markdown 的通知渠道）。
支持 wkhtmltoimage (imgkit) 与 markdown-to-file (m2f)，后者对 emoji 支持更好 (Issue #455)。

安全说明：imgkit 经 stdin 把 HTML 交给 wkhtmltoimage，而非拼进命令行参数，内容侧命令注入面有限；
输出为栅格 PNG（不执行脚本）；入参来自系统生成的报告而非任意用户原文。当前用法下风险视为较低。
"""

import logging
import os
import shutil
import subprocess
import tempfile
from typing import Optional

from src.formatters import markdown_to_html_document

logger = logging.getLogger(__name__)


def _markdown_to_image_m2f(markdown_text: str) -> Optional[bytes]:
    """通过 markdown-to-file (m2f) CLI 将 Markdown 转为 PNG；emoji 表现更好 (Issue #455)。"""
    if shutil.which("m2f") is None:
        logger.warning(
            "m2f (markdown-to-file) not found in PATH. "
            "Install with: npm i -g markdown-to-file. Fallback to text."
        )
        return None

    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        md_path = os.path.join(temp_dir, "report.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_text)

        result = subprocess.run(
            ["m2f", md_path, "png", f"outputDirectory={temp_dir}"],
            capture_output=True,
            timeout=60,
            check=False,
        )
        png_path = os.path.join(temp_dir, "report.png")
        if result.returncode != 0 or not os.path.isfile(png_path):
            logger.warning(
                "m2f conversion failed: returncode=%s, stderr=%s",
                result.returncode,
                (result.stderr or b"").decode("utf-8", errors="replace")[:200],
            )
            return None

        with open(png_path, "rb") as f:
            return f.read()
    except subprocess.TimeoutExpired:
        logger.warning("m2f conversion timed out (60s)")
        return None
    except Exception as e:
        logger.warning("markdown_to_image (m2f) failed: %s", e)
        return None
    finally:
        if temp_dir and os.path.isdir(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except OSError as e:
                logger.debug("Failed to remove temp dir %s: %s", temp_dir, e)


def _markdown_to_image_wkhtml(markdown_text: str) -> Optional[bytes]:
    """通过 imgkit / wkhtmltoimage 将 Markdown 转为 PNG。"""
    try:
        import imgkit
    except ImportError:
        logger.debug("imgkit not installed, markdown_to_image unavailable")
        return None

    html = markdown_to_html_document(markdown_text)
    try:
        options = {
            "format": "png",
            "encoding": "UTF-8",
            "quiet": "",
        }
        out = imgkit.from_string(html, False, options=options)
        if out and isinstance(out, bytes) and len(out) > 0:
            return out
        logger.warning("imgkit.from_string returned empty or invalid result")
        return None
    except OSError as e:
        if "wkhtmltoimage" in str(e).lower() or "wkhtmltopdf" in str(e).lower():
            logger.debug("wkhtmltopdf/wkhtmltoimage not found: %s", e)
        else:
            logger.warning("imgkit/wkhtmltoimage error: %s", e)
        return None
    except Exception as e:
        logger.warning("markdown_to_image conversion failed: %s", e)
        return None


def markdown_to_image(markdown_text: str, max_chars: int = 15000) -> Optional[bytes]:
    """
    将 Markdown 转为 PNG 字节。

    引擎由 ``config.md2img_engine`` 决定：默认 wkhtmltoimage，可选 markdown-to-file（emoji 更好, Issue #455）。

    转换失败或依赖缺失时返回 None，调用方可回退为纯文本推送。

    参数:
        markdown_text: 原始 Markdown 文本
        max_chars: 超过该长度则跳过转图并返回 None（避免过大图片），默认 15000

    返回:
        PNG 二进制；失败或缺依赖时为 None
    """
    if len(markdown_text) > max_chars:
        logger.warning(
            "Markdown content (%d chars) exceeds max_chars (%d), skipping image conversion",
            len(markdown_text),
            max_chars,
        )
        return None

    try:
        from src.config import get_config

        engine = getattr(get_config(), "md2img_engine", "wkhtmltoimage")
    except Exception:
        engine = "wkhtmltoimage"

    if engine == "markdown-to-file":
        return _markdown_to_image_m2f(markdown_text)
    return _markdown_to_image_wkhtml(markdown_text)
