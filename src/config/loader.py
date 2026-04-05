# 配置加载器
"""
从 JSON / YAML 文件加载配置到 dataclass 实例。

运行时仅依赖 Python 标准库 (json)。
如果安装了 pyyaml，也可以加载 YAML 格式。
"""

import json
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from .schema import RoutingMatrix


def _load_data(path: Path) -> dict:
    """从文件加载数据，根据扩展名自动选择解析器

    Args:
        path: 文件路径

    Returns:
        解析后的字典

    Raises:
        ImportError: 需要 pyyaml 但未安装
    """
    with open(path, "r", encoding="utf-8") as f:
        if path.suffix in ('.yaml', '.yml'):
            if not HAS_YAML:
                raise ImportError(
                    f"需要 pyyaml 才能读取 YAML 文件: {path}\n"
                    f"请安装: pip install pyyaml\n"
                    f"或使用 JSON 格式的配置文件。"
                )
            return yaml.safe_load(f)
        else:
            return json.load(f)


class ConfigLoader:
    """配置加载器

    使用方式：
        loader = ConfigLoader(config_dir="config/")
        matrix = loader.load_routing_matrix()
        settings = loader.load_settings()
    """

    def __init__(self, config_dir: str = "config/"):
        """
        Args:
            config_dir: 配置文件目录路径
        """
        self.config_dir = Path(config_dir)

    def load_routing_matrix(self, filename: str | None = None) -> RoutingMatrix:
        """加载路由矩阵

        查找顺序：JSON → YAML（优先使用无依赖的 JSON）。

        Args:
            filename: 矩阵文件名（不指定时自动查找）

        Returns:
            RoutingMatrix 实例

        Raises:
            FileNotFoundError: 矩阵文件不存在
            ValueError: 文件格式或数据结构不正确
        """
        if filename is not None:
            path = self.config_dir / filename
        else:
            # 自动查找：JSON 优先
            json_path = self.config_dir / "routing_matrix.json"
            yaml_path = self.config_dir / "routing_matrix.yaml"
            if json_path.exists():
                path = json_path
            elif yaml_path.exists():
                path = yaml_path
            else:
                raise FileNotFoundError(
                    f"路由矩阵文件不存在: 在 {self.config_dir} 中均未找到 "
                    f"routing_matrix.json 或 routing_matrix.yaml\n"
                    f"请先运行 generate_matrix.py 生成路由矩阵。"
                )

        if not path.exists():
            raise FileNotFoundError(
                f"路由矩阵文件不存在: {path}\n"
                f"请先运行 generate_matrix.py 生成路由矩阵。"
            )

        data = _load_data(path)

        if not isinstance(data, dict):
            raise ValueError(f"路由矩阵文件格式错误: 期望字典，收到 {type(data).__name__}")

        return RoutingMatrix.from_dict(data)

    def load_settings(self, filename: str | None = None) -> dict:
        """加载运行时配置

        Args:
            filename: 配置文件名（不指定时自动查找 JSON → YAML）

        Returns:
            配置字典

        Raises:
            FileNotFoundError: 配置文件不存在
        """
        if filename is not None:
            path = self.config_dir / filename
        else:
            json_path = self.config_dir / "settings.json"
            yaml_path = self.config_dir / "settings.yaml"
            if json_path.exists():
                path = json_path
            elif yaml_path.exists():
                path = yaml_path
            else:
                raise FileNotFoundError(
                    f"配置文件不存在: 在 {self.config_dir} 中均未找到 "
                    f"settings.json 或 settings.yaml"
                )

        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {path}")

        return _load_data(path)
