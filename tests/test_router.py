# 路由引擎测试
"""test_router.py — 8 个测试用例"""

import pytest

from src.core.router import SwitchRouter, SwitchResult
from src.core.state import SwitchStateManager
from src.core.evaluator import TaskEvaluator
from src.core import COOLDOWN_ROUNDS, MAX_SWITCHES_PER_SESSION


class TestProcessMessage:
    """process_message 自动切换流程测试"""

    def test_auto_switch_triggered(self, router, state_mgr):
        """自动切换完整流程：thought 中有标签 + 权重差 > 15 → 切换

        当前 model-a，REASONING 任务下 model-c 权重 95，model-a 权重 40
        权重差 = 55 > 15 → 应触发切换到 model-c
        """
        result = router.process_message(
            "分析这道数学题... [TASK_TYPE: REASONING] 需要逻辑推理。"
        )
        assert result is not None
        assert result.success is True
        assert result.previous_model == "model-a"
        assert result.current_model == "model-c"

    def test_skip_manual_mode(self, router, state_mgr):
        """手动模式 → 跳过评估"""
        state_mgr.set_mode("manual")
        result = router.process_message("[TASK_TYPE: REASONING]")
        assert result is None

    def test_skip_cooldown(self, router, state_mgr):
        """冷却中 → 跳过评估"""
        # 先触发一次切换，进入冷却期
        state_mgr.record_switch("model-b")
        # 冷却期内（刚切换，cooldown=3）
        # process_message 会先 tick_cooldown → cooldown=2，仍在冷却中
        result = router.process_message("[TASK_TYPE: REASONING]")
        assert result is None

    def test_skip_at_limit(self, router, state_mgr):
        """达到切换上限 → 跳过"""
        state_mgr._state.switch_count = MAX_SWITCHES_PER_SESSION
        result = router.process_message("[TASK_TYPE: REASONING]")
        assert result is None

    def test_below_threshold(self, router, state_mgr):
        """权重差 <= 15 → 不切换

        CHAT 任务：model-a=80(最高)，是当前模型，所以 weight_diff=0
        """
        result = router.process_message("[TASK_TYPE: CHAT]")
        assert result is None

    def test_same_model_no_switch(self, router, state_mgr):
        """推荐模型与当前模型相同 → 不切换

        CHAT 任务：model-a 权重 80（最高），当前也是 model-a
        """
        result = router.process_message("[TASK_TYPE: CHAT]")
        assert result is None


class TestManualSwitch:
    """manual_switch 手动切换测试"""

    def test_manual_switch_success(self, router, state_mgr):
        """手动切换不检查阈值和冷却"""
        result = router.manual_switch("model-b")
        assert result.success is True
        assert result.previous_model == "model-a"
        assert result.current_model == "model-b"
        assert state_mgr.get_state().switch_count == 1

    def test_manual_switch_during_cooldown(self, router, state_mgr):
        """手动切换在冷却期内也能执行"""
        state_mgr.record_switch("model-b")
        assert state_mgr.is_in_cooldown() is True
        result = router.manual_switch("model-c")
        assert result.success is True


class TestCooldownBehavior:
    """冷却行为测试"""

    def test_cooldown_ticks_each_round(self, router, state_mgr, sample_matrix):
        """切换后冷却期验证

        process_message 内部先调用 tick_cooldown() 再检查 is_in_cooldown()。
        因此 cooldown=3 时：
        - 第 1 次调用：tick→2，仍冷却中 → 跳过
        - 第 2 次调用：tick→1，仍冷却中 → 跳过
        - 第 3 次调用：tick→0，已过冷却期 → 正常评估
        """
        # 触发切换到 model-c（REASONING 权重差 = 55 > 15）
        result = router.process_message("[TASK_TYPE: REASONING]")
        assert result is not None
        assert result.success is True
        assert state_mgr.get_state().cooldown_remaining == COOLDOWN_ROUNDS

        # 前 2 轮在冷却中（tick 后 cooldown 仍 > 0）
        for i in range(COOLDOWN_ROUNDS - 1):
            result = router.process_message("[TASK_TYPE: CODE_COMPLEX]")
            assert result is None

        # 第 3 轮：tick→0，已过冷却期，可以评估
        # 当前是 model-c，CODE_COMPLEX: model-b=90, model-c=70，差值=20>15
        result = router.process_message("[TASK_TYPE: CODE_COMPLEX]")
        assert result is not None
        assert result.success is True
        assert result.current_model == "model-b"
