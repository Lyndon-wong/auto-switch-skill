# 任务类型解析器测试
"""test_evaluator.py — 8 个测试用例"""

import pytest

from src.core.evaluator import TaskEvaluator, TaskEvaluation


class TestParseTaskType:
    """parse_task_type 方法测试"""

    def test_parse_basic(self, evaluator):
        """基础解析：[TASK_TYPE: CODE_COMPLEX] → "CODE_COMPLEX" """
        result = evaluator.parse_task_type(
            "让我分析一下这个任务... [TASK_TYPE: CODE_COMPLEX] 这是一个复杂的编程任务。"
        )
        assert result == "CODE_COMPLEX"

    def test_parse_with_spaces(self, evaluator):
        """带空格：[TASK_TYPE:  CHAT ] 的 CHAT 后面空格应被忽略"""
        result = evaluator.parse_task_type("[TASK_TYPE:  CHAT]")
        assert result == "CHAT"

    def test_parse_lowercase(self, evaluator):
        """小写输入：[TASK_TYPE: chat] → "CHAT"（转大写）"""
        result = evaluator.parse_task_type("[TASK_TYPE: chat]")
        assert result == "CHAT"

    def test_parse_invalid_type(self, evaluator):
        """无效类型：[TASK_TYPE: UNKNOWN] → None"""
        result = evaluator.parse_task_type("[TASK_TYPE: UNKNOWN]")
        assert result is None

    def test_parse_no_match(self, evaluator):
        """无标签文本 → None"""
        result = evaluator.parse_task_type("这是一段普通文本，没有任务类型标签。")
        assert result is None

    def test_parse_none_input(self, evaluator):
        """输入 None → None"""
        result = evaluator.parse_task_type(None)
        assert result is None

    def test_parse_empty_string(self, evaluator):
        """空字符串 → None"""
        result = evaluator.parse_task_type("")
        assert result is None

    def test_parse_multiple_tags(self, evaluator):
        """多个标签取第一个"""
        result = evaluator.parse_task_type(
            "[TASK_TYPE: CHAT] 然后 [TASK_TYPE: CODE_COMPLEX]"
        )
        assert result == "CHAT"


class TestEvaluate:
    """evaluate 方法测试"""

    def test_evaluate_full(self, evaluator, sample_matrix):
        """完整评估流程，验证 weight_diff 计算正确"""
        # 当前模型 model-a（CODE_COMPLEX 权重 50），推荐 model-b（权重 90）
        result = evaluator.evaluate(
            "[TASK_TYPE: CODE_COMPLEX]",
            "model-a",
            sample_matrix,
        )
        assert result is not None
        assert result.task_type == "CODE_COMPLEX"
        assert result.recommended_model == "model-b"
        assert result.recommended_weight == 90
        assert result.current_weight == 50
        assert result.weight_diff == 40

    def test_evaluate_empty(self, evaluator, sample_matrix):
        """空文本评估返回 None"""
        result = evaluator.evaluate("", "model-a", sample_matrix)
        assert result is None

    def test_evaluate_current_is_best(self, evaluator, sample_matrix):
        """当前模型就是最优模型时，weight_diff 为 0"""
        # CHAT 任务：model-a 权重 80（最高）
        result = evaluator.evaluate(
            "[TASK_TYPE: CHAT]",
            "model-a",
            sample_matrix,
        )
        assert result is not None
        assert result.weight_diff == 0
        assert result.recommended_model == "model-a"
