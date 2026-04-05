# 文本格式化工具
"""
提供表格渲染、状态文本格式化等工具函数。
用于 /ms 命令的输出格式化。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.state import SwitchState
    from src.config.schema import RoutingMatrix

from src.core import MAX_SWITCHES_PER_SESSION, TASK_TYPE_ABBREV


def format_help() -> str:
    """格式化 /ms help 的帮助文本

    Returns:
        帮助信息字符串
    """
    return (
        "🔧 /ms 命令帮助 (MVP)\n"
        "\n"
        "模式与切换:\n"
        "  /ms auto                  恢复自动切换模式\n"
        "  /ms manual                切换到手动模式（禁用自动切换）\n"
        "  /ms <模型名>              切换到指定模型（不改变当前模式）\n"
        "\n"
        "路由管理:\n"
        "  /ms router                查看当前任务模型路由表\n"
        "\n"
        "基础信息:\n"
        "  /ms help                  显示本帮助信息\n"
        "  /ms status                查看当前运行状态\n"
        "  /ms list                  列出所有可用模型\n"
        "\n"
        "任务缩写对照: CHAT QA SUM TRA CS CC REA ANA CRE MS"
    )


def format_status(state: SwitchState, matrix: RoutingMatrix) -> str:
    """格式化 /ms status 的输出文本

    Args:
        state: 当前运行时状态
        matrix: 路由矩阵（用于查找模型别名）

    Returns:
        格式化的状态文本
    """
    # 获取当前模型别名
    model_entry = matrix.get_model_by_id(state.current_model)
    if model_entry:
        model_display = f"{model_entry.alias} ({model_entry.id})"
    else:
        model_display = state.current_model or "未设置"

    # 运行模式
    mode_display = "🤖 自动模式" if state.mode == "auto" else "✋ 手动模式"

    # 冷却状态
    if state.cooldown_remaining > 0:
        cooldown_display = f"❄️ 冷却中（剩余 {state.cooldown_remaining} 轮）"
    else:
        cooldown_display = "✅ 已过冷却期"

    # 最近任务
    if state.last_task_type:
        last_model = matrix.get_model_by_id(state.last_recommended_model)
        rec_name = last_model.alias if last_model else state.last_recommended_model
        task_display = (
            f"{state.last_task_type} → 推荐: {rec_name} "
            f"(权重 {state.last_recommended_weight})"
        )
    else:
        task_display = "暂无评估记录"

    return (
        f"📋 Auto-Switch-Skill 运行状态\n"
        f"\n"
        f"当前模型:   {model_display}\n"
        f"运行模式:   {mode_display}\n"
        f"冷却状态:   {cooldown_display}\n"
        f"最近任务:   {task_display}\n"
        f"本会话切换: {state.switch_count} / {MAX_SWITCHES_PER_SESSION} 次"
    )


def format_model_list(matrix: RoutingMatrix, current_model_id: str) -> str:
    """格式化 /ms list 的输出文本

    Args:
        matrix: 路由矩阵
        current_model_id: 当前使用的模型 ID

    Returns:
        格式化的模型列表
    """
    if not matrix.models:
        return "📦 可用模型列表\n\n  （无可用模型）"

    lines = ["📦 可用模型列表\n"]

    # 计算列宽
    alias_width = max(len(m.alias) for m in matrix.models)
    alias_width = max(alias_width, 6)  # 至少 6 字符
    id_width = max(len(m.id) for m in matrix.models)
    id_width = max(id_width, 8)

    # 表头
    header = f"  {'别名':<{alias_width + 2}}  {'模型全称':<{id_width + 2}}  {'上下文窗口':>8}   推理"
    lines.append(header)
    lines.append("  " + "─" * (alias_width + id_width + 30))

    # 每行数据
    for model in matrix.models:
        # 从 metadata 获取上下文窗口和推理模式
        ctx_window = model.metadata.get("contextWindow", "")
        if isinstance(ctx_window, int):
            if ctx_window >= 1024:
                ctx_display = f"{ctx_window // 1024}K"
            else:
                ctx_display = str(ctx_window)
        else:
            ctx_display = str(ctx_window) if ctx_window else "N/A"

        reasoning = model.metadata.get("reasoning", False)
        reasoning_display = "✅" if reasoning else "❌"

        # 当前模型标记
        marker = " ●" if model.id == current_model_id else ""

        line = (
            f"  {model.alias:<{alias_width + 2}}  "
            f"{model.id:<{id_width + 2}}  "
            f"{ctx_display:>8}   "
            f"{reasoning_display}"
            f"{marker}"
        )
        lines.append(line)

    # 底部当前模型提示
    current = matrix.get_model_by_id(current_model_id)
    if current:
        lines.append(f"\n  当前使用: {current.alias} ({current.id}) ●")

    return "\n".join(lines)


def format_router_table(matrix: RoutingMatrix) -> str:
    """格式化 /ms router 的路由表（含 ★ 标注最优模型）

    Args:
        matrix: 路由矩阵

    Returns:
        格式化的路由表字符串
    """
    if not matrix.models or not matrix.task_types:
        return "📊 当前任务模型路由表\n\n  （矩阵为空）"

    # 使用任务类型缩写
    # 创建反向映射：完整名称 → 缩写
    abbrev_reverse = {v: k for k, v in TASK_TYPE_ABBREV.items()}

    # 获取任务类型的缩写列表（按原始顺序）
    task_abbrevs = []
    for task in matrix.task_types:
        abbr = abbrev_reverse.get(task.id, task.id)
        task_abbrevs.append((task.id, abbr))

    # 找出每个任务类型的最优模型
    best_models = {}
    for task_id, _ in task_abbrevs:
        ranking = matrix.get_ranking(task_id)
        if ranking:
            best_models[task_id] = ranking[0][0]  # 最高权重的模型 ID

    # 模型标签（使用别名）
    model_labels = [m.alias for m in matrix.models]

    # 计算列宽
    model_col_width = max(len(label) for label in model_labels) + 2
    model_col_width = max(model_col_width, 8)
    task_col_width = 6  # 缩写都很短

    # 构建表格
    lines = ["📊 当前任务模型路由表"]

    # 表头分隔线
    header_parts = [f"{'模型':<{model_col_width}}"]
    for _, abbr in task_abbrevs:
        header_parts.append(f"{abbr:^{task_col_width}}")
    header = "│".join(header_parts)

    separator = "┼".join(
        ["─" * model_col_width]
        + ["─" * task_col_width] * len(task_abbrevs)
    )

    top_border = "┌" + "┬".join(
        ["─" * model_col_width]
        + ["─" * task_col_width] * len(task_abbrevs)
    ) + "┐"

    mid_border = "├" + separator + "┤"

    bottom_border = "└" + "┴".join(
        ["─" * model_col_width]
        + ["─" * task_col_width] * len(task_abbrevs)
    ) + "┘"

    lines.append(top_border)
    lines.append("│" + "│".join(header_parts) + "│")
    lines.append(mid_border)

    # 每行数据
    for model, label in zip(matrix.models, model_labels):
        row_parts = [f"{label:<{model_col_width}}"]
        for task_id, _ in task_abbrevs:
            weight = matrix.get_weight(task_id, model.id)
            is_best = best_models.get(task_id) == model.id
            if is_best:
                cell = f"{weight}★"
            else:
                cell = str(weight)
            row_parts.append(f"{cell:^{task_col_width}}")
        lines.append("│" + "│".join(row_parts) + "│")

    lines.append(bottom_border)
    lines.append("★ = 该任务类型的最优模型（路由首选）")

    return "\n".join(lines)
