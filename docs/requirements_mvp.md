# Auto-Switch-Skill MVP 需求文档

> **版本**：MVP v1.0
> **日期**：2026-04-06
> **范围**：一天可完成的最小可行产品
> **状态**：待实现

---

## 1. MVP 概述

### 1.1 目标

实现一个最小闭环：**用户发消息 → 模型自评估任务类型 → 查路由矩阵 → 直接阈值判定切换 → 执行切换**，并提供 `/ms` 命令让用户手动查看状态和切换模型。

### 1.2 MVP 范围

| 保留 | 砍掉（后续阶段） |
| :--- | :--- |
| ✅ 模型自评估任务类型 | ❌ 三层记忆栈（L1/L2/L3） |
| ✅ 适配度矩阵路由 | ❌ 智能提取管道 |
| ✅ 直接阈值切换判定 | ❌ 增量摘要 DAG |
| ✅ 路由矩阵自动生成器 | ❌ 切换势能累积/上下文惯性 |
| ✅ 7 个基础 `/ms` 命令 | ❌ 调试脚注/统计分析/配置导入导出 |
| ✅ 硬编码 3 轮冷却 | ❌ 记忆管理（memory/pin）|
| ✅ 30 次切换上限 | ❌ 多 Agent 协同切换 |

### 1.3 技术验证结论

**`session_status` API 已验证可用**：

- OpenClaw 容器（`research-multi-agent`）中 `session_status` 工具定义在 `pi-embedded` 模块
- 参数 Schema：`{ sessionKey?: string, model?: string }`
- 当传入 `model` 参数时，系统将其识别为 **变更操作**（mutating tool call），执行 per-session 模型覆盖
- 传入 `model=default` 可重置覆盖

**当前可用模型**（`openclaw.json` 中已注册）：

| Provider/ID | 别名 | 上下文窗口 | 推理模式 |
| :--- | :--- | :--- | :--- |
| `sjtu/deepseek-v3.2` | DeepSeek V3.2 | 128K | ❌ |
| `sjtu/deepseek-chat` | DeepSeek Chat | 128K | ❌ |
| `sjtu/minimax-m2.5` | MiniMax M2.5 | 192K | ✅ |
| `sjtu/qwen3coder` | Qwen3 Coder | 128K | ❌ |
| `sjtu/qwen3vl` | Qwen3 VL | 128K | ❌ |

---

## 2. 模型切换模块（简化版）

### 2.1 任务类型评估

##### 评估方式：模型自评估（Self-Evaluation）

在 System Prompt 中嵌入分类指令，让当前模型在 `thought` / `thinking` 字段中以 `[TASK_TYPE: XXX]` 格式输出任务类型标签。

##### 任务类型定义（10 种）

| 类型标识 | 缩写 | 中文名 | 典型场景 |
| :--- | :--- | :--- | :--- |
| `CHAT` | `CHAT` | 日常对话 | 闲聊、问候、简单问答 |
| `QA` | `QA` | 知识问答 | 事实查询、概念解释 |
| `SUMMARIZE` | `SUM` | 摘要生成 | 文档摘要、会议纪要 |
| `TRANSLATE` | `TRA` | 翻译 | 多语言互译 |
| `CODE_SIMPLE` | `CS` | 简单编程 | 函数编写、Bug 修复 |
| `CODE_COMPLEX` | `CC` | 复杂编程 | 架构设计、大规模重构 |
| `REASONING` | `REA` | 逻辑推理 | 数学证明、因果分析 |
| `ANALYSIS` | `ANA` | 深度分析 | 长文档分析、数据解读 |
| `CREATIVE` | `CRE` | 创意生成 | 文案创作、方案设计 |
| `MULTI_STEP` | `MS` | 多步骤任务 | 工作流编排、复合任务 |

##### System Prompt 注入片段

```
你是一个 AI 助手。在回答之前，请先在 thought/thinking 中分析任务类型，并以精确格式输出标签：
[TASK_TYPE: <TYPE>]

其中 <TYPE> 必须是以下之一：
CHAT, QA, SUMMARIZE, TRANSLATE, CODE_SIMPLE, CODE_COMPLEX, REASONING, ANALYSIS, CREATIVE, MULTI_STEP

然后正常回答用户的问题。
```

##### 解析逻辑

```python
import re

def parse_task_type(thought_text: str) -> str | None:
    """从 thought/thinking 字段中提取任务类型标签"""
    match = re.search(r'\[TASK_TYPE:\s*(\w+)\]', thought_text)
    if match:
        task_type = match.group(1).upper()
        if task_type in VALID_TASK_TYPES:
            return task_type
    return None  # 解析失败，不触发切换
```

### 2.2 切换判定（直接阈值，无势能累积）

MVP 采用最简单的直接阈值判定，**不累积势能**：

```
权重差 = 推荐模型权重 - 当前模型权重

if 权重差 > weight_diff_threshold (默认 15):
    → 执行切换（立即）
else:
    → 不切换
```

##### 完整决策流程

```
用户消息进入
    │
    ▼
[冷却期检查] ← 上次切换后是否已过 3 轮？
    │
    ├── 冷却中 → 跳过评估，使用当前模型
    │
    └── 已过冷却期
         │
         ▼
    [模式检查] ← 是否处于自动模式？
         │
         ├── 手动模式 → 跳过评估，使用当前模型
         │
         └── 自动模式
              │
              ▼
         [模型自评估] → 解析 thought 字段，提取任务类型标签
              │
              ├── 解析失败 → 跳过切换
              │
              └── 成功获取任务类型（如 CODE_COMPLEX）
                   │
                   ▼
              [适配度矩阵查询]
                   │
                   推荐模型 = 该任务类型权重最高的模型
                   推荐权重 = routing_matrix[推荐模型][任务类型]
                   当前权重 = routing_matrix[当前模型][任务类型]
                   权重差 = 推荐权重 - 当前权重
                   │
                   ▼
              权重差 > 15 且 推荐模型 ≠ 当前模型？
                   │
                   ├── 否 → 不切换
                   │
                   └── 是 → [切换次数检查]
                              │
                              ├── 已达 30 次上限 → 不切换
                              │
                              └── 未达上限 → ✅ 执行切换
                                               冷却计时开始
```

### 2.3 执行切换

调用 OpenClaw 的 `session_status` 工具：

```python
# 调用 session_status 设置模型覆盖
session_status(model="sjtu/deepseek-v3.2")

# 重置到默认模型
session_status(model="default")
```

##### 切换约束

| 约束 | 值 | 说明 |
| :--- | :--- | :--- |
| 冷却期 | 3 轮 | 硬编码，切换后 3 轮不再评估 |
| 切换上限 | 30 次 | 单会话最大切换次数 |
| 回退机制 | 简单回退 | 切换失败时保持使用当前模型 |

##### 接口定义

```python
from dataclasses import dataclass

@dataclass
class TaskEvaluation:
    task_type: str           # 如 "CODE_COMPLEX"
    recommended_model: str   # 如 "sjtu/minimax-m2.5"
    recommended_weight: int  # 推荐模型在该任务上的权重
    current_weight: int      # 当前模型在该任务上的权重
    weight_diff: int         # 推荐权重 - 当前权重

@dataclass
class SwitchResult:
    success: bool
    previous_model: str
    current_model: str
    reason: str

def evaluate_task(thought_text: str, current_model: str) -> TaskEvaluation | None:
    """从 thought 字段解析任务类型，查矩阵返回评估结果"""
    ...

def should_switch(evaluation: TaskEvaluation, state: SwitchState) -> bool:
    """判断是否应该切换（直接阈值 + 冷却 + 上限）"""
    ...

def execute_switch(target_model: str) -> SwitchResult:
    """调用 session_status(model=target) 执行切换"""
    ...
```

---

## 3. 路由矩阵自动生成器

### 3.1 生成流程

```
读取 openclaw.json              读取 model_profiles.yaml
中的已注册模型列表                （内置画像库，70+ 模型）
        │                                │
        └────────── 模糊匹配 ──────────────┘
                      │
                      ▼
              生成 routing_matrix.yaml
              （仅包含用户实际可用的模型）
                      │
                      ▼
              输出摘要表格供用户确认
```

### 3.2 模糊匹配规则

`openclaw.json` 中的模型 ID 格式为 `provider/model-name`（如 `sjtu/deepseek-v3.2`），而 `model_profiles.yaml` 中的键格式为 `vendor/model-name`（如 `deepseek/deepseek-v3.2`）。

匹配策略（按优先级）：

1. **精确匹配**：`openclaw.json` 的 model ID 名称部分（去掉 provider 前缀）与画像库的模型名称部分完全一致
   - `sjtu/deepseek-v3.2` → 提取 `deepseek-v3.2` → 匹配 `deepseek/deepseek-v3.2`
2. **模糊匹配**：对名称做标准化（转小写、去点号、去连字符）后再比较
   - `sjtu/minimax-m2.5` → `minimaxm25` → 匹配 `minimax/m2.7`?（不匹配，名称不同）
3. **关键词匹配**：提取模型名称中的关键词（品牌名+版本号），在画像库中搜索包含相同关键词的模型
   - `sjtu/qwen3coder` → 关键词 `qwen`, `3`, `coder` → 匹配 `alibaba/qwen-coder-*` 系列中最接近的
4. **未匹配**：所有任务权重默认为 `3`

### 3.3 当前模型匹配预期

| openclaw.json 模型 | 预期匹配画像 | 匹配方式 |
| :--- | :--- | :--- |
| `sjtu/deepseek-v3.2` | `deepseek/deepseek-v3.2` | 名称精确匹配 |
| `sjtu/deepseek-chat` | `deepseek/deepseek-v3` 或 fallback | 关键词匹配 |
| `sjtu/minimax-m2.5` | `minimax/m2.7`（最接近） | 关键词匹配 |
| `sjtu/qwen3coder` | `alibaba/qwen-coder-2.5-32b`（最接近） | 关键词匹配 |
| `sjtu/qwen3vl` | 无画像，默认权重 3 | 未匹配 |

### 3.4 生成的 routing_matrix.yaml 格式

```yaml
# Auto-Switch-Skill 路由矩阵
# 由自动生成器根据 model_profiles.yaml 生成
# 生成时间: 2026-04-06T02:00:00+08:00

models:
  - id: "sjtu/deepseek-v3.2"
    alias: "ds-v3"
    matched_profile: "deepseek/deepseek-v3.2"
  - id: "sjtu/deepseek-chat"
    alias: "ds-chat"
    matched_profile: "deepseek/deepseek-v3"
  - id: "sjtu/minimax-m2.5"
    alias: "mm"
    matched_profile: "minimax/m2.7"
  - id: "sjtu/qwen3coder"
    alias: "qwen-c"
    matched_profile: "alibaba/qwen-coder-2.5-32b"
  - id: "sjtu/qwen3vl"
    alias: "qwen-vl"
    matched_profile: null  # 未匹配画像

task_types:
  CHAT: "日常对话"
  QA: "知识问答"
  SUMMARIZE: "摘要生成"
  TRANSLATE: "翻译"
  CODE_SIMPLE: "简单编程"
  CODE_COMPLEX: "复杂编程"
  REASONING: "逻辑推理"
  ANALYSIS: "深度分析"
  CREATIVE: "创意生成"
  MULTI_STEP: "多步骤任务"

routing_matrix:
  CHAT:
    sjtu/deepseek-v3.2: 80
    sjtu/deepseek-chat: 72
    sjtu/minimax-m2.5: 72
    sjtu/qwen3coder: 35
    sjtu/qwen3vl: 3
  # ... 其余任务类型同理
```

---

## 4. 用户接口（`/ms` 命令）

### 4.1 MVP 命令清单（7 个）

```
┌──────────────┬─────────────────────────────────┐
│ 分类         │ 命令                             │
├──────────────┼─────────────────────────────────┤
│ 基础信息     │ help, status, list               │
├──────────────┼─────────────────────────────────┤
│ 模式与切换   │ auto, manual, <模型名>           │
├──────────────┼─────────────────────────────────┤
│ 路由查看     │ router                           │
└──────────────┴─────────────────────────────────┘
```

### 4.2 命令详细定义

#### `/ms help`

```
🔧 /ms 命令帮助 (MVP)

模式与切换:
  /ms auto                  恢复自动切换模式
  /ms manual                切换到手动模式（禁用自动切换）
  /ms <模型名>              切换到指定模型（不改变当前模式）

路由管理:
  /ms router                查看当前任务模型路由表

基础信息:
  /ms help                  显示本帮助信息
  /ms status                查看当前运行状态
  /ms list                  列出所有可用模型

任务缩写对照: CHAT QA SUM TRA CS CC REA ANA CRE MS
```

#### `/ms status`

```
📋 Auto-Switch-Skill 运行状态

当前模型:   MiniMax M2.5 (mm)
运行模式:   🤖 自动模式
冷却状态:   ✅ 已过冷却期
最近任务:   CODE_COMPLEX → 推荐: MiniMax M2.5 (权重 85)
本会话切换: 1 / 30 次
```

#### `/ms list`

```
📦 可用模型列表

  别名         模型全称                  上下文窗口   推理
  ─────────────────────────────────────────────────────
  ds-v3        sjtu/deepseek-v3.2       128K         ❌
  ds-chat      sjtu/deepseek-chat       128K         ❌
  mm           sjtu/minimax-m2.5        192K         ✅
  qwen-c       sjtu/qwen3coder          128K         ❌
  qwen-vl      sjtu/qwen3vl             128K         ❌

  当前使用: mm (sjtu/minimax-m2.5) ●
```

#### `/ms auto`

恢复自动切换模式。系统根据任务类型自动选取最优模型。

```
✅ 已切换到自动模式
   系统将根据任务类型自动选取最优模型。
```

#### `/ms manual`

切换到手动模式，禁用自动切换。

```
✅ 已切换到手动模式
   自动切换已禁用，仅响应手动切换命令。
```

#### `/ms <模型名>`

立即切换到指定模型，**不改变当前运行模式**。支持别名或完整 ID。

```
用户: /ms ds-v3

✅ 模型已切换
  来源: MiniMax M2.5 (mm)
  目标: DeepSeek V3.2 (ds-v3)
  当前模式: 🤖 自动模式（未改变）
```

#### `/ms router`

查看当前路由矩阵。

```
📊 当前任务模型路由表
┌────────────┬──────┬────┬─────┬─────┬──────┬──────┬─────┬─────┬─────┬──────┐
│ 模型       │ CHAT │ QA │ SUM │ TRA │ CS   │ CC   │ REA │ ANA │ CRE │ MS   │
├────────────┼──────┼────┼─────┼─────┼──────┼──────┼─────┼─────┼─────┼──────┤
│ ds-v3      │  80  │ 80 │  78 │  78 │  88★ │  78  │  78 │  80 │  72 │  78  │
│ ds-chat    │  72  │ 75 │  72 │  75 │  78  │  72  │  72 │  75 │  68 │  70  │
│ mm         │  72  │ 72 │  78 │  68 │  82  │  85★ │  72 │  75 │  72 │  80★ │
│ qwen-c     │  35  │ 42 │  32 │  28 │  85  │  72  │  50 │  42 │  25 │  45  │
│ qwen-vl    │   3  │  3 │   3 │   3 │   3  │   3  │   3 │   3 │   3 │   3  │
└────────────┴──────┴────┴─────┴─────┴──────┴──────┴─────┴─────┴─────┴──────┘
★ = 该任务类型的最优模型（路由首选）
```

### 4.3 错误处理

| 场景 | 输出 |
| :--- | :--- |
| 未知命令 | `❌ 未知命令: /ms foo。使用 /ms help 查看可用命令。` |
| 未知模型 | `❌ 未找到模型 "xxx"。使用 /ms list 查看可用模型。` |
| 已处于该模式 | `⚠️ 当前已是自动模式，无需重复切换。` |

### 4.4 实现方式

1. 创建 Skill 文件（`SKILL.md`），`description` 匹配 `/ms` 或 `/model-switch` 开头的消息
2. 在 SKILL.md 中定义命令解析和分发逻辑
3. 模式状态和切换计数存储在会话级变量中（内存即可，不持久化）
4. 模型切换调用 `session_status(model="目标模型")` 执行

---

## 5. 配置说明（精简版）

### 5.1 核心配置项

```yaml
auto_switch_skill:
  enabled: true

  evaluator:
    method: "self_eval"
    output_field: "thought"
    output_format: "[TASK_TYPE: {type}]"

  routing:
    matrix_file: "routing_matrix.yaml"
    profile_library: "model_profiles.yaml"
    default_weight: 3
    weight_diff_threshold: 15    # 权重差超过此值才触发切换

  switcher:
    max_switches_per_session: 30
    cooldown_rounds: 3           # 硬编码冷却轮数
```

### 5.2 文件路径约定

```
<skill安装目录>/
├── SKILL.md                         # Skill 入口（命令解析 + 切换逻辑指令）
├── config/
│   ├── model_profiles.yaml          # 内置画像库（70+ 模型，随 repo 分发）
│   ├── routing_matrix.yaml          # 安装时自动生成的用户路由矩阵
│   └── settings.yaml                # 运行时配置（阈值、冷却等）
└── scripts/
    └── generate_matrix.py           # 路由矩阵自动生成脚本
```

---

## 6. MVP 文件清单与实现顺序

### 6.1 需要创建/修改的文件

| 序号 | 文件 | 类型 | 说明 |
| :--- | :--- | :--- | :--- |
| 1 | `src/config/schema.py` | 修改 | 已有，确认数据模型满足 MVP 需求 |
| 2 | `scripts/generate_matrix.py` | 新建 | 路由矩阵自动生成器（读取 openclaw.json + 模糊匹配 model_profiles.yaml） |
| 3 | `src/core/evaluator.py` | 新建 | 任务类型解析器（从 thought 字段提取 `[TASK_TYPE: XXX]`） |
| 4 | `src/core/router.py` | 新建 | 路由引擎（查矩阵 → 判定切换 → 执行 session_status） |
| 5 | `src/core/state.py` | 新建 | 运行时状态管理（当前模型、模式、冷却计数、切换次数） |
| 6 | `src/skills/ms_command.py` | 新建 | `/ms` 命令解析器和 7 个子命令的输出格式化 |
| 7 | `SKILL.md` | 新建 | OpenClaw Skill 入口文件 |
| 8 | `routing_matrix.yaml` | 生成 | 由 generate_matrix.py 自动生成 |

### 6.2 推荐实现顺序

```
第 1 步：generate_matrix.py  （路由矩阵自动生成器）
   ↓  运行生成 routing_matrix.yaml，验证匹配结果
第 2 步：evaluator.py        （任务类型解析）
   ↓  单元测试验证解析正确
第 3 步：state.py             （状态管理）
   ↓
第 4 步：router.py            （路由 + 切换判定 + 执行）
   ↓
第 5 步：ms_command.py        （/ms 命令 7 个子命令）
   ↓
第 6 步：SKILL.md             （OpenClaw Skill 入口，串联一切）
   ↓
第 7 步：端到端验证           （在容器中测试完整流程）
```

---

## 7. 验收标准

### 7.1 Must Have（必须完成）

- [ ] `generate_matrix.py` 能读取 `openclaw.json` + `model_profiles.yaml`，生成正确的 `routing_matrix.yaml`
- [ ] 模糊匹配：至少 `deepseek-v3.2`、`minimax-m2.5` 能正确匹配到画像
- [ ] `evaluator.py` 能从 `[TASK_TYPE: CODE_COMPLEX]` 格式中正确解析出任务类型
- [ ] `router.py` 能根据任务类型查矩阵、判定是否切换、调用 `session_status`
- [ ] 冷却期：切换后 3 轮内不再触发切换
- [ ] 切换上限：超过 30 次不再切换
- [ ] 7 个 `/ms` 命令全部可用且输出格式正确
- [ ] `SKILL.md` 能被 OpenClaw 识别并加载

### 7.2 Nice to Have（如有余力）

- [ ] 切换失败自动回退
- [ ] `/ms router` 中用 `★` 标注每个任务的最优模型
- [ ] 未匹配画像的模型在 `/ms list` 中标注 `⚠️`

---

## 8. 与完整版的差异说明

> 本 MVP 从完整需求文档 `requirements.md`（v1.4, 1199 行）精简而来。
> 以下功能将在后续阶段实现：

| 阶段 | 功能 | 预估工时 |
| :--- | :--- | :--- |
| Phase 2 | 切换势能累积 + 上下文惯性 + 可配冷却 | 2-3 天 |
| Phase 2 | 三层记忆栈（L1/L2/L3）+ 智能提取管道 | 5-7 天 |
| Phase 2 | `/ms set`、`/ms reset`、`/ms debug`、`/ms history` | 1-2 天 |
| Phase 3 | 增量摘要 DAG 引擎 | 3-5 天 |
| Phase 3 | `/ms stats`、`/ms memory`、`/ms pin`、`/ms export/import` | 2-3 天 |
| Phase 3 | 多 Agent 协同切换 + 端到端测试 | 1 周 |

---

> **文档变更记录**
>
> | 版本 | 日期 | 变更说明 |
> | :--- | :--- | :--- |
> | MVP v1.0 | 2026-04-06 | 从 requirements.md v1.4 裁剪 MVP 版本；API 已验证；切换判定简化为直接阈值 |
