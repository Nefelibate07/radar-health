"""本地用户目录和扩展模块登记接口。

这两个页面原本只有浏览器内的演示数组。现在改为 SQLite 持久化，
但不扩展为认证、远程代码执行或插件加载系统。
"""
import sqlite3

from flask import Blueprint, jsonify, request

from .. import db

bp = Blueprint("management", __name__)

ROLES = {"系统管理员", "运维工程师", "观察员"}
STATUSES = {"启用", "禁用"}


@bp.get("/api/users")
def list_users():
    return jsonify({"ok": True, "data": db.list_local_users(), "scope": "local_demo_directory"})


@bp.post("/api/users")
def add_user():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    role = payload.get("role")
    if not username or len(username) > 64 or role not in ROLES:
        return jsonify({"ok": False, "error": "用户名不能为空且角色必须有效。"}), 400
    try:
        return jsonify({"ok": True, "data": db.add_local_user(username, role)}), 201
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "error": "用户名已存在。"}), 409


@bp.put("/api/users/<int:user_id>")
def update_user(user_id):
    payload = request.get_json(silent=True) or {}
    role = payload.get("role")
    status = payload.get("status")
    if role is not None and role not in ROLES:
        return jsonify({"ok": False, "error": "角色无效。"}), 400
    if status is not None and status not in STATUSES:
        return jsonify({"ok": False, "error": "状态必须为启用或禁用。"}), 400
    row = db.update_local_user(user_id, role=role, status=status)
    if row is None:
        return jsonify({"ok": False, "error": "用户不存在或没有修改内容。"}), 404
    return jsonify({"ok": True, "data": row})


@bp.get("/api/extensions")
def list_extensions():
    return jsonify({"ok": True, "data": db.list_extension_modules(), "scope": "registration_only"})


@bp.post("/api/extensions")
def add_extension():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    api_path = str(payload.get("api_path", "")).strip()
    if not name or not api_path.startswith("/api/"):
        return jsonify({"ok": False, "error": "模块名称不能为空，接口地址必须以 /api/ 开头。"}), 400
    try:
        return jsonify({"ok": True, "data": db.add_extension_module(name, api_path)}), 201
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "error": "模块名称已存在。"}), 409


@bp.put("/api/extensions/<int:module_id>")
def update_extension(module_id):
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload.get("enabled"), bool):
        return jsonify({"ok": False, "error": "enabled 必须是布尔值。"}), 400
    row = db.update_extension_module(module_id, payload["enabled"])
    if row is None:
        return jsonify({"ok": False, "error": "模块不存在。"}), 404
    return jsonify({"ok": True, "data": row})
