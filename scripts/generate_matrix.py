#!/usr/bin/env python3
# 路由矩阵自动生成器
"""
从 openclaw.json 读取已注册模型，与 model_profiles.yaml 模糊匹配，
生成用户专属的 routing_matrix.yaml。

使用方式：
    python scripts/generate_matrix.py \\
        --openclaw-config /path/to/openclaw.json \\
        --profiles config/model_profiles.yaml \\
        --output config/routing_matrix.yaml \\
        --default-weight 3
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml


# ─── 默认值 ───

DEFAULT_OPENCLAW_PATH = "/app/openclaw.json"
DEFAULT_PROFILES_PATH = "config/model_profiles.yaml"
DEFAULT_OUTPUT_PATH = "config/routing_matrix.json"
DEFAULT_WEIGHT = 3

# 标准任务类型定义（固定 10 种）
TASK_TYPES = {
    "CHAT": "日常对话",
    "QA": "知识问答",
    "SUMMARIZE": "摘要生成",
    "TRANSLATE": "翻译",
    "CODE_SIMPLE": "简单编程",
    "CODE_COMPLEX": "复杂编程",
    "REASONING": "逻辑推理",
    "ANALYSIS": "深度分析",
    "CREATIVE": "创意生成",
    "MULTI_STEP": "多步骤任务",
}


# ─── 匹配函数 ───


def normalize(name: str) -> str:
    """标准化名称：转小写，去除点号、连字符、下划线、空格

    Args:
        name: 模型名称字符串

    Returns:
        标准化后的字符串

    Examples:
        >>> normalize("deepseek-v3.2")
        'deepseekv32'
        >>> normalize("MiniMax_M2.5")
        'minimaxm25'
    """
    return re.sub(r'[.\-_\s]', '', name.lower())


def extract_keywords(name: str) -> set[str]:
    """提取关键词：品牌名 + 版本号 + 功能标识

    分词策略：按 -_./ 分割，再拆分数字和字母组合。

    Args:
        name: 模型名称字符串

    Returns:
        关键词集合

    Examples:
        >>> extract_keywords("qwen3coder")
        {'qwen', '3', 'coder'}
        >>> extract_keywords("deepseek-v3.2")
        {'deepseek', 'v', '3', '2'}
    """
    tokens = re.split(r'[-_./\s]', name.lower())
    keywords = set()
    for token in tokens:
        if not token:
            continue
        # 分离字母和数字组合
        parts = re.findall(r'[a-z]+|\d+', token)
        keywords.update(parts)
    return keywords


def match_model(openclaw_id: str, profile_keys: list[str]) -> str | None:
    """将 openclaw 模型 ID 匹配到画像库中的键

    4 级优先级匹配（匹配到即停止）：
    1. 名称精确匹配
    2. 标准化匹配
    3. 关键词 Jaccard 匹配（阈值 0.5）
    4. 未匹配 → 返回 None

    Args:
        openclaw_id: 如 "sjtu/deepseek-v3.2"
        profile_keys: 画像库所有键，如 ["deepseek/deepseek-v3.2", ...]

    Returns:
        匹配到的画像键，或 None
    """
    # 提取模型名称部分（去掉 provider 前缀）
    model_name = openclaw_id.split("/", 1)[-1]

    # 第 1 级：名称精确匹配
    for key in profile_keys:
        profile_name = key.split("/", 1)[-1]
        if model_name == profile_name:
            return key

    # 第 2 级：标准化匹配
    normalized_model = normalize(model_name)
    for key in profile_keys:
        if normalize(key.split("/", 1)[-1]) == normalized_model:
            return key

    # 第 3 级：关键词 Jaccard 匹配
    model_kw = extract_keywords(model_name)
    if not model_kw:
        return None

    best_match = None
    best_score = 0.0

    for key in profile_keys:
        profile_kw = extract_keywords(key.split("/", 1)[-1])
        if not profile_kw:
            continue
        intersection = model_kw & profile_kw
        union = model_kw | profile_kw
        score = len(intersection) / len(union) if union else 0
        if score > best_score and score >= 0.5:
            best_score = score
            best_match = key

    return best_match


# ─── 别名生成 ───


def generate_alias(model_id: str) -> str:
    """为模型生成短别名

    规则与 ModelEntry.__post_init__ 一致：
    取 / 后面的部分，转小写，去掉点号替换为连字符。

    Args:
        model_id: 模型完整 ID

    Returns:
        生成的短别名
    """
    parts = model_id.split("/")
    return parts[-1].lower().replace(".", "-")


# ─── 核心流程 ───


def load_openclaw_models(config_path: str) -> list[dict]:
    """从 openclaw.json 加载已注册模型列表

    Args:
        config_path: openclaw.json 文件路径

    Returns:
        模型字典列表，每个包含 id, name, contextWindow, reasoning 等字段

    Raises:
        FileNotFoundError: 配置文件不存在
        json.JSONDecodeError: JSON 格式错误
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(
            f"OpenClaw 配置文件不存在: {path}\n"
            f"请使用 --openclaw-config 参数指定正确路径。"
        )

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    models_section = data.get("models", {})

    # openclaw.json 的 models 字段是 {"providers": {"sjtu": {"models": [...]}}}
    # 需要遍历所有 provider，将模型展平为列表，并拼接 provider 前缀到 id
    if isinstance(models_section, dict):
        providers = models_section.get("providers", {})
        models = []
        for provider_name, provider_config in providers.items():
            if not isinstance(provider_config, dict):
                continue
            for model_info in provider_config.get("models", []):
                if not isinstance(model_info, dict):
                    continue
                # 将 provider 名拼接到模型 id 前面
                raw_id = model_info.get("id", "")
                if raw_id and "/" not in raw_id:
                    model_info = dict(model_info)  # 浅拷贝避免修改原数据
                    model_info["id"] = f"{provider_name}/{raw_id}"
                models.append(model_info)
    elif isinstance(models_section, list):
        # 兼容旧格式：models 直接是列表
        models = models_section
    else:
        models = []

    if not models:
        print("⚠️ 警告: openclaw.json 中未找到模型定义", file=sys.stderr)

    return models


def load_profiles(profile_path: str) -> dict[str, dict[str, int]]:
    """加载画像库

    Args:
        profile_path: model_profiles.yaml 文件路径

    Returns:
        {画像键: {任务类型: 权重}}

    Raises:
        FileNotFoundError: 画像库文件不存在
    """
    path = Path(profile_path)
    if not path.exists():
        raise FileNotFoundError(f"画像库文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        print("⚠️ 警告: 画像库格式异常，期望字典", file=sys.stderr)
        return {}

    # 过滤有效画像（值为字典且包含任务类型键）
    profiles = {}
    for key, value in data.items():
        if isinstance(value, dict):
            profiles[key] = value
        else:
            print(f"⚠️ 跳过异常画像: {key}（值不是字典）", file=sys.stderr)

    return profiles


def generate_matrix(
    models: list[dict],
    profiles: dict[str, dict[str, int]],
    default_weight: int = DEFAULT_WEIGHT,
) -> tuple[dict, dict[str, str | None]]:
    """生成路由矩阵

    Args:
        models: openclaw.json 中的模型列表
        profiles: 画像库数据
        default_weight: 未匹配模型的默认权重

    Returns:
        (矩阵字典, 匹配结果字典)
        矩阵字典符合 RoutingMatrix.from_dict() 格式
        匹配结果字典为 {模型ID: 匹配到的画像键 或 None}
    """
    profile_keys = list(profiles.keys())
    match_results: dict[str, str | None] = {}

    # 组装模型条目
    models_data = []
    for model_info in models:
        model_id = model_info.get("id", "")
        if not model_id:
            continue

        # 执行匹配
        matched_key = match_model(model_id, profile_keys)
        match_results[model_id] = matched_key

        # 构建模型条目（包含元数据）
        alias = generate_alias(model_id)
        model_entry = {
            "id": model_id,
            "alias": alias,
        }

        # 保留有用的元数据
        for meta_key in ("contextWindow", "reasoning", "name"):
            if meta_key in model_info:
                model_entry[meta_key] = model_info[meta_key]

        # 记录匹配来源
        if matched_key:
            model_entry["matched_profile"] = matched_key
        else:
            model_entry["matched_profile"] = None

        models_data.append(model_entry)

    # 组装路由矩阵
    routing_matrix = {}
    for task_type_id in TASK_TYPES:
        routing_matrix[task_type_id] = {}
        for model_info in models:
            model_id = model_info.get("id", "")
            if not model_id:
                continue

            matched_key = match_results.get(model_id)
            if matched_key and matched_key in profiles:
                # 使用画像中的权重
                weight = profiles[matched_key].get(task_type_id, default_weight)
            else:
                # 未匹配，使用默认权重
                weight = default_weight

            routing_matrix[task_type_id][model_id] = weight

    # 组装完整数据
    matrix_data = {
        "models": models_data,
        "task_types": TASK_TYPES,
        "routing_matrix": routing_matrix,
    }

    return matrix_data, match_results


# ─── 任务类型图标映射 ───

TASK_ICONS = {
    "CHAT": "💬",
    "QA": "❓",
    "SUMMARIZE": "📝",
    "TRANSLATE": "🌐",
    "CODE_SIMPLE": "💻",
    "CODE_COMPLEX": "🏗️",
    "REASONING": "🧠",
    "ANALYSIS": "📊",
    "CREATIVE": "🎨",
    "MULTI_STEP": "⚙️",
}


def _short_name(model_id: str) -> str:
    """把 provider/model-name 转为简短的展示名

    保留 provider 首字母缩写 + 模型名，控制总长度。

    Args:
        model_id: 如 "beijixing/deepseek-v3.2"

    Returns:
        短名称，如 "bjx/deepseek-v3.2"
    """
    provider_abbr = {
        "sjtu": "sjtu",
        "zuodachen": "zdc",
        "beijixing": "bjx",
        "openrouter": "or",
    }
    parts = model_id.split("/", 1)
    if len(parts) == 2:
        abbr = provider_abbr.get(parts[0], parts[0][:3])
        return f"{abbr}/{parts[1]}"
    return model_id


def _score_bar(score: int, width: int = 10) -> str:
    """生成分数条形图

    Args:
        score: 0-100 的分数
        width: 条形图总宽度（字符数）

    Returns:
        如 "████░░░░░░ 72"
    """
    filled = round(score / 100 * width)
    empty = width - filled
    return "█" * filled + "░" * empty


def print_install_report(
    matrix_data: dict,
    match_results: dict[str, str | None],
    output_path: str,
    top_n: int = 5,
) -> None:
    """打印安装报告（Markdown 兼容格式）

    输出兼容 Markdown 渲染，在终端直接阅读也很清晰。
    包含：匹配结果表、未匹配警告、每个任务 Top N 路由矩阵。

    Args:
        matrix_data: 生成的矩阵数据
        match_results: {模型ID: 匹配画像键 或 None}
        output_path: 输出文件路径
        top_n: 每个任务显示前几名模型
    """
    models = matrix_data.get("models", [])
    routing = matrix_data.get("routing_matrix", {})
    task_types = matrix_data.get("task_types", TASK_TYPES)

    matched = [(m, match_results[m["id"]]) for m in models if match_results.get(m["id"])]
    unmatched = [m for m in models if not match_results.get(m["id"])]
    total = len(models)

    lines = []
    ln = lines.append

    # ── 标题 ──
    ln("")
    ln("## 🚀 Auto-Switch-Skill 安装报告")
    ln("")

    # ── 统计概览 ──
    if unmatched:
        ln(f"> 已注册 **{total}** 个模型，"
           f"匹配成功 **{len(matched)}** 个，"
           f"未匹配 **{len(unmatched)}** 个")
    else:
        ln(f"> ✅ 已注册 **{total}** 个模型，**全部匹配成功**！")
    ln("")

    # ── 匹配成功表 ──
    ln("### ✅ 匹配成功的模型")
    ln("")
    ln("| # | 模型 ID | 匹配画像 |")
    ln("|--:|---------|----------|")
    for i, (model, profile_key) in enumerate(matched, 1):
        mid = model["id"]
        ln(f"| {i} | `{mid}` | `{profile_key}` |")
    ln("")

    # ── 未匹配模型 ──
    if unmatched:
        ln("### ⚠️ 未匹配的模型")
        ln("")
        ln(f"> 以下模型未在画像库中找到对应条目，所有任务权重为默认值 **{DEFAULT_WEIGHT}**。")
        ln(f"> 建议在 `config/model_profiles.yaml` 中补充画像后重新生成。")
        ln("")
        ln("| # | 模型 ID | 模型名称 |")
        ln("|--:|---------|----------|")
        for i, model in enumerate(unmatched, 1):
            mid = model["id"]
            mname = model.get("name", "-")
            ln(f"| {i} | `{mid}` | {mname} |")
        ln("")

    # ── 路由矩阵 Top N ──
    ln(f"### 📊 任务路由矩阵 Top {top_n}")
    ln("")
    ln(f"每种任务类型下，按权重降序列出前 {top_n} 名最优模型：")
    ln("")

    for task_id, task_desc in task_types.items():
        icon = TASK_ICONS.get(task_id, "📌")
        weights = routing.get(task_id, {})
        if not weights:
            continue

        # 按分数降序排列，取 Top N
        sorted_models = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:top_n]

        ln(f"#### {icon} {task_id}（{task_desc}）")
        ln("")
        ln("| 排名 | 模型 | 分数 | 能力条 |")
        ln("|:----:|------|-----:|--------|")
        medals = ["🥇", "🥈", "🥉", "4.", "5."]
        for rank, (mid, score) in enumerate(sorted_models):
            medal = medals[rank] if rank < len(medals) else f"{rank+1}."
            bar = _score_bar(score)
            short = _short_name(mid)
            ln(f"| {medal} | `{short}` | **{score}** | {bar} |")
        ln("")

    # ── 结尾 ──
    ln(f"---")
    ln(f"📁 路由矩阵已写入: `{output_path}`")
    ln("")

    # 输出所有内容
    print("\n".join(lines))


# ─── 入口 ───


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="生成 Auto-Switch-Skill 路由矩阵",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python scripts/generate_matrix.py\n"
            "  python scripts/generate_matrix.py --openclaw-config ./openclaw.json\n"
            "  python scripts/generate_matrix.py --default-weight 5"
        ),
    )

    parser.add_argument(
        "--openclaw-config",
        default=DEFAULT_OPENCLAW_PATH,
        help=f"OpenClaw 配置文件路径（默认: {DEFAULT_OPENCLAW_PATH}）",
    )
    parser.add_argument(
        "--profiles",
        default=DEFAULT_PROFILES_PATH,
        help=f"画像库路径（默认: {DEFAULT_PROFILES_PATH}）",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_PATH,
        help=f"输出路径（默认: {DEFAULT_OUTPUT_PATH}）",
    )
    parser.add_argument(
        "--default-weight",
        type=int,
        default=DEFAULT_WEIGHT,
        help=f"未匹配模型的默认权重（默认: {DEFAULT_WEIGHT}）",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=5,
        help="每个任务类型显示前 N 名模型（默认: 5）",
    )

    args = parser.parse_args()

    # 加载数据
    try:
        models = load_openclaw_models(args.openclaw_config)
        profiles = load_profiles(args.profiles)
    except FileNotFoundError as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)

    if not models:
        print("❌ 错误: 无可用模型，退出", file=sys.stderr)
        sys.exit(1)

    # 生成矩阵
    matrix_data, match_results = generate_matrix(
        models, profiles, args.default_weight
    )

    # 写入输出文件
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.suffix in ('.yaml', '.yml'):
        # YAML 格式输出
        header = (
            f"# Auto-Switch-Skill 路由矩阵\n"
            f"# 由 generate_matrix.py 自动生成\n"
            f"# 生成时间: {datetime.now().isoformat()}\n"
            f"# 画像库: {args.profiles}\n"
            f"# 源配置: {args.openclaw_config}\n"
            f"\n"
        )
        yaml_content = yaml.dump(
            matrix_data,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(header)
            f.write(yaml_content)
    else:
        # JSON 格式输出（默认，不需要第三方依赖即可读取）
        output_data = {
            "_meta": {
                "generator": "generate_matrix.py",
                "generated_at": datetime.now().isoformat(),
                "profiles_source": str(args.profiles),
                "openclaw_source": str(args.openclaw_config),
            },
            **matrix_data,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

    # 打印安装报告
    print_install_report(matrix_data, match_results, str(output_path), args.top_n)


if __name__ == "__main__":
    main()
