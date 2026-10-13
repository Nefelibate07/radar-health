"""跨平台路径管理 —— 支持 Mac/Windows/Linux 部署。

核心理念：
- 优先级：环境变量 → 相对路径 → 工作目录
    - 所有路径返回 pathlib.Path（自动处理 / vs \\ 差异）
- 初始化时验证（快速失败，清晰的错误提示）
"""
import os
from pathlib import Path


def get_project_root():
    """获取项目根目录 (毕业设计/雷达健康监测项目/)。

    查询顺序：
    1. 相对于当前模块位置（正常情况）
    2. 环境变量 PROJECT_ROOT
    3. 当前工作目录（命令行运行）
    4. 报错
    """
    # 方案 1: 相对于当前模块位置
    # 这个模块在 backend/app/paths.py
    # 所以 parent.parent = backend/app/.. = backend = 毕业设计/雷达健康监测项目/backend
    # 再 parent = 毕业设计/雷达健康监测项目/
    app_dir = Path(__file__).resolve().parent  # backend/app/
    backend_dir = app_dir.parent               # backend/
    potential_root = backend_dir.parent        # 毕业设计/雷达健康监测项目/

    if (potential_root / "config" / "params.json").exists():
        return potential_root

    # 方案 2: 环境变量
    if os.environ.get("PROJECT_ROOT"):
        root = Path(os.environ["PROJECT_ROOT"])
        if (root / "config" / "params.json").exists():
            return root

    # 方案 3: 当前工作目录
    if (Path.cwd() / "config" / "params.json").exists():
        return Path.cwd()

    # 都找不到，报错
    raise RuntimeError(
        f"Cannot find project root. Searched:\n"
        f"  1. Relative to module: {potential_root}\n"
        f"  2. Environment variable PROJECT_ROOT: {os.environ.get('PROJECT_ROOT', 'not set')}\n"
        f"  3. Current working directory: {Path.cwd()}\n"
        f"Please set PROJECT_ROOT environment variable or run from project directory."
    )


# 缓存项目根目录（避免重复查找）
_PROJECT_ROOT = None


def _ensure_project_root():
    """初始化项目根目录缓存。"""
    global _PROJECT_ROOT
    if _PROJECT_ROOT is None:
        _PROJECT_ROOT = get_project_root()
    return _PROJECT_ROOT


def get_config_dir():
    """获取 config/ 目录（存储参数、配置文件）。"""
    root = _ensure_project_root()
    return root / "config"


def get_params_path():
    """获取 config/params.json 路径（子系统参数定义）。"""
    config_dir = get_config_dir()
    params_file = config_dir / "params.json"
    if not params_file.exists():
        raise FileNotFoundError(
            f"params.json not found at {params_file}\n"
            f"Expected location: {config_dir}/params.json"
        )
    return params_file


def get_backend_data_dir():
    """获取运行时数据目录（数据库、日志）。

    打包后的桌面应用通常安装在只读目录（例如 Windows 的 Program Files
    或 macOS 的 App bundle），所以运行时数据不能继续写到应用资源目录。
    通过 RADAR_DATA_DIR 可以把数据库和日志重定向到系统用户数据目录；
    未设置时仍保持源码开发模式下的 backend/data 行为。
    """
    data_dir = os.environ.get("RADAR_DATA_DIR")
    if data_dir:
        return Path(data_dir).expanduser()

    root = _ensure_project_root()
    return root / "backend" / "data"


def get_db_path():
    """获取数据库文件路径 backend/data/app.db。"""
    return get_backend_data_dir() / "app.db"


def get_log_dir():
    """获取日志目录 backend/data/logs/。"""
    return get_backend_data_dir() / "logs"


def ensure_directories():
    """确保所有必需的目录存在，带错误处理。"""
    dirs = [
        (get_backend_data_dir(), "数据目录"),
        (get_log_dir(), "日志目录"),
    ]

    for dir_path, desc in dirs:
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            raise RuntimeError(
                f"权限不足，无法创建{desc}: {dir_path}\n"
                f"请检查文件权限或以管理员/sudo 身份运行。"
            )
        except OSError as e:
            raise RuntimeError(
                f"无法创建{desc}: {dir_path}\n"
                f"错误: {e}"
            )
