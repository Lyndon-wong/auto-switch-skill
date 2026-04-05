# 任务类型解析器
"""
从模型的 thought/thinking 字段中解析任务类型标签，
并结合路由矩阵生成评估结果。

设计原则：解析失败时返回 None，绝不抛异常，静默跳过。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config.schema import RoutingMatrix

from src.core import VALID_TASK_TYPES


@dataclass
class TaskEvaluation:
    """任务评估结果

    Attributes:
        task_type: 解析出的任务类型，如 "CODE_COMPLEX"
        recommended_model: 该任务类型下权重最高的模型 ID
        recommended_weight: 推荐模型在该任务上的权重（0-100）
        current_weight: 当前模型在该任务上的权重（0-100）
        weight_diff: 推荐权重 - 当前权重
    """

    task_type: str
    recommended_model: str
    recommended_weight: int
    current_weight: int
    weight_diff: int


class TaskEvaluator:
    """任务类型解析器

    职责：
    1. 从 thought 文本中提取任务类型标签
    2. 查询路由矩阵，找到推荐模型
    3. 计算权重差，返回评估结果
    """

    # 解析正则（编译为类属性，避免重复编译）
    TASK_TYPE_PATTERN = re.compile(r'\[TASK_TYPE:\s*(\w+)\]')

    def parse_task_type(self, thought_text: str) -> str | None:
        """从 thought 文本中提取任务类型标签

        Args:
            thought_text: 模型的 thought/thinking 字段文本

        Returns:
            任务类型字符串（如 "CODE_COMPLEX"），解析失败返回 None

        解析规则：
        - 正则匹配 [TASK_TYPE: XXX] 格式
        - 提取的类型转为大写后必须在 VALID_TASK_TYPES 中
        - 如有多个匹配，取第一个
        """
        # 防御性检查：None 或非字符串
        if not thought_text or not isinstance(thought_text, str):
            return None

        match = self.TASK_TYPE_PATTERN.search(thought_text)
        if not match:
            return None

        task_type = match.group(1).strip().upper()
        if task_type in VALID_TASK_TYPES:
            return task_type

        return None

    def evaluate(
        self,
        thought_text: str,
        current_model: str,
        matrix: RoutingMatrix,
    ) -> TaskEvaluation | None:
        """完整评估：解析任务类型 + 查矩阵 + 计算权重差

        Args:
            thought_text: 模型的 thought 字段文本
            current_model: 当前使用的模型 ID
            matrix: 路由矩阵实例

        Returns:
            TaskEvaluation 实例，解析失败返回 None

        流程：
        1. 调用 parse_task_type() 提取任务类型
        2. 调用 matrix.get_ranking(task_type) 获取排名
        3. 取排名第 1 的模型作为推荐模型
        4. 计算 weight_diff = recommended_weight - current_weight
        """
        task_type = self.parse_task_type(thought_text)
        if task_type is None:
            return None

        ranking = matrix.get_ranking(task_type)
        if not ranking:
            return None

        recommended_model, recommended_weight = ranking[0]
        current_weight = matrix.get_weight(task_type, current_model)
        weight_diff = recommended_weight - current_weight

        return TaskEvaluation(
            task_type=task_type,
            recommended_model=recommended_model,
            recommended_weight=recommended_weight,
            current_weight=current_weight,
            weight_diff=weight_diff,
        )
