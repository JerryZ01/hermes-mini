# 第一章 · Agent Loop：感知 → 推理 → 行动

> 本章配套代码：`src/core/agent_loop.py`

---

## 本章目标

- 理解什么是 Agent Loop，为什么它是 Agent 的心脏
- 区分"真正的 Agent"和"伪 Agent"（提示词管道）
- 用 ~200 行代码实现一个最小可用的 Agent Loop
- 理解工具调用（Tool Use）在本阶段的作用

---

## 什么是 Agent Loop？

> Agent Loop = 不断重复"感知环境 → 推理下一步 → 采取行动"的过程，直到任务完成。

这是 Hermes Agent、Claude Code、AutoGPT 等所有 Agent 系统的通用架构。

但"循环"本身不是壁垒。真正的难点是：**每一步用什么信息做决策？**

---

## 伪 Agent 的陷阱

很多人写的"Agent"是这个样子：

```python
# 这不是 Agent，这是一个高级 if-else
response = llm.chat("用户说: " + user_input)
if "查天气" in response:
    result = call_weather_api()
    final = llm.chat(f"根据{result}回复用户")
```

这是一个**提示词管道**——LLM 只负责文字接龙，工具调用被硬编码进 if-else。
它不能泛化，不能自我修正，无法处理未知的输入。

真正的 Agent 是这样工作的：

```
输入：用户的模糊目标
   ↓
【感知】构建完整的上下文（历史对话 + 环境状态 + 可用工具）
   ↓
【推理】LLM 分析并决定：调用哪个工具？还是直接回答？
   ↓
【行动】执行工具，拿到结果
   ↓
【判断】任务完成了吗？未完成则回到【感知】继续循环
```

---

## 最小 Agent Loop 实现

（见 `src/core/agent_loop.py`，逐行注释）

### 核心概念

- **Turn**：一次用户消息 + Agent 响应 = 一个 Turn
- **Message**：包含 role（user/assistant/system/tool）+ content
- **Tool Call**：LLM 决定调用的工具，格式为 `{"name": "...", "args": {...}}`
- **Stop 条件**：模型输出 END 信号，或达到最大轮次

---

## 练习题

1. 把 `src/core/agent_loop.py` 中的模型从 GLM-5 切换到 Qwen，跑通
2. 添加一个"思考过程"输出，打印每轮 LLM 的完整推理
3. 实现一个"最大轮次限制"，防止 Agent 陷入死循环

---

## 下一章预告

Agent Loop 可以跑起来了，但每次对话 Agent 都是"从零开始"——
它不记得你们之前聊了什么，下一次对话也是陌生人。

**第二章：记忆系统**解决它。
