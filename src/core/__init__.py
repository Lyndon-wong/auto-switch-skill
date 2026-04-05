# 核心业务逻辑模块
"""
核心业务逻辑子系统 — 包含任务评估、状态管理和路由引擎。
"""

# MVP 硬编码常量
COOLDOWN_ROUNDS = 3              # 切换后冷却轮数
MAX_SWITCHES_PER_SESSION = 30    # 单会话最大切换次数
WEIGHT_DIFF_THRESHOLD = 15       # 权重差阈值
DEFAULT_WEIGHT = 3               # 未匹配画像的默认权重

# 有效任务类型集合
VALID_TASK_TYPES = frozenset({
    "CHAT", "QA", "SUMMARIZE", "TRANSLATE",
    "CODE_SIMPLE", "CODE_COMPLEX", "REASONING",
    "ANALYSIS", "CREATIVE", "MULTI_STEP",
})

# 任务类型缩写映射
TASK_TYPE_ABBREV = {
    "CHAT": "CHAT", "QA": "QA", "SUM": "SUMMARIZE",
    "TRA": "TRANSLATE", "CS": "CODE_SIMPLE", "CC": "CODE_COMPLEX",
    "REA": "REASONING", "ANA": "ANALYSIS", "CRE": "CREATIVE",
    "MS": "MULTI_STEP",
}

# 任务类型中文名映射
TASK_TYPE_NAMES = {
    "CHAT": "日常对话",
    "QA": "知识问答",
    "SUMMARIZE": "摘要生成",
    "TRANSLATE": "翻译",
    "CODE_SIMPLE": "简单编程",
    "CODE_COMPLEX": "复杂编程",
    "REASONING": "逻辑推理",
    "ANALYSIS": "深度分析",
    "CREATIVE": "创意生成",
    "MULTI_STEP": "多步骤任务",
}
