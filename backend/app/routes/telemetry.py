"""POST /api/send-item —— 主动上报联调入口。

当前系统的正式信号来源是 ScenarioEngine 的合成演示快照。这个兼容接口只返回
当前唯一快照，不把外部 JSON 伪装成新的健康信号，也不写入旁路 health_logs。
"""
from flask import Blueprint, jsonify, request
from ..scenario import get_dashboard_payload

bp = Blueprint("telemetry", __name__)


@bp.post("/api/send-item")
def send_item():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not payload:
        return jsonify({"ok": False, "error": "请求体必须是非空 JSON 对象"}), 400

    # 该兼容入口不接收任意外部测点；只有前端联调约定的来源标记可以
    # 触发“返回当前快照”。这样既保持旧页面可用，也不会让任意 JSON 被
    # 误报成已接入的雷达遥测。
    source = payload.get("source")
    is_trigger = payload.get("test") == "trigger"
    if source not in {None, "authority_replay"} or (source is None and not is_trigger):
        return jsonify({
            "ok": False,
            "error": "仅支持 source=authority_replay 或 test=trigger 的联调请求",
        }), 400

    # 保留旧的 ok 响应，同时返回同一场景引擎的当前快照，
    # 让主动上报接口、Socket.IO 和健康页面不会各自看到不同的模拟数据。
    dashboard = get_dashboard_payload()
    record = dashboard.get("scenario_record", {})
    return jsonify({
        "ok": True,
        "dashboard": dashboard,
        "source": {
            "source_type": record.get("source_type"),
            "source_file": record.get("source_file"),
            "source_line_no": record.get("source_line_no"),
            "source_decoded_timestamp": record.get("source_decoded_timestamp"),
            "source_sequence": record.get("source_sequence"),
            "source_quality": record.get("source_quality"),
        },
    })
