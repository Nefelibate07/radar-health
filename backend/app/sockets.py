"""Socket.IO 事件 —— 对齐 socket/dashboardSocket.js (update_dashboard) 与 demo/FaultAlarmListener.vue (fault_alarm)。

用 threading 模式(不装 eventlet/gevent):
  - eventlet/gevent 在 Windows + Python 3.12 上 monkey-patch 经常出兼容问题,
    而部署目标是 Windows(16G/RTX3060),所以选纯标准库线程的 threading 模式,
    牺牲一些并发吞吐,换跨平台稳定性 —— 骨架阶段的连接数很小,足够用。
"""
import threading

from flask_socketio import SocketIO

from .config import DASHBOARD_PUSH_INTERVAL, logger
from .scenario import build_scenario_alarm, consume_pending_alarm, get_dashboard_payload

socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")

_push_thread = None
_push_thread_lock = threading.Lock()
_stop_event = threading.Event()

def emit_fault_alarm(payload=None):
    """对外暴露的手动触发点(供 /api/debug/trigger-fault 调用,也供未来真实故障检测复用)。"""
    socketio.emit("fault_alarm", payload or build_scenario_alarm())


def _push_loop():
    logger.info("[sockets] dashboard push loop started")
    while not _stop_event.is_set():
        socketio.emit("update_dashboard", get_dashboard_payload())
        alarm = consume_pending_alarm()
        if alarm:
            emit_fault_alarm(alarm)
        _stop_event.wait(DASHBOARD_PUSH_INTERVAL)
    logger.info("[sockets] dashboard push loop stopped")


def start_dashboard_push():
    """启动后台推送线程(幂等,重复调用不会起第二个线程)。"""
    global _push_thread
    with _push_thread_lock:
        if _push_thread is None or not _push_thread.is_alive():
            _stop_event.clear()
            _push_thread = threading.Thread(target=_push_loop, daemon=True)
            _push_thread.start()
            logger.info("[sockets] dashboard push thread started")


def stop_dashboard_push():
    _stop_event.set()
    logger.info("[sockets] dashboard push stop signal sent")
