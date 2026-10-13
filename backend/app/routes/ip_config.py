"""GET/POST /api/config/ip —— 对齐 IPSettingIndustrialView.vue / demo/IPSettingView.vue"""
import re
import json
import sqlite3
from pathlib import Path
from datetime import datetime

from flask import Blueprint, jsonify, request

from .. import db

bp = Blueprint("ip_config", __name__)

_IPV4_RE = re.compile(
    r"^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$"
)


@bp.get("/api/config/ip")
def get_ip():
    current_ip = db.get_setting("upper_computer_ip", "127.0.0.1")
    return jsonify({"current_ip": current_ip})


@bp.post("/api/config/ip")
def set_ip():
    payload = request.get_json(silent=True) or {}
    new_ip = payload.get("new_ip", "")
    if not _IPV4_RE.match(new_ip):
        return jsonify({"error": "IP 格式不正确"}), 400
    db.set_setting("upper_computer_ip", new_ip)
    return jsonify({"ok": True, "current_ip": new_ip})


DEFAULT_PATHS = {
    'capture_mode': 'replay',
    'capture_input_dir': '',
    'generator_output_dir': '',
    'health_database_path': '',
    'fault_database_path': '',
    'file_pattern': '*.txt,*.asc',
    'poll_interval_seconds': 1.0,
}


@bp.get('/api/config/paths')
def get_paths():
    raw = db.get_setting('data_paths')
    try:
        data = json.loads(raw) if raw else {}
    except (TypeError, json.JSONDecodeError):
        data = {}
    return jsonify({'ok': True, 'data': {**DEFAULT_PATHS, **data}})


@bp.post('/api/config/paths')
def set_paths():
    payload = request.get_json(silent=True) or {}
    data = {**DEFAULT_PATHS, **{key: payload[key] for key in DEFAULT_PATHS if key in payload}}
    if data['capture_mode'] not in {'replay', 'file_capture', 'file_generator'}:
        return jsonify({'ok': False, 'error': 'capture_mode 必须是 replay、file_capture 或 file_generator'}), 400
    try:
        data['poll_interval_seconds'] = max(0.1, float(data['poll_interval_seconds']))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'poll_interval_seconds 必须是数字'}), 400
    db.set_setting('data_paths', json.dumps(data, ensure_ascii=False))
    try:
        db.init_configured_databases()
    except (OSError, sqlite3.Error) as exc:
        return jsonify({'ok': False, 'error': f'数据库目录不可用：{exc}'}), 400
    return jsonify({'ok': True, 'data': data, 'updated_at': datetime.now().isoformat(timespec='seconds')})
