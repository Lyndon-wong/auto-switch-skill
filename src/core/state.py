# 运行时状态管理
"""
管理 Auto-Switch-Skill 的会话级运行时状态。
所有状态存储在内存中，会话结束自动销毁。

设计原则：
- 纯内存，不持久化
- 单例模式（每个会话一个实例）
- 不使用锁（MVP 假设单线程）
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core import COOLDOWN_ROUNDS, MAX_SWITCHES_PER_SESSION


@dataclass
class SwitchState:
    """运行时切换状态（会话级，不持久化）

    Attributes:
        current_model: 当前使用的模型 ID
        mode: 运行模式，"auto" 或 "manual"
        cooldown_remaining: 剩余冷却轮数（0 表示已过冷却期）
        switch_count: 本会话已切换次数
        last_task_type: 最近一次评估的任务类型
        last_recommended_model: 最近一次推荐的模型
        last_recommended_weight: 最近一次推荐模型的权重
    """

    current_model: str = ""
    mode: str = "auto"
    cooldown_remaining: int = 0
    switch_count: int = 0
    last_task_type: str = ""
    last_recommended_model: str = ""
    last_recommended_weight: int = 0


class SwitchStateManager:
    """状态管理器

    封装所有状态变更操作，保证状态一致性。

    使用方式：
        mgr = SwitchStateManager(default_model="sjtu/deepseek-v3.2")
        state = mgr.get_state()
    """

    def __init__(self, default_model: str = ""):
        """初始化

        Args:
            default_model: 默认模型 ID
        """
        self._state = SwitchState(current_model=default_model)

    def get_state(self) -> SwitchState:
        """获取当前状态的引用

        Returns:
            当前 SwitchState（直接引用，调用者不应直接修改）
        """
        return self._state

    def set_mode(self, mode: str) -> None:
        """设置运行模式

        Args:
            mode: "auto" 或 "manual"

        Raises:
            ValueError: mode 值非法
        """
        if mode not in ("auto", "manual"):
            raise ValueError(f"无效模式: {mode}，必须为 'auto' 或 'manual'")
        self._state.mode = mode

    def record_switch(self, new_model: str) -> None:
        """记录一次模型切换

        操作：
        - current_model 更新为 new_model
        - switch_count += 1
        - cooldown_remaining 重置为 COOLDOWN_ROUNDS (3)

        Args:
            new_model: 新的模型 ID
        """
        self._state.current_model = new_model
        self._state.switch_count += 1
        self._state.cooldown_remaining = COOLDOWN_ROUNDS

    def tick_cooldown(self) -> None:
        """每轮调用，递减冷却计数

        cooldown_remaining = max(0, cooldown_remaining - 1)
        """
        if self._state.cooldown_remaining > 0:
            self._state.cooldown_remaining -= 1

    def is_in_cooldown(self) -> bool:
        """是否处于冷却期

        Returns:
            True 如果 cooldown_remaining > 0
        """
        return self._state.cooldown_remaining > 0

    def is_at_limit(self) -> bool:
        """是否已达切换次数上限

        Returns:
            True 如果 switch_count >= MAX_SWITCHES_PER_SESSION
        """
        return self._state.switch_count >= MAX_SWITCHES_PER_SESSION

    def update_last_evaluation(
        self, task_type: str, model: str, weight: int
    ) -> None:
        """更新最近一次评估信息（用于 /ms status 显示）

        Args:
            task_type: 任务类型
            model: 推荐的模型 ID
            weight: 推荐模型的权重
        """
        self._state.last_task_type = task_type
        self._state.last_recommended_model = model
        self._state.last_recommended_weight = weight
