<p align="center">
  <h1 align="center">🔄 Auto-Switch-Skill</h1>
  <p align="center">
    <img src="https://img.shields.io/badge/版本-MVP_v0.1.0_测试版-orange?style=for-the-badge" alt="version"/>
    <img src="https://img.shields.io/badge/状态-Alpha_测试中-red?style=for-the-badge" alt="status"/>
    <img src="https://img.shields.io/badge/许可证-MIT-green?style=for-the-badge" alt="license"/>
  </p>
  <p align="center">
    <strong>OpenClaw 多智能体系统的智能模型自动切换模块</strong>
  </p>
  <p align="center">
    赋予 Agent "自知之明" —— 根据任务类型智能切换 LLM 模型，兼顾质量与成本
  </p>
</p>

> [!CAUTION]
> **本版本为 MVP 测试版（Alpha）**，仅用于内部功能验证与早期测试。  
> API 和配置格式可能在后续版本中发生重大变化，不建议在生产环境使用。

---

## 📋 版本说明

| 项目 | 说明 |
|:-----|:-----|
| **版本号** | MVP v0.1.0 (Alpha) |
| **发布日期** | 2026-04-06 |
| **版本类型** | 测试版 — 功能验证阶段 |
| **目标** | 实现最小闭环：任务评估 → 路由查询 → 阈值判定 → 模型切换 |
| **稳定性** | ⚠️ 不稳定，接口可能变更 |

---

## 💡 项目简介

在 OpenClaw 多智能体系统中，每个 Agent 绑定固定的 LLM 模型。然而实际场景中，任务的复杂度差异巨大——从简单的问答闲聊到复杂的架构设计和逻辑推理。固定绑定单一模型会导致两个核心问题：

| 问题 | 描述 |
|:-----|:-----|
| **能力不足** | 轻量模型面对复杂推理任务时质量下降 |
| **资源浪费** | 高性能模型处理简单任务时造成不必要的 Token 消耗 |

**Auto-Switch-Skill** 通过「任务×模型适配度矩阵」驱动的智能路由系统，让 Agent 自动选择最合适的模型，在**保证任务质量的同时优化成本**。

---

## ✅ MVP 已实现功能

### 核心模块

| 模块 | 文件 | 状态 | 说明 |
|:-----|:-----|:----:|:-----|
| **任务评估器** | `src/core/evaluator.py` | ✅ | 从 thought/thinking 字段解析 `[TASK_TYPE: XXX]` 标签 |
| **路由引擎** | `src/core/router.py` | ✅ | 查询适配度矩阵，判定是否切换，返回推荐模型 |
| **状态管理** | `src/core/state.py` | ✅ | 管理运行模式、冷却期、切换计数等会话级状态 |
| **命令处理器** | `src/skills/ms_command.py` | ✅ | `/ms` 命令解析与 7 个子命令分发 |
| **输出格式化** | `src/utils/formatter.py` | ✅ | 路由表、模型列表、状态信息的格式化输出 |
| **配置加载** | `src/config/loader.py` | ✅ | JSON 格式路由矩阵加载器 |
| **矩阵生成** | `scripts/generate_matrix.py` | ✅ | 从 openclaw.json + model_profiles.yaml 自动生成路由矩阵 |
| **CLI 入口** | `scripts/ms_cli.py` | ✅ | Shell 命令行入口，适配容器环境 |
| **Skill 入口** | `SKILL.md` | ✅ | OpenClaw Skill 规范文件 |

### 已实现的 `/ms` 命令

| 命令 | 说明 | 状态 |
|:-----|:-----|:----:|
| `/ms help` | 显示帮助信息 | ✅ |
| `/ms status` | 查看运行状态（模型、模式、冷却、切换次数） | ✅ |
| `/ms list` | 列出所有可用模型 | ✅ |
| `/ms router` | 查看任务模型路由表 | ✅ |
| `/ms auto` | 恢复自动切换模式 | ✅ |
| `/ms manual` | 切换到手动模式 | ✅ |
| `/ms <模型名>` | 切换到指定模型 | ✅ |

### 测试覆盖

| 测试文件 | 覆盖模块 | 状态 |
|:---------|:---------|:----:|
| `tests/test_evaluator.py` | 任务类型解析 | ✅ |
| `tests/test_router.py` | 路由引擎 | ✅ |
| `tests/test_state.py` | 状态管理 | ✅ |
| `tests/test_ms_command.py` | 命令处理 | ✅ |
| `tests/test_generate_matrix.py` | 矩阵生成 | ✅ |
| `tests/test_integration.py` | 端到端集成 | ✅ |

---

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                      Auto-Switch-Skill MVP                      │
├──────────────┬──────────────┬───────────────┬───────────────────┤
│ 任务评估模块 │ 路由引擎模块 │ 状态管理模块  │ 命令处理模块      │
│ (evaluator)  │ (router)     │ (state)       │ (ms_command)      │
├──────────────┼──────────────┼───────────────┼───────────────────┤
│ 配置加载模块 │ 输出格式化   │ CLI 入口      │ 矩阵生成器        │
│ (loader)     │ (formatter)  │ (ms_cli)      │ (generate_matrix) │
└──────────────┴──────────────┴───────────────┴───────────────────┘
```

### MVP 切换决策流程

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
         ├── 手动模式 → 跳过评估
         │
         └── 自动模式
              │
              ▼
         [模型自评估] → 解析 thought 字段，提取 [TASK_TYPE: XXX]
              │
              ├── 解析失败 → 跳过切换
              │
              └── 成功获取任务类型
                   │
                   ▼
              [适配度矩阵查询]
                   │
                   推荐模型 = 该任务最高权重模型
                   权重差 = 推荐权重 - 当前权重
                   │
                   ▼
              权重差 > 15 且 推荐 ≠ 当前？
                   │
                   ├── 否 → 不切换
                   │
                   └── 是 → 切换次数 < 30？
                            │
                            ├── 否 → 不切换
                            │
                            └── 是 → ✅ 执行切换
```

---

## 📂 项目结构

```
auto-switch-skill/
├── README.md                          # 项目说明（本文件，测试版）
├── README_original.md                 # 原始项目说明（完整版路线）
├── LICENSE                            # MIT 许可证
├── SKILL.md                           # OpenClaw Skill 入口文件
│
├── config/                            # 运行时配置
│   ├── model_profiles.yaml            # 内置模型能力画像库（70+ 模型）
│   ├── routing_matrix.json            # 自动生成的路由矩阵（JSON）
│   ├── routing_matrix.yaml            # 自动生成的路由矩阵（YAML）
│   └── settings.yaml                  # 运行时配置（阈值、冷却等）
│
├── scripts/                           # 脚本工具
│   ├── generate_matrix.py             # 路由矩阵自动生成器
│   └── ms_cli.py                      # CLI 命令行入口
│
├── src/                               # 源码
│   ├── __init__.py
│   ├── config/                        # 配置管理
│   │   ├── __init__.py
│   │   ├── schema.py                  # 数据模型定义
│   │   └── loader.py                  # 配置加载器
│   ├── core/                          # 核心逻辑
│   │   ├── __init__.py
│   │   ├── evaluator.py               # 任务类型评估器
│   │   ├── router.py                  # 路由引擎
│   │   └── state.py                   # 运行时状态管理
│   ├── skills/                        # Skill 命令处理
│   │   ├── __init__.py
│   │   └── ms_command.py              # /ms 命令处理器
│   └── utils/                         # 工具函数
│       ├── __init__.py
│       └── formatter.py               # 输出格式化
│
├── tests/                             # 测试
│   ├── conftest.py                    # 测试夹具
│   ├── test_evaluator.py             # 评估器测试
│   ├── test_router.py                # 路由引擎测试
│   ├── test_state.py                 # 状态管理测试
│   ├── test_ms_command.py            # 命令处理测试
│   ├── test_generate_matrix.py       # 矩阵生成测试
│   └── test_integration.py           # 集成测试
│
├── docs/                              # 文档
│   ├── requirements.md                # 完整需求文档（v1.4）
│   ├── requirements_mvp.md            # MVP 需求文档
│   ├── technical_design.md            # 技术设计文档
│   ├── benchmark_mapping.md           # Benchmark 映射方案
│   ├── model_profiles.yaml            # 模型画像库参考
│   └── discussion_notes.md            # 设计讨论记录
│
└── examples/                          # 示例（待完善）
```

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- [OpenClaw](https://github.com/anthropics/openclaw) 多智能体框架
- **无第三方库依赖**（仅使用标准库 `json`, `re`, `argparse`）

### 安装

```bash
# 克隆仓库
git clone https://github.com/Lyndon-wong/auto-switch-skill.git

# 进入项目目录
cd auto-switch-skill
```

### 在 OpenClaw 中使用

#### 方式 1：使用预生成的路由矩阵（推荐）

路由矩阵 `config/routing_matrix.json` 已预生成，无需额外操作。
将项目目录拷贝或链接到 OpenClaw 的 skills 目录即可。

#### 方式 2：重新生成路由矩阵

在**宿主机**上运行（需要 `pyyaml`）：

```bash
python3 scripts/generate_matrix.py \
    --openclaw-config /path/to/openclaw.json \
    --profiles config/model_profiles.yaml \
    --output config/routing_matrix.json
```

### CLI 使用示例

```bash
# 查看帮助
python3 scripts/ms_cli.py help

# 查看运行状态
python3 scripts/ms_cli.py status \
  --config-dir config \
  --current-model "sjtu/minimax-m2.5"

# 列出可用模型
python3 scripts/ms_cli.py list \
  --config-dir config \
  --current-model "sjtu/minimax-m2.5"

# 查看路由表
python3 scripts/ms_cli.py router --config-dir config

# 切换模型
python3 scripts/ms_cli.py switch \
  --target "sjtu/deepseek-v3.2" \
  --config-dir config \
  --current-model "sjtu/minimax-m2.5"
```

---

## 🗺️ 路由矩阵示例

系统根据 [Benchmark 数据](docs/benchmark_mapping.md) 与已注册模型自动生成适配度矩阵：

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

权重参考标准：

| 权重范围 | 含义 |
|:---------|:-----|
| 90-100 | 最佳适配（首选模型） |
| 70-89 | 高度适配 |
| 50-69 | 基本适配 |
| 30-49 | 勉强适配 |
| 0-29 | 不推荐 |

---

## ⚙️ MVP 核心参数

| 参数 | 值 | 说明 |
|:-----|:---|:-----|
| 权重差阈值 | 15 | 推荐模型与当前模型权重差超过此值才触发切换 |
| 冷却期 | 3 轮 | 切换后 3 轮内不再评估（硬编码） |
| 切换上限 | 30 次 | 单会话最大切换次数 |
| 默认权重 | 3 | 未匹配画像的模型默认权重 |
| 任务类型 | 10 种 | CHAT, QA, SUM, TRA, CS, CC, REA, ANA, CRE, MS |

---

## 🔬 已验证的技术要点

- ✅ **`session_status` API**：OpenClaw 容器中 `session_status(model="...")` 可执行 per-session 模型覆盖
- ✅ **无外部依赖**：CLI 入口仅使用 Python 标准库（`json`, `re`, `argparse`），适配容器环境
- ✅ **模糊匹配**：支持从 `openclaw.json` 的 `provider/model` 格式匹配到画像库
- ✅ **JSON 输出**：CLI 命令结果通过 `__JSON_RESULT__:` 前缀输出结构化 JSON

---

## 🚧 已知限制

> [!WARNING]
> 以下为当前测试版的已知限制，将在后续版本中改进。

1. **无上下文管理**：切换模型时不保存/恢复上下文，依赖 OpenClaw 原生上下文处理
2. **无势能累积**：使用简单阈值判定，不累积切换势能（可能导致边界值抖动）
3. **无持久化状态**：模式和切换计数仅在会话内有效，重启后重置
4. **画像匹配有限**：部分模型（如 `qwen3vl`）可能无法匹配到画像，使用默认低权重
5. **无调试脚注**：不支持 `/ms debug` 等高级调试功能

---

## 🛣️ 开发路线

### Phase 1：MVP — 命令框架与路由引擎 `✅ 已完成`
- [x] 需求文档与技术设计文档
- [x] 内置模型画像库（70+ 模型）
- [x] 路由矩阵自动生成器
- [x] 配置加载与数据模型
- [x] 任务类型评估器
- [x] 路由引擎（矩阵查询 + 阈值判定）
- [x] 状态管理器（模式 + 冷却 + 计数）
- [x] `/ms` 命令处理器（7 个子命令）
- [x] CLI 入口（`ms_cli.py`）
- [x] OpenClaw Skill 入口（`SKILL.md`）
- [x] 单元测试 + 集成测试

### Phase 2：智能切换 + 上下文管理 `🔜 规划中`
- [ ] 切换势能累积 + 上下文惯性机制
- [ ] 三层记忆栈框架（L1/L2/L3）
- [ ] 智能提取管道（扫描→分类→提取→校验）
- [ ] `/ms set`、`/ms reset`、`/ms debug`、`/ms history` 命令
- [ ] 可配置冷却期与非对称阈值

### Phase 3：增强与优化 `📋 待定`
- [ ] 增量摘要 DAG 引擎
- [ ] 切换统计与成本分析（`/ms stats`）
- [ ] 记忆管理（`/ms memory`、`/ms pin`）
- [ ] 配置导入/导出（`/ms export`、`/ms import`）
- [ ] 多 Agent 协同切换
- [ ] 端到端测试套件

---

## 🤝 参与贡献

欢迎参与测试和反馈！本项目当前处于早期测试阶段，特别需要以下方面的反馈：

1. **功能验证**：在 OpenClaw 环境中测试各 `/ms` 命令
2. **路由准确性**：模型匹配和任务路由是否合理
3. **边界场景**：发现切换逻辑的异常行为

请通过 GitHub Issues 提交问题和建议。

---

## 📄 许可证

[MIT License](LICENSE)

## 🔗 相关项目

- [OpenClaw](https://github.com/anthropics/openclaw) — 多智能体协作框架

---

<p align="center">
  <sub>⚠️ Auto-Switch-Skill MVP v0.1.0 测试版 — 仅供内部测试使用</sub>
</p>
