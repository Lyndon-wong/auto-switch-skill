# Benchmark → 任务类型映射方案

> **目的**：为 `model_profiles.yaml` 中每个任务类型的权重值提供可追溯的 Benchmark 数据支撑。
> **版本**：v1.0 | 2026-04-05

---

## 一、推荐 Benchmark 矩阵

下表列出每个任务类型对应的最佳 Benchmark，以及为什么选它。

| 任务类型 | 主参考 Benchmark | 辅助参考 | 为什么选这个 |
|:---------|:----------------|:---------|:------------|
| **CHAT** | LMSYS Chatbot Arena — Overall Elo | Artificial Analysis Quality Index | Arena 是唯一基于**真人盲测**的对话偏好排名，最贴近用户对"聊天体验"的主观感受 |
| **QA** | MMLU-Pro / MMLU-Redux | OpenCompass 综合分 | 知识问答本质是事实准确率，MMLU 系列覆盖 57+ 学科知识 |
| **SUMMARIZE** | LMSYS Arena — Long Context 子榜 | LongBench / InfiniteBench | 摘要能力强依赖长上下文理解，Arena 的 Long Context 分榜直接衡量这一点 |
| **TRANSLATE** | WMT25 人工评估排名 | FLORES-200 | WMT 是翻译领域的"奥林匹克"，人工评估（MQM/ESA）比自动指标更可靠 |
| **CODE_SIMPLE** | LiveCodeBench（简单/中等难度子集） | HumanEval+ / MBPP+ | LiveCodeBench 持续更新、抗污染；HumanEval/MBPP 已饱和但可辅助参考 |
| **CODE_COMPLEX** | SWE-bench Verified | SWE-bench Pro / Terminal-Bench | SWE-bench 是仓库级软件工程的金标准，衡量多文件修改、API 迁移等真实能力 |
| **REASONING** | AIME 2025 + GPQA Diamond | MATH-500 / Humanity's Last Exam | AIME 衡量多步数学推理，GPQA 衡量博士级科学推理，两者互补 |
| **ANALYSIS** | LMSYS Arena — Long Context 子榜 | LongBench / Doc-level QA | 长文档分析本质是长上下文理解+信息提取+总结，Arena 长上下文子榜最直接 |
| **CREATIVE** | LMSYS Arena — Creative Writing 子榜 | EQ-Bench / WritingBench | Arena 的创意写作子榜基于真人偏好评分，最贴近"创意质量"感知 |
| **MULTI_STEP** | OSWorld / Terminal-Bench（Agent 基准） | WebArena / AgentBench | 多步骤任务本质是 Agent 能力，OSWorld/Terminal-Bench 衡量真实环境下的自主规划和执行 |

---

## 二、关键 Benchmark 数据摘要（2026.04）

### 2.1 LMSYS Chatbot Arena — Overall Elo（→ CHAT）

| 排名 | 模型 | Elo |
|:-----|:-----|:----|
| 1 | GPT-5.4 Pro | 1502 |
| 2 | Claude Opus 4.6 | 1494 |
| 3 | GPT-5.4 Thinking | 1488 |
| 4 | Gemini 3.1 Pro | 1476 |
| 5 | Claude Sonnet 4.6 | 1468 |
| 6 | DeepSeek V3.2 Speciale | 1451 |
| 7 | Qwen3-Max-Instruct | 1445 |
| 8 | GPT-5.2 Pro | 1439 |
| 9 | Llama 4 (81B) | 1428 |
| 10 | Gemini 3.1 Flash | 1412 |

> ⚠️ Coding 子榜中 Claude Opus 4.6 以 Elo 1515 排名第一。

### 2.2 SWE-bench Verified（→ CODE_COMPLEX）

| 排名 | 模型 | 通过率 |
|:-----|:-----|:------|
| 1 | Claude Opus 4.5 | ~80.9% |
| 2 | Claude Opus 4.6 | ~80.8% |
| 3 | Gemini 3.1 Pro | ~80.6% |
| 4 | MiniMax M2.5 | ~80.2% |
| 5 | GPT-5.2 | ~80.0% |
| 6 | Claude Sonnet 4.6 | ~79.6% |
| 7 | GLM-5.1 | ~77.8% |
| 8 | Kimi K2.5 | ~76.8% |
| 9 | DeepSeek V3.2 | ~73.0% |

### 2.3 AIME + GPQA Diamond（→ REASONING）

| 模型系列 | AIME 大致得分 | GPQA Diamond |
|:---------|:------------|:-------------|
| OpenAI o3 / o3-pro | 96%–98% | 83%–88% |
| Claude 4.x 系列 | 很高（具体因版本而异） | 80%–95%+ |
| Gemini 3.1 Pro | ~90%+ | ~90%+ |
| DeepSeek R1 | 79%–91%（随版本提升） | 71%–81% |

### 2.4 WMT25 人工评估（→ TRANSLATE）

| 表现等级 | 代表模型 |
|:---------|:--------|
| 第一梯队 | Gemini 2.5 Pro, GPT-4.1 |
| 准第一梯队 | GPT-5 系列, Claude 4/4.5, Gemini 3.0 Pro |
| 高竞争力开源 | DeepSeek-V3, Qwen 3, Llama 4 |
| 优化自动指标 | Hunyuan-MT（自动指标分高但人工评估不如上述） |

### 2.5 LiveCodeBench（→ CODE_SIMPLE）

> HumanEval/MBPP 已饱和（头部模型 85-90%+ 无区分度）。LiveCodeBench 持续更新，抗数据污染。

| 表现等级 | 代表模型 |
|:---------|:--------|
| 顶级 | Gemini 3 Pro, DeepSeek V3.2 Speciale, GPT-5 系列 |
| 高竞争力 | Claude Opus/Sonnet 4.6, MiniMax M2.5, GLM-5.1 |
| 中等 | Qwen3-Max, Llama 4-70B |

---

## 三、权重换算方法论

### 3.1 标准化思路

不同 Benchmark 的分数量纲完全不同（Elo 1200-1500 vs. 百分比 0-100% vs. 排名 1-N），需要统一换算为 0-100 权重。

**推荐方法：分位归一化（Percentile Normalization）**

```
步骤：
1. 对每个 Benchmark，收集所有已知模型的原始分数
2. 计算每个模型的百分位排名：percentile = (排名位置 / 模型总数) × 100
3. 映射到权重：
   - Top 5%  → 权重 90-100
   - 5%-20%  → 权重 70-89
   - 20%-50% → 权重 50-69
   - 50%-80% → 权重 30-49
   - 80%-100% → 权重 0-29
4. 对于无数据的模型，使用"模型家族最近画像"或默认值 3
```

### 3.2 换算示例

以 CHAT 任务（LMSYS Arena Elo）为例：

```
原始 Elo 范围：约 1100（最低模型）~ 1502（GPT-5.4 Pro）
有效区间：约 400 点

GPT-5.4 Pro:   Elo 1502 → Top 1% → 权重 ≈ 95
Claude Opus 4.6: Elo 1494 → Top 2% → 权重 ≈ 92
Gemini 3.1 Pro: Elo 1476 → Top 5% → 权重 ≈ 88
Qwen3-Max:     Elo 1445 → Top 10% → 权重 ≈ 80
Llama 4 (81B): Elo 1428 → Top 15% → 权重 ≈ 75
GPT-4o-mini:   Elo ~1380 → Top 30% → 权重 ≈ 65
Qwen-2.5-7B:   Elo ~1200 → Top 70% → 权重 ≈ 35
```

以 CODE_COMPLEX 任务（SWE-bench Verified）为例：

```
原始分数范围：约 10%（最低模型）~ 80.9%（Claude Opus）
有效区间：约 70 个百分点

Claude Opus 4.6: 80.8% → Top 2% → 权重 ≈ 96
Gemini 3.1 Pro:  80.6% → Top 3% → 权重 ≈ 94
GPT-5.2:         80.0% → Top 5% → 权重 ≈ 90
GLM-5.1:         77.8% → Top 10% → 权重 ≈ 82
DeepSeek V3.2:   73.0% → Top 15% → 权重 ≈ 78
Qwen-2.5-72B:    ~55%  → Top 35% → 权重 ≈ 60
Qwen-2.5-7B:     ~15%  → Top 85% → 权重 ≈ 15
```

### 3.3 多 Benchmark 融合

部分任务类型参考了多个 Benchmark，融合策略：

| 任务类型 | 主 Benchmark 权重 | 辅助 Benchmark 权重 |
|:---------|:-----------------|:-------------------|
| CHAT | Arena Overall 100% | — |
| CODE_SIMPLE | LiveCodeBench 70% | HumanEval+ 30% |
| CODE_COMPLEX | SWE-bench Verified 70% | SWE-bench Pro 30% |
| REASONING | AIME 50% | GPQA Diamond 50% |
| ANALYSIS | Arena Long Context 60% | LongBench 40% |
| TRANSLATE | WMT25 人工 80% | FLORES-200 20% |

---

## 四、数据局限性说明

| 局限 | 影响范围 | 缓解方式 |
|:-----|:--------|:---------|
| **部分模型无公开 Benchmark 数据** | 小米 MiMo、商汤、百川、讯飞等 | 基于同规模/同家族模型推测 + 标注为"估算" |
| **Benchmark 版本不一致** | 不同来源报告的分数基于不同版本的测试集 | 尽量使用同一时期（2026 Q1）的数据 |
| **Agent 类 Benchmark 还在早期** | MULTI_STEP 任务缺乏成熟的横向对比数据 | 以 OSWorld/Terminal-Bench 定性排名为主 |
| **翻译特定语言对差异大** | 中→英 vs. 英→日 表现不同 | 取多语言对的平均表现 |
| **创意评估主观性强** | Arena Creative Writing 依赖人类偏好 | 接受主观性，作为"最不坏"的参考 |

---

## 五、数据源清单

| 来源 | 链接 | 覆盖任务 |
|:-----|:-----|:---------|
| LMSYS Chatbot Arena | https://lmarena.ai/ | CHAT, CREATIVE, SUMMARIZE, ANALYSIS |
| SWE-bench | https://www.swebench.com/ | CODE_COMPLEX |
| LiveCodeBench | https://livecodebench.github.io/ | CODE_SIMPLE |
| Artificial Analysis | https://artificialanalysis.ai/ | 综合质量/速度/价格 |
| OpenCompass | https://opencompass.org.cn/ | QA（MMLU系列）、国产模型综合 |
| WMT (ACL Anthology) | https://aclanthology.org/ | TRANSLATE |
| OSWorld / AgentBench | 相关论文 | MULTI_STEP |
| BenchLM | https://benchlm.ai/ | 多维度综合 |

> 💡 **建议**：在实际实现中，可以编写一个脚本定期从上述 API/网页抓取最新数据，自动更新 `model_profiles.yaml` 中的权重值。这样画像库就能随行业发展自动演进。
