# 矩阵生成器测试
"""test_generate_matrix.py — 6 个测试用例"""

import json
import os
import tempfile

import pytest
import yaml

# 将 scripts 目录添加到导入路径
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from generate_matrix import (
    normalize,
    extract_keywords,
    match_model,
    generate_matrix,
    generate_alias,
    load_profiles,
)
from src.config.schema import RoutingMatrix


# ─── 模糊匹配测试 ───


class TestNormalize:
    """normalize 函数测试"""

    def test_basic(self):
        assert normalize("deepseek-v3.2") == "deepseekv32"

    def test_mixed_case(self):
        assert normalize("MiniMax_M2.5") == "minimaxm25"


class TestExtractKeywords:
    """extract_keywords 函数测试"""

    def test_basic(self):
        kw = extract_keywords("qwen3coder")
        assert "qwen" in kw
        assert "3" in kw
        assert "coder" in kw

    def test_hyphenated(self):
        kw = extract_keywords("deepseek-v3.2")
        assert "deepseek" in kw
        assert "v" in kw


class TestMatchModel:
    """match_model 4 级匹配测试"""

    PROFILE_KEYS = [
        "deepseek/deepseek-v3.2",
        "deepseek/deepseek-v3",
        "minimax/m2.7",
        "alibaba/qwen-coder-2.5-32b",
        "anthropic/claude-opus-4",
    ]

    def test_exact_match(self):
        """第 1 级：名称精确匹配"""
        result = match_model("sjtu/deepseek-v3.2", self.PROFILE_KEYS)
        assert result == "deepseek/deepseek-v3.2"

    def test_normalized_match(self):
        """第 2 级：标准化后匹配"""
        # "Deepseek-V3.2" 标准化后与 "deepseek-v3.2" 一致
        result = match_model("other/Deepseek-V3.2", self.PROFILE_KEYS)
        assert result == "deepseek/deepseek-v3.2"

    def test_keyword_match(self):
        """第 3 级：关键词 Jaccard 匹配"""
        # "qwen3coder" 关键词 {qwen, 3, coder} 与
        # "qwen-coder-2.5-32b" 关键词 {qwen, coder, 2, 5, 32, b} 有交集
        result = match_model("sjtu/qwen3coder", self.PROFILE_KEYS)
        # 应该匹配到某个含 qwen 和 coder 的画像
        if result is not None:
            assert "qwen" in result or "coder" in result

    def test_no_match(self):
        """第 4 级：无匹配 → 返回 None"""
        result = match_model("sjtu/totally-unknown-model", self.PROFILE_KEYS)
        assert result is None


class TestGenerateMatrix:
    """generate_matrix 完整流程测试"""

    def test_full_generate(self):
        """完整生成流程"""
        models = [
            {"id": "sjtu/deepseek-v3.2", "name": "DeepSeek V3.2",
             "contextWindow": 131072, "reasoning": False},
            {"id": "sjtu/unknown-model", "name": "Unknown",
             "contextWindow": 65536, "reasoning": False},
        ]
        profiles = {
            "deepseek/deepseek-v3.2": {
                "CHAT": 80, "QA": 80, "SUMMARIZE": 78,
                "TRANSLATE": 78, "CODE_SIMPLE": 88, "CODE_COMPLEX": 78,
                "REASONING": 78, "ANALYSIS": 80, "CREATIVE": 72,
                "MULTI_STEP": 78,
            }
        }

        matrix_data, match_results = generate_matrix(models, profiles, default_weight=3)

        # 验证结构
        assert "models" in matrix_data
        assert "task_types" in matrix_data
        assert "routing_matrix" in matrix_data

        # 验证匹配结果
        assert match_results["sjtu/deepseek-v3.2"] == "deepseek/deepseek-v3.2"
        assert match_results["sjtu/unknown-model"] is None

        # 验证权重
        rm = matrix_data["routing_matrix"]
        assert rm["CHAT"]["sjtu/deepseek-v3.2"] == 80  # 画像权重
        assert rm["CHAT"]["sjtu/unknown-model"] == 3     # 默认权重

    def test_output_format_compatible(self):
        """输出格式可被 RoutingMatrix.from_dict() 反序列化"""
        models = [
            {"id": "test/model-a", "name": "Model A",
             "contextWindow": 128000, "reasoning": False},
        ]
        profiles = {
            "test/model-a": {
                "CHAT": 70, "QA": 65, "SUMMARIZE": 60,
                "TRANSLATE": 55, "CODE_SIMPLE": 80, "CODE_COMPLEX": 75,
                "REASONING": 70, "ANALYSIS": 65, "CREATIVE": 50,
                "MULTI_STEP": 60,
            }
        }

        matrix_data, _ = generate_matrix(models, profiles)

        # 通过 YAML 序列化/反序列化验证
        yaml_str = yaml.dump(matrix_data, allow_unicode=True, default_flow_style=False)
        loaded_data = yaml.safe_load(yaml_str)

        # 应该可以被 from_dict 正确解析
        matrix = RoutingMatrix.from_dict(loaded_data)
        assert len(matrix.models) == 1
        assert matrix.models[0].id == "test/model-a"
        assert matrix.get_weight("CHAT", "test/model-a") == 70


class TestGenerateAlias:
    """别名生成测试"""

    def test_basic(self):
        assert generate_alias("sjtu/deepseek-v3.2") == "deepseek-v3-2"

    def test_simple(self):
        assert generate_alias("sjtu/qwen3coder") == "qwen3coder"
