# 第五章 · 多平台 Gateway：让 Agent 随时在线

> 本章配套代码：`src/gateway/`

---

## 本章目标

- 理解 Gateway 模式：统一消息路由 + 跨平台会话管理
- 实现 CLI 入口（`hermes` 命令行）
- 实现 Telegram Adapter（扩展示例）
- 实现多会话管理：不同平台的同一用户，同一个 Agent 上下文

---

## 5.1 Gateway 是什么？

Gateway = 消息网关。它负责：
- 接收来自不同平台（Telegram / Discord / CLI / Web）的消息
- 统一格式后路由到 Agent Loop
- 把 Agent 的响应送回对应平台

```
Telegram ──┐
Discord  ──┼──▶ [Gateway Router] ──▶ [Agent Loop] ──▶ Memory/Skills/Tools
CLI      ──┤                │
Web      ──┘                │
                              └──▶ [Telegram/Discord/CLI/Web]
```

**核心价值：**
- Agent 核心逻辑只需写一份
- 新增平台只需写一个 Adapter（适配器）
- 用户在任意平台都能找到同一个 Agent

---

## 5.2 适配器模式（Adapter Pattern）

Gateway 的核心设计思想：适配器模式。

```python
class PlatformAdapter(ABC):
    """平台适配器基类"""
    @abstractmethod
    def send(self, user_id: str, text: str):
        raise NotImplementedError
```

每新增一个平台，只需要：
1. 继承 `PlatformAdapter`
2. 实现 `send()` 方法
3. 注册到 Gateway

不需要修改任何 Agent 核心代码。

**Telegram 适配器示例：**

```python
class TelegramAdapter(PlatformAdapter):
    def __init__(self, bot_token: str, session_manager):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send(self, user_id: str, text: str):
        requests.post(
            f"{self.base_url}/sendMessage",
            json={"chat_id": user_id, "text": text, "parse_mode": "Markdown"},
        )
```

**这就是适配器模式的力量**：Telegram 的 API 格式完全不同于 CLI，但封装之后，对 Gateway 来说它们没有任何区别。

---

## 5.3 跨平台会话管理

这是最容易被忽略但最重要的部分。

**问题：**
- 用户在 Telegram 上和 Agent 说"我叫杰哥"
- 用户在 CLI 上问"我是谁？"
- Agent 应该记得"杰哥"这个名字

**解决：SessionManager**

```python
class SessionManager:
    """跨平台会话管理器"""
    def __init__(self):
        self.sessions: dict[str, Session] = {}  # user_id → Session

    def get_or_create(self, user_id: str) -> Session:
        if user_id not in self.sessions:
            self.sessions[user_id] = Session(user_id=user_id)
        return self.sessions[user_id]

    def touch(self, user_id: str, platform: str, chat_id: str):
        session = self.get_or_create(user_id)
        session.touch(platform, chat_id)  # 记录该用户在某平台最近一次对话的 chat_id
        self._save()
```

`user_id` 是跨平台唯一标识：同一用户在 Telegram / CLI / Web 中使用同一个 user_id，共享同一个 Session（共享同一个 AgentLoop 实例和记忆上下文）。

---

## 5.4 统一消息格式（Message）

```python
@dataclass
class Message:
    user_id: str     # 跨平台唯一用户标识
    platform: str    # 来源平台："cli" | "telegram" | "web"
    chat_id: str     # 平台内会话 ID
    text: str        # 消息内容
    timestamp: float # 时间戳
```

所有平台的消息都转换成这个统一格式后进入 Gateway。
无论消息来自 Telegram Bot、Discord Bot 还是 HTTP POST，Agent 看到的数据格式完全一样。

---

## 5.5 Gateway 路由主循环

```python
class GatewayRouter:
    def __init__(self, agent_factory, session_manager):
        self.agent_factory = agent_factory
        self.session_manager = session_manager
        self.agents: dict[str, AgentLoop] = {}
        self.adapters: dict[str, PlatformAdapter] = {}

    def route(self, message: Message):
        # 1. 记录会话活跃
        self.session_manager.touch(message.user_id, message.platform, message.chat_id)

        # 2. 获取/创建 Agent（同用户共享）
        if message.user_id not in self.agents:
            self.agents[message.user_id] = self.agent_factory(message.user_id)

        agent = self.agents[message.user_id]

        # 3. 调用 Agent
        try:
            response = agent.chat(message.text)
        except Exception as e:
            response = f"[错误] Agent 处理失败: {e}"

        # 4. 发送响应
        adapter = self.adapters.get(message.platform)
        if adapter:
            adapter.send(message.user_id, response)
```

**注意第 2 步**：同一个 `user_id` 只创建一个 `AgentLoop` 实例。
这保证了：
- 用户在 Telegram 的对话上下文，会影响 CLI 中的 Agent 行为
- 记忆系统跨平台共享
- Skill 在不同平台都可调用

---

## 5.6 CLI 入口实现

Hermes-mini 的 CLI 是最直接的 Gateway 应用：

```python
# 用户输入 → CLI Adapter → Gateway → Agent
# Agent 响应 → CLI Adapter → 打印到终端
```

启动流程：
```bash
hermes              # 启动交互式 CLI
hermes gateway      # 启动后台网关（接受来自 Telegram 等的消息）
```

CLI 适配器直接打印到 stdout：

```python
class CliAdapter(PlatformAdapter):
    def send(self, user_id: str, text: str):
        print(f"\n[Agent] {text}\n> ", end="")
```

---

## 5.7 Telegram Bot 接入（实战步骤）

如果你想把 Hermes-mini 接到 Telegram：

**Step 1：创建 Bot**
- 在 Telegram 搜索 `@BotFather`
- 发送 `/newbot`，按提示创建
- 获取 Bot Token（格式：`123456789:ABCdef...`）

**Step 2：配置 Webhook 或长轮询**

方案 A - Webhook（推荐生产环境）：
```bash
# 让 Telegram 把消息推送到你的服务器
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://your-domain.com/webhook"
```

方案 B - 长轮询（适合本地开发）：
```python
class TelegramLongPolling:
    def start(self, token):
        offset = 0
        while True:
            updates = requests.get(f"{BASE}/getUpdates", params={"offset": offset}).json()
            for update in updates.get("result", []):
                # 提取 message，转发给 Gateway
                msg = Message(
                    user_id=str(update["message"]["from"]["id"]),
                    platform="telegram",
                    chat_id=str(update["message"]["chat"]["id"]),
                    text=update["message"]["text"],
                    timestamp=update["message"]["date"],
                )
                gateway.route(msg)
                offset = update["update_id"] + 1
```

**Step 3：注册适配器**
```python
gateway = GatewayRouter(agent_factory=make_agent)
gateway.register_telegram(bot_token="你的Token")
```

---

## 5.8 安全设计：谁可以访问？

Gateway 暴露在公网上，必须考虑安全：

```python
ALLOWED_USERS = {"telegram_id_1", "telegram_id_2"}

def route(self, message: Message):
    # 验证用户身份
    if message.platform == "telegram":
        if message.user_id not in ALLOWED_USERS:
            adapter = self.adapters.get("telegram")
            adapter.send(message.user_id, "你没有访问权限。")
            return
```

真实系统还需要：
- 命令白名单（哪些命令可以执行，哪些不能）
- 沙箱隔离（危险命令需要二次确认）
- 速率限制（防止滥用）

---

## 代码结构

```
src/gateway/
├── router.py   # GatewayRouter + SessionManager + PlatformAdapter + Message
└── __init__.py
```

---

## 练习题

1. **实现 Web Adapter**：用 Flask 实现一个简单的 Web 接收端，把 HTTP POST 消息转发给 Gateway

2. **实现命令白名单**：在 `gateway/router.py` 中添加一个命令白名单配置，只有白名单内的命令才会被执行

3. **实现会话持久化**：把 `agents` 字典序列化到磁盘，Gateway 重启后恢复已有 Agent 实例（而不是每个用户都创建新的）

4. **实现多租户隔离**：修改 SessionManager，支持多用户隔离，同一平台不同用户不共享 Agent 实例

---

## 下一章预告

六章内容全部讲完了。**第六章**把 everything 整合在一起，一条命令跑起完整的 Hermes-mini Agent。
