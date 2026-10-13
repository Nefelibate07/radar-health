"""调试专用接口 —— 手动触发一次 fault_alarm 推送,方便联调告警链路(通知/详情抽屉)。
不属于前端正式契约,仅用于开发阶段验证。
"""
from flask import Blueprint, jsonify

from ..scenario import build_scenario_alarm
from ..sockets import emit_fault_alarm

bp = Blueprint("debug", __name__)


@bp.post("/api/debug/trigger-fault")
def trigger_fault():
    emit_fault_alarm(build_scenario_alarm())
    return jsonify({"ok": True})
