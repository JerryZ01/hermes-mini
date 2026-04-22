# 第四章 · 自进化 Skill：从"学会"到"记住"

> 本章配套代码：`src/skills/`

---

## 本章目标

- 理解 Hermes 的 Skill 自进化机制——为什么它是核心创新
- 实现 Skill 的自动生成：任务完成后，Agent 主动创建 Skill
- 实现 Skill 的复用：同类任务触发时，直接调用而非重新推理
- 实现 Skill 的持续优化：同一 Skill 被多次调用后，Agent 主动改进它

---

## 为什么 Skill 自进化是关键创新？

当前大多数 Agent 的问题是：**每次遇到任务，都要从零推理。**

用户让 Agent"帮我写一篇博客"，Agent 每次都要重新思考：
- 博客的结构是什么？
- 应该用什么语气？
- 如何开头，如何收尾？

Skill 自进化解决的就是这个问题：学会一次，下次同类任务直接调用，不再浪费 token 和时间。

---

## Skill 的生命周期

```
任务完成
   ↓
【判断】这个任务是否值得创建 Skill？
   ↓
【生成】Agent 提炼任务流程 → 生成 SKILL.md
   ↓
【存储】Skill 存入 ~/.hermes/skills/
   ↓
【复用】下次同类任务触发 → 直接调用 Skill
   ↓
【优化】Skill 被调用 N 次后，Agent 主动检测并改进
```

---

## Skill 文件结构

```
~/.hermes/skills/博客写作/
├── SKILL.md          # Skill 核心定义（名称、触发条件、执行步骤）
├── references/       # 参考资料
│   └── examples.md   # 示例
└── memory/
    └── usage.json    # 使用统计（调用次数、成功率、改进记录）
```

---

## SKILL.md 格式

```markdown
# 博客写作

## 触发条件
用户说："写一篇博客"、"写篇文章"、"发一篇帖子"

## 执行步骤
1. 确认主题和受众
2. 确定结构：引入 → 核心观点 → 案例 → 结论
3. 开头要有 Hook（第一句决定读者去留）
4. 语气：简洁有力，避免废话
5. 结尾要有 Call to Action

## 注意事项
- 中文为主，除非用户指定英文
- 每段不超过 4 行
- 配图位置用 [图片占位] 标注
```

---

## 代码结构

```
src/skills/
├── generator.py     # Skill 自动生成逻辑
├── loader.py        # Skill 加载与触发匹配
├── evaluator.py     # Skill 使用效果评估 + 优化触发
└── __init__.py
```

---

## 练习题

1. 实现一个简单的 Skill 生成器：根据对话历史自动提炼 SKILL.md
2. 实现 Skill 触发匹配：根据用户输入的关键词匹配已有 Skill
3. 实现"Skill 使用次数统计"：被调用超过 5 次的 Skill 在下次使用时打印"已优化 N 次"

---

## 下一章预告

Agent 现在有了记忆、工具、自进化能力，但它只能在终端里用。

**第五章：多平台 Gateway**——让 Agent 跑在 Telegram、Discord 上，随时随地可以找到它。
