"""
第六章 · 完整 Agent 整合
整合 Agent Loop + 记忆系统 + 工具系统 + Skill 系统

配套文档：docs/06-完整Agent上线.md
"""

import os
import time
from pathlib import Path

from .core.agent_loop import AgentLoop, make_llm_call, TOOL_REGISTRY
from .memory import WorkingMemory, LongTermMemory, HonchoProfile
from .skills import SkillGenerator, SkillLoader


class HermesMini:
    """
    Hermes-mini 完整 Agent。

    整合所有模块：
    - AgentLoop：核心推理循环
    - WorkingMemory：当前会话上下文
    - LongTermMemory：跨会话记忆
    - HonchoProfile：用户画像
    - SkillLoader：Skill 匹配与加载
    - SkillGenerator：Skill 自动生成
    """

    def __init__(
        self,
        user_id: str = "default",
        provider: str = "minimax",
        model: str = "minimax",
    ):
        self.user_id = user_id
        self.provider = provider
        self.model = model

        # 记忆系统
        self.working = WorkingMemory()
        self.longterm = LongTermMemory()
        self.honcho = HonchoProfile(user_id)

        # Skill 系统
        self.skill_loader = SkillLoader()
        self.skill_generator = SkillGenerator()

        # Agent Loop
        self._build_agent()

    def _build_agent(self):
        """构建 AgentLoop，注入所有上下文。"""
        # Honcho 用户画像（注入 system prompt）
        honcho_context = self.honcho.get_context()

        # 构建 system prompt（包含工具说明）
        tool_descs = []
        for name, t in TOOL_REGISTRY.items():
            # 兼容两种格式：ToolDefinition 对象 或 直接的函数
            if hasattr(t, "description"):
                desc = t.description or "无说明"
            else:
                desc = (t.__doc__ or "无说明").strip()
            tool_descs.append(f"- {name}: {desc}")

        system_prompt = f"""你是一个智能助手。{honcho_context}

【可用工具】
{{tools}}

【重要规则】
1. 当需要调用工具时，输出 JSON：{{"name": "工具名", "args": {{"参数": "值"}}}}
2. 如果不需要工具，直接输出回答
3. 用户偏好：{self.honcho.get('回答风格') or '按正常方式回答'}
"""

        self.agent = AgentLoop(
            system_prompt=system_prompt,
            provider=self.provider,
            model=self.model,
        )

    def chat(self, user_input: str) -> str:
        """
        主入口：一轮对话的完整生命周期。

        生命周期：
        1. 注入工作记忆上下文
        2. 检查 Skill 匹配（如果命中，直接返回 Skill 内容）
        3. 检查长期记忆相关上下文
        4. 调用 Agent Loop
        5. 更新 Honcho 画像
        6. 判断是否创建新 Skill
        """
        # Step 1: 检查 Skill 匹配
        matched_skill = self.skill_loader.match(user_input)
        if matched_skill:
            # Skill 命中，告诉用户这是直接调用的 Skill
            print(f"[Skill 命中] {matched_skill['path'].parent.name}")
            return f"[调用已有技能]\n{matched_skill['content'][:300]}..."

        # Step 2: 注入长期记忆上下文（如果有关联记忆）
        memory_context = self.longterm.build_context(
            user_input,
            llm_summarize_fn=lambda p: self._llm_call_simple(p),
        )
        if memory_context:
            print(f"[长期记忆] 注入相关记忆上下文")

        # Step 3: 注入工作记忆
        self.working.add_user(user_input)

        # Step 4: 调用 Agent
        response = self.agent.chat(user_input)

        # Step 5: 更新 Honcho 画像
        self.honcho.update(user_input, response)

        # Step 6: 更新长期记忆
        self.longterm.store_from_turn(user_input, response, self.user_id)

        # Step 7: 尝试创建新 Skill（如果满足触发条件）
        new_skill = self.skill_generator.create_skill(user_input, response)
        if new_skill:
            print(f"[新 Skill 创建] {new_skill}")
            # 重新加载 Skill 列表
            self.skill_loader.refresh()

        # Step 8: 更新工作记忆
        self.working.add_assistant(response)

        # Step 9: 检查是否需要上下文压缩（接近 token 上限）
        if self.working.is_near_limit():
            print("[上下文压缩] 消息历史过长，正在压缩...")
            summary = self.working.compress(
                llm_summarize_fn=lambda p: self._llm_call_simple(p),
            )
            print(f"[压缩摘要] {summary[:100]}...")

        return response

    def _llm_call_simple(self, prompt: str) -> str:
        """用于摘要生成的简单 LLM 调用（不注入记忆，防止循环）。"""
        try:
            return make_llm_call(
                [{"role": "user", "content": prompt}],
                provider=self.provider,
                model=self.model,
            )
        except Exception:
            return "[摘要生成失败]"

    def reset(self):
        """重置当前会话（保留长期记忆和用户画像）。"""
        self.working.clear()
        self.agent.reset()
        print("[会话已重置，长期记忆和用户画像保留]")


# ============================================================
# CLI 入口
# ============================================================

def main():
    print("=" * 50)
    print("Hermes-mini · 完整 Agent · 对话模式")
    print("=" * 50)
    print("【模块】记忆系统 · 工具系统 · Skill 系统 · Gateway")
    print("【指令】reset - 重置会话 | skills - 查看 Skill 列表 | quit - 退出\n")

    agent = HermesMini()

    print(f"【用户画像】{agent.honcho.get('回答风格') or '默认（尚未建立）'}")
    print(f"【已加载 Skill】{agent.skill_loader.get_all_skills() or '暂无'}")
    print()

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

        if user_input.lower() == "reset":
            agent.reset()
            continue

        if user_input.lower() == "skills":
            skills = agent.skill_loader.get_all_skills()
            print(f"已加载 Skill：{skills or '暂无'}")
            continue

        print()
        response = agent.chat(user_input)
        print(f"Agent > {response}")
        print()


if __name__ == "__main__":
    main()
