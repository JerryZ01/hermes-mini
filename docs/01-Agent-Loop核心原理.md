# 第一章 · Agent Loop：感知 → 推理 → 行动

> 本章配套代码：`src/core/agent_loop.py`

---

## 本章目标

- 理解 Agent Loop 为什么是 Agent 的心脏
- 区分"真正的 Agent"和"伪 Agent"（提示词管道）
- 理解工具调用的本质：LLM 输出结构化 JSON → 执行 → 结果注入
- 用 ~280 行代码实现一个最小可用的 Agent Loop
- 理解为什么 Hermes 把"不断循环直到结束"作为核心设计

---

## 1.1 先把核心概念说清楚

**Agent 不是什么：**

大多数人对 Agent 的理解是错的。市面上 90% 的"AI Agent 课程"教的是这个：

```python
# 这不是 Agent，这是高级 if-else
response = llm.chat("用户说: " + user_input)
if "查天气" in response:
    result = call_weather_api()
    final = llm.chat(f"用户问天气，天气是{result}，请回复")
```

这段代码的致命问题：**工具调用被硬编码进了 if-else**。如果用户说"帮我看看今天适合出门吗"，这个 if-else 就失效了——它永远无法处理未曾预见的输入。

**Agent 是什么：**

真正的 Agent 让 LLM **自己决定**什么时候调用工具、调用哪个工具、传什么参数：

```
用户："帮我看看今天适合出门吗"
        ↓
LLM 推理：我需要先知道天气，才能判断是否适合出门
         → 输出 {"name": "weather", "args": {"city": "上海"}}
        ↓
执行 weather( city="上海" ) → "多云，22度"
        ↓
LLM 继续推理：天气不差，适合出门
         → 输出 "今天上海多云22度，适合出门"
```

这个循环一直持续，直到 LLM 认为"不需要再调用工具了"。

---

## 1.2 Agent Loop 的完整生命周期

```
                    ┌──────────────────────────────────────┐
                    │            Agent Loop                 │
                    │                                      │
  用户输入 ──▶ [构建上下文] ──▶ [LLM 推理] ──▶ [判断输出类型] │
                           │                │                │
                    ┌───────┴───────┐  ┌──────┴───────┐     │
                    │ 工具调用 JSON  │  │  普通文本响应  │     │
                    └───────┬───────┘  └──────────────┘     │
                           │                                │
                    [执行工具]                               │
                           │                                │
                    [结果注入上下文] ───────────────────────▶│ [LLM 继续推理]
                                                           │
                                                      [停止]
```

每一步的详细说明：

**构建上下文（Context Building）**
- 把用户消息 + 历史对话 + system prompt 拼接成完整的消息列表
- system prompt 里要告诉 LLM：你有哪些工具、怎么调用
- 上下文就是 LLM 的"眼睛"，它只能看到上下文里的信息

**LLM 推理（Reasoning）**
- 把完整的上下文发给 LLM
- LLM 根据所有信息决定：下一步应该做什么

**判断输出类型（Output Parsing）**
- 如果 LLM 输出普通文本 → 结束本轮，返回给用户
- 如果 LLM 输出 JSON 工具调用 → 解析 JSON，执行工具，把结果注入上下文，继续推理

**停止条件**
- LLM 输出普通文本（认为任务完成）
- 达到最大循环轮次（防止死循环，通常设为 10）

---

## 1.3 工具调用协议：LLM 和代码之间的"合约"

LLM 怎么知道要输出什么格式？这是通过 system prompt 约定的"协议"。

Hermes-mini 的协议：

```
当你需要调用工具时，输出一个 JSON 对象：
{"name": "工具名", "args": {"参数名": "参数值"}}

如果不需要工具，直接输出你的回答。
```

**协议的关键要素：**
- 工具名（`name`）：LLM 用来识别要调用哪个工具
- 参数对象（`args`）：LLM 自主决定传什么参数
- 格式：JSON 字符串（比自然语言更可靠、更易解析）

真实系统（Claude Code、OpenAI）会用更严格的 schema 验证，
但教学目的下这个简化协议已经能覆盖 90% 的场景。

---

## 1.4 为什么 Hermes 把它叫"Loop"而不是"Pipeline"

Pipeline 是线性流程：输入 → 一步处理 → 输出。

Loop 是循环流程：输入 → 判断 → 处理 → 判断 → 处理 → ... → 输出。

**为什么 Agent 必须用循环？**

因为现实中的任务很少是一次性的：

1. **任务分解**：用户说"帮我分析这个项目"，LLM 决定"先读文件，再跑测试"
2. **条件分支**：LLM 根据上一步的结果决定下一步做什么
3. **自我修正**：工具调用失败后，LLM 需要决定是重试还是换方法
4. **多工具协作**：需要 A 工具的结果作为 B 工具的输入

这些都是 if-else 无法处理的场景，只有循环可以。

---

## 1.5 代码逐行解析

### 消息格式

```python
# 每条消息是一个 dict，role 决定角色
messages = [
    {"role": "system", "content": "你是一个助手..."},
    {"role": "user", "content": "用户说了什么"},
    {"role": "assistant", "content": "助手回答了什么"},
]
```

格式和 OpenAI Chat Completions API 完全一致。后续切换 provider 时不需要改格式。

### 工具注册表

```python
TOOL_REGISTRY: dict[str, callable] = {}

@register_tool("计算器")
def calculator(expr: str) -> str:
    ...
```

装饰器把函数注册进全局表，Agent Loop 通过名字查找并调用。这是**动态工具注册**的核心——新增工具不需要改 Agent 代码，只需要在 `tools/` 里写一个新函数并注册即可。

### 工具调用解析

```python
def parse_tool_call(raw: str) -> Optional[dict]:
    # 去掉 markdown 代码块包裹
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"```$", "", raw).strip()

    # 找第一个 JSON 对象
    start = raw.find("{")
    end = raw.rfind("}") + 1
    json_str = raw[start:end]

    try:
        data = json.loads(json_str)
        if "name" in data:
            return data
    except json.JSONDecodeError:
        pass
    return None  # 不是工具调用，是普通文本
```

这段代码处理了 LLM 最常见的输出格式问题——LLM 经常把 JSON 包裹在代码块里。

### 主循环

```python
def chat(self, user_input: str) -> str:
    self.messages.append({"role": "user", "content": user_input})

    for turn in range(MAX_TURNS):  # 防止死循环
        llm_output = make_llm_call(self.messages)  # 调用 LLM

        tool_call = parse_tool_call(llm_output)

        if tool_call is None:
            # 普通文本，结束
            self.messages.append({"role": "assistant", "content": llm_output})
            return llm_output

        # 工具调用
        result = call_tool(tool_call["name"], tool_call["args"])

        # 把工具结果注入上下文，LLM 继续推理
        self.messages.append({
            "role": "user",
            "content": f"[工具结果] {tool_call['name']}: {result}\n请继续。"
        })
```

---

## 1.6 真实 Agent 系统 vs Hermes-mini

| 维度 | Claude Code / GPT Agent | Hermes-mini |
|------|------------------------|-------------|
| 工具描述 | JSON Schema 严格定义 | 简化的自然语言描述 |
| 工具调用 | 函数调用（Function Calling）API 支持 | 正则解析 JSON 字符串 |
| 循环控制 | API 层面支持 | 自实现循环 |
| 上下文窗口 | 100K+ tokens | 受限于 LLM context |
| 多轮推理 | 支持 | 支持 |

Hermes-mini 的实现更简单，但核心逻辑和工业级系统完全一致——理解了这个循环，你就理解了 Claude Code 90% 的代码。

---

## 练习题

1. **修改 system prompt**：在 `agent_loop.py` 中给 LLM 增加一个"在回复前先输出思考过程"的指令，观察 LLM 的行为变化

2. **添加新工具**：在 `tools/registry.py` 中注册一个"网页搜索"工具，并验证 Agent 可以调用它（需要 requests 库）

3. **实现工具调用失败处理**：修改 `call_tool` 函数，当工具执行报错时，让 LLM 知道错误信息并自动重试或换方法

4. **增加最大轮次日志**：修改 Agent Loop，在达到第 5 轮时打印警告信息

---

## 下一章预告

Agent Loop 可以跑起来了，但每次对话 Agent 都是"从零开始"——
它不记得你们之前聊了什么，下一次对话也是陌生人。

**第二章：记忆系统**解决它。
