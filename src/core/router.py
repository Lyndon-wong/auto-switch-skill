# 路由引擎
"""
串联「评估 → 判定 → 执行」的完整模型切换决策流程。

设计原则：
- 单一入口 process_message()，内部封装完整决策逻辑
- execute_switch() 负责状态更新，实际 session_status 调用
  由 SKILL.md 指令层完成
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core import WEIGHT_DIFF_THRESHOLD
from src.core.evaluator import TaskEvaluator, TaskEvaluation
from src.core.state import SwitchStateManager
from src.config.schema import RoutingMatrix


@dataclass
class SwitchResult:
    """切换执行结果

    Attributes:
        success: 切换是否成功
        previous_model: 切换前的模型 ID
        current_model: 切换后的模型 ID（成功时为新模型，失败时为原模型）
        reason: 切换原因或失败原因的文本描述
    """

    success: bool
    previous_model: str
    current_model: str
    reason: str


class SwitchRouter:
    """路由引擎

    负责：
    1. 串联完整的切换决策流程
    2. 执行模型切换（更新内部状态 + 返回切换指令）
    3. 提供手动切换能力（供 /ms <模型名> 调用）
    """

    def __init__(
        self,
        matrix: RoutingMatrix,
        state_mgr: SwitchStateManager,
        evaluator: TaskEvaluator | None = None,
    ):
        """
        Args:
            matrix: 路由矩阵
            state_mgr: 状态管理器
            evaluator: 任务评估器（默认创建新实例）
        """
        self.matrix = matrix
        self.state_mgr = state_mgr
        self.evaluator = evaluator or TaskEvaluator()

    def process_message(self, thought_text: str) -> SwitchResult | None:
        """处理一条消息的完整切换决策流程

        这是自动切换的 **唯一入口**。每条用户消息的 thought 字段
        都应经由此方法处理。

        决策流程：
        1. 递减冷却计数
        2. 前置检查（模式、冷却、上限）
        3. 评估任务类型
        4. 记录评估结果
        5. 判定是否切换
        6. 执行切换

        Args:
            thought_text: 模型返回的 thought/thinking 字段文本

        Returns:
            SwitchResult: 如果执行了切换（成功或失败）
            None: 如果决定不切换（冷却中/手动模式/解析失败/权重差不足）
        """
        # Step 1: 递减冷却
        self.state_mgr.tick_cooldown()

        state = self.state_mgr.get_state()

        # Step 2: 前置检查
        if state.mode != "auto":
            return None
        if self.state_mgr.is_in_cooldown():
            return None
        if self.state_mgr.is_at_limit():
            return None

        # Step 3: 评估
        evaluation = self.evaluator.evaluate(
            thought_text, state.current_model, self.matrix
        )
        if evaluation is None:
            return None

        # Step 4: 记录评估结果
        self.state_mgr.update_last_evaluation(
            evaluation.task_type,
            evaluation.recommended_model,
            evaluation.recommended_weight,
        )

        # Step 5: 判定
        if not self.should_switch(evaluation):
            return None

        # Step 6: 执行
        return self.execute_switch(evaluation.recommended_model)

    def should_switch(self, evaluation: TaskEvaluation) -> bool:
        """判断是否应该切换

        条件（全部满足才切换）：
        1. weight_diff > WEIGHT_DIFF_THRESHOLD (15)
        2. recommended_model != current_model

        Args:
            evaluation: 任务评估结果

        Returns:
            True 如果应该切换
        """
        state = self.state_mgr.get_state()
        return (
            evaluation.weight_diff > WEIGHT_DIFF_THRESHOLD
            and evaluation.recommended_model != state.current_model
        )

    def execute_switch(self, target_model: str) -> SwitchResult:
        """执行模型切换

        更新内部状态，返回切换结果。
        实际的 session_status API 调用由 SKILL.md 指令层完成。

        Args:
            target_model: 目标模型 ID

        Returns:
            SwitchResult
        """
        state = self.state_mgr.get_state()
        previous = state.current_model

        try:
            self.state_mgr.record_switch(target_model)
            return SwitchResult(
                success=True,
                previous_model=previous,
                current_model=target_model,
                reason=f"任务类型切换: {state.last_task_type}",
            )
        except Exception as e:
            return SwitchResult(
                success=False,
                previous_model=previous,
                current_model=previous,
                reason=f"切换失败: {e}",
            )

    def manual_switch(self, target_model: str) -> SwitchResult:
        """手动切换（由 /ms <模型名> 触发，不检查阈值）

        与 execute_switch 的区别：
        - 不检查冷却期、切换上限、权重差
        - 不改变当前模式（auto/manual）

        Args:
            target_model: 目标模型 ID

        Returns:
            SwitchResult
        """
        return self.execute_switch(target_model)
