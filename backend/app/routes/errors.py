"""GET /api/errors, GET /api/errors/:id/export/docx —— 对齐 FaultHistoryCenterView.vue / FaultDetailDrawer.vue"""
import json
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file

from ..db import get_fault_conn
from ..export import build_fault_report_docx
from ..pagination import PaginationError, parse_page

bp = Blueprint("errors", __name__)


def _row_to_item(row):
    item = dict(row)
    item["fault_report"] = json.loads(item["fault_report"])
    return item


@bp.get("/api/errors")
def list_errors():
    try:
        page, page_size = parse_page(request)
    except PaginationError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    sort = request.args.get("sort", "DESC").upper()
    sort = "DESC" if sort not in ("ASC", "DESC") else sort

    with get_fault_conn() as conn:
        # JSON 序列化空格可能因版本变化，按 source_type 键值判断，避免旧
        # mock/seed 故障混入正式接口。
        clause = "WHERE fault_report LIKE ? OR fault_report LIKE ?"
        filter_values = ('%"source_type": "scenario_engine"%', '%"source_type":"scenario_engine"%')
        total = conn.execute(f"SELECT COUNT(*) FROM fault_errors {clause}", filter_values).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM fault_errors {clause} ORDER BY timestamp {sort} LIMIT ? OFFSET ?",
            (*filter_values, page_size, (page - 1) * page_size),
        ).fetchall()

    items = [_row_to_item(r) for r in rows]
    return jsonify({"items": items, "total": total, "source": "scenario_engine"})


@bp.get("/api/errors/<int:error_id>/export/docx")
def export_error_docx(error_id):
    with get_fault_conn() as conn:
        row = conn.execute(
            "SELECT * FROM fault_errors WHERE id = ? AND (fault_report LIKE ? OR fault_report LIKE ?)",
            (error_id, '%"source_type": "scenario_engine"%', '%"source_type":"scenario_engine"%'),
        ).fetchone()

    if not row:
        return jsonify({"error": "未找到该故障记录"}), 404

    buf = build_fault_report_docx(_row_to_item(row))
    filename = f"FaultReport_{error_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.docx"
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=filename,
    )
