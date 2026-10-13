"""应用工厂 —— 组装 Flask app、CORS、SQLite 初始化、蓝图注册、Socket.IO。"""
import atexit

from flask import Flask
from flask_cors import CORS

from .config import CORS_ORIGINS
from .db import init_db
from .sockets import socketio, start_dashboard_push, stop_dashboard_push
from .hourly_job import start_hourly_job, stop_hourly_job
from .scenario import start_scenario_engine, stop_scenario_engine

_CLEANUP_REGISTERED = False


def create_app():
    global _CLEANUP_REGISTERED
    app = Flask(__name__)
    CORS(app, origins=CORS_ORIGINS)

    init_db()
    # 不再写入随机种子日志/故障/趋势数据。实时数据、历史数据和前端显示
    # 全部由 ScenarioEngine 的合成演示快照快照提供。

    # 模型文件是运行时产物，首次启动自动训练一次；训练数据规模很小，保证桌面端
    # 首次打开也能直接看到真实的模型状态。失败时不阻断已有监测页面，接口会返回明确错误。
    from .model_runtime import ensure_models
    try:
        ensure_models()
    except Exception:
        from .config import logger
        logger.exception("[models] initial model training failed; health pages remain available")

    from .routes import logs, errors, health, ip_config, telemetry, debug, scenario, graph, database, algorithms, management, system, radar_reconstruction, data_processing, fault_diagnosis

    app.register_blueprint(logs.bp)
    app.register_blueprint(errors.bp)
    app.register_blueprint(health.bp)
    app.register_blueprint(ip_config.bp)
    app.register_blueprint(telemetry.bp)
    app.register_blueprint(debug.bp)
    app.register_blueprint(scenario.bp)
    app.register_blueprint(graph.bp)
    app.register_blueprint(database.bp)
    app.register_blueprint(algorithms.bp)
    app.register_blueprint(radar_reconstruction.bp)
    app.register_blueprint(data_processing.bp)
    app.register_blueprint(fault_diagnosis.bp)
    app.register_blueprint(management.bp)
    app.register_blueprint(system.bp)

    socketio.init_app(app)
    start_scenario_engine()
    # 配置为 file_capture 时，服务启动即跟读私有工程原始文本目录；首次有效
    # 演示快照 到达前不会用内部合成场景覆盖页面。
    try:
        from .db import get_setting
        import json
        from .file_capture import FILE_CAPTURE
        paths = json.loads(get_setting("data_paths") or "{}")
        if paths.get("capture_mode") in {"file_capture", "file_generator"}:
            capture_dir = paths.get("capture_input_dir") if paths.get("capture_mode") == "file_capture" else paths.get("generator_output_dir")
            if capture_dir:
                FILE_CAPTURE.start(capture_dir, paths.get("file_pattern"), paths.get("poll_interval_seconds"))
    except Exception:
        from .config import logger
        logger.exception("[capture] configured file capture could not start")
    start_dashboard_push()

    # 启动每小时定时快照任务
    start_hourly_job()

    # Flask 的 teardown_appcontext 会在每个请求后触发，不能在这里停后台线程。
    # 统一注册为进程退出清理，确保 REST 请求不会意外终止场景/小时任务。
    if not _CLEANUP_REGISTERED:
        def shutdown():
            stop_hourly_job()
            stop_scenario_engine()
            stop_dashboard_push()

        atexit.register(shutdown)
        _CLEANUP_REGISTERED = True

    return app
