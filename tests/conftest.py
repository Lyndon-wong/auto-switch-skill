# 测试共享 fixtures
"""
提供所有测试模块共享的 pytest fixtures。
"""

import pytest

from src.config.schema import ModelEntry, TaskTypeEntry, RoutingMatrix
from src.core.state import SwitchStateManager
from src.core.evaluator import TaskEvaluator
from src.core.router import SwitchRouter


@pytest.fixture
def sample_matrix():
    """创建一个包含 3 个模型和 3 种任务类型的简化路由矩阵"""
    matrix = RoutingMatrix()

    # 添加任务类型
    matrix.add_task_type(TaskTypeEntry(id="CHAT", description="日常对话"))
    matrix.add_task_type(TaskTypeEntry(id="CODE_COMPLEX", description="复杂编程"))
    matrix.add_task_type(TaskTypeEntry(id="REASONING", description="逻辑推理"))

    # 添加模型
    matrix.add_model(
        ModelEntry(
            id="model-a",
            alias="a",
            metadata={"contextWindow": 131072, "reasoning": False, "name": "Model A"},
        )
    )
    matrix.add_model(
        ModelEntry(
            id="model-b",
            alias="b",
            metadata={"contextWindow": 196608, "reasoning": True, "name": "Model B"},
        )
    )
    matrix.add_model(
        ModelEntry(
            id="model-c",
            alias="c",
            metadata={"contextWindow": 131072, "reasoning": False, "name": "Model C"},
        )
    )

    # 设置权重
    # CHAT: a=80, b=60, c=40
    matrix.set_weight("CHAT", "model-a", 80)
    matrix.set_weight("CHAT", "model-b", 60)
    matrix.set_weight("CHAT", "model-c", 40)

    # CODE_COMPLEX: a=50, b=90, c=70
    matrix.set_weight("CODE_COMPLEX", "model-a", 50)
    matrix.set_weight("CODE_COMPLEX", "model-b", 90)
    matrix.set_weight("CODE_COMPLEX", "model-c", 70)

    # REASONING: a=40, b=60, c=95
    matrix.set_weight("REASONING", "model-a", 40)
    matrix.set_weight("REASONING", "model-b", 60)
    matrix.set_weight("REASONING", "model-c", 95)

    return matrix


@pytest.fixture
def state_mgr():
    """创建状态管理器，默认模型为 model-a"""
    return SwitchStateManager(default_model="model-a")


@pytest.fixture
def evaluator():
    """创建任务评估器"""
    return TaskEvaluator()


@pytest.fixture
def router(sample_matrix, state_mgr, evaluator):
    """创建路由引擎"""
    return SwitchRouter(
        matrix=sample_matrix,
        state_mgr=state_mgr,
        evaluator=evaluator,
    )
