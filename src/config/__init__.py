"""
配置管理
统一管理所有可配置项：API、模型、路径等
"""

import os
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Config:
    """Hermes-mini 全局配置。"""

    # LLM 配置
    provider: str = os.environ.get("HERMES_PROVIDER", "minimax")
    model: str = os.environ.get("HERMES_MODEL", "minimax")
    api_key: str = os.environ.get("HERMES_API_KEY", "")

    # 路径配置
    home_dir: Path = field(default_factory=lambda: Path.home() / ".hermes")
    skills_dir: Path = field(init=False)
    memory_db: Path = field(init=False)
    sessions_file: Path = field(init=False)

    def __post_init__(self):
        self.home_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir = self.home_dir / "skills"
        self.memory_db = self.home_dir / "memory.db"
        self.sessions_file = self.home_dir / "sessions.json"

    # MiniMax EAS 配置
    # 请在 .env 或环境变量 HERMES_MINIMAX_API_KEY 中配置
    minimax_base_url: str = os.environ.get(
        "HERMES_MINIMAX_BASE_URL",
        "http://1505824313958960.cn-hangzhou.pai-eas.aliyuncs.com"
        "/api/predict/minimax_m2/v1/chat/completions",
    )
    minimax_api_key: str = os.environ.get("HERMES_MINIMAX_API_KEY", "")


# 全局配置实例
config = Config()
