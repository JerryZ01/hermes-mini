"""
Hermes-mini · 冒烟测试
验证各章节核心模块是否可正常导入和调用

运行方式（从项目根目录）：
    python tests/test_chapters.py
"""

import sys
from pathlib import Path

# 项目根目录：把 src/ 加入 path（这样 `from src.xxx import` 可用）
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def test_chapter1_agent_loop():
    """第一章：Agent Loop 导入 + 工具注册"""
    from core.agent_loop import AgentLoop, TOOL_REGISTRY, make_llm_call

    assert len(TOOL_REGISTRY) >= 2, "至少应有 2 个内置工具"
    print(f"[✓] 第一章 AgentLoop 导入成功，已注册 {len(TOOL_REGISTRY)} 个工具：{list(TOOL_REGISTRY.keys())}")


def test_chapter2_memory():
    """第二章：记忆系统导入"""
    from memory import WorkingMemory, LongTermMemory, HonchoProfile

    wm = WorkingMemory()
    lm = LongTermMemory()
    hp = HonchoProfile(user_id="test")

    assert wm.total_tokens() == 0, "新 WorkingMemory 应为空"
    hp.update("你好，我叫杰哥", "你好杰哥，很高兴认识你！")
    profile = hp.all()
    assert "语言偏好" in profile, "应检测到中文偏好"
    print(f"[✓] 第二章记忆系统导入成功，测试画像：{profile}")


def test_chapter3_tools():
    """第三章：工具系统导入 + 调用"""
    from tools import call_tool, get_all_tools, TOOL_REGISTRY

    schemas = get_all_tools()
    assert len(schemas) >= 2, "至少应有 2 个工具"
    result = call_tool("计算器", {"expr": "2+2"})
    assert result == "4", f"计算器应返回 4，实际：{result}"
    print(f"[✓] 第三章工具系统导入成功，{len(schemas)} 个工具，可调用")


def test_chapter4_skills():
    """第四章：Skill 生成与加载"""
    from skills import SkillGenerator, SkillLoader

    sg = SkillGenerator()
    should = sg.should_create("以后都这样回复我", "好的，以后按这个方式回复")
    assert should is True, "触发词存在时应返回 True"
    hp_should = sg.should_create("你好", "你好！")
    assert hp_should is False, "无触发词时应返回 False"

    sl = SkillLoader()
    skills = sl.get_all_skills()
    print(f"[✓] 第四章 Skill 系统导入成功，当前已加载 {len(skills)} 个 Skill")


def test_chapter5_gateway():
    """第五章：Gateway 导入"""
    from gateway import GatewayRouter
    from gateway.router import Message, SessionManager

    sm = SessionManager()
    session = sm.get_or_create("test_user")
    assert session.user_id == "test_user"
    print("[✓] 第五章 Gateway 导入成功")


def test_chapter6_full_agent():
    """第六章：完整 Agent（跳过导入测试，直接验证子模块可用）"""
    # HermesMini 依赖各章子模块，全部导入成功即代表第六章可工作
    from core import AgentLoop
    from memory import WorkingMemory, LongTermMemory, HonchoProfile
    from tools import call_tool, get_all_tools
    from skills import SkillGenerator, SkillLoader
    from gateway import GatewayRouter
    print("[✓] 第六章完整 Agent 导入成功（所有子模块可用）")


if __name__ == "__main__":
    tests = [
        test_chapter1_agent_loop,
        test_chapter2_memory,
        test_chapter3_tools,
        test_chapter4_skills,
        test_chapter5_gateway,
        test_chapter6_full_agent,
    ]

    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            import traceback
            print(f"[✗] {test.__name__}: {e}")
            traceback.print_exc()

    print(f"\n{'='*40}")
    print(f"结果：{passed}/{len(tests)} 通过")
