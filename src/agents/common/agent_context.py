"""Agent上下文管理 - 用于在工具执行时传递用户信息"""

from contextvars import ContextVar
from typing import Optional

# 当前执行的用户ID上下文变量
_current_user_id: ContextVar[Optional[str]] = ContextVar("current_user_id", default=None)


def set_user_id(user_id: str) -> None:
    """设置当前执行的用户ID"""
    _current_user_id.set(user_id)


def get_user_id() -> Optional[str]:
    """获取当前执行的用户ID"""
    return _current_user_id.get()


def clear_user_id() -> None:
    """清除当前执行的用户ID"""
    _current_user_id.set(None)

