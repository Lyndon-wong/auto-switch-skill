# 配置数据模型定义
"""
定义 Auto-Switch-Skill 配置系统的所有数据结构。

核心数据结构：
- ModelEntry: 单个模型条目
- TaskTypeEntry: 任务类型定义
- RoutingMatrix: 任务×模型 权重矩阵
- AutoSwitchConfig: 顶层配置容器
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelEntry:
    """模型条目

    Attributes:
        id: 模型完整标识，格式为 "厂商/模型名"，如 "OpenAI/GPT-4o"
        alias: 用户友好的短别名，用于 /ms 命令，如 "gpt4"
        metadata: 可选的附加元数据（如价格、上下文窗口大小等）
    """

    id: str
    alias: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.alias:
            # 自动从 id 生成别名：取 / 后面的部分，转小写，去掉点号
            parts = self.id.split("/")
            self.alias = parts[-1].lower().replace(".", "-")


@dataclass
class TaskTypeEntry:
    """任务类型定义

    Attributes:
        id: 任务类型标识符，如 "CODE_COMPLEX"
        description: 任务类型的中文描述，用于 System Prompt 指引模型分类
    """

    id: str
    description: str


@dataclass
class RoutingMatrix:
    """任务×模型 权重矩阵

    核心数据结构，存储每个任务类型对每个模型的适配权重（0-100）。

    Attributes:
        models: 已注册的模型列表
        task_types: 任务类型定义列表
        matrix: 二维权重矩阵，格式为 {task_type_id: {model_id: weight}}
    """

    models: list[ModelEntry] = field(default_factory=list)
    task_types: list[TaskTypeEntry] = field(default_factory=list)
    matrix: dict[str, dict[str, int]] = field(default_factory=dict)

    def get_weight(self, task_type: str, model_id: str) -> int:
        """获取指定任务类型对指定模型的权重

        Args:
            task_type: 任务类型标识
            model_id: 模型 ID

        Returns:
            权重值（0-100），如果未找到返回 0
        """
        return self.matrix.get(task_type, {}).get(model_id, 0)

    def set_weight(self, task_type: str, model_id: str, weight: int) -> None:
        """设置指定任务类型对指定模型的权重

        Args:
            task_type: 任务类型标识
            model_id: 模型 ID
            weight: 权重值（0-100）

        Raises:
            ValueError: 权重值超出范围
        """
        if not 0 <= weight <= 100:
            raise ValueError(f"权重值必须在 0-100 之间，收到: {weight}")
        if task_type not in self.matrix:
            self.matrix[task_type] = {}
        self.matrix[task_type][model_id] = weight

    def get_ranking(self, task_type: str) -> list[tuple[str, int]]:
        """获取某任务类型下所有模型按权重排序的列表

        Args:
            task_type: 任务类型标识

        Returns:
            按权重从高到低排序的 (model_id, weight) 列表
        """
        weights = self.matrix.get(task_type, {})
        return sorted(weights.items(), key=lambda x: x[1], reverse=True)

    def get_model_ids(self) -> list[str]:
        """获取所有已注册模型的 ID 列表"""
        return [m.id for m in self.models]

    def get_task_type_ids(self) -> list[str]:
        """获取所有任务类型的 ID 列表"""
        return [t.id for t in self.task_types]

    def get_model_by_alias(self, alias: str) -> ModelEntry | None:
        """通过别名查找模型

        Args:
            alias: 模型别名

        Returns:
            匹配的 ModelEntry，未找到返回 None
        """
        for model in self.models:
            if model.alias == alias:
                return model
        return None

    def get_model_by_id(self, model_id: str) -> ModelEntry | None:
        """通过 ID 查找模型

        Args:
            model_id: 模型 ID

        Returns:
            匹配的 ModelEntry，未找到返回 None
        """
        for model in self.models:
            if model.id == model_id:
                return model
        return None

    def add_model(self, model: ModelEntry, default_weight: int = 3) -> None:
        """添加模型到矩阵

        Args:
            model: 模型条目
            default_weight: 该模型在所有任务类型上的默认权重
        """
        if self.get_model_by_id(model.id) is not None:
            raise ValueError(f"模型 '{model.id}' 已存在")
        self.models.append(model)
        # 为所有任务类型添加默认权重
        for task_type_id in self.get_task_type_ids():
            if task_type_id not in self.matrix:
                self.matrix[task_type_id] = {}
            self.matrix[task_type_id][model.id] = default_weight

    def remove_model(self, model_id: str) -> None:
        """从矩阵中移除模型

        Args:
            model_id: 要移除的模型 ID

        Raises:
            ValueError: 模型不存在
        """
        model = self.get_model_by_id(model_id)
        if model is None:
            raise ValueError(f"模型 '{model_id}' 不存在")
        self.models.remove(model)
        # 从所有任务类型中移除该模型的权重
        for task_weights in self.matrix.values():
            task_weights.pop(model_id, None)

    def add_task_type(
        self, task_type: TaskTypeEntry, default_weight: int = 3
    ) -> None:
        """添加新的任务类型

        Args:
            task_type: 任务类型条目
            default_weight: 所有模型在该任务上的默认权重
        """
        existing_ids = self.get_task_type_ids()
        if task_type.id in existing_ids:
            raise ValueError(f"任务类型 '{task_type.id}' 已存在")
        self.task_types.append(task_type)
        # 为该任务类型创建默认权重行
        self.matrix[task_type.id] = {
            m.id: default_weight for m in self.models
        }

    def remove_task_type(self, task_type_id: str) -> None:
        """从矩阵中移除任务类型

        Args:
            task_type_id: 要移除的任务类型 ID

        Raises:
            ValueError: 任务类型不存在
        """
        task = None
        for t in self.task_types:
            if t.id == task_type_id:
                task = t
                break
        if task is None:
            raise ValueError(f"任务类型 '{task_type_id}' 不存在")
        self.task_types.remove(task)
        self.matrix.pop(task_type_id, None)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（用于 YAML 输出）"""
        return {
            "models": [
                {"id": m.id, "alias": m.alias, **m.metadata}
                for m in self.models
            ],
            "task_types": {t.id: t.description for t in self.task_types},
            "routing_matrix": copy.deepcopy(self.matrix),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoutingMatrix:
        """从字典反序列化

        Args:
            data: 包含 models、task_types、routing_matrix 的字典

        Returns:
            RoutingMatrix 实例
        """
        models = []
        for m in data.get("models", []):
            model_id = m.pop("id")
            alias = m.pop("alias", "")
            models.append(ModelEntry(id=model_id, alias=alias, metadata=m))

        task_types = []
        for tid, desc in data.get("task_types", {}).items():
            task_types.append(TaskTypeEntry(id=tid, description=desc))

        matrix = data.get("routing_matrix", {})

        return cls(models=models, task_types=task_types, matrix=matrix)

    def format_table(self) -> str:
        """以可读表格形式格式化矩阵

        Returns:
            格式化后的表格字符串
        """
        if not self.models or not self.task_types:
            return "（矩阵为空）"

        # 计算列宽
        model_labels = [
            m.alias if m.alias else m.id.split("/")[-1]
            for m in self.models
        ]
        task_col_width = max(len(t.id) for t in self.task_types) + 2
        model_col_width = max(len(l) for l in model_labels) + 2
        model_col_width = max(model_col_width, 6)

        # 表头
        header = "任务类型".ljust(task_col_width)
        for label in model_labels:
            header += label.center(model_col_width)
        lines = [header, "─" * len(header)]

        # 每行数据
        for task_type in self.task_types:
            row = task_type.id.ljust(task_col_width)
            for model in self.models:
                w = self.get_weight(task_type.id, model.id)
                row += str(w).center(model_col_width)
            lines.append(row)

        return "\n".join(lines)


@dataclass
class DampingConfig:
    """阻尼系统配置

    基于权重差动态调整势能增量。

    Attributes:
        upgrade_threshold: 升级触发阈值（越小越敏感）
        downgrade_threshold: 降级触发阈值（越大越保守）
        decay_rate: 一致时每轮势能衰减量
        cooldown_rounds: 切换后冷却轮数
        weight_delta_tiers: 权重差→势能增量的分级配置
    """

    upgrade_threshold: int = 50
    downgrade_threshold: int = 80
    decay_rate: int = 30
    cooldown_rounds: int = 3

    # 权重差→势能增量的分级配置
    # 格式: [(最小权重差, 势能增量), ...]，按权重差从大到小排序
    weight_delta_tiers: list[tuple[int, int]] = field(
        default_factory=lambda: [
            (50, 45),  # 权重差 > 50 → 增量 45（巨大差距，快速切换）
            (30, 35),  # 权重差 > 30 → 增量 35（明显差距）
            (15, 25),  # 权重差 > 15 → 增量 25（中等差距）
            (0, 10),   # 权重差 <= 15 → 增量 10（差距不大）
        ]
    )

    def get_increment(self, weight_delta: int) -> int:
        """根据权重差获取势能增量

        Args:
            weight_delta: 最优模型与当前模型的权重差（绝对值）

        Returns:
            势能增量
        """
        abs_delta = abs(weight_delta)
        for min_delta, increment in self.weight_delta_tiers:
            if abs_delta > min_delta:
                return increment
        # 默认返回最小增量
        return self.weight_delta_tiers[-1][1] if self.weight_delta_tiers else 10


@dataclass
class InertiaConfig:
    """上下文惯性配置

    Attributes:
        enabled: 是否启用惯性机制
        threshold_multiplier: 惯性生效时阈值放大倍数
        topic_change_keywords: 话题转换信号词
        idle_reset_minutes: 超时重置惯性的分钟数
    """

    enabled: bool = True
    threshold_multiplier: float = 1.5
    topic_change_keywords: list[str] = field(
        default_factory=lambda: [
            "新的需求", "另一个问题", "换个话题", "接下来",
            "新任务", "下一个", "别的事情",
        ]
    )
    idle_reset_minutes: int = 30


@dataclass
class SwitcherConfig:
    """切换策略总配置

    Attributes:
        max_switches_per_session: 单会话最大切换次数
        require_confirm_for_top: 切换到最高权重模型时是否需要用户确认
        damping: 阻尼系统配置
        inertia: 上下文惯性配置
    """

    max_switches_per_session: int = 10
    require_confirm_for_top: bool = False
    damping: DampingConfig = field(default_factory=DampingConfig)
    inertia: InertiaConfig = field(default_factory=InertiaConfig)


@dataclass
class StrategicMemoryConfig:
    """L1 战略层配置"""

    max_tokens: int = 2000
    pin_enabled: bool = True
    auto_dedup: bool = True


@dataclass
class SummaryChainConfig:
    """L2 摘要链配置"""

    max_tokens: int = 4000
    merge_trigger: str = "depth_count"
    merge_threshold: int = 3
    compression_ratio: float = 0.4
    importance_decay_normal: float = 1.0
    importance_decay_decision: float = 0.5
    importance_decay_pin: float = 0.0
    importance_discard_threshold: int = 3


@dataclass
class WorkingMemoryConfig:
    """L3 工作区配置"""

    preserve_recent_rounds: int = 5


@dataclass
class ExtractionPipelineConfig:
    """提取管道配置"""

    executor: str = "current_model"
    validation_enabled: bool = True
    abort_on_validation_fail: bool = True


@dataclass
class SwitchComposerConfig:
    """切换重组配置"""

    inject_l1_full: bool = True
    inject_l2_recent_count: int = 3
    inject_l2_root: bool = True
    max_memory_ratio: float = 0.05


@dataclass
class ContextConfig:
    """上下文管理配置（三层记忆栈）

    Attributes:
        strategy: 上下文策略
        strategic_memory: L1 战略层
        summary_chain: L2 摘要链
        working_memory: L3 工作区
        extraction_pipeline: 提取管道
        switch_composer: 切换重组
    """

    strategy: str = "memory_stack"
    strategic_memory: StrategicMemoryConfig = field(
        default_factory=StrategicMemoryConfig
    )
    summary_chain: SummaryChainConfig = field(
        default_factory=SummaryChainConfig
    )
    working_memory: WorkingMemoryConfig = field(
        default_factory=WorkingMemoryConfig
    )
    extraction_pipeline: ExtractionPipelineConfig = field(
        default_factory=ExtractionPipelineConfig
    )
    switch_composer: SwitchComposerConfig = field(
        default_factory=SwitchComposerConfig
    )


@dataclass
class EvaluatorConfig:
    """评估器配置"""

    method: str = "self_eval"
    output_field: str = "thought"
    output_format: str = "[TASK_TYPE: {type}]"


@dataclass
class AutoSwitchConfig:
    """Auto-Switch-Skill 顶层配置容器

    Attributes:
        enabled: 全局开关
        evaluator: 评估器配置
        routing: 权重矩阵（核心）
        switcher: 切换策略配置
        context: 上下文管理配置
    """

    enabled: bool = True
    evaluator: EvaluatorConfig = field(default_factory=EvaluatorConfig)
    routing: RoutingMatrix = field(default_factory=RoutingMatrix)
    switcher: SwitcherConfig = field(default_factory=SwitcherConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
