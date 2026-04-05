# 命令解析器测试
"""test_ms_command.py — 10 个测试用例"""

import pytest

from src.skills.ms_command import MsCommandHandler
from src.core.router import SwitchRouter
from src.core.state import SwitchStateManager


@pytest.fixture
def handler(router, state_mgr, sample_matrix):
    """创建命令处理器"""
    return MsCommandHandler(
        router=router,
        state_mgr=state_mgr,
        matrix=sample_matrix,
    )


class TestMsCommand:
    """MsCommandHandler 测试"""

    def test_help(self, handler):
        """/ms help 返回帮助文本"""
        output = handler.handle("/ms help")
        assert "🔧 /ms 命令帮助" in output
        assert "/ms auto" in output
        assert "/ms manual" in output
        assert "/ms status" in output

    def test_empty_command(self, handler):
        """/ms（空命令）→ 显示 help"""
        output = handler.handle("/ms")
        assert "🔧 /ms 命令帮助" in output

    def test_status(self, handler):
        """/ms status 返回当前状态"""
        output = handler.handle("/ms status")
        assert "📋 Auto-Switch-Skill 运行状态" in output
        assert "model-a" in output
        assert "自动模式" in output

    def test_list(self, handler):
        """/ms list 返回模型列表"""
        output = handler.handle("/ms list")
        assert "📦 可用模型列表" in output
        assert "model-a" in output
        assert "model-b" in output
        assert "model-c" in output

    def test_auto_already(self, handler, state_mgr):
        """已是自动模式 → 返回 ⚠️ 提示"""
        assert state_mgr.get_state().mode == "auto"
        output = handler.handle("/ms auto")
        assert "⚠️" in output
        assert "已是自动模式" in output

    def test_manual(self, handler, state_mgr):
        """/ms manual → 切换到手动模式"""
        output = handler.handle("/ms manual")
        assert "✅" in output
        assert "手动模式" in output
        assert state_mgr.get_state().mode == "manual"

    def test_auto_after_manual(self, handler, state_mgr):
        """/ms auto（从手动切回）→ 成功"""
        state_mgr.set_mode("manual")
        output = handler.handle("/ms auto")
        assert "✅" in output
        assert "自动模式" in output
        assert state_mgr.get_state().mode == "auto"

    def test_router_table(self, handler):
        """/ms router 返回路由表"""
        output = handler.handle("/ms router")
        assert "📊 当前任务模型路由表" in output
        assert "★" in output  # 最优模型标注

    def test_switch_by_alias(self, handler, state_mgr):
        """/ms b → 切换到 model-b"""
        output = handler.handle("/ms b")
        assert "✅ 模型已切换" in output
        assert "model-b" in output
        assert state_mgr.get_state().current_model == "model-b"

    def test_switch_unknown(self, handler):
        """/ms xyz → 返回 ❌ 错误"""
        output = handler.handle("/ms xyz")
        assert "❌" in output
        assert "未找到模型" in output

    def test_model_switch_prefix(self, handler, state_mgr):
        """/model-switch b → 也能切换"""
        output = handler.handle("/model-switch b")
        assert "✅ 模型已切换" in output
        assert state_mgr.get_state().current_model == "model-b"
