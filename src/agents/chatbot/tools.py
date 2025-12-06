from typing import Any

from src.agents.common.tools import get_buildin_tools


def get_tools() -> list[Any]:
    """获取所有可运行的工具（给大模型使用）"""
    tools = get_buildin_tools()
    return tools
