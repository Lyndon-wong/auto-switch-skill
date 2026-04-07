# 重构模型切换流程：规范化输出协议

## 问题背景

当前 `/ms <模型名>` 的切换流程存在两个核心问题：

1. **模型需要做逻辑判断**：解析混合输出（文本 + `__JSON_RESULT__` JSON），判断 success 字段，决定是否调用 session_status
2. **输出格式不规范**：不同子命令输出格式不一致，模型的回复格式也不稳定

## 设计原则

> **模型做一件事，只调用一次工具脚本，逻辑判断全在脚本里，模型只负责知道何时该调用什么。**

> **脚本输出规范化**：具有清晰的定义、数据格式和键名称，使模型的回复格式稳定、可靠。覆盖异常情况下模型通过消息汇报异常的场景。

---

## CLI 输出协议（CLI Output Protocol）

### 核心规则

所有 `ms_cli.py` 子命令的输出统一为**单行 JSON**，遵循以下 schema：

```json
{
  "action": "<动作类型>",
  "status": "<执行状态>",
  "data": { ... },
  "message": "<面向用户的展示文本>"
}
```

### 字段定义

| 字段 | 类型 | 必填 | 说明 |
|:-----|:-----|:-----|:-----|
| `action` | string | ✅ | 模型应执行的动作，见下方动作类型表 |
| `status` | string | ✅ | `"ok"` 或 `"error"` |
| `data` | object | ✅ | 结构化数据，内容因 action 而异 |
| `message` | string | ✅ | 面向用户的展示文本，模型应直接展示给用户 |

### 动作类型（action）

| action 值 | 含义 | 模型行为 |
|:----------|:-----|:---------|
| `"switch"` | 需要执行模型切换 | 调用 `session_status(model=data.target_model)` |
| `"display"` | 纯展示信息 | 将 `message` 展示给用户，不做额外操作 |
| `"error"` | 操作失败/被拒绝 | 将 `message` 展示给用户，汇报异常原因 |

### 模型行为规则（写入 SKILL.md）

```
根据 action 字段执行：
- action="switch" 且 status="ok" → 调用 session_status(model=data.target_model)，并展示 message
- action="display"               → 展示 message
- action="error"                 → 展示 message，汇报异常
```

---

### 各场景的输出定义

#### 场景 1：切换成功

```json
{
  "action": "switch",
  "status": "ok",
  "data": {
    "target_model": "zuodachen/glm-5",
    "target_alias": "glm-5",
    "previous_model": "zuodachen/kimi-k2.5",
    "previous_alias": "kimi-k2-5",
    "context_window": 128000
  },
  "message": "✅ 模型切换就绪\n  来源: kimi-k2-5 (zuodachen/kimi-k2.5)\n  目标: glm-5 (zuodachen/glm-5)\n  上下文窗口: 128k"
}
```

#### 场景 2：模型不存在

```json
{
  "action": "error",
  "status": "error",
  "data": {
    "error_code": "MODEL_NOT_FOUND",
    "input": "xxx"
  },
  "message": "❌ 未找到模型 \"xxx\"。使用 /ms list 查看可用模型。"
}
```

#### 场景 3：上下文窗口不安全

```json
{
  "action": "error",
  "status": "error",
  "data": {
    "error_code": "CONTEXT_WINDOW_UNSAFE",
    "target_model": "zuodachen/glm-5",
    "target_alias": "glm-5",
    "context_window": 128000,
    "min_safe_window": 150000
  },
  "message": "⚠️ 拒绝切换到 glm-5 (zuodachen/glm-5)\n  原因: 上下文窗口 128k < 安全阈值 150k\n  系统提示+工具定义已占用约 ~30k tokens，切换过程还会额外消耗 ~90k tokens"
}
```

#### 场景 4：达到切换上限

```json
{
  "action": "error",
  "status": "error",
  "data": {
    "error_code": "SWITCH_LIMIT_REACHED",
    "switch_count": 30,
    "max_switches": 30
  },
  "message": "⚠️ 已达本会话切换上限 (30/30 次)，拒绝继续切换。"
}
```

#### 场景 5：脚本内部异常

```json
{
  "action": "error",
  "status": "error",
  "data": {
    "error_code": "INTERNAL_ERROR",
    "exception": "FileNotFoundError: routing_matrix.json"
  },
  "message": "❌ 内部错误: 无法加载配置文件 routing_matrix.json。请检查 config 目录。"
}
```

#### 场景 6：/ms list（纯展示）

```json
{
  "action": "display",
  "status": "ok",
  "data": {
    "model_count": 23,
    "current_model": "zuodachen/kimi-k2.5"
  },
  "message": "📦 可用模型列表\n\n  别名          模型全称                        上下文窗口   推理\n  ─────────────────────────────────────────────────────\n  ..."
}
```

#### 场景 7：/ms status（纯展示）

```json
{
  "action": "display",
  "status": "ok",
  "data": {
    "current_model": "zuodachen/kimi-k2.5",
    "current_alias": "kimi-k2-5",
    "mode": "auto",
    "cooldown_remaining": 0,
    "switch_count": 2,
    "max_switches": 30
  },
  "message": "📋 Auto-Switch-Skill 运行状态\n\n当前模型: kimi-k2-5 (zuodachen/kimi-k2.5)\n..."
}
```

#### 场景 8：/ms help（纯展示）

```json
{
  "action": "display",
  "status": "ok",
  "data": {},
  "message": "🔧 /ms 命令帮助 (MVP)\n\n模式与切换:\n  /ms auto  ..."
}
```

#### 场景 9：/ms auto, /ms manual（模式切换）

```json
{
  "action": "display",
  "status": "ok",
  "data": {
    "mode": "auto",
    "previous_mode": "manual"
  },
  "message": "✅ 已切换到自动模式\n   系统将根据任务类型自动选取最优模型。"
}
```

#### 场景 10：/ms evaluate（自动切换判定）

需要切换时：
```json
{
  "action": "switch",
  "status": "ok",
  "data": {
    "target_model": "sjtu/deepseek-v3.2",
    "target_alias": "deepseek-v3-2",
    "previous_model": "zuodachen/kimi-k2.5",
    "previous_alias": "kimi-k2-5",
    "task_type": "CODE_COMPLEX",
    "reason": "任务类型切换: CODE_COMPLEX"
  },
  "message": "🔄 自动切换: kimi-k2-5 → deepseek-v3-2（任务类型: CODE_COMPLEX）"
}
```

不需要切换时：
```json
{
  "action": "display",
  "status": "ok",
  "data": {
    "decision": "no_switch"
  },
  "message": ""
}
```

---

## 修改方案

### 核心组件

#### [MODIFY] [__init__.py](file:///home/b220/share2/user/wld/project/auto-switch-skill/src/core/__init__.py)

新增常量：

```python
MIN_SAFE_CONTEXT_WINDOW = 150000  # 上下文窗口安全阈值（150k tokens）
```

---

#### [MODIFY] [ms_command.py](file:///home/b220/share2/user/wld/project/auto-switch-skill/src/skills/ms_command.py)

**整体改动**：所有 `cmd_*()` 方法的返回值从 `str` 改为 `dict`，统一输出规范化的字典结构。

核心改动点：

1. **`cmd_switch()`**：整合别名解析 + 上下文窗口检查 + 切换上限检查 + 切换执行，返回规范字典
2. **`cmd_status()`**：返回结构化 data + message
3. **`cmd_list()`**：返回结构化 data + message
4. **`cmd_help()`**：返回 display 类型字典
5. **`cmd_auto()` / `cmd_manual()`**：返回 display 类型字典
6. **新增 `cmd_evaluate()`**：将 evaluate 逻辑从 ms_cli.py 移入 handler，保持"一个入口"

> [!IMPORTANT]
> 关键变化：`cmd_switch()` 中的安全检查顺序为：
> 1. 别名解析（模型是否存在）
> 2. 上下文窗口安全检查
> 3. 切换上限检查
> 4. 执行切换
>
> 全部通过 → `action="switch"`，任一失败 → `action="error"`

---

#### [MODIFY] [ms_cli.py](file:///home/b220/share2/user/wld/project/auto-switch-skill/scripts/ms_cli.py)

**整体改动**：每个 `cmd_*()` 函数不再直接 `print(handler.xxx())`，而是统一通过 `output_json()` 输出：

```python
import json

def output_json(result: dict) -> None:
    """统一输出单行 JSON"""
    print(json.dumps(result, ensure_ascii=False))

def cmd_switch(args):
    handler, _, _, _ = build_components(args)
    output_json(handler.cmd_switch(args.target))

def cmd_status(args):
    handler, _, _, _ = build_components(args)
    output_json(handler.cmd_status())
```

**新增全局异常捕获**：在 `main()` 中添加 try-except，确保即使脚本崩溃也输出规范 JSON：

```python
def main():
    try:
        # ... 原有逻辑 ...
        args.func(args)
    except Exception as e:
        output_json({
            "action": "error",
            "status": "error",
            "data": {
                "error_code": "INTERNAL_ERROR",
                "exception": f"{type(e).__name__}: {e}"
            },
            "message": f"❌ 内部错误: {e}"
        })
        sys.exit(1)
```

---

### SKILL.md 层

#### [MODIFY] [SKILL.md](file:///home/b220/share2/user/wld/project/auto-switch-skill/SKILL.md)

重写命令处理部分，定义清晰的输出协议和模型行为规则：

```markdown
## 命令处理

所有 /ms 子命令通过 shell 执行 CLI 脚本。
脚本输出为**单行 JSON**，格式统一：

```json
{"action": "...", "status": "...", "data": {...}, "message": "..."}
```

### 输出处理规则

根据 JSON 中的 action 字段决定操作：

| action 值  | 模型行为 |
|:-----------|:---------|
| `switch`   | 调用 `session_status(model=data.target_model)` 执行切换，并展示 message |
| `display`  | 将 message 展示给用户 |
| `error`    | 将 message 展示给用户，汇报异常 |

### /ms <模型名> — 切换到指定模型

（bash 命令不变）

脚本内置别名解析和安全检查（上下文窗口、切换上限），
action 为 switch 时调用 session_status，否则展示 message。

### /ms status / list / help / auto / manual / router

（bash 命令不变）

这些命令的 action 均为 display，直接展示 message。
```

---

### 测试层

#### [MODIFY] [test_ms_command.py](file:///home/b220/share2/user/wld/project/auto-switch-skill/tests/test_ms_command.py)

更新所有测试：

1. 所有 `cmd_*()` 断言改为检查返回字典的 `action`、`status`、`data`、`message` 字段
2. **新增**：上下文窗口不安全的测试 → 断言 `data.error_code == "CONTEXT_WINDOW_UNSAFE"`
3. **新增**：切换上限测试 → 断言 `data.error_code == "SWITCH_LIMIT_REACHED"`
4. **新增**：模型不存在测试 → 断言 `data.error_code == "MODEL_NOT_FOUND"`

#### [MODIFY] [test_integration.py](file:///home/b220/share2/user/wld/project/auto-switch-skill/tests/test_integration.py)

更新集成测试中与输出格式相关的断言。

---

## 变更总结

| 维度 | 改动前 | 改动后 |
|:-----|:------|:------|
| 输出格式 | 混合文本 + `__JSON_RESULT__` 尾部 JSON | 统一单行 JSON |
| 输出 schema | 无规范，各命令各异 | 统一 `{action, status, data, message}` |
| 模型逻辑判断 | 解析 JSON、判断 success、提取字段 | 只看 `action` 字段决定行为 |
| 安全检查 | 无 | 上下文窗口检查 + 切换上限检查 |
| 异常覆盖 | 脚本崩溃时输出 Python traceback | 全局 try-except → 输出规范 error JSON |
| SKILL.md 行为定义 | 分散在各命令段落，含 JSON 解析说明 | 统一规则表：action → 行为 |

---

## 开放问题

> [!IMPORTANT]
> **上下文窗口阈值 `MIN_SAFE_CONTEXT_WINDOW = 150000` 是否合适？**
> 根据上下文分析报告，系统提示+工具定义约 30k，切换流程约 90k，总计 ~120k。150k 留了 ~30k 余量。
> 如果你觉得 128k 的模型完全不应被使用（而不只是切换时拒绝），可以考虑在 `routing_matrix.json` 生成阶段就排除这些模型。

> [!IMPORTANT]
> **`/ms evaluate` 的输出也走该协议是否可行？**
> 当前 evaluate 由 ms_cli.py 直接输出 JSON。按本方案会统一到 handler 层，输出格式与 switch 一致。
> 这意味着自动切换和手动切换的输出协议完全统一，SKILL.md 中的行为规则也完全相同。

---

## 验证计划

### 自动化测试

```bash
cd /home/b220/share2/user/wld/project/auto-switch-skill
python3 -m pytest tests/ -v
```

### 手动验证

1. 各子命令输出是否为合法单行 JSON
2. 切换到 128k 模型（如 `glm-5`）时是否被安全检查拒绝
3. 切换到不存在模型时的 error 输出
4. 脚本故意报错（如删除配置文件）时是否输出规范 error JSON
