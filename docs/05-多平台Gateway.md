# 第五章 · 多平台 Gateway：让 Agent 随时在线

> 本章配套代码：`src/gateway/`

---

## 本章目标

- 理解 Gateway 模式：统一消息路由 + 跨平台会话管理
- 实现 CLI 入口（`hermes` 命令行）
- 实现 Telegram Adapter（作为扩展示例）
- 实现多会话管理：不同平台的同一用户，同一个 Agent 上下文

---

## Gateway 是什么？

Gateway = 消息网关。它负责：
- 接收来自不同平台（Telegram / Discord / CLI / Web）的消息
- 统一格式后路由到 Agent Loop
- 把 Agent 的响应送回对应平台

```
Telegram ←→ Gateway ←→ Agent Loop ←→ Memory/Skills/Tools
Discord  ←↗
CLI      ←↗
Web      ←↗
```

这样做的好处：**Agent 核心逻辑只需写一份**，新增平台只需写一个 Adapter。

---

## 会话映射

每个用户在不同平台都是独立的 chat_id，但 Agent 需要把他们识别为"同一个人"。

方案：用 `user_id` 作为跨平台唯一标识，同一用户的 Telegram 和 CLI 共享同一会话上下文。

---

## 代码结构

```
src/gateway/
├── router.py        # 消息路由器（核心，统一分发）
├── adapters/
│   ├── cli.py       # 命令行适配器
│   └── telegram.py  # Telegram 适配器
├── session.py       # 跨平台会话管理
└── __init__.py
```

---

## CLI 入口

```bash
# 安装后一条命令跑起来
hermes              # 启动交互式 CLI
hermes --model glm  # 指定模型
hermes gateway      # 启动消息网关（后台运行）
```

---

## 练习题

1. 实现一个简单的 Web Adapter：用 Flask 接收 HTTP 请求，路由到 Agent
2. 实现"会话隔离"：同一用户在 Telegram 和 CLI 中开启的是同一个会话
3. 实现 Gateway 的优雅退出：Ctrl+C 时保存当前上下文，不丢数据

---

## 下一章预告

六章内容全部讲完了。**第六章**把 everything 整合在一起，一条命令跑起完整的 Hermes-mini Agent。
