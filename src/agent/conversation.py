# -*- coding: utf-8 -*-
"""
Agent 多轮对话的会话管理。

按 TTL 管理多个对话会话，持久化消息历史与上下文。
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.storage import get_db

logger = logging.getLogger(__name__)

@dataclass
class ConversationSession:
    """单次多轮对话会话。"""
    session_id: str
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)

    def add_message(self, role: str, content: str):
        """写入一条消息到会话历史。"""
        get_db().save_conversation_message(self.session_id, role, content)
        self.last_active = datetime.now()

    def update_context(self, key: str, value: Any):
        """更新会话上下文字段。"""
        self.context[key] = value
        self.last_active = datetime.now()

    def get_history(self) -> List[Dict[str, Any]]:
        """读取消息历史。"""
        messages = get_db().get_conversation_history(self.session_id)
        return messages

class ConversationManager:
    """在 TTL 内管理多个对话会话。"""
    
    def __init__(self, ttl_minutes: int = 30):
        self._sessions: Dict[str, ConversationSession] = {}
        self.ttl = timedelta(minutes=ttl_minutes)
        self._lock = threading.RLock()

    def get_or_create(self, session_id: str) -> ConversationSession:
        """获取已有会话；不存在则创建。"""
        with self._lock:
            self._cleanup_expired()

            if session_id not in self._sessions:
                self._sessions[session_id] = ConversationSession(session_id=session_id)
                logger.info(f"Created new conversation session: {session_id}")
            else:
                # 更新最后活跃时间
                self._sessions[session_id].last_active = datetime.now()

            return self._sessions[session_id]

    def add_message(self, session_id: str, role: str, content: str):
        """向指定会话追加一条消息。"""
        session = self.get_or_create(session_id)
        session.add_message(role, content)

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """读取指定会话的消息历史。"""
        session = self.get_or_create(session_id)
        return session.get_history()

    def clear(self, session_id: str):
        """从内存中移除会话（数据库历史保留）。"""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info(f"Cleared conversation session: {session_id}")
        # 此处不删库表记录，仅清内存；如需删库可另增方法。

    def _cleanup_expired(self):
        """清理超过 TTL 未活跃的内存会话。"""
        with self._lock:
            now = datetime.now()
            expired = [
                sid for sid, session in self._sessions.items()
                if now - session.last_active > self.ttl
            ]
            for sid in expired:
                del self._sessions[sid]
                logger.info(f"Cleaned up expired conversation session: {sid}")

# 全局单例
conversation_manager = ConversationManager()
