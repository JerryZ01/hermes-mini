"""
Skill 生成器
任务完成后判断是否创建 Skill，并生成 SKILL.md
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class SkillGenerator:
    """
    Skill 自动生成器。

    工作流程：
    1. 每次任务完成后，Agent 判断是否值得创建 Skill
    2. 如果值得，调用 generate() 生成 SKILL.md
    3. 写入 ~/.hermes/skills/{skill_name}/SKILL.md

    生成策略（简化版，不依赖 LLM）：
    - 关键词匹配：包含"以后都"、"每次"、"以后帮我"等触发词
    - 重复检测：同类任务出现 2 次以上
    """

    SKILLS_DIR = Path.home() / ".hermes" / "skills"
    # 触发创建 Skill 的关键词
    CREATE_TRIGGERS = [
        "以后都", "以后帮我", "每次", "以后请", "记住了",
        "以后用这个", "按这个", "参照这个",
    ]

    def __init__(self):
        self.SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    def should_create(self, user_input: str, assistant_output: str) -> bool:
        """判断当前任务是否值得创建 Skill。"""
        text = user_input + assistant_output
        return any(trigger in text for trigger in self.CREATE_TRIGGERS)

    def extract_skill_name(self, user_input: str) -> str:
        """
        从用户输入中提取 Skill 名称。

        简化版：从"以后都 XXX"中提取 XXX 作为名称
        """
        for trigger in self.CREATE_TRIGGERS:
            if trigger in user_input:
                # 取触发词后面的内容作为 skill 名
                parts = user_input.split(trigger)
                if len(parts) > 1:
                    name = parts[1].strip().rstrip("。")
                    # 取前 20 字符，移除标点
                    name = "".join(c for c in name if c.isalnum() or c in " -_").strip()
                    return name[:20] or "自定义技能"
        return "自定义技能"

    def generate(
        self,
        skill_name: str,
        user_input: str,
        assistant_output: str,
    ) -> Path:
        """
        生成 SKILL.md 文件。

        返回：
            Path：生成的文件路径
        """
        skill_dir = self.SKILLS_DIR / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)

        # 生成 SKILL.md 内容
        lines = [
            f"# {skill_name}",
            "",
            f"> 自动生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "> 触发原因：用户要求以后按此方式处理",
            "",
            "## 执行流程",
            "",
            "### 输入",
            f"用户说：`{user_input}`",
            "",
            "### 输出示例",
            f"```",
            assistant_output[:500] + ("..." if len(assistant_output) > 500 else ""),
            "```",
            "",
            "### 注意事项",
            "- 严格按照上述流程执行",
            "- 如有疑问，先思考再回答",
            "",
            "## 使用统计",
            "```json",
            json.dumps({
                "created_at": datetime.now().isoformat(),
                "invocation_count": 0,
                "last_used": None,
            }, ensure_ascii=False, indent=2),
            "```",
        ]

        skill_md_path = skill_dir / "SKILL.md"
        skill_md_path.write_text("\n".join(lines), encoding="utf-8")

        return skill_md_path

    def create_skill(
        self,
        user_input: str,
        assistant_output: str,
    ) -> Optional[Path]:
        """便捷入口：判断+生成一条龙。"""
        if not self.should_create(user_input, assistant_output):
            return None

        name = self.extract_skill_name(user_input)
        path = self.generate(name, user_input, assistant_output)
        return path
