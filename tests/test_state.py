# 状态管理测试
"""test_state.py — 8 个测试用例"""

import pytest

from src.core.state import SwitchState, SwitchStateManager
from src.core import COOLDOWN_ROUNDS, MAX_SWITCHES_PER_SESSION


class TestSwitchState:
    """SwitchState 数据类测试"""

    def test_default_values(self):
        """默认值检查"""
        state = SwitchState()
        assert state.current_model == ""
        assert state.mode == "auto"
        assert state.cooldown_remaining == 0
        assert state.switch_count == 0
        assert state.last_task_type == ""


class TestSwitchStateManager:
    """SwitchStateManager 测试"""

    def test_initial_state(self, state_mgr):
        """初始状态检查"""
        state = state_mgr.get_state()
        assert state.current_model == "model-a"
        assert state.mode == "auto"
        assert state.cooldown_remaining == 0
        assert state.switch_count == 0

    def test_set_mode_auto(self):
        """设置自动模式"""
        mgr = SwitchStateManager()
        mgr.set_mode("manual")
        assert mgr.get_state().mode == "manual"
        mgr.set_mode("auto")
        assert mgr.get_state().mode == "auto"

    def test_set_mode_manual(self, state_mgr):
        """设置手动模式"""
        state_mgr.set_mode("manual")
        assert state_mgr.get_state().mode == "manual"

    def test_set_mode_invalid(self, state_mgr):
        """设置无效模式 → 抛 ValueError"""
        with pytest.raises(ValueError, match="无效模式"):
            state_mgr.set_mode("turbo")

    def test_record_switch(self, state_mgr):
        """记录切换：current_model 更新, count+1, cooldown=3"""
        state_mgr.record_switch("model-b")
        state = state_mgr.get_state()
        assert state.current_model == "model-b"
        assert state.switch_count == 1
        assert state.cooldown_remaining == COOLDOWN_ROUNDS

    def test_tick_cooldown(self, state_mgr):
        """递减冷却：3 → 2 → 1 → 0 → 0"""
        state_mgr.record_switch("model-b")
        assert state_mgr.is_in_cooldown() is True

        state_mgr.tick_cooldown()
        assert state_mgr.get_state().cooldown_remaining == 2

        state_mgr.tick_cooldown()
        assert state_mgr.get_state().cooldown_remaining == 1

        state_mgr.tick_cooldown()
        assert state_mgr.get_state().cooldown_remaining == 0
        assert state_mgr.is_in_cooldown() is False

        # 继续递减不会变负
        state_mgr.tick_cooldown()
        assert state_mgr.get_state().cooldown_remaining == 0

    def test_is_at_limit(self):
        """达到切换上限 → 返回 True"""
        mgr = SwitchStateManager(default_model="model-a")
        for i in range(MAX_SWITCHES_PER_SESSION):
            assert mgr.is_at_limit() is False
            mgr.record_switch(f"model-{i}")

        assert mgr.is_at_limit() is True
        assert mgr.get_state().switch_count == MAX_SWITCHES_PER_SESSION

    def test_update_last_evaluation(self, state_mgr):
        """更新最近评估信息"""
        state_mgr.update_last_evaluation("CODE_COMPLEX", "model-b", 90)
        state = state_mgr.get_state()
        assert state.last_task_type == "CODE_COMPLEX"
        assert state.last_recommended_model == "model-b"
        assert state.last_recommended_weight == 90
