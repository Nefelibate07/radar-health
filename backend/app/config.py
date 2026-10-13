import os
import logging
from pathlib import Path

from .paths import get_backend_data_dir, get_db_path, get_log_dir, ensure_directories

# 确保数据目录存在
ensure_directories()

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
DATA_DIR = get_backend_data_dir()
DB_PATH = get_db_path()

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "5000"))
DEBUG = os.environ.get("FLASK_DEBUG", "1") == "1"

# 开发阶段放开跨域,方便前端在 5173/5174 等任意 vite 端口直连;
# 部署时应收紧为具体前端地址。
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")

# 后台线程向前端推送 update_dashboard 的间隔(秒)
DASHBOARD_PUSH_INTERVAL = float(os.environ.get("DASHBOARD_PUSH_INTERVAL", "1"))

# ===== 日志配置 =====
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FILE = get_log_dir() / "app.log"

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='[%(asctime)s] %(levelname)s [%(name)s]: %(message)s',
    handlers=[
        logging.StreamHandler(),  # 打印到控制台
        logging.FileHandler(LOG_FILE, encoding='utf-8'),  # 写到日志文件
    ]
)

logger = logging.getLogger(__name__)
logger.info(f"后端服务启动配置: HOST={HOST}, PORT={PORT}, DEBUG={DEBUG}, LOG_LEVEL={LOG_LEVEL}")
