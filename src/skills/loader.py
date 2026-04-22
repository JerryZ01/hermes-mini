"""
Skill 加载与触发匹配

给定用户输入，判断是否匹配已有 Skill；如果匹配，加载并执行。
"""

import json
from pathlib import Path
from typing import Optional


class SkillLoader:
    """
    Skill 加载与触发器。

    工作流程：
    1. 扫描 ~/.hermes/skills/ 下所有 SKILL.md
    2. 给定用户输入，用关键词匹配找到相关 Skill
    3. 返回匹配的 Skill 内容，供 Agent 直接使用
    """

    SKILLS_DIR = Path.home() / ".hermes" / "skills"

    def __init__(self):
        self.SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, dict] = {}  # skill_name -> {content, path, ...}
        self.refresh()

    def refresh(self):
        """扫描 skills 目录，更新缓存。"""
        self._cache.clear()
        if not self.SKILLS_DIR.exists():
            return

        for skill_dir in self.SKILLS_DIR.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            content = skill_md.read_text(encoding="utf-8")
            self._cache[skill_dir.name] = {
                "path": skill_md,
                "content": content,
                "invocation_count": 0,
            }

    def match(self, user_input: str) -> Optional[dict]:
        """
        判断用户输入是否匹配某个 Skill。

        匹配策略（简化版）：
        - 关键词匹配：Skill 名或内容中的关键词出现在用户输入中

        Returns:
            匹配的 Skill dict（包含 content 等），未匹配返回 None
        """
        user_input_lower = user_input.lower()

        for skill_name, skill_info in self._cache.items():
            # 优先匹配 Skill 名称
            if skill_name.lower() in user_input_lower:
                self._increment_count(skill_info)
                return skill_info

            # 次级匹配：用户输入包含 skill 内容中的关键词
            content_lower = skill_info["content"].lower()
            # 简单匹配：检查 skill 内容中是否有词汇出现在用户输入中
            if self._fuzzy_match(user_input_lower, content_lower):
                self._increment_count(skill_info)
                return skill_info

        return None

    def _fuzzy_match(self, user_input: str, skill_content: str) -> bool:
        """简单模糊匹配：技能内容的前 200 字中，有 2 个以上的词出现在用户输入中。"""
        # 提取技能内容的关键词（取前 200 字）
        sample = skill_content[:200]
        # 提取中文词（简化版）
        import re
        words = re.findall(r"[\u4e00-\u9fff]{2,}", sample)
        matched = sum(1 for w in words if w in user_input)
        return matched >= 2

    def _increment_count(self, skill_info: dict):
        """更新调用次数统计。"""
        skill_info["invocation_count"] = (
            skill_info.get("invocation_count", 0) + 1
        )
        # 写入 usage.json
        skill_path = skill_info["path"].parent
        usage_file = skill_path / "usage.json"
        usage_file.write_text(
            json.dumps(
                {"invocation_count": skill_info["invocation_count"]},
                ensure_ascii=False,
            )
        )

    def get_all_skills(self) -> list[str]:
        """返回所有已加载的 Skill 名称列表。"""
        return list(self._cache.keys())

    def get_skill(self, name: str) -> Optional[dict]:
        """按名称获取 Skill。"""
        return self._cache.get(name)
