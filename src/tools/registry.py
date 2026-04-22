"""
工具注册与调用系统

设计思路（对应 docs/03-工具系统设计.md）：
- 每个工具 = Python 函数 + 元数据（名称、描述、参数 schema）
- 用装饰器注册到全局 ToolRegistry
- Agent Loop 通过 registry 调用工具，把结果注入上下文
"""

import inspect
from typing import Any, Callable, Optional


# ============================================================
# 全局工具注册表
# ============================================================

TOOL_REGISTRY: dict[str, "ToolDefinition"] = {}


class ToolDefinition:
    """
    工具定义：封装一个可调用工具的元信息。
    """

    def __init__(self, name: str, func: Callable, description: str = ""):
        self.name = name
        self.func = func
        self.description = description or (func.__doc__ or "").strip()
        # 从函数签名提取参数信息
        sig = inspect.signature(func)
        self.params = {
            p.name: {
                "type": "string",  # 简化版不做复杂类型推断
                "default": p.default if p.default != inspect.Parameter.empty else None,
            }
            for p in sig.parameters.values()
        }

    def invoke(self, args: dict) -> str:
        """调用工具函数，返回字符串结果。"""
        try:
            result = self.func(**args)
            return str(result) if result is not None else "[成功，无返回内容]"
        except TypeError as e:
            # 参数缺失或类型错误
            missing = [p for p in self.params if p not in args]
            return f"[错误] 缺少参数: {missing}。原始错误: {e}"
        except Exception as e:
            return f"[错误] {self.name} 执行失败: {e}"

    def to_schema(self) -> dict:
        """
        生成 JSON Schema（供 LLM 理解工具接口）。

        用于在 system prompt 中告诉 LLM 工具的用法。
        """
        param_schemas = {}
        for pname, pinfo in self.params.items():
            schema = {"type": pinfo["type"]}
            if pinfo["default"] is not None:
                schema["default"] = pinfo["default"]
            param_schemas[pname] = schema

        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": param_schemas,
                "required": [
                    p for p, info in self.params.items()
                    if info["default"] is None
                ],
            },
        }


# ============================================================
# 注册装饰器
# ============================================================

def register_tool(name: str, description: str = ""):
    """
    装饰器：注册一个工具函数。

    用法：
        @register_tool("天气查询", "查询指定城市的天气")
        def weather(city: str) -> str:
            '''城市名称，返回天气描述'''
            ...
    """
    def decorator(func: Callable) -> Callable:
        TOOL_REGISTRY[name] = ToolDefinition(name, func, description or func.__doc__ or "")
        return func
    return decorator


def call_tool(name: str, args: dict) -> str:
    """根据工具名调用对应函数。"""
    if name not in TOOL_REGISTRY:
        available = list(TOOL_REGISTRY.keys())
        return f"[错误] 未知工具: {name}。可用工具: {available}"
    return TOOL_REGISTRY[name].invoke(args)


def get_all_tools() -> list[dict]:
    """返回所有工具的 JSON Schema 列表。"""
    return [t.to_schema() for t in TOOL_REGISTRY.values()]


# ============================================================
# 内置工具集
# ============================================================

@register_tool("计算器", "安全执行数学表达式，支持加减乘除括号。使用 eval 的沙箱版本。")
def calculator(expr: str) -> str:
    """计算数学表达式（仅支持数字和 + - * / . ( )）"""
    import re
    expr = expr.strip()
    if not re.match(r"^[\d\s\+\-\*\/\.\(\)]+$", expr):
        return f"[错误] 包含非法字符"
    try:
        result = eval(expr, {"__builtins__": {}})
        return str(result)
    except Exception as e:
        return f"[错误] 计算失败: {e}"


@register_tool("日期", "返回当前日期和时间")
def get_date() -> str:
    """返回当前日期"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %A %H:%M:%S")


@register_tool("搜索", "在 Google 上搜索关键词，返回搜索结果摘要")
def web_search(query: str) -> str:
    """
    搜索网页（需要网络）。

    这里用了 DuckDuckGo 的免 API Key 免费接口。
    真实项目中替换成 Google Serper / SerpAPI 等付费接口。
    """
    try:
        fromduck = __import__("requests")
    except ImportError:
        return "[错误] requests 库未安装，无法搜索"

    try:
        resp = __import__("requests").get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1"},
            timeout=10,
        )
        data = resp.json()
        results = data.get("RelatedTopics", [])
        if not results:
            return "未找到相关结果"
        snippets = [
            r.get("Text", "")
            for r in results[:5]
            if r.get("Text")
        ]
        return "\n".join(f"• {s}" for s in snippets) if snippets else "未找到相关结果"
    except Exception as e:
        return f"[错误] 搜索失败: {e}"


@register_tool("读文件", "读取指定路径的文件内容")
def read_file(path: str) -> str:
    """读取文件内容（限制最大 50KB）"""
    try:
        content = Path(path).read_text(encoding="utf-8")
        if len(content) > 50_000:
            return content[:50_000] + "\n[...文件过长，已截断...]"
        return content
    except FileNotFoundError:
        return f"[错误] 文件不存在: {path}"
    except Exception as e:
        return f"[错误] 读取失败: {e}"


@register_tool("写文件", "向指定路径写入内容")
def write_file(path: str, content: str) -> str:
    """写入文件（自动创建父目录）"""
    try:
        import os
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        Path(path).write_text(content, encoding="utf-8")
        return f"[成功] 已写入 {path}，共 {len(content)} 字符"
    except Exception as e:
        return f"[错误] 写入失败: {e}"


from pathlib import Path
