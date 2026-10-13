"""GET/DELETE /api/logs, GET /api/export/docx —— 只读取真实场景快照。"""
import json
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file

from ..db import get_health_conn
from ..export import build_health_report_docx
from ..pagination import PaginationError, parse_page

bp = Blueprint("logs", __name__)


def _snapshot_row(row):
    payload = json.loads(row["payload_json"])
    health = payload.get("data", {}).get("health", {})
    parameters = health.get("parameters", [])
    motors = [
        item for item in parameters
        if item.get("dtype") != "enum" and ("电机" in item.get("name", "") or "motor" in item.get("name", "").lower())
    ]
    temperatures = [item for item in parameters if item.get("unit") == "℃"]
    record = payload.get("scenario_record", {})
    return {
        "id": row["sequence"],
        "timestamp": row["timestamp"],
        "sys_mode": record.get("mode_label") or row["mode"],
        "sys_lock_status": "合成演示快照",
        "m1_temp": temperatures[0].get("value") if temperatures else None,
        "m2_temp": temperatures[1].get("value") if len(temperatures) > 1 else None,
        "overall_score": row["overall_score"],
        "overall_status": row["overall_status"],
        "source_type": row["source_type"],
        "source_file": row["source_file"],
        "source_line_no": row["source_line_no"],
        "source_sequence": row["source_sequence"],
        "parameter_count": len(parameters),
        "motor_samples": [
            {"name": item.get("name"), "value": item.get("value"), "unit": item.get("unit", "")}
            for item in motors[:6]
        ],
    }


@bp.get("/api/logs")
def list_logs():
    try:
        page, page_size = parse_page(request)
    except PaginationError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    sort = request.args.get("sort", "DESC").upper()
    sort = "DESC" if sort not in ("ASC", "DESC") else sort

    with get_health_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM scenario_snapshots").fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM scenario_snapshots ORDER BY timestamp {sort}, sequence {sort} LIMIT ? OFFSET ?",
            (page_size, (page - 1) * page_size),
        ).fetchall()

    return jsonify({"items": [_snapshot_row(row) for row in rows], "total": total, "source": "scenario_snapshots"})


@bp.delete("/api/logs/<int:log_id>")
def delete_log(log_id):
    with get_health_conn() as conn:
        conn.execute("DELETE FROM scenario_snapshots WHERE sequence = ?", (log_id,))
        conn.execute("DELETE FROM health_database_records WHERE scenario_sequence = ?", (log_id,))
    return jsonify({"ok": True})


@bp.get("/api/export/docx")
def export_docx():
    start = request.args.get("start")
    end = request.args.get("end")
    algorithm = request.args.get("algorithm")

    # DOCX 展开每条完整快照的成本较高。默认最多导出最近 1000 条，仍允许
    # 页面通过 limit 选择更小的范围，避免历史库增长后一次请求拖住场景线程。
    try:
        _, export_limit = parse_page(
            request,
            default_size=1000,
            max_size=1000,
        )
    except PaginationError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    with get_health_conn() as conn:
        clauses = []
        params = []
        if start:
            clauses.append("timestamp >= ?")
            params.append(start)
        if end:
            clauses.append("timestamp <= ?")
            params.append(end)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"SELECT * FROM scenario_snapshots {where} ORDER BY timestamp DESC, sequence DESC LIMIT ?",
            [*params, export_limit],
        ).fetchall()

    if not rows:
        return jsonify({"error": "所选时间范围内无数据"}), 400

    buf = build_health_report_docx(start, end, algorithm, [_snapshot_row(row) for row in rows])
    filename = f"HealthReport_{datetime.now().strftime('%Y%m%d%H%M%S')}.docx"
    response = send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=filename,
    )
    response.headers["X-Export-Limit"] = str(export_limit)
    response.headers["X-Export-Truncated"] = "1" if len(rows) >= export_limit else "0"
    return response
