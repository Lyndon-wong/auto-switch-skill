---
name: auto-switch-skill
description: |
  智能模型自动切换 Skill。根据任务类型自动选择最优 LLM 模型。
  匹配以 /ms 或 /model-switch 开头的消息。
triggers:
  - pattern: "^/ms(\\s|$)"
  - pattern: "^/model-switch(\\s|$)"
---

# Auto-Switch-Skill

## 概述

Auto-Switch-Skill 是 OpenClaw 多智能体系统中的智能模型切换 Skill。
它通过模型自评估任务类型、查询路由矩阵、直接阈值判定来自动选择最优模型，
同时提供 `/ms` 命令让用户手动查看状态和切换模型。

## 触发条件

当用户消息以 `/ms` 或 `/model-switch` 开头时，本 Skill 被激活。

## System Prompt 注入

**以下内容需要注入到每条消息的 System Prompt 中：**

你是一个 AI 助手。在回答之前，请先在 thought/thinking 中分析任务类型，
并以精确格式输出标签：
[TASK_TYPE: <TYPE>]

其中 <TYPE> 必须是以下之一：
CHAT, QA, SUMMARIZE, TRANSLATE, CODE_SIMPLE, CODE_COMPLEX,
REASONING, ANALYSIS, CREATIVE, MULTI_STEP

任务类型说明：
- CHAT: 日常对话、闲聊、问候、简单问答
- QA: 知识问答、事实查询、概念解释
- SUMMARIZE: 文档摘要、会议纪要
- TRANSLATE: 多语言互译
- CODE_SIMPLE: 函数编写、Bug 修复、简单脚本
- CODE_COMPLEX: 架构设计、大规模重构、多文件协同
- REASONING: 逻辑推理、数学证明、因果分析
- ANALYSIS: 长文档分析、数据解读、报告生成
- CREATIVE: 文案创作、营销文本、方案设计
- MULTI_STEP: 工作流编排、复合任务、多步骤规划

然后正常回答用户的问题。

## 命令处理

当检测到 `/ms` 或 `/model-switch` 命令时，通过 shell 执行对应的 CLI 命令。

**路径变量**（根据安装位置替换）：
```
SKILL_DIR=~/.openclaw/skills/auto-switch-skill
CONFIG_DIR=$SKILL_DIR/config
```

### /ms 或 /ms help — 显示帮助

```bash
python3 $SKILL_DIR/scripts/ms_cli.py help
```

### /ms status — 显示运行状态

```bash
python3 $SKILL_DIR/scripts/ms_cli.py status \
  --config-dir $CONFIG_DIR \
  --current-model "$CURRENT_MODEL"
```

`$CURRENT_MODEL` 替换为当前会话使用的模型 ID（如 `sjtu/minimax-m2.5`）。

### /ms list — 列出可用模型

```bash
python3 $SKILL_DIR/scripts/ms_cli.py list \
  --config-dir $CONFIG_DIR \
  --current-model "$CURRENT_MODEL"
```

### /ms router — 查看路由表

```bash
python3 $SKILL_DIR/scripts/ms_cli.py router \
  --config-dir $CONFIG_DIR
```

### /ms <模型名> — 切换到指定模型

```bash
python3 $SKILL_DIR/scripts/ms_cli.py switch \
  --target "<模型别名或ID>" \
  --config-dir $CONFIG_DIR \
  --current-model "$CURRENT_MODEL"
```

输出最后一行为 `__JSON_RESULT__:` 开头的 JSON，包含切换结果：
```json
{"action": "switch", "success": true, "target_model": "sjtu/deepseek-v3.2"}
```

如果 `success` 为 `true`，调用 `session_status(model="目标模型ID")` 执行实际切换。

### /ms auto — 恢复自动模式

```bash
python3 $SKILL_DIR/scripts/ms_cli.py auto \
  --config-dir $CONFIG_DIR \
  --current-model "$CURRENT_MODEL"
```

### /ms manual — 切换到手动模式

```bash
python3 $SKILL_DIR/scripts/ms_cli.py manual \
  --config-dir $CONFIG_DIR \
  --current-model "$CURRENT_MODEL"
```

## 自动切换处理

当非 `/ms` 命令的普通消息到达时：

1. 获取模型返回中的 thought/thinking 字段文本。

2. 通过 shell 执行评估：
   ```bash
   python3 $SKILL_DIR/scripts/ms_cli.py evaluate \
     --thought "$THOUGHT_TEXT" \
     --config-dir $CONFIG_DIR \
     --current-model "$CURRENT_MODEL"
   ```

3. 输出为 JSON：
   ```json
   {"action": "switch", "success": true, "target_model": "...", "reason": "..."}
   ```
   或
   ```json
   {"action": "none", "success": false}
   ```

4. 如果 `action` 为 `"switch"` 且 `success` 为 `true`：
   - 调用 `session_status(model=target_model)` 执行实际切换
   - 在回复末尾追加通知：
     ```
     🔄 已自动切换模型: {前模型别名} → {新模型别名}（任务类型: {task_type}）
     ```

5. 如果 `action` 为 `"none"` 或 `success` 为 `false`：
   - 不做任何额外操作

## 安装说明

### 方式 1：使用预生成的路由矩阵（推荐）

路由矩阵 `config/routing_matrix.json` 已预生成，直接使用即可。

### 方式 2：重新生成路由矩阵

在**宿主机**上运行（需要 pyyaml）：

```bash
python3 $SKILL_DIR/scripts/generate_matrix.py \
    --openclaw-config /path/to/openclaw.json \
    --profiles $SKILL_DIR/config/model_profiles.yaml \
    --output $SKILL_DIR/config/routing_matrix.json
```

## 运行时依赖

- Python 3.10+（容器内自带）
- **无第三方库依赖**（仅使用标准库 json, re, argparse）
