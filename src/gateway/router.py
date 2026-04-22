"""
多平台消息网关

设计思路（对应 docs/05-多平台Gateway.md）：
- GatewayRouter 是统一入口，接收不同平台的消息，统一格式后路由到 Agent
- 跨平台会话管理：同一用户在 Telegram / CLI / Web 中共享同一 Agent 上下文
- 支持扩展：新增平台只需实现对应的 Adapter
"""

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Message:
    """统一消息格式。"""
    user_id: str         # 跨平台唯一用户标识
    platform: str        # 来源平台："cli" | "telegram" | "web" | ...
    chat_id: str         # 平台内会话 ID
    text: str            # 消息内容
    timestamp: float     # 时间戳


@dataclass
class Session:
    """
    跨平台会话。
    一个 Session 对应一个 AgentLoop 实例，
    同一 user_id 在所有平台共享同一个 Session。
    """
    user_id: str
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    platform_last: dict = field(default_factory=dict)  # platform -> last_chat_id

    def touch(self, platform: str, chat_id: str):
        self.last_active = time.time()
        self.platform_last[platform] = chat_id


class PlatformAdapter(ABC):
    """平台适配器基类。各平台需实现 send() 方法。"""

    @abstractmethod
    def send(self, user_id: str, text: str):
        """发送消息给用户（平台相关实现）"""
        raise NotImplementedError


class CliAdapter(PlatformAdapter):
    """CLI 适配器：直接打印到终端。"""

    def __init__(self, session_manager: "SessionManager"):
        self.sm = session_manager

    def send(self, user_id: str, text: str):
        print(f"\n[Agent] {text}\n> ", end="")


class TelegramAdapter(PlatformAdapter):
    """Telegram 适配器。"""

    def __init__(
        self,
        bot_token: str,
        session_manager: "SessionManager",
    ):
        import requests
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.sm = session_manager

    def _call(self, method: str, params: dict = None) -> dict:
        import requests
        resp = requests.post(f"{self.base_url}/{method}", json=params or {}, timeout=10)
        return resp.json()

    def send(self, user_id: str, text: str):
        chat_id = self.sm.get_chat_id(user_id, "telegram") or user_id
        self._call("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})


class SessionManager:
    """
    跨平台会话管理器。
    核心逻辑：user_id 是跨平台唯一标识，同一用户在不同平台的会话共享同一 Agent 上下文。
    """

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            storage_path = str(Path.home() / ".hermes" / "sessions.json")
        self.storage_path = storage_path
        Path(storage_path).parent.mkdir(parents=True, exist_ok=True)
        self.sessions: dict[str, Session] = {}
        self._load()

    def _load(self):
        if Path(self.storage_path).exists():
            try:
                data = json.loads(Path(self.storage_path).read_text())
                for uid, sdata in data.items():
                    self.sessions[uid] = Session(
                        user_id=sdata["user_id"],
                        created_at=sdata["created_at"],
                        last_active=sdata["last_active"],
                        platform_last=sdata.get("platform_last", {}),
                    )
            except Exception:
                pass

    def _save(self):
        data = {
            uid: {
                "user_id": s.user_id,
                "created_at": s.created_at,
                "last_active": s.last_active,
                "platform_last": s.platform_last,
            }
            for uid, s in self.sessions.items()
        }
        Path(self.storage_path).write_text(json.dumps(data, ensure_ascii=False))

    def get_or_create(self, user_id: str) -> Session:
        if user_id not in self.sessions:
            self.sessions[user_id] = Session(user_id=user_id)
            self._save()
        return self.sessions[user_id]

    def get_chat_id(self, user_id: str, platform: str) -> Optional[str]:
        session = self.sessions.get(user_id)
        if session:
            return session.platform_last.get(platform)
        return None

    def touch(self, user_id: str, platform: str, chat_id: str):
        session = self.get_or_create(user_id)
        session.touch(platform, chat_id)
        self._save()


class GatewayRouter:
    """
    消息网关主路由。

    工作流程：
    1. 接收来自任意平台的消息（Message 格式）
    2. 根据 user_id 获取/创建 Session
    3. 把消息路由到对应的 Agent 实例
    4. 把 Agent 响应通过对应平台适配器发回

    平台扩展：在 __init__ 中注册对应的 PlatformAdapter
    """

    def __init__(
        self,
        agent_factory,
        session_manager: Optional[SessionManager] = None,
    ):
        """
        Args:
            agent_factory: callable(user_id) -> AgentLoop 实例
            session_manager: SessionManager 实例
        """
        self.agent_factory = agent_factory
        self.session_manager = session_manager or SessionManager()
        self.agents: dict[str, object] = {}  # user_id -> AgentLoop
        self.adapters: dict[str, PlatformAdapter] = {}

        # 注册默认 CLI 适配器
        self.register_adapter("cli", CliAdapter(self.session_manager))

    def register_adapter(self, platform: str, adapter: PlatformAdapter):
        """注册平台适配器。"""
        self.adapters[platform] = adapter

    def register_telegram(self, bot_token: str):
        """便捷方法：注册 Telegram 适配器。"""
        self.register_adapter("telegram", TelegramAdapter(bot_token, self.session_manager))

    def route(self, message: Message):
        """
        主路由方法：处理一条消息。

        流程：
        1. 记录会话活跃时间
        2. 获取/创建 Agent 实例
        3. 调用 Agent.chat()
        4. 通过平台适配器发送响应
        """
        # Step 1: 记录会话活跃
        self.session_manager.touch(
            message.user_id, message.platform, message.chat_id
        )

        # Step 2: 获取 Agent 实例（同用户共享）
        if message.user_id not in self.agents:
            self.agents[message.user_id] = self.agent_factory(message.user_id)

        agent = self.agents[message.user_id]

        # Step 3: 调用 Agent
        try:
            response = agent.chat(message.text)
        except Exception as e:
            response = f"[错误] Agent 处理失败: {e}"

        # Step 4: 发送响应
        adapter = self.adapters.get(message.platform)
        if adapter:
            adapter.send(message.user_id, response)
        else:
            print(f"[Gateway] 无适配器，跳过发送 (platform={message.platform})")
