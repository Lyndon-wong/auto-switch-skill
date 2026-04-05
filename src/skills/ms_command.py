# 命令解析器
"""
解析 /ms 命令并分发到对应的处理函数。
每个处理函数返回格式化的文本字符串。

设计原则：纯函数式，接收字符串输入，返回字符串输出。
"""

from __future__ import annotations

from src.core.router import SwitchRouter
from src.core.state import SwitchStateManager
from src.config.schema import RoutingMatrix
from src.utils.formatter import (
    format_help,
    format_status,
    format_model_list,
    format_router_table,
)


class MsCommandHandler:
    """命令处理器

    使用方式：
        handler = MsCommandHandler(router, state_mgr, matrix)
        output = handler.handle("/ms status")
        # output 是格式化后的文本，直接返回给用户
    """

    # 已注册的子命令集合（用于区分命令和模型名）
    KNOWN_COMMANDS = {"help", "status", "list", "auto", "manual", "router"}

    def __init__(
        self,
        router: SwitchRouter,
        state_mgr: SwitchStateManager,
        matrix: RoutingMatrix,
    ):
        """
        Args:
            router: 路由引擎实例
            state_mgr: 状态管理器实例
            matrix: 路由矩阵实例
        """
        self.router = router
        self.state_mgr = state_mgr
        self.matrix = matrix

    def handle(self, command_text: str) -> str:
        """解析并执行命令

        Args:
            command_text: 完整命令文本，如 "/ms status"、"/ms ds-v3"

        Returns:
            格式化的输出文本
        """
        # 去除前缀 "/ms" 或 "/model-switch"
        text = command_text.strip()
        for prefix in ("/ms ", "/model-switch "):
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break
        else:
            if text in ("/ms", "/model-switch"):
                text = ""

        # 空命令或 help → 显示帮助
        if not text or text.lower() == "help":
            return self.cmd_help()

        # 分发子命令
        sub_cmd = text.split()[0].lower()

        if sub_cmd == "status":
            return self.cmd_status()
        elif sub_cmd == "list":
            return self.cmd_list()
        elif sub_cmd == "auto":
            return self.cmd_auto()
        elif sub_cmd == "manual":
            return self.cmd_manual()
        elif sub_cmd == "router":
            return self.cmd_router()
        else:
            # 尝试作为模型名解析
            return self.cmd_switch(sub_cmd)

    def cmd_help(self) -> str:
        """显示帮助信息

        Returns:
            帮助文本
        """
        return format_help()

    def cmd_status(self) -> str:
        """显示当前运行状态

        Returns:
            状态文本
        """
        state = self.state_mgr.get_state()
        return format_status(state, self.matrix)

    def cmd_list(self) -> str:
        """列出所有可用模型

        Returns:
            模型列表
        """
        state = self.state_mgr.get_state()
        return format_model_list(self.matrix, state.current_model)

    def cmd_auto(self) -> str:
        """切换到自动模式

        Returns:
            操作结果文本
        """
        state = self.state_mgr.get_state()
        if state.mode == "auto":
            return "⚠️ 当前已是自动模式，无需重复切换。"
        self.state_mgr.set_mode("auto")
        return "✅ 已切换到自动模式\n   系统将根据任务类型自动选取最优模型。"

    def cmd_manual(self) -> str:
        """切换到手动模式

        Returns:
            操作结果文本
        """
        state = self.state_mgr.get_state()
        if state.mode == "manual":
            return "⚠️ 当前已是手动模式，无需重复切换。"
        self.state_mgr.set_mode("manual")
        return "✅ 已切换到手动模式\n   自动切换已禁用，仅响应手动切换命令。"

    def cmd_switch(self, model_name: str) -> str:
        """切换到指定模型

        查找逻辑（按优先级）：
        1. 按别名查找
        2. 按完整 ID 查找
        3. 均未找到 → 返回错误提示

        切换逻辑：
        - 调用 router.manual_switch(target_model_id)
        - 不改变当前模式

        Args:
            model_name: 模型别名或完整 ID

        Returns:
            操作结果文本
        """
        # 查找模型
        model = self.matrix.get_model_by_alias(model_name)
        if model is None:
            model = self.matrix.get_model_by_id(model_name)
        if model is None:
            return f'❌ 未找到模型 "{model_name}"。使用 /ms list 查看可用模型。'

        result = self.router.manual_switch(model.id)
        if result.success:
            # 获取来源模型的别名
            prev_model = self.matrix.get_model_by_id(result.previous_model)
            prev_alias = prev_model.alias if prev_model else result.previous_model
            state = self.state_mgr.get_state()
            mode_emoji = "🤖 自动模式" if state.mode == "auto" else "✋ 手动模式"
            return (
                f"✅ 模型已切换\n"
                f"  来源: {prev_alias} ({result.previous_model})\n"
                f"  目标: {model.alias} ({model.id})\n"
                f"  当前模式: {mode_emoji}（未改变）"
            )
        else:
            return f"❌ 切换失败: {result.reason}"

    def cmd_router(self) -> str:
        """显示路由矩阵

        Returns:
            路由表文本
        """
        return format_router_table(self.matrix)
