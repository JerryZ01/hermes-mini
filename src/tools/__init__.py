"""
第三章 · 工具系统
工具注册、调用、结果注入

配套文档：docs/03-工具系统设计.md
"""

from .registry import register_tool, call_tool, get_all_tools, TOOL_REGISTRY

__all__ = ["register_tool", "call_tool", "get_all_tools", "TOOL_REGISTRY"]
