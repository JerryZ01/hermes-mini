"""
Honcho 用户画像
"方言式"用户特征记录——不记"说了什么"，而是记"你是什么样的人"

参考 Hermes Agent 的 Honcho 设计：
https://github.com/nousresearch/hermes-agent
https://github.com/plastic-labs/honcho

核心思路：
- 每次对话后，从对话中提炼用户的"特征信号"
- 特征存储为自然语言描述（不用结构化标签，更灵活）
- 下次对话时，主动注入相关特征到 system prompt
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class HonchoProfile:
    """
    用户画像生成器。

    工作方式：
    1. 初始化：读取已有画像（JSON 文件）
    2. 注入信号：每次对话后调用 update()，从对话中提炼特征
    3. 查询信号：根据当前对话内容，返回相关的用户特征

    数据文件：~/.hermes/honcho/{user_id}.json
    """

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.profile_path = Path.home() / ".hermes" / "honcho" / f"{user_id}.json"
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        self.profile: dict[str, str] = {}  # {trait: description}
        self._load()

    # ----------------------------------------------------------
    # 持久化
    # ----------------------------------------------------------

    def _load(self):
        if self.profile_path.exists():
            try:
                self.profile = json.loads(self.profile_path.read_text())
            except Exception:
                self.profile = {}

    def _save(self):
        self.profile_path.write_text(json.dumps(self.profile, ensure_ascii=False, indent=2))

    # ----------------------------------------------------------
    # 画像更新（由 Agent Loop 在每轮对话后调用）
    # ----------------------------------------------------------

    def update(self, user_input: str, assistant_output: str):
        """
        从一轮对话中提取用户特征信号，更新画像。

        实现策略（简化版，无 LLM）：
        - 检测语言偏好（中文/英文/中英混杂）
        - 检测回答风格偏好（简洁/详细）
        - 检测话题倾向

        后续升级：接入 LLM 提炼，精度更高
        """
        changed = False

        # 检测语言偏好
        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in user_input)
        has_english = any('a' <= c <= 'z' for c in user_input.lower())
        if has_chinese and not has_english:
            trait = "语言偏好"
            value = "倾向使用中文，不喜欢中英混杂"
            if self.profile.get(trait) != value:
                self.profile[trait] = value
                changed = True
        elif has_chinese and has_english:
            trait = "语言偏好"
            value = "接受中英混杂表达"
            if self.profile.get(trait) != value:
                self.profile[trait] = value
                changed = True

        # 检测回答风格偏好（通过用户输入长度判断）
        input_len = len(user_input)
        if input_len < 30:
            trait = "回答风格"
            value = "偏好简洁直接的回答，避免废话"
            if self.profile.get(trait) != value:
                self.profile[trait] = value
                changed = True
        elif input_len > 200:
            trait = "回答风格"
            value = "偏好详细全面的回答"
            if self.profile.get(trait) != value:
                self.profile[trait] = value
                changed = True

        # 检测话题倾向（基于关键词）
        topic_keywords = {
            "足球": ["足球", "球员", "比赛", "进球", "梅西", "C罗"],
            "技术": ["代码", "Python", "API", "编程", "开发"],
            "AI/大模型": ["LLM", "模型", "Agent", "AI", "GPT"],
        }
        for topic, kws in topic_keywords.items():
            if any(kw in user_input for kw in kws):
                trait = "兴趣话题"
                self.profile[trait] = f"对 {topic} 有持续兴趣"
                changed = True
                break

        if changed:
            self._save()

    # ----------------------------------------------------------
    # 查询画像（注入到 system prompt）
    # ----------------------------------------------------------

    def get_context(self, current_input: str = "") -> str:
        """
        根据当前输入，返回相关的用户画像片段。

        用法：
        agent = AgentLoop()
        profile_context = honcho.get_context(user_input)
        # profile_context 注入到 system prompt 中
        """
        if not self.profile:
            return ""

        lines = ["【用户画像】"]
        for trait, desc in self.profile.items():
            lines.append(f"- {desc}")
        return "\n".join(lines)

    # ----------------------------------------------------------
    # 画像查询
    # ----------------------------------------------------------

    def get(self, trait: str) -> Optional[str]:
        return self.profile.get(trait)

    def all(self) -> dict[str, str]:
        return self.profile.copy()
