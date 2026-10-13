"""开发文档 8-23 要求的健康/故障数据库查询接口。"""
from flask import Blueprint, jsonify, request

from .. import db
from ..pagination import PaginationError, parse_range

bp = Blueprint("database", __name__)


def _range():
    limit, offset = parse_range(request)
    return request.args.get("start"), request.args.get("end"), limit, offset


@bp.get("/api/database/health")
def health_records():
    try:
        start, end, limit, offset = _range()
    except PaginationError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "data": db.query_health_records(start, end, limit, offset)})


@bp.get("/api/database/fault-parameters")
def fault_parameters():
    try:
        start, end, limit, offset = _range()
    except PaginationError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "data": db.query_fault_parameters(start, end, limit, offset)})


@bp.get("/api/database/fault-analysis")
def fault_analysis():
    try:
        start, end, limit, offset = _range()
    except PaginationError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "data": db.query_fault_analysis(start, end, limit, offset)})
