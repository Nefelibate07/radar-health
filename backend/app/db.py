"""SQLite 持久化层 —— 用标准库 sqlite3,零依赖、跨平台,不用担心 Windows 兼容问题。

表设计与前端已读取的字段名严格对齐(见 frontend/src/views/*.vue 的 axios 调用):
  health_logs  -> GET/DELETE /api/logs, GET /api/export/docx      (HealthHistoryView)
  fault_errors -> GET /api/errors, GET /api/errors/:id/export/docx (FaultHistoryCenterView, FaultDetailDrawer)
  daily_scores -> GET /api/health/daily-report                    (AlertsView, HealthView)
  app_settings -> GET/POST /api/config/ip, GET/POST /api/health/algorithm (key-value 表,通用配置)
"""
import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager

from .config import logger
from .paths import get_db_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS health_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    sys_mode TEXT,
    sys_lock_status TEXT,
    m1_temp REAL,
    m2_temp REAL
);

CREATE TABLE IF NOT EXISTS fault_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    error_type TEXT NOT NULL,
    fault_report TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_scores (
    date TEXT PRIMARY KEY,
    score REAL NOT NULL,
    fault_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS hourly_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hour TEXT UNIQUE NOT NULL,
    overall_score REAL NOT NULL,
    overall_status TEXT NOT NULL,
    category_scores TEXT NOT NULL,
    fault_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

-- ScenarioEngine 是唯一实时信号源。每个推送给前端的快照同时写入这里，
-- 历史、趋势和导出接口只读取本表，不再回退到随机种子数据。
CREATE TABLE IF NOT EXISTS scenario_snapshots (
    sequence INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    mode TEXT NOT NULL,
    overall_score REAL NOT NULL,
    overall_status TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_file TEXT,
    source_line_no INTEGER,
    source_sequence INTEGER,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scenario_snapshots_timestamp ON scenario_snapshots(timestamp);

-- 开发文档 8-23：健康数据库只保存健康结果，不保存原始参数。
CREATE TABLE IF NOT EXISTS health_database_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_timestamp TEXT NOT NULL,
    scenario_sequence INTEGER NOT NULL UNIQUE,
    overall_score REAL NOT NULL,
    overall_status TEXT NOT NULL,
    subsystem_scores_json TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_file TEXT,
    source_line_no INTEGER,
    source_sequence INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_health_database_timestamp ON health_database_records(source_timestamp);

-- 故障数据库拆成原始参数和解释性分析两类，二者通过时间+场景序号对应。
CREATE TABLE IF NOT EXISTS fault_parameter_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_timestamp TEXT NOT NULL,
    scenario_sequence INTEGER NOT NULL UNIQUE,
    mode TEXT NOT NULL,
    source_file TEXT,
    source_line_no INTEGER,
    source_sequence INTEGER,
    parameters_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fault_parameter_timestamp ON fault_parameter_records(source_timestamp);

CREATE TABLE IF NOT EXISTS fault_analysis_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_timestamp TEXT NOT NULL,
    scenario_sequence INTEGER NOT NULL UNIQUE,
    fault_type TEXT NOT NULL,
    fault_subsystems_json TEXT NOT NULL,
    fault_parameters_json TEXT NOT NULL,
    overall_score REAL NOT NULL,
    overall_status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fault_analysis_timestamp ON fault_analysis_records(source_timestamp);

CREATE TABLE IF NOT EXISTS custom_algorithms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    file_path TEXT NOT NULL,
    config_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS algorithm_configs (
    algorithm_key TEXT PRIMARY KEY,
    params_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 本地演示版用户目录：只负责界面角色/启用状态持久化，不保存密码，
-- 也不应被误认为生产认证系统。
CREATE TABLE IF NOT EXISTS local_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT '启用',
    last_login TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 扩展模块是登记和启用状态管理，不动态执行用户填写的文件或远程代码。
CREATE TABLE IF NOT EXISTS extension_modules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    api_path TEXT NOT NULL,
    description TEXT NOT NULL,
    version TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    builtin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""
# 注: category_scores 列名为历史遗留(原按11大类计分);
# 自 2026-08-07 起改为33子系统扁平方案后,存的是各子系统({subsystem, score})的 JSON 数组,
# 列名保留未改以避免 DB 迁移。


@contextmanager
def get_conn():
    with _connection(get_db_path()) as conn:
        yield conn


@contextmanager
def _connection(path):
    """打开指定 SQLite 文件，并统一处理提交、回滚和连接关闭。"""
    # 场景线程按秒写入、历史导出可能持续读取；WAL 让读事务不阻塞短写事务，
    # timeout/busy_timeout 则给 SQLite 一个有限的等待窗口，避免偶发丢快照。
    conn = sqlite3.connect(str(path), timeout=10)  # 转字符串以兼容某些 sqlite3 版本
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout = 10000")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
        except sqlite3.DatabaseError:
            # 只读或旧版 SQLite 不支持切换日志模式时，保留默认模式；连接
            # 仍然拥有 timeout 和 busy_timeout，不因优化项阻断查询。
            pass
        yield conn
        conn.commit()
    except Exception as e:
        logger.error(f"数据库错误: {e}", exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()


def _configured_database_path(kind):
    """读取开发文档 8-23 中的可选健康库/故障库路径。

    空路径保持历史兼容：所有记录继续写入 backend/data/app.db。
    路径配置保存在主库 app_settings 中，因此切换数据库不会丢失配置。
    """
    raw = get_setting("data_paths")
    try:
        configured = json.loads(raw) if raw else {}
    except (TypeError, json.JSONDecodeError):
        configured = {}
    value = str(configured.get(kind) or "").strip()
    return get_db_path() if not value else __import__("pathlib").Path(value).expanduser()


def _ensure_database(path):
    path = __import__("pathlib").Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connection(path) as conn:
        conn.executescript(SCHEMA)
    return path


def init_configured_databases():
    """为已配置的健康库和故障库创建同样的表结构。"""
    health_path = _ensure_database(_configured_database_path("health_database_path"))
    fault_path = _ensure_database(_configured_database_path("fault_database_path"))

    # 用户首次切换到独立数据库时，保留已有主库历史，避免页面突然变成空白。
    # INSERT OR IGNORE 使重复初始化安全，也不会覆盖用户在专用库中的记录。
    main_path = get_db_path()
    if health_path != main_path:
        with get_conn() as source, _connection(health_path) as target:
            rows = source.execute("SELECT * FROM scenario_snapshots").fetchall()
            target.executemany(
                """INSERT OR IGNORE INTO scenario_snapshots
                (sequence, timestamp, mode, overall_score, overall_status, source_type,
                 source_file, source_line_no, source_sequence, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [tuple(row) for row in rows],
            )
    if fault_path != main_path:
        with get_conn() as source, _connection(fault_path) as target:
            rows = source.execute("SELECT * FROM fault_errors").fetchall()
            target.executemany(
                "INSERT OR IGNORE INTO fault_errors (id, timestamp, error_type, fault_report) VALUES (?, ?, ?, ?)",
                [tuple(row) for row in rows],
            )


def get_health_conn():
    return _connection(_configured_database_path("health_database_path"))


def get_fault_conn():
    return _connection(_configured_database_path("fault_database_path"))


def write_scenario_snapshot(payload):
    """把前端可见的完整快照写入主库，并同步到独立健康库。"""
    record = payload["scenario_record"]
    values = (
        record["sequence"], record["timestamp"], record["mode"],
        record["overall_score"], record["overall_status"], record["source_type"],
        record.get("source_file"), record.get("source_line_no"),
        record.get("source_sequence"), _json(payload),
    )
    statement = """
        INSERT OR REPLACE INTO scenario_snapshots
        (sequence, timestamp, mode, overall_score, overall_status, source_type,
         source_file, source_line_no, source_sequence, payload_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    with get_conn() as conn:
        conn.execute(statement, values)
    if _configured_database_path("health_database_path") != get_db_path():
        with get_health_conn() as conn:
            conn.execute(statement, values)


def init_db():
    try:
        with get_conn() as conn:
            conn.executescript(SCHEMA)
            _seed_local_management(conn)
        init_configured_databases()
        logger.info(f"数据库初始化成功: {get_db_path()}")
    except sqlite3.Error as e:
        logger.error(f"数据库初始化失败: {e}", exc_info=True)
        raise RuntimeError(f"Failed to initialize database: {e}")


def _seed_local_management(conn):
    """首次初始化时登记页面需要展示的本地目录项。"""
    now = datetime.now().isoformat(timespec="seconds")
    if not conn.execute("SELECT 1 FROM local_users LIMIT 1").fetchone():
        conn.executemany(
            "INSERT INTO local_users (username, role, status, last_login, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("admin", "系统管理员", "启用", None, now, now),
                ("operator", "运维工程师", "启用", None, now, now),
                ("observer", "观察员", "启用", None, now, now),
            ],
        )
    defaults = [
        ("健康预测模型", "/api/health/predict", "基于当前实时快照运行三层网络、线性趋势和指数平滑预测。", "v1.0.0"),
        ("关系图导入服务", "/api/graph/import", "解析 VSDX、Excel、XLS 或 CSV 关系图并生成运行时拓扑。", "v1.0.0"),
        ("健康数据库", "/api/database/health", "保存并查询场景引擎输出的健康度快照。", "v1.0.0"),
    ]
    for name, api_path, description, version in defaults:
        conn.execute(
            "INSERT OR IGNORE INTO extension_modules (name, api_path, description, version, enabled, builtin, created_at, updated_at) VALUES (?, ?, ?, ?, 1, 1, ?, ?)",
            (name, api_path, description, version, now, now),
        )


def get_setting(key, default=None):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def write_health_record(record):
    """写入一条与场景快照严格同序号的健康度记录。"""
    with get_health_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO health_database_records
            (source_timestamp, scenario_sequence, overall_score, overall_status,
             subsystem_scores_json, source_type, source_file, source_line_no,
             source_sequence, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record['timestamp'], record['sequence'], record['overall_score'],
                record['overall_status'], _json(record.get('subsystems', {})),
                record.get('source_type', 'unknown'), record.get('source_file'),
                record.get('source_line_no'), record.get('source_sequence'),
                datetime.now().isoformat(timespec='seconds'),
            ),
        )


def write_fault_records(record, parameters, fault_type, fault_subsystems, fault_parameters):
    """同一事务写入故障原始参数与故障分析，保证二者可按序号对应。"""
    with get_fault_conn() as conn:
        common = (
            record['timestamp'], record['sequence'], record.get('mode', 'unknown'),
            record.get('source_file'), record.get('source_line_no'), record.get('source_sequence'),
        )
        conn.execute(
            """INSERT OR REPLACE INTO fault_parameter_records
            (source_timestamp, scenario_sequence, mode, source_file, source_line_no,
             source_sequence, parameters_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (*common, _json(parameters), datetime.now().isoformat(timespec='seconds')),
        )
        conn.execute(
            """INSERT OR REPLACE INTO fault_analysis_records
            (source_timestamp, scenario_sequence, fault_type, fault_subsystems_json,
             fault_parameters_json, overall_score, overall_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record['timestamp'], record['sequence'], fault_type,
                _json(fault_subsystems), _json(fault_parameters),
                record['overall_score'], record['overall_status'],
                datetime.now().isoformat(timespec='seconds'),
            ),
        )


def _query_records(table, start, end, limit, offset, json_columns=()):
    clauses, args = [], []
    if start:
        clauses.append("source_timestamp >= ?"); args.append(start)
    if end:
        clauses.append("source_timestamp <= ?"); args.append(end)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with get_conn() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM {table}{where}", args).fetchone()[0]
        rows = [dict(row) for row in conn.execute(
            f"SELECT * FROM {table}{where} ORDER BY source_timestamp DESC, scenario_sequence DESC LIMIT ? OFFSET ?",
            [*args, limit, offset],
        ).fetchall()]
    for row in rows:
        for column in json_columns:
            try:
                row[column] = json.loads(row[column])
            except (TypeError, json.JSONDecodeError):
                row[column] = [] if column.endswith("json") else {}
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


def _query_records_from(connection_factory, table, start, end, limit, offset, json_columns=()):
    clauses, args = [], []
    if start:
        clauses.append("source_timestamp >= ?"); args.append(start)
    if end:
        clauses.append("source_timestamp <= ?"); args.append(end)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with connection_factory() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM {table}{where}", args).fetchone()[0]
        rows = [dict(row) for row in conn.execute(
            f"SELECT * FROM {table}{where} ORDER BY source_timestamp DESC, scenario_sequence DESC LIMIT ? OFFSET ?",
            [*args, limit, offset],
        ).fetchall()]
    for row in rows:
        for column in json_columns:
            try:
                row[column] = json.loads(row[column])
            except (TypeError, json.JSONDecodeError):
                row[column] = [] if column.endswith("json") else {}
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


def query_health_records(start=None, end=None, limit=50, offset=0):
    result = _query_records_from(get_health_conn, "health_database_records", start, end, limit, offset, ("subsystem_scores_json",))
    for row in result["items"]:
        row["subsystem_scores"] = row.pop("subsystem_scores_json", {})
    return result


def query_fault_parameters(start=None, end=None, limit=50, offset=0):
    result = _query_records_from(get_fault_conn, "fault_parameter_records", start, end, limit, offset, ("parameters_json",))
    for row in result["items"]:
        row["parameters"] = row.pop("parameters_json", {})
    return result


def query_fault_analysis(start=None, end=None, limit=50, offset=0):
    result = _query_records_from(get_fault_conn, "fault_analysis_records", start, end, limit, offset, ("fault_subsystems_json", "fault_parameters_json"))
    for row in result["items"]:
        row["fault_subsystems"] = row.pop("fault_subsystems_json", [])
        row["fault_parameters"] = row.pop("fault_parameters_json", [])
    return result


def get_algorithm_config(key):
    with get_conn() as conn:
        row = conn.execute("SELECT params_json FROM algorithm_configs WHERE algorithm_key = ?", (key,)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["params_json"])
    except (TypeError, json.JSONDecodeError):
        return None


def save_algorithm_config(key, params):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO algorithm_configs (algorithm_key, params_json, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(algorithm_key) DO UPDATE SET params_json=excluded.params_json, updated_at=excluded.updated_at",
            (key, _json(params), datetime.now().isoformat(timespec="seconds")),
        )


def list_custom_algorithms():
    with get_conn() as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM custom_algorithms ORDER BY id DESC").fetchall()]


def add_custom_algorithm(name, category, file_path, config_path):
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO custom_algorithms (name, category, file_path, config_path, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (name, category, file_path, config_path, now, now),
        )
        row = conn.execute("SELECT * FROM custom_algorithms WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def delete_custom_algorithm(algorithm_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM custom_algorithms WHERE id = ?", (algorithm_id,))


def list_local_users():
    with get_conn() as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM local_users ORDER BY id").fetchall()]


def add_local_user(username, role):
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO local_users (username, role, status, last_login, created_at, updated_at) VALUES (?, ?, '启用', NULL, ?, ?)",
            (username, role, now, now),
        )
        row = conn.execute("SELECT * FROM local_users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def update_local_user(user_id, role=None, status=None):
    fields, values = [], []
    if role is not None:
        fields.append("role = ?"); values.append(role)
    if status is not None:
        fields.append("status = ?"); values.append(status)
    if not fields:
        return None
    fields.append("updated_at = ?"); values.append(datetime.now().isoformat(timespec="seconds"))
    values.append(user_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE local_users SET {', '.join(fields)} WHERE id = ?", values)
        row = conn.execute("SELECT * FROM local_users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def list_extension_modules():
    with get_conn() as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM extension_modules ORDER BY builtin DESC, id DESC").fetchall()]


def add_extension_module(name, api_path):
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO extension_modules (name, api_path, description, version, enabled, builtin, created_at, updated_at) VALUES (?, ?, ?, 'v0.1.0', 0, 0, ?, ?)",
            (name, api_path, "用户登记的扩展模块；仅登记接口地址，不执行外部代码。", now, now),
        )
        row = conn.execute("SELECT * FROM extension_modules WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def update_extension_module(module_id, enabled):
    with get_conn() as conn:
        conn.execute(
            "UPDATE extension_modules SET enabled = ?, updated_at = ? WHERE id = ?",
            (1 if enabled else 0, datetime.now().isoformat(timespec="seconds"), module_id),
        )
        row = conn.execute("SELECT * FROM extension_modules WHERE id = ?", (module_id,)).fetchone()
    return dict(row) if row else None
