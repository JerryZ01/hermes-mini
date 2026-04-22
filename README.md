# Hermes-mini

> 用 2000 行代码，拆解 Hermes Agent 的核心机制。
> 每章配有可运行的代码 + 深度解析，带你从零构建一个真正能"记住你、学会新技能"的 AI Agent。

[English](./README-en.md) | **中文**

---

## 核心定位

**Hermes Agent 有 109K stars，但真正用起来的人不到 1%。**

原因是它默认你已经是 Agent 老手——上手门槛高、概念跨度大、新人很难找到"从哪开始"。

Hermes-mini 是它的**中文教学版**：不依赖重型框架，用最少的代码实现 Hermes 最有价值的功能，每一步都有解释。

---

## 目标读者

- 想深入理解 Agent 架构的前端/后端开发者
- 想从"用 AI 工具"进阶到"造 AI 工具"的工程师
- 对 Agent 开发感兴趣，但被 LangChain/官方文档劝退的同学

**前置要求：** 会 Python，了解 LLM API 调用（OpenAI / GLM / Qwen 风格均可）

---

## 学习路径（6 章）

| 章节 | 内容 | 代码量 |
|------|------|--------|
| [01 · Agent Loop](docs/01-Agent-Loop核心原理.md) | 感知→推理→行动的核心循环，理解"Agent 不是什么" | ~200 行 |
| [02 · 记忆系统](docs/02-记忆系统设计.md) | Working Memory + FTS5 长期记忆 + Honcho 用户画像 | ~300 行 |
| [03 · 工具系统](docs/03-工具系统设计.md) | 工具注册、调用、结果注入的完整链路 | ~200 行 |
| [04 · 自进化 Skill](docs/04-自进化Skill机制.md) | 任务完成后自动创建 Skill，下次同类任务直接调用 | ~300 行 |
| [05 · 多平台 Gateway](docs/05-多平台Gateway.md) | CLI + Telegram + 消息路由与统一会话管理 | ~400 行 |
| [06 · 完整 Agent 上线](docs/06-完整Agent上线.md) | 整合所有模块，一个命令跑起来 | ~600 行 |

**总计：~2000 行 Python，无重型依赖。**

---

## 快速开始

```bash
# 克隆项目
git clone https://github.com/JerryZ01/hermes-mini.git
cd hermes-mini

# 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 HERMES_MINIMAX_API_KEY

# 创建虚拟环境（可选）
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动完整 Agent
python -m src
```

**默认使用 MiniMax M2（EAS）。** 切换模型只需修改 `HERMES_PROVIDER` 环境变量。

---

## 与原版 Hermes Agent 的区别

| | Hermes Agent（官方） | Hermes-mini（教学版） |
|--|--|--|
| 代码量 | ~100,000+ 行 | ~2,000 行 |
| 依赖 | uv + 多级 extras | 标准库 + requests |
| 用途 | 生产级 Agent 平台 | 学习 + 理解核心机制 |
| 侧重点 | 功能完整 + 多平台 | 原理解透 + 可修改 |
| 文档 | 英文为主 | 中文详解 + 逐行注释 |

---

## 项目结构

```
hermes-mini/
├── src/
│   ├── core/          # Agent Loop（第一章）
│   ├── memory/        # 记忆系统（第二章）
│   ├── tools/         # 工具系统（第三章）
│   ├── skills/        # 自进化 Skill（第四章）
│   ├── gateway/       # 多平台网关（第五章）
│   └── config/        # 配置管理
├── docs/              # 教程文档（每章配对应 .md）
├── tests/             # 单元测试
├── assets/            # 架构图等资源
└── requirements.txt
```

---

## 配套视频（待上线）

每个章节配有中文讲解视频（B站），关注 [JerryZ01](https://github.com/JerryZ01) 获取更新通知。

---

## License

MIT · 欢迎 Star · 欢迎 PR

> 项目思路参考 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)，侵删。
