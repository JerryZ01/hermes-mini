"""
工作记忆（Working Memory）
管理当前会话的上下文：消息历史 + token 统计 + 上下文压缩

原理：
- 每次对话的消息历史就是"工作记忆"
- 当 token 接近上限时，需要压缩历史（保留关键信息，丢弃细节）
"""

import tiktoken
from typing import Optional


class WorkingMemory:
    """
    当前会话的上下文管理器。

    核心功能：
    1. 维护消息列表
    2. 估算当前 token 数量
    3. 上下文压缩（保留 system + 最近的 N 轮 + 关键摘要）
    """

    def __init__(
        self,
        model: str = "gpt-4o",  # tiktoken 用 GPT-4o 的 cl100k_base 编码器
        max_tokens: int = 32000,  # 保留 32K token 上下文（留 buffer 给新输入）
    ):
        try:
            self.enc = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # 如果 tiktoken 不可用，用粗略估算（1 token ≈ 2 中文字符 ≈ 4 英文单词）
            self.enc = None

        self.model = model
        self.max_tokens = max_tokens
        self.messages: list[dict] = []
        self.summary: Optional[str] = None  # 压缩后生成的摘要

    # ----------------------------------------------------------
    # Token 估算
    # ----------------------------------------------------------

    def count_tokens(self, text: str) -> int:
        """估算文本的 token 数量。"""
        if self.enc is not None:
            return len(self.enc.encode(text))
        # 兜底：简单估算
        return len(text) // 2

    def total_tokens(self) -> int:
        """估算当前消息历史的总 token 数。"""
        total = 0
        for msg in self.messages:
            total += self.count_tokens(msg.get("content", ""))
            total += 4  # role + 结构开销
        return total

    def tokens_remaining(self) -> int:
        """剩余可用 token 数。"""
        return self.max_tokens - self.total_tokens()

    def is_near_limit(self, buffer: int = 2000) -> bool:
        """是否接近 token 上限。"""
        return self.total_tokens() > self.max_tokens - buffer

    # ----------------------------------------------------------
    # 消息管理
    # ----------------------------------------------------------

    def add_user(self, content: str):
        self.messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str):
        self.messages.append({"role": "assistant", "content": content})

    def add_system(self, content: str):
        self.messages.insert(0, {"role": "system", "content": content})

    def get_messages(self) -> list[dict]:
        return self.messages

    def clear(self):
        self.messages = []
        self.summary = None

    # ----------------------------------------------------------
    # 上下文压缩
    # ----------------------------------------------------------

    def compress(self, llm_summarize_fn, keep_recent: int = 4) -> str:
        """
        压缩上下文，保留关键信息。

        策略：
        1. 用 LLM 从消息历史中提炼"关键摘要"
        2. 保留 system prompt + 摘要 + 最近 N 轮对话

        后续章节会直接调用这个方法，由 Agent Loop 自动触发压缩
        """
        if len(self.messages) <= keep_recent * 2:
            return ""  # 消息不多，不需要压缩

        # 生成摘要
        history_text = "\n".join(
            f"[{m['role']}] {m['content'][:200]}"
            for m in self.messages
            if m["role"] != "system"
        )

        prompt = f"""请提炼以下对话的核心内容，保留：
- 用户的主要目标和需求
- 关键的决策和结论
- 未完成的事项

对话记录：
{history_text}

请用 3-5 句话概括："""

        self.summary = llm_summarize_fn(prompt)

        # 保留 system + 摘要 + 最近的消息
        system_msgs = [m for m in self.messages if m["role"] == "system"]
        recent_msgs = self.messages[-(keep_recent * 2) :]

        self.messages = system_msgs + [
            {"role": "system", "content": f"【对话历史摘要】{self.summary}"}
        ] + recent_msgs

        return self.summary
