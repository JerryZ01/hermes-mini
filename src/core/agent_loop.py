"""
Agent Loop — Agent 的心脏

核心思路（对应 docs/01-Agent-Loop核心原理.md）：
1. 构建消息历史（上下文）
2. 发送给 LLM 推理
3. 判断输出类型：
   - 如果是普通文本 → 直接返回，结束本轮
   - 如果是工具调用 → 执行工具，把结果注入消息，继续推理
4. 循环直到不再需要工具调用，或达到最大轮次

这是 Hermes / Claude Code / AutoGPT 等所有 Agent 系统的通用骨架。
"""

import json
import time
from typing import Literal, Optional

# ============================================================
# LLM 调用层（支持 GLM / Qwen / OpenAI 三种后端）
# 只需修改 DEFAULT_PROVIDER 切换模型
# ============================================================

DEFAULT_PROVIDER = "minimax"  # "minimax" | "glm" | "qwen" | "openai"


def make_llm_call(
    messages: list[dict],
    provider: str = DEFAULT_PROVIDER,
    model: str = "glm-5",
    api_key: Optional[str] = None,
) -> str:
    """
    通用的 LLM 调用接口。

    Args:
        messages: [{"role": "user/assistant/system", "content": "..."}]
        provider: "glm" | "qwen" | "openai"
        model:   模型名称
        api_key: API Key（也可通过环境变量 GLM_API_KEY / QWEN_API_KEY 设置）

    Returns:
        LLM 的原始输出字符串
    """
    import os

    if provider == "minimax":
        import requests

        api_key = api_key or os.environ.get("HERMES_MINIMAX_API_KEY", "")
        minimax_url = os.environ.get(
            "HERMES_MINIMAX_BASE_URL",
            "http://1505824313958960.cn-hangzhou.pai-eas.aliyuncs.com/api/predict/minimax_m2/v1/chat/completions",
        )
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": model or "minimax", "messages": messages}
        resp = requests.post(minimax_url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    elif provider == "glm":
        import requests

        api_key = api_key or os.environ.get("GLM_API_KEY", "")
        url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": model, "messages": messages}
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    elif provider == "qwen":
        import requests

        api_key = api_key or os.environ.get("QWEN_API_KEY", "")
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": model, "messages": messages}
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    elif provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY", ""))
        # 把 role 映射成 OpenAI 格式
        openai_messages = [
            {"role": m["role"], "content": m["content"]} for m in messages
        ]
        response = client.chat.completions.create(
            model=model, messages=openai_messages
        )
        return response.choices[0].message.content

    else:
        raise ValueError(f"不支持的 provider: {provider}")


# ============================================================
# 工具调用协议
#
# LLM 返回工具调用时，格式为 JSON 字符串：
# {"name": "工具名", "args": {"参数": "值"}}
# ============================================================

TOOL_CALL_STOP_SIGNAL = "###AGENT:DONE###"  # 标记一轮结束


def parse_tool_call(raw: str) -> Optional[dict]:
    """
    尝试从 LLM 输出中解析工具调用。

    策略：查找 JSON 对象（以 { 开头，以 } 结尾），尝试解析。
    如果解析失败，返回 None，视为普通文本。

    真实 Agent 系统（如 Claude Code）会用更严格的 schema，
    这里用简化版本方便教学理解。
    """
    import re

    raw = raw.strip()
    # 去掉可能的 markdown 代码块包裹
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"^```\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    # 尝试找第一个 JSON 对象
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return None

    json_str = raw[start:end]
    try:
        data = json.loads(json_str)
        if "name" in data:
            return data
    except json.JSONDecodeError:
        pass
    return None


# ============================================================
# 工具注册表
# ============================================================

TOOL_REGISTRY: dict[str, callable] = {}


def register_tool(name: str):
    """
    装饰器：注册一个工具函数。

    用法：
        @register_tool("天气查询")
        def weather(city: str) -> str:
            ...
    """

    def decorator(func: callable):
        TOOL_REGISTRY[name] = func
        return func

    return decorator


def call_tool(name: str, args: dict) -> str:
    """根据工具名调用对应函数，返回结果字符串。"""
    if name not in TOOL_REGISTRY:
        return f"[错误] 未知工具: {name}"
    try:
        result = TOOL_REGISTRY[name](**args)
        return str(result)
    except Exception as e:
        return f"[错误] 工具 {name} 执行失败: {e}"


# ============================================================
# 内置工具（第三章会详细讲，这里先注册两个最基础的）
# ============================================================

@register_tool("计算器")
def calculator(expr: str) -> str:
    """安全的数学计算工具（只支持加减乘除括号）"""
    import re

    expr = expr.strip()
    # 安全检查：只允许数字和 +-*/.()
    if not re.match(r"^[\d\s\+\-\*\/\.\(\)]+$", expr):
        return f"[错误] 计算表达式包含非法字符: {expr}"
    try:
        result = eval(expr, {"__builtins__": {}})
        return str(result)
    except Exception as e:
        return f"[错误] 计算失败: {e}"


@register_tool("日期")
def get_date() -> str:
    """返回当前日期"""
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %A")


# ============================================================
# Agent Loop 核心
# ============================================================

MAX_TURNS = 10  # 最大循环轮次，防止死循环


class AgentLoop:
    """
    Agent Loop 主循环。

    与 Hermes Agent 的核心 loop 完全对应：
    1. 构建 system prompt（包含工具描述）
    2. 循环：发消息 → LLM 推理 → 判断是否工具调用 → 执行 → 注入结果
    3. 直到 LLM 输出普通文本（或达到最大轮次）
    """

    def __init__(
        self,
        system_prompt: str = "",
        provider: str = DEFAULT_PROVIDER,
        model: str = "glm-5",
        api_key: Optional[str] = None,
    ):
        self.messages: list[dict] = []
        self.provider = provider
        self.model = model
        self.api_key = api_key

        # 系统提示词：Agent 的人设 + 工具说明
        if system_prompt:
            self.system_prompt = system_prompt
        else:
            self.system_prompt = self._default_system_prompt()

        # 把 system prompt 放在消息历史最前面
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def _default_system_prompt(self) -> str:
        """默认系统提示词：告诉 Agent 有哪些工具可用"""
        tool_descs = []
        for name, func in TOOL_REGISTRY.items():
            doc = func.__doc__ or "无说明"
            tool_descs.append(f"- {name}: {doc.strip()}")

        return f"""你是一个智能助手，可以通过调用工具来完成用户任务。

【可用工具】
{chr(10).join(tool_descs)}

【调用工具的方法】
当需要调用工具时，输出一个 JSON 对象：
{{"name": "工具名", "args": {{"参数名": "参数值"}}}}

如果不需要调用工具，直接输出你的回答。

【重要】
1. 只输出 JSON 或普通文本，不要输出其他内容
2. 工具调用结果会注入到上下文中，继续推理后输出最终答案
3. 如果工具调用失败，说明原因并尝试其他方式
"""

    def reset(self):
        """重置对话历史（保留 system prompt）"""
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def chat(self, user_input: str) -> str:
        """
        主入口：接收用户输入，返回 Agent 响应。

        完整流程：
        1. 把用户消息加入历史
        2. 调用 LLM
        3. 解析输出：
           - 普通文本 → 返回
           - 工具调用 → 执行 → 把结果注入 → 回到步骤 2
        """
        # Step 1: 加入用户消息
        self.messages.append({"role": "user", "content": user_input})

        # Step 2: 进入推理循环
        for turn in range(MAX_TURNS):
            try:
                llm_output = make_llm_call(
                    messages=self.messages,
                    provider=self.provider,
                    model=self.model,
                    api_key=self.api_key,
                )
            except Exception as e:
                return f"[LLM 调用失败] {e}"

            # 解析工具调用
            tool_call = parse_tool_call(llm_output)

            if tool_call is None:
                # 没有工具调用 → 普通文本响应，结束本轮
                # 把 LLM 的文本输出作为 assistant 消息记录
                self.messages.append({"role": "assistant", "content": llm_output})
                return llm_output

            # 有工具调用 → 执行工具
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})

            # 打印工具调用过程（方便调试）
            print(f"[工具调用 #{turn + 1}] {tool_name}({tool_args})")

            tool_result = call_tool(tool_name, tool_args)
            print(f"[工具结果] {tool_result[:100]}{'...' if len(tool_result) > 100 else ''}")

            # 把工具调用和结果注入消息历史
            self.messages.append(
                {
                    "role": "user",
                    "content": (
                        f"[工具调用结果]\n"
                        f"工具: {tool_name}\n"
                        f"参数: {json.dumps(tool_args, ensure_ascii=False)}\n"
                        f"结果: {tool_result}\n\n"
                        "请基于工具结果继续推理，或输出最终回答。"
                    ),
                }
            )

        # 达到最大轮次仍未结束
        return "[停止] 达到最大循环轮次，可能陷入死循环。"


# ============================================================
# 演示入口
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("Hermes-mini · 第一章 · Agent Loop 演示")
    print("=" * 50)
    print()

    # 创建 Agent（使用默认 system prompt）
    agent = AgentLoop()

    # 内置了两个工具：计算器、日期
    print("【已注册工具】计算器、日期")
    print("【指令】输入 quit 退出\n")

    while True:
        try:
            user_input = input("你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("再见！")
            break

        print()
        response = agent.chat(user_input)
        print(f"Agent > {response}")
        print()
