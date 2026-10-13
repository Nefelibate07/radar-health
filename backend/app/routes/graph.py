"""关系图导入接口。"""

from flask import Blueprint, jsonify, request

from ..graph_import import GraphImportError
from ..scenario import get_dashboard_payload, get_graph_status, reset_graph, import_graph as apply_graph_import

bp = Blueprint("graph", __name__)


@bp.get("/api/graph")
def graph_status():
    return jsonify({"ok": True, "data": get_graph_status()})


@bp.post("/api/graph/import")
def import_graph_file():
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({"ok": False, "error": "请选择 .vsdx、.xlsx、.xls 或 .csv 文件。"}), 400
    try:
        status = apply_graph_import(uploaded.filename, uploaded.read())
        # 关系图导入后立即构造一次完整快照，确保前端拿到的 dashboard
        # 与下一次 Socket.IO 推送使用同一张图，而不是延迟到后台线程才暴露错误。
        payload = get_dashboard_payload()
    except GraphImportError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception:
        from flask import current_app
        current_app.logger.exception("graph import failed")
        return jsonify({"ok": False, "error": "关系图解析失败，请检查文件格式和表头。"}), 400
    return jsonify({"ok": True, "data": status, "dashboard": payload})


@bp.post("/api/graph/reset")
def reset_imported_graph():
    status = reset_graph()
    return jsonify({"ok": True, "data": status, "dashboard": get_dashboard_payload()})
