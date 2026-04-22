# 第六章 · 完整 Agent：整合所有模块，上线运行

> 本章配套代码：`src/__main__.py`

---

## 本章目标

- 整合 Agent Loop + 记忆系统 + 工具系统 + Skill + Gateway
- 实现一条命令启动完整 Agent
- 理解各模块之间的协作关系
- 了解部署到云端的基本步骤
- 运行完整的端到端验收测试

---

## 6.1 整合架构总览

```
用户消息（Telegram / CLI / Web）
        │
        ▼
   Gateway Router（路由 + 会话管理）
        │
        ▼
   HermesMini（完整 Agent）
        │
        ├──────────────────────────────────────────────┐
        │                                              │
        ▼                                              ▼
  Skill 匹配层                                Agent Loop
  ├── SkillLoader（匹配已有 Skill）              │
  └── SkillGenerator（创建新 Skill）             ▼
                                         LLM 推理（MiniMax/GLM/Qwen）
        │                                    │
        │◀─────── 工具系统 ────────────────►│
        │      ToolRegistry + 注册表          │
        │                                    ▼
        │                              响应输出
        │
        ├── Honcho Profile（用户画像注入）
        ├── WorkingMemory（会话上下文）
        └── LongTermMemory（跨会话记忆）
```

---

## 6.2 HermesMini 主类的设计

```python
class HermesMini:
    def __init__(self, user_id, provider, model):
        # 记忆系统
        self.working = WorkingMemory()
        self.longterm = LongTermMemory()
        self.honcho = HonchoProfile(user_id)

        # Skill 系统
        self.skill_loader = SkillLoader()
        self.skill_generator = SkillGenerator()

        # Agent Loop
        self._build_agent()
```

**为什么这样分层？**

- `working` / `longterm` / `honcho` 是**记忆层**，负责"知道什么"
- `skill_loader` / `skill_generator` 是**知识层**，负责"会做什么"
- `agent` 是**推理层**，负责"决定做什么"

三层各司其职，耦合低，容易单独测试和替换。

---

## 6.3 一轮对话的完整生命周期

`HermesMini.chat()` 是所有逻辑的汇聚点：

```python
def chat(self, user_input: str) -> str:
    # Step 1: Skill 匹配（优先）
    matched = self.skill_loader.match(user_input)
    if matched:
        return f"[调用已有技能]\n{matched['content']}"

    # Step 2: 注入长期记忆上下文
    memory_context = self.longterm.build_context(user_input, self._llm_call_simple)

    # Step 3: 注入工作记忆 + 调用 Agent
    self.working.add_user(user_input)
    response = self.agent.chat(user_input)

    # Step 4: 更新各层记忆
    self.honcho.update(user_input, response)      # 用户画像
    self.longterm.store_from_turn(...)           # 长期记忆
    self.working.add_assistant(response)          # 工作记忆

    # Step 5: 判断是否创建新 Skill
    new_skill = self.skill_generator.create_skill(user_input, response)
    if new_skill:
        print(f"[新 Skill 创建] {new_skill}")

    # Step 6: 上下文压缩（接近 token 上限时）
    if self.working.is_near_limit():
        self.working.compress(self._llm_call_simple)

    return response
```

---

## 6.4 安装与启动

### 本地安装

```bash
cd hermes-mini

# 方式 1：安装到系统
pip install -e .

# 方式 2：直接运行
python -m src

# 启动完整 Agent（带所有模块）
python -m src
```

### 第一次使用

```bash
# 1. 复制配置模板
cp .env.example .env

# 2. 编辑 .env，填入 API Key
nano .env

# 3. 运行
python -m src
```

### 交互命令

| 命令 | 作用 |
|------|------|
| `quit` / `exit` | 退出 |
| `reset` | 重置当前会话（保留长期记忆） |
| `skills` | 查看已加载的 Skill 列表 |

---

## 6.5 云端部署（$5 VPS）

以阿里云轻量应用服务器为例：

**Step 1：准备服务器**
```bash
# 安装 Python 3.11+
apt update && apt install -y python3.11 python3.11-venv

# 安装 uv（更快的包管理器）
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Step 2：拉取代码**
```bash
git clone https://github.com/JerryZ01/hermes-mini.git
cd hermes-mini
```

**Step 3：配置**
```bash
cp .env.example .env
# 编辑 .env 填入 API Key
```

**Step 4：后台运行**
```bash
# 用 systemd 管理进程（服务器重启自动启动）
sudo tee /etc/systemd/system/hermes.service <<EOF
[Unit]
Description=Hermes-mini Agent
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/hermes-mini
ExecStart=/home/ubuntu/.local/bin/python -m src
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable hermes
sudo systemctl start hermes
sudo systemctl status hermes
```

**Step 5：接入 Telegram（可选）**
```bash
hermes gateway --platform telegram --token 你的BotToken
```

---

## 6.6 验收测试清单

完成部署后，按以下清单验证各功能是否正常：

```
✅ 基本对话
   - 输入 "你好"，Agent 正常回复

✅ 工具调用
   - 输入 "1+1 等于几"，Agent 调用计算器返回 "2"
   - 输入 "今天几号"，Agent 调用日期工具返回当前日期

✅ 记忆系统
   - 第一次说 "我叫杰哥"
   - 第二次问 "我叫什么名字"，Agent 记住

✅ Skill 自进化
   - 输入 "以后都叫我老大"，Agent 记录
   - 后续对话中，Agent 自动使用这个称呼

✅ 多会话
   - 输入 "reset" 重置会话
   - Agent 记住的内容应该保留（长期记忆），当前会话内容清空

✅ Token 压缩
   - 进行多轮长时间对话（超过 30 轮）
   - 观察 Agent 是否自动压缩上下文（打印 "[上下文压缩]"）

✅ 跨平台（如接入了 Telegram）
   - 在 Telegram 上说 "你好"
   - Agent 记得在 CLI 中记录的信息
```

---

## 6.7 性能与成本优化

### 降低成本

- **使用本地模型**：接入 Ollama + Qwen2.5-7B，成本降至零
- **缓存 LLM 响应**：重复问题直接返回缓存结果
- **减少工具调用次数**：合并多个小操作为一个工具调用

### 提升性能

- **异步工具执行**：多个工具可以并行调用，不阻塞 Agent
- **流式输出**：用 SSE（Server-Sent Events）实时返回 Agent 输出
- **连接池**：复用 HTTP 连接，减少 API 调用延迟

---

## 6.8 后续方向

学完这六章，你已经完整理解了 Hermes Agent 的核心机制。

**可以继续探索的方向：**

| 方向 | 说明 |
|------|------|
| **接入更多平台** | Discord / 飞书 / Slack / WhatsApp |
| **接入本地模型** | Ollama / vLLM，接入 Qwen2.5-72B |
| **RLHF 微调** | 用轨迹数据训练自己的模型 |
| **MCP 协议** | 对接 Model Context Protocol 连接更多工具 |
| **多 Agent 协作** | 多个 Agent 分工协作（如一个分析、一个执行） |
| **量化部署** | 4-bit 量化后可以在 CPU 上跑大模型 |

---

## 恭喜你 🎉

学完这六章，你已经不只是"会用 Hermes"——你真正理解它为什么这样设计。

Hermes Agent 有 109K stars，大多数人用它只是用它的功能。
你学完这个教程，理解的是它的架构思路。

这就是造轮子和用轮子的区别。

**祝你在 Agent 开发之路上玩得开心，欢迎提交 PR！**
