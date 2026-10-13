"""Configuration and live status for every signal's processing pipeline."""
from flask import Blueprint, jsonify, request

from ..data_processing import get_processing_snapshot, save_processing_config

bp = Blueprint("data_processing", __name__)


@bp.get("/api/data-processing")
def get_data_processing():
    return jsonify(get_processing_snapshot())


@bp.put("/api/data-processing/config")
def put_data_processing_config():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "请求体必须是 JSON 对象"}), 400
    try:
        config = save_processing_config(payload)
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "data": config})
