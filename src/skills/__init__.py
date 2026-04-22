"""
第四章 · 自进化 Skill 系统
任务完成后自动创建 Skill，下次同类任务直接调用

配套文档：docs/04-自进化Skill机制.md
"""

from .generator import SkillGenerator
from .loader import SkillLoader

__all__ = ["SkillGenerator", "SkillLoader"]
