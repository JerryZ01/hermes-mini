# 第六章 · 完整 Agent：整合所有模块

> 本章配套代码：`src/__main__.py` + `src/client.py`

---

## 本章目标

- 整合 Agent Loop + 记忆系统 + 工具系统 + Skill + Gateway
- 实现一条命令启动完整 Agent
- 部署到云端（可选，$5 VPS 即可）
- 测试完整对话流程，验证各模块协作

---

## 整合架构图

```
用户消息（Telegram / CLI / Web）
        ↓
   Gateway（router.py）—— 统一入口
        ↓
   会话管理（session.py）—— 加载用户上下文
        ↓
   Agent Loop（agent_loop.py）
        ├── 记忆注入（working.py + longterm.py + honcho.py）
        ├── Skill 匹配（loader.py）
        └── 工具调用（registry.py）
            ↓
         LLM 推理（GLM-5 / Qwen / Kimi / OpenAI）
            ↓
        响应 + 记忆更新 + Skill 自进化（generator.py）
        ↓
   Gateway —— 响应送回对应平台
```

---

## 一条命令跑起来

```bash
# 安装
pip install -e .

# 启动完整 Agent
hermes

# 启动 Telegram 网关（需要配置 BOT_TOKEN）
hermes gateway --platform telegram
```

---

## $5 VPS 部署指南

（以 DigitalOcean / 阿里云轻量为例）

1. 安装 Python 3.11+ 和 uv
2. 克隆项目：`git clone https://github.com/JerryZ01/hermes-mini`
3. 配置 API Key（GLM_API_KEY / QWEN_API_KEY）
4. 运行：`nohup hermes gateway --platform telegram &`
5. Agent 24 小时在线，随时响应

---

## 验收测试

完成部署后，测试以下场景：

- [ ] 在 Telegram 发消息，Agent 记得之前的对话
- [ ] 让 Agent 读一个文件，它正确返回内容
- [ ] 让 Agent 写一段代码，它写出可运行的代码
- [ ] 重复一个任务，Agent 调用了已有的 Skill（不再重新推理）
- [ ] 关闭后重新打开，Agent 仍然记得你的偏好

---

## 后续方向

Hermes-mini 只是一个起点。你可以在此基础上：

- 添加更多平台（Discord、Slack、飞书）
- 接入本地模型（Ollama / vLLM）降低成本
- 实现 RLHF 微调：用轨迹数据训练自己的模型
- 对接 MCP 协议，连接更多工具生态

---

## 恭喜你 🎉

学完这六章，你已经完整理解了 Hermes Agent 的核心机制。

这不只是"会用 Hermes"，而是真正理解它为什么这样设计——这就是造轮子和用轮子的区别。

**祝你玩得开心，欢迎提交 PR！**
