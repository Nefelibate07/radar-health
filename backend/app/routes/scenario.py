"""场景模拟控制接口。"""
import json
from flask import Blueprint, jsonify, request

from ..scenario import (
    SCENARIO_MODES,
    get_dashboard_payload,
    get_scenario_status,
    set_scenario_mode,
    start_scenario_engine,
    stop_scenario_engine,
)
from ..authority_replay import AUTHORITY_REPLAY
from ..file_capture import FILE_CAPTURE

bp = Blueprint("scenario", __name__)


@bp.get("/api/scenario/status")
def status():
    return jsonify({"ok": True, "data": get_scenario_status()})


@bp.get("/api/dashboard")
def dashboard():
    """返回当前场景引擎快照，供需要手动刷新的页面复用唯一数据源。"""
    return jsonify(get_dashboard_payload())


@bp.post("/api/scenario/mode")
def set_mode():
    payload = request.get_json(silent=True) or {}
    mode = payload.get("mode")
    if mode not in SCENARIO_MODES:
        return jsonify({"ok": False, "error": f"未知场景模式: {mode}", "modes": list(SCENARIO_MODES)}), 400
    return jsonify({"ok": True, "data": set_scenario_mode(mode), "dashboard": get_dashboard_payload()})


@bp.post("/api/scenario/trigger")
def trigger():
    return set_mode()


@bp.post("/api/scenario/start")
def start():
    start_scenario_engine()
    return jsonify({"ok": True, "data": get_scenario_status()})


@bp.post("/api/scenario/stop")
def stop():
    stop_scenario_engine()
    return jsonify({"ok": True, "data": get_scenario_status()})


@bp.post("/api/scenario/replay/reset")
def reset_replay():
    """将合成演示快照游标归零，不改变场景模式或实时接口契约。"""
    AUTHORITY_REPLAY.reset()
    return jsonify({"ok": True, "data": get_scenario_status()})


@bp.get('/api/capture/status')
def capture_status():
    return jsonify({'ok': True, 'data': FILE_CAPTURE.status()})


@bp.post('/api/capture/start')
def capture_start():
    payload = request.get_json(silent=True) or {}
    if payload.get('mode') == 'file_generator' and not payload.get('input_dir'):
        payload['input_dir'] = payload.get('generator_output_dir')
    try:
        data = FILE_CAPTURE.start(payload.get('input_dir'), payload.get('pattern'), payload.get('interval'))
    except ValueError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400
    return jsonify({'ok': True, 'data': data})


@bp.get('/api/capture/decoder')
def capture_decoder():
    from ..authority_raw_capture import decoder_status
    try:
        return jsonify({'ok': True, 'data': decoder_status()})
    except (OSError, RuntimeError, ValueError) as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 500


@bp.post('/api/capture/stop')
def capture_stop():
    return jsonify({'ok': True, 'data': FILE_CAPTURE.stop()})


@bp.post('/api/capture/test-read')
def capture_test_read():
    payload = request.get_json(silent=True) or {}
    input_dir = payload.get('input_dir')
    pattern = payload.get('pattern') or '*.txt,*.asc'
    if not input_dir:
        return jsonify({'ok': False, 'error': '请提供 input_dir'}), 400
    from pathlib import Path
    path = Path(input_dir).expanduser()
    if not path.is_dir():
        return jsonify({'ok': False, 'error': f'目录不存在：{path}'}), 400
    try:
        result = FILE_CAPTURE.test_read(str(path), pattern)
    except (OSError, ValueError, RuntimeError) as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400
    return jsonify({'ok': True, 'data': result})
