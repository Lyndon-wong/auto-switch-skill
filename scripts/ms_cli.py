#!/usr/bin/env python3
# Auto-Switch-Skill CLI 入口
"""
通过命令行执行 /ms 子命令，用于 OpenClaw Agent 的 shell 调用。

运行时仅依赖 Python 标准库（json, re, argparse 等）。
配置文件使用 JSON 格式（由 generate_matrix.py 生成）。

用法：
    python3 ms_cli.py help
    python3 ms_cli.py status  --config-dir config/ --current-model sjtu/minimax-m2.5
    python3 ms_cli.py list    --config-dir config/ --current-model sjtu/minimax-m2.5
    python3 ms_cli.py switch  --target deepseek-v3.2 --config-dir config/ --current-model sjtu/minimax-m2.5
    python3 ms_cli.py router  --config-dir config/
    python3 ms_cli.py evaluate --thought "[TASK_TYPE: CODE_COMPLEX]" --config-dir config/ --current-model sjtu/minimax-m2.5
"""

import argparse
import json
import sys
from pathlib import Path

# 设置模块搜索路径：将 Skill 根目录加入 sys.path
SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT))

from src.config.loader import ConfigLoader
from src.core.evaluator import TaskEvaluator
from src.core.router import SwitchRouter
from src.core.state import SwitchStateManager
from src.skills.ms_command import MsCommandHandler
from src.utils.formatter import format_help


def build_components(args):
    """构建核心组件

    Args:
        args: 解析后的命令行参数

    Returns:
        (handler, router, state_mgr, matrix) 元组
    """
    config_dir = getattr(args, 'config_dir', 'config/')
    current_model = getattr(args, 'current_model', '')

    loader = ConfigLoader(config_dir=config_dir)
    matrix = loader.load_routing_matrix()
    state_mgr = SwitchStateManager(default_model=current_model)
    evaluator = TaskEvaluator()
    router = SwitchRouter(matrix=matrix, state_mgr=state_mgr, evaluator=evaluator)
    handler = MsCommandHandler(router=router, state_mgr=state_mgr, matrix=matrix)

    return handler, router, state_mgr, matrix


def cmd_help(args):
    """显示帮助信息"""
    print(format_help())


def cmd_status(args):
    """显示当前运行状态"""
    handler, _, _, _ = build_components(args)
    print(handler.cmd_status())


def cmd_list(args):
    """列出所有可用模型"""
    handler, _, _, _ = build_components(args)
    print(handler.cmd_list())


def cmd_router(args):
    """显示路由表"""
    handler, _, _, _ = build_components(args)
    print(handler.cmd_router())


def cmd_switch(args):
    """切换到指定模型"""
    handler, _, state_mgr, matrix = build_components(args)

    # 调用切换
    output = handler.cmd_switch(args.target)
    print(output)

    # 输出 JSON 格式的切换结果，便于 Agent 解析
    state = state_mgr.get_state()
    if "✅ 模型已切换" in output:
        # 查找目标模型的完整 ID
        model = matrix.get_model_by_alias(args.target)
        if model is None:
            model = matrix.get_model_by_id(args.target)
        target_id = model.id if model else args.target

        result = {
            "action": "switch",
            "success": True,
            "target_model": target_id,
            "previous_model": state.current_model if state.current_model != target_id else "",
        }
    else:
        result = {"action": "switch", "success": False}

    print(f"\n__JSON_RESULT__:{json.dumps(result, ensure_ascii=False)}")


def cmd_auto(args):
    """切换到自动模式"""
    handler, _, _, _ = build_components(args)
    print(handler.cmd_auto())


def cmd_manual(args):
    """切换到手动模式"""
    handler, _, _, _ = build_components(args)
    print(handler.cmd_manual())


def cmd_evaluate(args):
    """评估 thought 文本，判断是否需要切换模型

    输出 JSON 格式的判定结果。
    """
    _, router, _, _ = build_components(args)

    result = router.process_message(args.thought)
    if result and result.success:
        output = {
            "action": "switch",
            "success": True,
            "previous_model": result.previous_model,
            "target_model": result.current_model,
            "reason": result.reason,
        }
    else:
        output = {"action": "none", "success": False}

    print(json.dumps(output, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(
        description="Auto-Switch-Skill CLI — 智能模型切换命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python3 ms_cli.py help\n"
            "  python3 ms_cli.py status --config-dir config/ --current-model sjtu/minimax-m2.5\n"
            "  python3 ms_cli.py switch --target deepseek-v3.2 --config-dir config/ --current-model sjtu/minimax-m2.5\n"
        ),
    )

    subparsers = parser.add_subparsers(dest='command', help='子命令')

    # --- help ---
    p_help = subparsers.add_parser('help', help='显示帮助信息')
    p_help.set_defaults(func=cmd_help)

    # --- status ---
    p_status = subparsers.add_parser('status', help='显示当前运行状态')
    p_status.add_argument('--config-dir', default='config/', help='配置目录路径')
    p_status.add_argument('--current-model', default='', help='当前使用的模型 ID')
    p_status.set_defaults(func=cmd_status)

    # --- list ---
    p_list = subparsers.add_parser('list', help='列出所有可用模型')
    p_list.add_argument('--config-dir', default='config/', help='配置目录路径')
    p_list.add_argument('--current-model', default='', help='当前使用的模型 ID')
    p_list.set_defaults(func=cmd_list)

    # --- router ---
    p_router = subparsers.add_parser('router', help='显示路由表')
    p_router.add_argument('--config-dir', default='config/', help='配置目录路径')
    p_router.add_argument('--current-model', default='', help='当前使用的模型 ID')
    p_router.set_defaults(func=cmd_router)

    # --- switch ---
    p_switch = subparsers.add_parser('switch', help='切换到指定模型')
    p_switch.add_argument('--target', required=True, help='目标模型别名或完整 ID')
    p_switch.add_argument('--config-dir', default='config/', help='配置目录路径')
    p_switch.add_argument('--current-model', default='', help='当前使用的模型 ID')
    p_switch.set_defaults(func=cmd_switch)

    # --- auto ---
    p_auto = subparsers.add_parser('auto', help='切换到自动模式')
    p_auto.add_argument('--config-dir', default='config/', help='配置目录路径')
    p_auto.add_argument('--current-model', default='', help='当前使用的模型 ID')
    p_auto.set_defaults(func=cmd_auto)

    # --- manual ---
    p_manual = subparsers.add_parser('manual', help='切换到手动模式')
    p_manual.add_argument('--config-dir', default='config/', help='配置目录路径')
    p_manual.add_argument('--current-model', default='', help='当前使用的模型 ID')
    p_manual.set_defaults(func=cmd_manual)

    # --- evaluate ---
    p_eval = subparsers.add_parser('evaluate', help='评估 thought 文本，判断是否需要切换')
    p_eval.add_argument('--thought', required=True, help='模型返回的 thought/thinking 文本')
    p_eval.add_argument('--config-dir', default='config/', help='配置目录路径')
    p_eval.add_argument('--current-model', default='', help='当前使用的模型 ID')
    p_eval.set_defaults(func=cmd_evaluate)

    args = parser.parse_args()

    if not args.command:
        # 无子命令 → 显示帮助
        cmd_help(args)
        return

    args.func(args)


if __name__ == '__main__':
    main()
