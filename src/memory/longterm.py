"""
长期记忆（Long-term Memory）
用 SQLite FTS5 做全文索引 + LLM 摘要检索

原理：
- 每轮对话结束后，把重要内容以 embedding-friendly 格式存入 SQLite
- 新会话开始时，根据当前任务关键词检索相关历史
- 用 LLM 把检索结果总结成"上下文注入"到对话
"""

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


class LongTermMemory:
    """
    跨会话长期记忆系统。

    数据存储：SQLite（FTS5 全文索引）
    数据格式：每条记忆 = 时间戳 + 关键词 + 内容摘要

    不依赖任何外部向量库，用关键词 + 摘要做轻量检索。
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(Path.home() / ".hermes" / "memory.db")
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ----------------------------------------------------------
    # 数据库初始化
    # ----------------------------------------------------------

    def _init_db(self):
        """建表（如果不存在）"""
        conn = sqlite3.connect(self.db_path)
        # unicode61 tokenizer 对中文更友好
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories
            USING fts5(
                keywords,
                content,
                session_id,
                timestamp,
                tokenize='unicode61'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_meta (
                memory_id INTEGER PRIMARY KEY,
                session_id TEXT,
                created_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    # ----------------------------------------------------------
    # 写入记忆
    # ----------------------------------------------------------

    def store(
        self,
        content: str,
        keywords: list[str],
        session_id: str = "default",
    ) -> int:
        """
        存储一条记忆。

        Args:
            content: 记忆内容（通常是 LLM 提炼后的摘要）
            keywords: 关键词列表（用于 FTS5 检索）
            session_id: 所属会话 ID

        Returns:
            memory_id（后续可用来删除或更新）
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "INSERT INTO memories (keywords, content, session_id, timestamp) VALUES (?, ?, ?, ?)",
            (" ".join(keywords), content, session_id, datetime.now().isoformat()),
        )
        memory_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return memory_id

    def store_from_turn(
        self,
        user_input: str,
        assistant_output: str,
        session_id: str = "default",
    ):
        """
        便捷方法：从一轮对话自动提炼并存储记忆。

        判断标准（简化版，不依赖 LLM）：
        - 用户输入包含问题/请求 → 值得记录
        - 助手的回答包含决策/结论 → 值得记录
        """
        # 简单的关键词判断（后续可升级为 LLM 提炼）
        should_store = any(
            kw in user_input or kw in assistant_output
            for kw in ["帮我", "帮我做", "完成了", "结论是", "答案是", "建议", "决定"]
        )
        if not should_store:
            return

        keywords = self._extract_keywords(user_input + " " + assistant_output)
        content = f"用户：{user_input}\n助手：{assistant_output}"
        self.store(content, keywords, session_id)

    def _extract_keywords(self, text: str, top_n: int = 5) -> list[str]:
        """
        简单的关键词提取（基于词频）。

        真实系统中用 LLM 提炼关键词，这里用词频替代。
        """
        # 去掉停用词
        stop_words = {
            "的", "是", "在", "了", "和", "与", "或", "吗", "呢", "啊",
            "你", "我", "他", "她", "它", "这", "那", "什么", "怎么",
        }
        words = [
            w for w in text
            if len(w) >= 2 and w not in stop_words
        ]
        from collections import Counter
        counter = Counter(words)
        return [w for w, _ in counter.most_common(top_n)]

    # ----------------------------------------------------------
    # 检索记忆
    # ----------------------------------------------------------

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        检索相关记忆。

        Args:
            query: 查询文本（通常是当前任务描述）
            top_k: 返回前 N 条

        Returns:
            [{"keywords": ..., "content": ..., "timestamp": ...}, ...]
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                """
                SELECT keywords, content, timestamp
                FROM memories
                WHERE memories MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, top_k),
            )
            rows = cursor.fetchall()
            conn.close()
        except (sqlite3.OperationalError, UnicodeEncodeError, UnicodeDecodeError):
            # FTS5 中文检索可能遇到编码问题，降级返回空
            return []
        return [
            {"keywords": r[0], "content": r[1], "timestamp": r[2]}
            for r in rows
        ]

    # ----------------------------------------------------------
    # 上下文注入（给 Agent Loop 用）
    # ----------------------------------------------------------

    def build_context(self, query: str, llm_summarize_fn, top_k: int = 3) -> str:
        """
        根据当前查询，检索相关记忆并 LLM 总结，生成注入上下文的字符串。

        Returns:
            格式化的记忆上下文字符串，如果无相关记忆则返回空字符串
        """
        results = self.search(query, top_k=top_k)
        if not results:
            return ""

        context_lines = [
            f"【历史记忆 #{i + 1}】{r['content']}"
            for i, r in enumerate(results)
        ]
        context_text = "\n".join(context_lines)

        prompt = f"""以下是与当前任务相关的历史记忆，请提炼出对当前任务有帮助的信息：

{context_text}

请总结："""

        summary = llm_summarize_fn(prompt)
        return f"\n【相关记忆】{summary}\n"
