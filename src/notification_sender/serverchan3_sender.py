# -*- coding: utf-8 -*-
"""
Server酱（serverchan3）推送

「Server酱」是第三方推送服务的品牌名称，不是英文短语的中文翻译。
本类通过 ``Config.serverchan3_sendkey``（SendKey）调用其文档中的 HTTPS 接口发送 title/desp。
类名中的 ``serverchan3`` 与配置字段命名一致，便于与旧版接口区分，不代表额外意译。
"""
import logging
from typing import Optional
import requests
from datetime import datetime
import re

from src.config import Config


logger = logging.getLogger(__name__)


class Serverchan3Sender:
    
    def __init__(self, config: Config):
        """
        初始化发送器（读取配置中的 SendKey）。

        参数:
            config: 全局配置对象
        """
        self._serverchan3_sendkey = getattr(config, 'serverchan3_sendkey', None)
        
    def send_to_serverchan3(self, content: str, title: Optional[str] = None) -> bool:
        """
        调用 Server酱的 `.send` 接口发送一条消息。

        请求地址与字段以对方开放文档为准，常见形态包括：
        - ``POST https://sctapi.ftqq.com/{sendkey}.send``
        - 或 ``POST https://{num}.push.ft07.com/send/{sendkey}.send``（sendkey 以 ``sctp`` 前缀区分通道）

        请求体为 JSON，字段含 title、desp、options（可为空对象）。

        参数:
            content: 正文（通常为 Markdown）
            title: 标题；省略时使用带日期的默认标题

        返回:
            是否请求成功（HTTP 200 且按返回 JSON 视为成功时记为 True）
        """
        if not self._serverchan3_sendkey:
            logger.warning("未配置 Server酱 SendKey（serverchan3_sendkey），跳过推送")
            return False

        # 处理消息标题
        if title is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
            title = f"📈 股票分析报告 - {date_str}"

        try:
            # 根据 sendkey 格式构造 URL
            sendkey = self._serverchan3_sendkey
            if sendkey.startswith('sctp'):
                match = re.match(r'sctp(\d+)t', sendkey)
                if match:
                    num = match.group(1)
                    url = f"https://{num}.push.ft07.com/send/{sendkey}.send"
                else:
                    logger.error(
                        "Server酱 SendKey 无法解析：应为 sctp 前缀且匹配 sctp{n}t… 形态，请对照官方说明"
                    )
                    return False
            else:
                url = f"https://sctapi.ftqq.com/{sendkey}.send"

            # 构建请求参数
            params = {
                'title': title,
                'desp': content,
                'options': {}
            }

            # 发送请求
            headers = {
                'Content-Type': 'application/json;charset=utf-8'
            }
            response = requests.post(url, json=params, headers=headers, timeout=10)

            if response.status_code == 200:
                result = response.json()
                logger.info(f"Server酱 消息发送成功: {result}")
                return True
            else:
                logger.error(f"Server酱 请求失败: HTTP {response.status_code}")
                logger.error(f"响应内容: {response.text}")
                return False

        except Exception as e:
            logger.error(f"发送 Server酱 消息失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

