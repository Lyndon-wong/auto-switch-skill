# Auto-Switch-Skill v0.2 测试版需求文档

> **版本**：v0.2-beta
> **日期**：2026-04-08
> **基线**：基于 MVP v1.0 升级
> **状态**：草案

---

## 0. 设计原则

> [!IMPORTANT]
> 以下两条设计原则贯穿 v0.2 所有功能的设计与实现，是本版本最核心的架构约束。

### 原则一：模型做执行者，脚本做决策者

> **模型做一件事，只调用一次工具脚本，逻辑判断全在脚本里，模型只负责知道何时该调用什么。**

- 所有切换判定逻辑（别名解析、安全检查、势能累积、惯性判断等）封装在 Python 脚本中
- 模型不做 JSON 解析、不做条件分支判断，只根据脚本输出的 `action` 字段执行对应行为
- 这确保了即使更换底层模型，切换行为也完全一致、可预测

### 原则二：脚本输出规范化

> **脚本输出具有清晰的定义、数据格式和键名称，使模型的回复格式稳定、可靠。覆盖异常情况下模型通过消息汇报异常的场景。**

- 所有命令输出统一为 `{action, status, data, message}` 四字段 JSON
- 正常流程和异常流程共用同一输出 schema，消除不确定性
- 全局 try-except 兜底，确保即使脚本崩溃也输出合法 JSON

---

## 1. 版本概述

### 1.1 版本目标

v0.2 版本在 MVP 基础上进行三大方向的升级：

1. **切换决策机制升级**：从 MVP 的「直接阈值判定」升级为「阻尼式势能累积 + 上下文惯性」，显著减少误切换和频繁切换问题
2. **上下文压缩机制**：解决模型切换过程中的 token 膨胀问题（切换中间消息残留），通过指令引导压缩冗余上下文
3. **用户控制能力增强**：新增 4 个 `/ms` 命令，覆盖路由管理、调试监控、统计分析等场景，使用户从「只能看」升级为「能看、能改、能调试」

### 1.2 与 MVP 的功能对比表

| 功能域 | MVP v1.0 | v0.2 新增/升级 |
| :--- | :--- | :--- |
| **切换判定** | 直接阈值（权重差 > 15 立即切换） | ✨ 阻尼式势能累积（升级~2轮、降级~4轮触发） |
| **防误切换** | 无 | ✨ 上下文惯性（连贯对话阈值×1.5） |
| **路由管理** | 仅 `/ms router` 查看 | ✨ 新增 `/ms set` 修改 + `/ms reset` 重置 |
| **调试模式** | 无 | ✨ `/ms debug` + 回答末尾调试脚注（含上下文压缩信息） |
| **统计分析** | 无 | ✨ `/ms stats` 基础版（次数、占比） |
| **切换日志** | 无 | ✨ 结构化日志记录 |
| **输出协议** | 混合文本 + 尾部 JSON | ✨ 统一单行 JSON 协议（`{action, status, data, message}`） |
| **安全检查** | 无 | ✨ 上下文窗口安全检查（切换前校验目标模型窗口是否足够） |
| **上下文压缩** | 无（切换残留消息导致 token 膨胀） | ✨ 切换后自动压缩中间消息，减少 token 浪费 |
| **异常处理** | 脚本崩溃输出 Python traceback | ✨ 全局 try-except → 规范 error JSON |
| `/ms` 命令数 | 7 个 | **11 个**（+4） |

### 1.3 版本范围

#### v0.2 包含的功能

| 编号 | 功能 | 优先级 | 预估工时 |
| :--- | :--- | :--- | :--- |
| F1 | 切换势能累积机制（阻尼系统） | P0 | 1-1.5 天 |
| F2 | 上下文惯性 | P0 | 0.5-1 天 |
| F3 | `/ms set` + `/ms reset` | P0 | 0.5 天 |
| F4 | `/ms debug` + 调试脚注 | P1 | 0.5-1 天 |
| F7 | 切换日志记录 | P1 | 0.5 天 |
| F8 | `/ms stats` 基础版 | P2 | 0.5 天 |
| F9 | CLI 输出协议规范化（统一 JSON 输出） | P0 | 0.5-1 天 |
| F10 | 上下文窗口安全检查 | P0 | 0.5 天 |
| F11 | 切换上下文压缩机制 | P0 | 1-1.5 天 |

> **合计预估**：6-8 天

#### v0.2 明确不包含的功能（推迟至 v0.3+）

| 功能 | 推迟原因 |
| :--- | :--- |
| 三层记忆栈（L1/L2/L3） | 工作量大（5-7天），需独立迭代 |
| 智能提取管道（4步流程） | 依赖三层记忆栈 |
| 切换重组编排器 | 依赖三层记忆栈 |
| 增量摘要 DAG 引擎 | 依赖三层记忆栈的 L2 层 |
| `/ms memory`、`/ms pin` | 依赖三层记忆栈 |
| `/ms export`、`/ms import` | 优先级较低 |
| `/ms cooldown`、`/ms threshold` | v0.2 参数通过 settings.yaml 配置即可，暂不需要命令行调整 |
| `/ms history` | 优先级较低，debug 模式已可观测切换行为 |
| 多 Agent 协同切换 | 需独立设计，工作量 1 周+ |

---

## 2. [F1] 新增功能：切换势能累积机制

### 2.1 需求描述

**MVP 现状**：直接阈值判定——权重差 > 15 时立即切换。这种方式过于敏感，例如用户在复杂编程过程中偶尔发一句「好的」（被识别为 CHAT 任务），虽然权重差可能超过 15，但立即切换会中断工作流。

**v0.2 升级**：引入「切换势能」概念，模拟物理阻尼效果。**不是一次命中就切换，而是持续累积势能，只有越过阈值才真正触发切换**。这样可以有效过滤偶发的任务类型波动。

### 2.2 势能更新规则

每轮对话执行一次评估后，按以下规则更新势能值：

```
if 推荐模型 ≠ 当前模型 且 权重差绝对值 > weight_diff_threshold (15):
    势能 += 方向增量（升级增量 或 降级增量）
elif 推荐模型 == 当前模型 或 权重差绝对值 ≤ weight_diff_threshold:
    势能 = max(势能 - 衰减值, 0)

if 势能 >= 方向阈值:
    → 触发切换，势能归零
```

### 2.3 方向不对称阈值

升级和降级采用不同的参数——**升级敏感，降级保守**：

| 切换方向 | 阈值 | 每轮增量 | 衰减值 | 约需连续轮数 | 设计原因 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **升级**（推荐权重 > 当前） | 50 | +40 | 30 | ~2 轮 | 能力不足直接影响输出质量，需快速响应 |
| **降级**（推荐权重 < 当前） | 80 | +20 | 30 | ~4-5 轮 | 大模型处理小任务不出错，只是浪费成本，不紧急 |

> ⚠️ 以上参数沿用总体需求 `requirements.md` §2.2.3 的默认值，可通过 `settings.yaml` 调整。

### 2.4 完整决策流程图（v0.2 版）

相比 MVP 的决策流程，v0.2 新增了势能累积和上下文惯性两个环节：

```
用户消息进入
    │
    ▼
[冷却期检查] ← 上次切换后是否已过冷却轮数？（v0.2: 可配置）
    │
    ├── 冷却中 → 跳过评估，使用当前模型
    │
    └── 已过冷却期
         │
         ▼
    [模式检查] ← 是否处于自动模式？
         │
         ├── 手动模式 → 跳过评估
         │
         └── 自动模式
              │
              ▼
         [模型自评估] → 解析 thought 字段，提取任务类型标签
              │
              ├── 解析失败 → 势能衰减，不切换
              │
              └── 成功获取任务类型
                   │
                   ▼
              [适配度矩阵查询] → 推荐模型 + 权重差
                   │
                   ▼
              权重差绝对值 > weight_diff_threshold (15)？
                   │
                   ├── 否 → 势能衰减（势能 = max(势能 - 30, 0)），不切换
                   │
                   └── 是 → 判断切换方向（升级/降级）
                             │
                             ▼
                        势能 += 方向增量（升级 +40 / 降级 +20）
                             │
                             ▼
                        [上下文惯性检查]  ← 🆕 v0.2 新增
                             │
                             ├── 惯性高 → 阈值 ×1.5（更难触发）
                             └── 惯性低 → 使用原始阈值
                                  │
                                  ▼
                            势能 >= 最终阈值？
                                  │
                                  ├── 否 → 不切换，势能保留至下一轮
                                  │
                                  └── 是 → [切换次数检查]
                                              │
                                              ├── 已达上限 → 不切换
                                              └── 未达上限 → ✅ 执行切换
                                                               势能归零
                                                               冷却计时开始
                                                               写入切换日志
```

### 2.5 效果举例

假设当前可用模型为 MVP 环境中的 5 个模型，用户当前使用 **MiniMax M2.5 (mm)**（CODE_COMPLEX 权重 85）：

| 轮次 | 用户消息 | 类型判断 | 推荐模型(权重) | 当前模型(权重) | 差值 | 势能变化 | 势能值 | 切换？ |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | "帮我重构这个模块" | CODE_COMPLEX | mm(85) | mm(85) | 0 | 衰减 -30 | 0 | ❌ |
| 2 | "好的，谢谢" | CHAT | ds-v3(80) | mm(72) | +8 | 衰减 -30 | 0 | ❌ 差值<15 |
| 3 | "这段代码逻辑对不对" | REASONING | mm(72) | mm(72) | 0 | 衰减 -30 | 0 | ❌ |
| 4 | "写个简单函数" | CODE_SIMPLE | ds-v3(88) | mm(82) | +6 | 衰减 -30 | 0 | ❌ 差值<15 |
| 5 | "帮我整理会议记录" | SUMMARIZE | ds-v3(78) | mm(78) | 0 | 衰减 -30 | 0 | ❌ |

> 💡 **观察**：由于可用模型之间权重差异不大（最大差距约 6-8），大多数切换不会被触发。势能累积机制进一步确保了只有持续出现显著权重差的场景才会切换——这正是预期效果。

---

## 3. [F2] 新增功能：上下文惯性

### 3.1 需求描述

**问题场景**：用户在进行连贯的多轮复杂编程任务时，偶尔插入简单消息（如「好的」「谢谢」「明白了」），这些消息会被识别为 CHAT 类型。若无惯性机制，势能可能因短暂的任务类型变化而累积，导致不必要的切换。

**解决方案**：引入上下文惯性机制。当检测到当前处于连贯的多轮任务中时，提高切换阈值（×1.5 倍），使切换更难触发。

### 3.2 惯性生效条件

当同时满足以下条件时，判定为「惯性活跃」：

- 最近 N 轮（默认 N=3）属于同一主题/任务的连续对话
- 未出现明确的话题转换信号
- 距离上次消息未超过 30 分钟

**惯性效果**：切换阈值乘以 **×1.5 放大倍数**

| 切换方向 | 原始阈值 | 惯性活跃时的阈值 | 影响 |
| :--- | :--- | :--- | :--- |
| 升级 | 50 | 75 | 约需 ~3 轮连续信号 |
| 降级 | 80 | 120 | 约需 ~7 轮连续信号 |

### 3.3 话题转换信号

以下信号触发惯性重置（惯性失效，恢复原始阈值）：

| 信号类型 | 示例 |
| :--- | :--- |
| 转折语句 | 「新的需求」「另一个问题」「换个话题」「接下来」 |
| 任务完成信号 | 「搞定了」「可以了」「没问题了」 |
| 超时 | 两轮消息间隔超过 30 分钟 |

> 话题转换关键词暂时使用总体需求中定义的列表，不做扩展。

### 3.4 与势能机制的交互

上下文惯性不改变势能的累积速度，只改变触发阈值：

```
最终阈值 = 基础阈值 × (1.5 if 惯性活跃 else 1.0)

势能累积速度不变：升级 +40/轮，降级 +20/轮
衰减速度不变：-30/轮
```

这意味着：
- 惯性只延迟切换的触发时机，不阻止势能的正常累积
- 一旦惯性因话题转换而重置，已累积的势能可能立即越过新阈值，触发切换

---

## 4. [F11] 新增功能：切换上下文压缩机制

### 4.1 问题背景

根据实际测试（详见 `context_switch_analysis.md`），模型切换过程会产生**三重 token 膨胀**：

| 膨胀来源 | 估算 token 数 | 说明 |
| :--- | :--- | :--- |
| **第一重：系统提示** | ~25-30k | System Prompt + Tools schema + SKILL.md 注入（固定开销） |
| **第二重：切换过程** | ~90k | shell_exec tool_use/result + Agent thinking + session_status 调用 |
| **第三重：切换残留** | 持续累积 | 中间 tool_use/tool_result 消息残留在对话历史中，后续每次请求都重复携带 |

**实测数据**（以 128k 窗口模型为例）：
- 新会话后首条消息：input ~28.4k tokens
- 执行 `/ms <模型名>` 切换：input 暴涨至 ~121k tokens（增加 ~93k）
- 切换完成后首条消息：input ~84.7k tokens（切换残留 ~53k 仍存在）

> ⚠️ 切换过程本身就消耗了 128k 窗口的 **94.5%**。切换后残留消息持续占据 **~66%** 窗口空间。

### 4.2 v0.2 压缩策略

v0.2 采用**简单压缩处理机制**——在切换完成后，通过 SKILL.md 指令让模型主动清理/压缩切换过程中产生的冗余上下文。

#### 核心思路

```
切换完成后:
    │
    ▼
[压缩指令] → 模型收到切换完成的信号后，在下一轮回复中：
    │
    ├── 1. 不携带/忽略切换过程中产生的中间 tool_use/result 消息
    │
    ├── 2. 仅保留切换结果摘要（来源模型 → 目标模型，切换原因）
    │
    └── 3. 继续保持对话历史中的用户消息和任务上下文
```

#### 具体实现方式

**方式一：SKILL.md 中的切换后指令**

在 SKILL.md 的切换处理规则中，增加切换完成后的压缩指令：

```markdown
### 切换完成后

当 action="switch" 执行成功后：
1. 在你的回复中，用一句话总结切换结果（如："已从 mm 切换到 ds-v3"）
2. 不要引用或重复切换过程中的 CLI 输出、JSON 数据等中间内容
3. 继续正常响应用户的任务，保持上下文连贯
```

**方式二：CLI 输出中嵌入压缩提示**

当 `action="switch"` 时，在 `data` 中增加 `context_hint` 字段，指导模型如何处理上下文：

```json
{
  "action": "switch",
  "status": "ok",
  "data": {
    "target_model": "sjtu/deepseek-v3.2",
    "previous_model": "sjtu/minimax-m2.5",
    "context_hint": "切换完成。忽略本次切换过程中的中间输出，仅保留此摘要。"
  },
  "message": "✅ 模型已切换: mm → ds-v3"
}
```

### 4.3 debug 模式下的上下文监控

开启 `/ms debug` 后，调试脚注中增加上下文相关信息，用于验证压缩效果：

```
───────────────────────────────────────
🐛 Debug | Model: MiniMax M2.5 | Task: CODE_COMPLEX
   Potential: 40/50 ↑升级 | Rec: mm (Δ=0, 保持)
   Cooldown: ✅ 已过 | Inertia: 活跃(3轮同主题)
   Switches: 1/30 | Context: 压缩后(上次切换减少~53k tokens)  ← 🆕
───────────────────────────────────────
```

### 4.4 配置项

上下文压缩相关参数在 `settings.yaml` 中配置（不通过命令行调整）：

```yaml
auto_switch_skill:
  # ... 其他配置 ...

  # 🆕 v0.2 新增：上下文压缩
  context_compression:
    enabled: true                    # 是否启用切换后压缩
    strategy: "skill_instruction"    # 压缩策略：skill_instruction | context_hint

  # 阻尼/惯性等参数继续通过 settings.yaml 配置（不提供命令行调整）
  switcher:
    max_switches_per_session: 30
    cooldown_rounds: 3
    damping:
      upgrade_increment: 40
      downgrade_increment: 20
      decay_rate: 30
      upgrade_threshold: 50
      downgrade_threshold: 80
    context_inertia:
      enabled: true
      threshold_multiplier: 1.5
      topic_change_keywords:
        - "新的需求"
        - "另一个问题"
        - "换个话题"
        - "接下来"
      idle_reset_minutes: 30

  debug:
    enabled: false
```

### 4.5 与 v0.3 三层记忆栈的关系

v0.2 的上下文压缩是**轻量级方案**，通过指令引导模型行为来减少 token 浪费。

v0.3 将实现**系统级方案**——三层记忆栈（L1/L2/L3）+ 智能提取管道，在切换时主动提取关键信息、丢弃冗余内容，实现真正的上下文瘦身。v0.2 的压缩机制是 v0.3 的基础铺垫。

---

## 5. 新增 `/ms` 命令

### 5.1 命令总览（MVP 7 个 → v0.2 11 个）

```
┌──────────────┬──────────────────────────────────────────────────────┐
│ 分类         │ 命令                                                 │
├──────────────┼──────────────────────────────────────────────────────┤
│ 基础信息     │ help, status, list                        （MVP 已有）│
├──────────────┼──────────────────────────────────────────────────────┤
│ 模式与切换   │ auto, manual, <模型名>                    （MVP 已有）│
├──────────────┼──────────────────────────────────────────────────────┤
│ 路由管理     │ router（MVP 已有）, 🆕 set, 🆕 reset                │
├──────────────┼──────────────────────────────────────────────────────┤
│ 调试与监控   │ 🆕 debug, 🆕 stats                                  │
└──────────────┴──────────────────────────────────────────────────────┘
```

> v0.2 新增 4 个命令：`set`、`reset`、`debug`、`stats`

### 5.2 [F3] `/ms set` —— 修改路由矩阵权重

| 项目 | 说明 |
| :--- | :--- |
| 格式 | `/ms set <模型别名> <任务缩写> <适配度>` |
| 作用 | 修改某模型在某任务类型上的适配度权重（0-100） |
| 持久化 | 修改写入 `routing_matrix.yaml` 文件 |

**任务缩写对照表**：

| 缩写 | 全称 |
| :--- | :--- |
| `CHAT` | CHAT |
| `QA` | QA |
| `SUM` | SUMMARIZE |
| `TRA` | TRANSLATE |
| `CS` | CODE_SIMPLE |
| `CC` | CODE_COMPLEX |
| `REA` | REASONING |
| `ANA` | ANALYSIS |
| `CRE` | CREATIVE |
| `MS` | MULTI_STEP |

**输出示例**：

```
用户: /ms set mm CC 90

✅ 权重已更新
  模型:   MiniMax M2.5
  任务:   CODE_COMPLEX (复杂编程)
  权重:   85 → 90
```

**错误处理**：

| 错误场景 | 输出 |
| :--- | :--- |
| 参数缺失 | `❌ 缺少参数。用法: /ms set <模型> <任务缩写> <适配度>` |
| 未知模型 | `❌ 未找到模型 "xxx"。使用 /ms list 查看可用模型。` |
| 未知任务缩写 | `❌ 未知任务缩写 "xxx"。有效缩写: CHAT QA SUM TRA CS CC REA ANA CRE MS` |
| 权重越界 | `❌ 适配度必须在 0-100 之间，当前值: 150` |

### 5.3 [F3] `/ms reset` —— 重置路由矩阵

| 项目 | 说明 |
| :--- | :--- |
| 格式 | `/ms reset` |
| 作用 | 从内置画像库 `model_profiles.yaml` 重新生成路由矩阵，覆盖所有手动修改 |
| 持久化 | 重新生成 `routing_matrix.yaml` 文件 |

**交互流程**：

```
用户: /ms reset

⚠️ 即将重置路由矩阵
  这会覆盖所有手动修改的权重，从画像库重新生成。
  确认执行？(回复 "确认" 继续)

用户: 确认

✅ 路由矩阵已重置
  匹配画像: 4 个模型
  未匹配(使用默认权重 3): 1 个
  详情请使用 /ms router 查看
```

### 5.4 [F4] `/ms debug` —— 调试模式与脚注

| 项目 | 说明 |
| :--- | :--- |
| 格式 | `/ms debug [on\|off]` |
| 作用 | 开启/关闭调试模式。无参数时切换（toggle）当前状态 |
| 持久化 | 会话级，不持久化 |

**开启调试模式后**，系统在每条回答末尾追加调试脚注：

```
（模型正常回答内容...）

───────────────────────────────────────
🐛 Debug | Model: MiniMax M2.5 | Task: CODE_COMPLEX
   Potential: 40/50 ↑升级 | Rec: MiniMax M2.5 (Δ=0, 保持)
   Cooldown: ✅ 已过 | Inertia: 活跃(3轮同主题)
   Switches: 1/30
───────────────────────────────────────
```

**脚注字段说明**：

| 字段 | 说明 | 示例 |
| :--- | :--- | :--- |
| `Model` | 当前使用的模型 | `MiniMax M2.5` |
| `Task` | 本轮识别的任务类型 | `CODE_COMPLEX` |
| `Potential` | 当前势能值 / 触发阈值 + 方向 | `40/50 ↑升级` |
| `Rec` | 推荐模型及权重差 | `ds-v3 (Δ=+6, 保持)` |
| `Cooldown` | 冷却状态 | `✅ 已过` 或 `⏳ 剩余2轮` |
| `Inertia` | 惯性状态 | `活跃(3轮同主题)` 或 `不活跃` |
| `Switches` | 本会话切换次数/上限 | `1/30` |

### 5.5 [F8] `/ms stats`（基础版） —— 切换统计

| 项目 | 说明 |
| :--- | :--- |
| 格式 | `/ms stats` |
| 作用 | 查看本会话的切换统计数据 |
| 版本说明 | v0.2 为基础版，仅包含次数和占比。成本估算留待 v0.3 |

**输出示例**：

```
📈 本会话切换统计

  运行时长:    1h 32m
  总对话轮次:   28 轮
  切换次数:    2 次（升级 1 / 降级 1）
  切换频率:    每 14 轮切换 1 次

  模型使用占比:
    MiniMax M2.5     ████████████████░░░░  62% (17 轮)
    DeepSeek V3.2    ██████░░░░░░░░░░░░░░  25% (7 轮)
    Qwen3 Coder      ███░░░░░░░░░░░░░░░░░  14% (4 轮)
```

> 💡 v0.2 基础版不包含 Token 消耗估算和成本节省分析，这些功能将在 v0.3 中实现。

### 5.6 `/ms help` 更新

v0.2 需更新 `/ms help` 的输出，包含所有 11 个命令：

```
🔧 /ms 命令帮助 (v0.2)

模式与切换:
  /ms auto                            恢复自动切换模式
  /ms manual                          切换到手动模式（禁用自动切换）
  /ms <模型名>                         切换到指定模型（不改变当前模式）

路由管理:
  /ms router                          查看当前任务模型路由表
  /ms set <模型> <任务缩写> <适配度>    修改某模型某任务的权重
  /ms reset                           从画像库重新生成路由矩阵

调试与监控:
  /ms debug [on|off]                  开启/关闭调试模式（含上下文压缩信息）
  /ms stats                           查看切换统计

基础信息:
  /ms help                            显示本帮助信息
  /ms status                          查看当前运行状态
  /ms list                            列出所有可用模型

任务缩写对照: CHAT QA SUM TRA CS CC REA ANA CRE MS
```

### 5.7 `/ms status` 更新

v0.2 需更新 `/ms status` 输出，展示势能和惯性信息：

```
📋 Auto-Switch-Skill 运行状态 (v0.2)

当前模型:   MiniMax M2.5 (mm)
运行模式:   🤖 自动模式
调试模式:   ❌ 关闭

当前势能:   30 / 50 (升级方向)          ← 🆕
冷却状态:   ✅ 已过冷却期
上下文惯性: 活跃（连续 3 轮同主题）      ← 🆕

最近任务:   CODE_COMPLEX → 推荐: MiniMax M2.5 (权重 85)
本会话切换: 1 / 30 次
```

---

## 6. [F9/F10] 新增功能：CLI 输出协议规范化

### 6.1 需求描述

**MVP 现状**：不同 `/ms` 子命令的输出格式不一致——部分返回纯文本，部分返回混合格式（文本 + `__JSON_RESULT__` 尾部 JSON）。模型需要解析混合输出、判断 `success` 字段、决定是否调用 `session_status`，逻辑判断分散在脚本和 SKILL.md 之间。

**v0.2 升级**：所有 `ms_cli.py` 子命令的输出统一为**单行 JSON**，遵循统一的 CLI 输出协议。逻辑判断全部封装在脚本中，模型只根据 `action` 字段执行对应行为。

### 6.2 统一输出 Schema

所有命令输出遵循以下格式：

```json
{
  "action": "<动作类型>",
  "status": "<执行状态>",
  "data": { ... },
  "message": "<面向用户的展示文本>"
}
```

| 字段 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `action` | string | ✅ | 模型应执行的动作 |
| `status` | string | ✅ | `"ok"` 或 `"error"` |
| `data` | object | ✅ | 结构化数据，内容因 action 而异 |
| `message` | string | ✅ | 面向用户的展示文本，模型应直接展示给用户 |

### 6.3 动作类型定义

| action 值 | 含义 | 模型行为 |
| :--- | :--- | :--- |
| `"switch"` | 需要执行模型切换 | 调用 `session_status(model=data.target_model)` 并展示 `message` |
| `"display"` | 纯展示信息 | 将 `message` 展示给用户，不做额外操作 |
| `"error"` | 操作失败/被拒绝 | 将 `message` 展示给用户，汇报异常原因 |

### 6.4 SKILL.md 中的模型行为规则

```
根据 JSON 中的 action 字段执行：
- action="switch" 且 status="ok" → 调用 session_status(model=data.target_model)，并展示 message
- action="display"               → 展示 message
- action="error"                 → 展示 message，汇报异常
```

> 💡 模型不需要解析 `data` 字段的具体内容，只需根据 `action` 决定行为。`data` 字段供调试和日志使用。

### 6.5 各场景输出定义

#### 切换成功

```json
{
  "action": "switch",
  "status": "ok",
  "data": {
    "target_model": "sjtu/deepseek-v3.2",
    "target_alias": "ds-v3",
    "previous_model": "sjtu/minimax-m2.5",
    "previous_alias": "mm",
    "context_window": 128000
  },
  "message": "✅ 模型切换就绪\n  来源: mm (sjtu/minimax-m2.5)\n  目标: ds-v3 (sjtu/deepseek-v3.2)\n  上下文窗口: 128k"
}
```

#### 模型不存在

```json
{
  "action": "error",
  "status": "error",
  "data": { "error_code": "MODEL_NOT_FOUND", "input": "xxx" },
  "message": "❌ 未找到模型 \"xxx\"。使用 /ms list 查看可用模型。"
}
```

#### 上下文窗口不安全（🆕 v0.2 新增安全检查）

```json
{
  "action": "error",
  "status": "error",
  "data": {
    "error_code": "CONTEXT_WINDOW_UNSAFE",
    "target_model": "sjtu/某模型",
    "context_window": 128000,
    "min_safe_window": 150000
  },
  "message": "⚠️ 拒绝切换到 某模型\n  原因: 上下文窗口 128k < 安全阈值 150k"
}
```

#### 达到切换上限

```json
{
  "action": "error",
  "status": "error",
  "data": { "error_code": "SWITCH_LIMIT_REACHED", "switch_count": 30, "max_switches": 30 },
  "message": "⚠️ 已达本会话切换上限 (30/30 次)，拒绝继续切换。"
}
```

#### 脚本内部异常（🆕 全局 try-except 兜底）

```json
{
  "action": "error",
  "status": "error",
  "data": { "error_code": "INTERNAL_ERROR", "exception": "FileNotFoundError: routing_matrix.json" },
  "message": "❌ 内部错误: 无法加载配置文件 routing_matrix.json。请检查 config 目录。"
}
```

#### 纯展示命令（status / list / help / auto / manual / router 等）

```json
{
  "action": "display",
  "status": "ok",
  "data": { ... },
  "message": "📋 Auto-Switch-Skill 运行状态\n..."
}
```

#### 自动切换判定（evaluate）

需要切换时：
```json
{
  "action": "switch",
  "status": "ok",
  "data": {
    "target_model": "sjtu/deepseek-v3.2",
    "task_type": "CODE_COMPLEX",
    "reason": "任务类型切换: CODE_COMPLEX, 2轮势能累积"
  },
  "message": "🔄 自动切换: mm → ds-v3（任务类型: CODE_COMPLEX）"
}
```

不需要切换时：
```json
{
  "action": "display",
  "status": "ok",
  "data": { "decision": "no_switch" },
  "message": ""
}
```

### 6.6 上下文窗口安全检查

**问题背景**：系统提示 + 工具定义约占 ~30k tokens，切换流程还会额外消耗上下文。若目标模型上下文窗口过小，切换后可能导致上下文溢出。

**安全检查规则**：

| 项目 | 说明 |
| :--- | :--- |
| 安全阈值 | `MIN_SAFE_CONTEXT_WINDOW = 150000`（150k tokens） |
| 检查时机 | 手动切换（`/ms <模型名>`）和自动切换（evaluate）执行前 |
| 拒绝行为 | 返回 `action="error", error_code="CONTEXT_WINDOW_UNSAFE"` |
| 配置来源 | 从 `routing_matrix` 中的模型元数据读取 `context_window` 字段 |

**检查流程**（在 `cmd_switch()` 中）：

```
别名解析（模型存在？）
    ↓
上下文窗口安全检查（窗口 >= 150k？）  ← 🆕
    ↓
切换上限检查（< 30 次？）
    ↓
执行切换 → action="switch"
```

### 6.7 全局异常捕获

在 `ms_cli.py` 的 `main()` 入口添加全局 try-except：

```python
def main():
    try:
        args = parser.parse_args()
        args.func(args)
    except Exception as e:
        output_json({
            "action": "error",
            "status": "error",
            "data": { "error_code": "INTERNAL_ERROR", "exception": f"{type(e).__name__}: {e}" },
            "message": f"❌ 内部错误: {e}"
        })
        sys.exit(1)
```

> 确保脚本在任何情况下（包括配置文件缺失、依赖缺失等）都输出合法 JSON，模型永远不会收到 Python traceback。

### 6.8 对 MVP 代码的改动

| 组件 | 改动 |
| :--- | :--- |
| `ms_command.py` | 所有 `cmd_*()` 返回值从 `str` 改为 `dict`（统一 `{action, status, data, message}` 格式） |
| `ms_cli.py` | 新增 `output_json()` 统一输出函数；所有子命令通过它输出 |
| `ms_cli.py` | 新增全局 try-except 兜底 |
| `src/core/__init__.py` | 新增常量 `MIN_SAFE_CONTEXT_WINDOW = 150000` |
| `SKILL.md` | 命令处理部分重写为统一的 action → 行为规则表 |
| `tests/` | 所有 `cmd_*()` 测试改为断言返回字典的四个字段；新增安全检查测试 |

---

## 7. [F7] 新增功能：切换日志与监控

### 7.1 日志记录内容

每次模型切换时，记录以下结构化信息：

| 字段 | 类型 | 说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `timestamp` | datetime | 切换时间戳 | `2026-04-08T14:23:10+08:00` |
| `direction` | str | 切换方向 | `upgrade` / `downgrade` |
| `task_type` | str | 触发切换的任务类型 | `CODE_COMPLEX` |
| `source_model` | str | 来源模型 ID | `sjtu/deepseek-v3.2` |
| `target_model` | str | 目标模型 ID | `sjtu/minimax-m2.5` |
| `recommended_weight` | int | 推荐模型权重 | `85` |
| `current_weight` | int | 当前模型权重 | `78` |
| `weight_diff` | int | 权重差值 | `+7` |
| `potential_at_trigger` | int | 触发时的势能值 | `50` |
| `rounds_accumulated` | int | 势能累积经过的轮数 | `2` |
| `switch_result` | bool | 切换是否成功 | `true` |
| `reason` | str | 切换原因文本描述 | `权重差 +7, 2轮累积` |

### 7.2 日志存储方式

| 项目 | 说明 |
| :--- | :--- |
| 存储位置 | 会话级内存（`SwitchState.switch_history` 列表） |
| 持久化 | v0.2 **不持久化**，仅会话内有效 |
| 访问方式 | `/ms stats` 命令聚合统计；`/ms debug` 脚注展示 |
| 数据结构 | `list[SwitchLogEntry]`，每条为一个 dataclass 实例 |

> 💡 持久化切换日志（写入文件）将在 v0.3 中实现，届时同时支持跨会话的统计分析。

### 7.3 SwitchLogEntry 数据结构

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class SwitchLogEntry:
    """切换日志条目"""
    timestamp: datetime
    direction: str              # "upgrade" | "downgrade"
    task_type: str
    source_model: str
    target_model: str
    recommended_weight: int
    current_weight: int
    weight_diff: int
    potential_at_trigger: int
    rounds_accumulated: int
    switch_result: bool
    reason: str
```

---

## 8. 对 MVP 模块的修改说明

### 8.1 `state.py` 的扩展

**新增字段**（在 `SwitchState` dataclass 中）：

| 新增字段 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `potential` | int | 0 | 当前切换势能值 |
| `potential_direction` | str | "" | 势能方向（`"upgrade"` / `"downgrade"` / `""`） |
| `potential_rounds` | int | 0 | 势能连续累积的轮数 |
| `inertia_active` | bool | False | 上下文惯性是否活跃 |
| `inertia_consecutive_rounds` | int | 0 | 连续同主题轮数 |
| `last_message_time` | datetime / None | None | 上次消息时间（用于超时判断） |
| `debug_mode` | bool | False | 调试模式是否开启 |
| `switch_history` | list | [] | 切换历史日志列表 |
| `session_start_time` | datetime | now() | 会话开始时间（用于 stats） |
| `rounds_per_model` | dict | {} | 各模型使用的轮数统计 |
| `total_rounds` | int | 0 | 总对话轮数 |
| `upgrade_count` | int | 0 | 升级切换次数 |
| `downgrade_count` | int | 0 | 降级切换次数 |

**新增方法**（在 `SwitchStateManager` 中）：

| 方法 | 说明 |
| :--- | :--- |
| `update_potential(direction, increment)` | 累积/衰减势能 |
| `reset_potential()` | 势能归零 |
| `check_inertia(task_type, message_time)` | 检查并更新惯性状态 |
| `reset_inertia()` | 重置惯性 |
| `add_switch_log(entry)` | 添加切换日志条目 |
| `get_switch_history()` | 获取切换历史 |
| `get_stats()` | 获取统计数据 |
| `tick_round(model_id)` | 计数轮次，更新各模型使用统计 |

### 8.2 `router.py` 的升级

**核心变更**：`should_switch()` 方法从「直接阈值判定」重构为「势能累积判定」。

**MVP 版本逻辑**（将被替换）：

```python
def should_switch(evaluation, state):
    return evaluation.weight_diff > WEIGHT_DIFF_THRESHOLD
```

**v0.2 版本逻辑**：

```python
def should_switch(evaluation, state, config):
    # 1. 权重差是否超过阈值
    if abs(evaluation.weight_diff) <= config.weight_diff_threshold:
        state_mgr.decay_potential(config.decay_rate)
        return False

    # 2. 判断方向并累积势能
    if evaluation.weight_diff > 0:
        direction = "upgrade"
        increment = config.upgrade_increment
        threshold = config.upgrade_threshold
    else:
        direction = "downgrade"
        increment = config.downgrade_increment
        threshold = config.downgrade_threshold

    state_mgr.update_potential(direction, increment)

    # 3. 上下文惯性调整阈值
    if state.inertia_active:
        threshold = int(threshold * config.inertia_multiplier)

    # 4. 势能是否越过阈值
    if state.potential >= threshold:
        state_mgr.reset_potential()
        return True

    return False
```

**新增方法**：

| 方法 | 说明 |
| :--- | :--- |
| `process_message_v2(thought_text, message_text, message_time)` | v0.2 版完整消息处理（含惯性检查） |

### 8.3 `ms_command.py` 的扩展

**新增 4 个命令处理函数**：

| 函数 | 对应命令 | 说明 |
| :--- | :--- | :--- |
| `cmd_set(model, task_abbrev, weight)` | `/ms set` | 修改矩阵权重 + 更新 YAML 文件 |
| `cmd_reset()` | `/ms reset` | 调用 `generate_matrix.py` 逻辑重生成 |
| `cmd_debug(on_off)` | `/ms debug` | 切换调试模式状态 |
| `cmd_stats()` | `/ms stats` | 聚合统计数据格式化输出 |

**已有命令更新**：

| 函数 | 变更 |
| :--- | :--- |
| `cmd_help()` | 输出增加 4 个新命令的帮助信息 |
| `cmd_status()` | 输出增加势能值、惯性状态、调试模式 |

### 8.4 `settings.yaml` 的扩展

在现有配置基础上新增 `damping`、`context_inertia`、`debug` 三个配置段（详见 §4.3）。

**向下兼容**：若 `settings.yaml` 缺少新增配置段，代码使用默认值，不报错。

### 8.5 新增文件

| 文件 | 说明 |
| :--- | :--- |
| `src/core/damping.py` | 🆕 势能累积与衰减逻辑封装 |
| `src/core/inertia.py` | 🆕 上下文惯性检测逻辑封装 |
| `src/core/logger.py` | 🆕 切换日志管理（SwitchLogEntry + 格式化） |
| `src/core/context_compressor.py` | 🆕 切换上下文压缩逻辑（context_hint 生成 + 压缩效果度量） |

---

## 9. 验收标准

### 9.1 Must Have（必须完成）

- [ ] 势能累积机制：权重差 > 15 时累积势能，升级方向 ~2 轮触发，降级方向 ~4 轮触发
- [ ] 势能衰减：权重差 ≤ 15 或推荐模型 == 当前模型时，势能 -30 直至 0
- [ ] 上下文惯性：连续同主题轮次 ≥ 3 时阈值 ×1.5
- [ ] 话题转换信号能正确重置惯性
- [ ] `/ms set` 能修改矩阵权重并写入 YAML 文件
- [ ] `/ms reset` 能重新生成路由矩阵
- [ ] `/ms debug on` 能在回答末尾追加调试脚注（含上下文压缩信息）
- [ ] `/ms stats` 能显示切换次数和模型使用占比
- [ ] `/ms help` 和 `/ms status` 输出已更新
- [ ] 切换日志记录完整（含 §7.1 定义的全部字段）
- [ ] 现有 MVP 功能不回退（7 个旧命令、直接切换、冷却、上限）
- [ ] CLI 输出协议：所有命令输出为统一的单行 JSON（`{action, status, data, message}`）
- [ ] 上下文窗口安全检查：切换到窗口 < 150k 的模型时拒绝并返回 error
- [ ] 全局异常捕获：脚本崩溃时输出规范 error JSON，不输出 traceback
- [ ] SKILL.md 行为规则：模型仅根据 action 字段执行行为，不做额外判断
- [ ] 切换上下文压缩：切换完成后模型不携带/重复中间 tool_use/result 消息
- [ ] debug 模式下能观测上下文压缩效果

### 9.2 Nice to Have（如有余力）

- [ ] `/ms stats` 中的模型占比使用 ASCII 进度条可视化
- [ ] 调试脚注中追加 Token 用量信息（需依赖 OpenClaw API）
- [ ] 惯性检测支持基于任务类型连续性的判断（不仅依赖关键词）
- [ ] 上下文压缩效果量化度量（压缩前后 token 数对比）

---

## 10. 后续版本规划（v0.3 预告）

v0.3 将聚焦「上下文管理」，在 v0.2 的智能切换基础上解决模型切换时的上下文连续性问题：

| 功能 | 预估工时 | 说明 |
| :--- | :--- | :--- |
| 三层记忆栈（L1/L2/L3） | 3-4 天 | 战略层 + 摘要链 + 工作区分层存储 |
| 智能提取管道 | 2-3 天 | 4 步流程：扫描→分类→提取→校验 |
| 切换重组编排器 | 1-2 天 | Token 预算分配 + 上下文注入 |
| `[PIN]` 永不过期标记 | 0.5 天 | 关键信息保护机制 |
| `/ms memory` + `/ms pin` | 1 天 | 记忆管理用户命令 |
| 增量摘要 DAG 引擎 | 2-3 天 | 树状摘要合并 + 重要度衰减 |
| `/ms export` + `/ms import` | 0.5 天 | 配置导入导出 |
| `/ms stats` 完整版 | 0.5 天 | Token 消耗估算 + 成本节省分析 |
| 切换日志持久化 | 0.5 天 | 写入文件，支持跨会话统计 |

---

> **文档变更记录**
>
> | 版本 | 日期 | 变更说明 |
> | :--- | :--- | :--- |
> | v0.2-draft | 2026-04-08 | 初始版本，基于 MVP v1.0 和总体需求对比分析创建 |
> | v0.2-draft-2 | 2026-04-08 | 新增设计原则章节（§0）；新增 CLI 输出协议规范化（§6，含上下文窗口安全检查）；功能清单增加 F9/F10 |
> | v0.2-draft-3 | 2026-04-08 | 移除 `/ms cooldown`、`/ms threshold`、`/ms history` 命令；新增 §4 切换上下文压缩机制（F11）；命令数 14→11 |
