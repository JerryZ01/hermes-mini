# 第四章 · 自进化 Skill：从"学会"到"记住"

> 本章配套代码：`src/skills/`

---

## 本章目标

- 理解 Hermes 的 Skill 自进化机制——为什么它是核心创新
- 实现 Skill 的自动生成：任务完成后，Agent 主动创建 Skill
- 实现 Skill 的复用：同类任务触发时，直接调用而非重新推理
- 实现 Skill 的持续优化：同一 Skill 被调用多次后，Agent 主动改进

---

## 4.1 为什么 Skill 自进化是关键创新？

**当前大多数 Agent 的通病：**

用户让 Agent "帮我写一篇博客"，Agent 每次都要重新思考：
1. 博客的结构是什么？——引入、核心观点、案例、结论
2. 应该用什么语气？——简洁有力
3. 如何开头？—— Hook（第一句决定读者去留）
4. 如何收尾？—— Call to Action

这些推理在每次任务中都是重复的。

**Skill 自进化解决的就是这个问题：**

```
任务完成
   ↓
【判断】这个任务值得创建 Skill 吗？
   ↓
【生成】Agent 提炼任务流程 → 生成 SKILL.md
   ↓
【存储】Skill 存入 ~/.hermes/skills/
   ↓
【复用】下次同类任务触发 → 直接调用 Skill（不再重新推理）
   ↓
【优化】Skill 被调用多次后，Agent 主动检测并改进
```

---

## 4.2 Skill 的生命周期

```
创建 → 存储 → 触发 → 执行 → 统计 → (优化) → 更新
```

**创建（Create）**
- 触发条件：用户说"以后都这样"、"记住了"、"以后帮我..."
- 或者：同类任务出现 2 次以上（重复检测）

**存储（Store）**
- 存储位置：`~/.hermes/skills/{skill_name}/SKILL.md`
- 附带使用统计：`usage.json`

**触发（Trigger）**
- 当新任务来临时，SkillLoader 扫描已有 Skills
- 匹配到相关 Skill → 直接调用
- 未匹配 → 正常 Agent Loop

**执行（Execute）**
- 读取 SKILL.md，按流程执行
- 不需要 LLM 重新规划

**统计（Track）**
- 记录调用次数、成功率
- 调用次数 ≥ N 时，触发优化

**优化（Improve）**
- Agent 主动分析 SKILL.md 的执行效果
- 如果发现流程可以更优，更新文件内容

---

## 4.3 SKILL.md 的格式设计

```markdown
# 博客写作

> 自动生成时间：2026-04-22 17:00
> 触发原因：用户要求以后按此方式处理

## 执行流程

### 输入
用户说：`帮我写一篇关于...的博客`

### 输出标准
1. 结构：Hook → 核心观点 → 案例 → 结论 → CTA
2. 字数：800-1200 字
3. 语气：简洁有力，避免废话

### 写作步骤
1. 确定主题和目标受众
2. 写一个吸引人的 Hook（第一句）
3. 展开核心观点（每个观点配一个例子）
4. 总结并给出行动建议

## 使用统计
```json
{"invocation_count": 0, "last_used": null}
```
```

**设计原则：**
- 格式足够简单，Agent 和人类都能读写
- 包含足够信息，让 Agent 不需要额外推理
- 使用统计外置（不污染核心内容）

---

## 4.4 Skill 生成器实现

```python
CREATE_TRIGGERS = [
    "以后都", "以后帮我", "每次", "记住了",
    "以后请", "按这个", "参照这个",
]

def should_create(self, user_input: str, assistant_output: str) -> bool:
    """判断是否值得创建 Skill"""
    text = user_input + assistant_output
    return any(trigger in text for trigger in self.CREATE_TRIGGERS)
```

这个实现很简单但有效。用户主动说"以后都..."，说明这个流程值得固化。

**进阶方向：LLM 判断**
真实系统会让 LLM 在每次任务完成后判断"这个任务是否有通用性，值得创建 Skill？"
成本更高，但准确性也更高。

---

## 4.5 Skill 匹配器实现

```python
def match(self, user_input: str) -> Optional[dict]:
    """判断用户输入是否匹配某个 Skill"""
    for skill_name, skill_info in self._cache.items():
        # 优先匹配 Skill 名称
        if skill_name.lower() in user_input.lower():
            self._increment_count(skill_info)
            return skill_info

        # 次级匹配：内容关键词
        if self._fuzzy_match(user_input, skill_info["content"]):
            self._increment_count(skill_info)
            return skill_info

    return None
```

匹配策略分层：
1. **名称精确匹配**："博客写作" in "帮我写博客"
2. **关键词模糊匹配**：技能内容中的词出现在用户输入中
3. **未匹配**：回退到正常 Agent Loop

---

## 4.6 自进化 vs. 模板系统

| 维度 | 自进化 Skill | 模板系统 |
|------|------------|---------|
| 创建方式 | Agent 自动生成 | 人工编写 |
| 更新方式 | 被调用后自动优化 | 手动更新 |
| 适用场景 | 动态、个性化流程 | 固定标准化流程 |
| 维护成本 | 低 | 高 |
| 精度 | 依赖 LLM 质量 | 依赖人工质量 |

**为什么 Hermes 选择自进化？**

因为 Agent 的工作场景是动态的——用户的需求会变化，流程不能写死。自进化让 Agent 可以适应用户的习惯，而不需要用户手动维护模板。

---

## 4.7 工程挑战

### 挑战 1：Skill 爆炸

如果每个任务都创建 Skill，目录会迅速膨胀到几百个。

解决：
- 相似 Skill 合并（名称相似或内容相似的合并）
- Skill 淘汰（长时间不用的自动归档）
- Skill 分组（按领域分类）

### 挑战 2：Skill 质量

自动生成的 SKILL.md 可能质量参差不齐。

解决：
- 调用次数超过阈值时，触发 LLM 审查并优化
- 保留原始版本，方便回滚

### 挑战 3：Skill 冲突

两个 Skill 的建议互相矛盾。

解决：
- 用 Honcho 的用户偏好作为最终裁决标准
- 保留多个版本，用户手动选择

---

## 代码结构

```
src/skills/
├── generator.py   # SkillGenerator：自动创建 SKILL.md
├── loader.py      # SkillLoader：匹配 + 加载已有 Skills
└── __init__.py
```

---

## 练习题

1. **实现 Skill 合并**：在 `loader.py` 中添加一个 `merge_similar_skills()` 函数，合并名称相似的 Skill

2. **实现 Skill 淘汰**：在 `generator.py` 中添加一个定期清理逻辑，超过 60 天未使用的 Skill 自动归档到 `archive/` 目录

3. **实现 Skill 版本管理**：在 `SKILL.md` 中增加版本号，Skill 更新时保留历史版本

4. **添加"Skill 使用效果评估"**：在 Skill 被调用后，询问用户是否满意，根据反馈调整后续生成策略

---

## 下一章预告

Agent 现在有了记忆、工具、自进化能力，但它只能在终端里用。

**第五章：多平台 Gateway**——让 Agent 跑在 Telegram、Discord 上，随时随地可以找到它。
