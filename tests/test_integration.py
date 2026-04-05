# 集成测试
"""test_integration.py — 端到端流程验证"""

import pytest

from src.config.schema import ModelEntry, TaskTypeEntry, RoutingMatrix
from src.core.state import SwitchStateManager
from src.core.evaluator import TaskEvaluator
from src.core.router import SwitchRouter
from src.skills.ms_command import MsCommandHandler
from src.core import COOLDOWN_ROUNDS


class TestEndToEndAutoSwitch:
    """端到端：从消息到切换完成"""

    def test_full_auto_switch_flow(self):
        """完整自动切换流程"""
        # 1. 准备路由矩阵
        matrix = RoutingMatrix()
        matrix.add_task_type(TaskTypeEntry(id="CHAT", description="日常对话"))
        matrix.add_task_type(TaskTypeEntry(id="REASONING", description="逻辑推理"))
        matrix.add_task_type(TaskTypeEntry(id="CODE_COMPLEX", description="复杂编程"))

        matrix.add_model(ModelEntry(id="model-a", alias="a"))
        matrix.add_model(ModelEntry(id="model-b", alias="b"))

        matrix.set_weight("CHAT", "model-a", 85)
        matrix.set_weight("CHAT", "model-b", 60)
        matrix.set_weight("REASONING", "model-a", 40)
        matrix.set_weight("REASONING", "model-b", 92)
        matrix.set_weight("CODE_COMPLEX", "model-a", 50)
        matrix.set_weight("CODE_COMPLEX", "model-b", 88)

        # 2. 初始化
        state_mgr = SwitchStateManager(default_model="model-a")
        evaluator = TaskEvaluator()
        router = SwitchRouter(matrix=matrix, state_mgr=state_mgr, evaluator=evaluator)

        # 3. CHAT 任务 → 当前 model-a 权重 85（最高）→ 不切换
        result = router.process_message("[TASK_TYPE: CHAT] 你好")
        assert result is None
        assert state_mgr.get_state().current_model == "model-a"

        # 4. REASONING 任务 → model-b 权重 92, model-a 权重 40, 差 52 > 15 → 切换
        result = router.process_message("[TASK_TYPE: REASONING] 请证明...")
        assert result is not None
        assert result.success is True
        assert result.current_model == "model-b"

        # 5. 验证冷却期
        assert state_mgr.get_state().cooldown_remaining == COOLDOWN_ROUNDS
        for _ in range(COOLDOWN_ROUNDS):
            result = router.process_message("[TASK_TYPE: CODE_COMPLEX]")
            assert result is None

        # 6. 冷却过后，CODE_COMPLEX → model-b 已经是最优（权重 88）→ 不切换
        result = router.process_message("[TASK_TYPE: CODE_COMPLEX]")
        assert result is None  # model-b 已经是最优

        # 7. 验证计数
        assert state_mgr.get_state().switch_count == 1


class TestEndToEndMsCommands:
    """端到端：/ms 命令全流程"""

    def test_full_command_flow(self):
        """7 个命令全流程测试"""
        # 准备
        matrix = RoutingMatrix()
        matrix.add_task_type(TaskTypeEntry(id="CHAT", description="日常对话"))
        matrix.add_task_type(TaskTypeEntry(id="CODE_COMPLEX", description="复杂编程"))

        matrix.add_model(
            ModelEntry(id="model-x", alias="x",
                       metadata={"contextWindow": 131072, "reasoning": False})
        )
        matrix.add_model(
            ModelEntry(id="model-y", alias="y",
                       metadata={"contextWindow": 196608, "reasoning": True})
        )

        matrix.set_weight("CHAT", "model-x", 80)
        matrix.set_weight("CHAT", "model-y", 60)
        matrix.set_weight("CODE_COMPLEX", "model-x", 50)
        matrix.set_weight("CODE_COMPLEX", "model-y", 90)

        state_mgr = SwitchStateManager(default_model="model-x")
        router = SwitchRouter(matrix=matrix, state_mgr=state_mgr)
        handler = MsCommandHandler(router=router, state_mgr=state_mgr, matrix=matrix)

        # 1. /ms help
        out = handler.handle("/ms help")
        assert "🔧" in out

        # 2. /ms status → 初始状态
        out = handler.handle("/ms status")
        assert "model-x" in out
        assert "自动模式" in out

        # 3. /ms list
        out = handler.handle("/ms list")
        assert "model-x" in out
        assert "model-y" in out

        # 4. /ms y → 手动切换到 model-y
        out = handler.handle("/ms y")
        assert "✅ 模型已切换" in out
        assert state_mgr.get_state().current_model == "model-y"

        # 5. /ms status → 切换后状态
        out = handler.handle("/ms status")
        assert "model-y" in out

        # 6. /ms manual → 切换到手动模式
        out = handler.handle("/ms manual")
        assert "✅" in out
        assert state_mgr.get_state().mode == "manual"

        # 7. /ms auto → 恢复自动模式
        out = handler.handle("/ms auto")
        assert "✅" in out
        assert state_mgr.get_state().mode == "auto"

        # 8. /ms router
        out = handler.handle("/ms router")
        assert "📊" in out
        assert "★" in out

        # 9. 错误处理
        out = handler.handle("/ms nonexistent")
        assert "❌" in out
