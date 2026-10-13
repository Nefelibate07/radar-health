"""系统自检接口。自检只读取当前场景快照和数据库状态，不修改监测数据。"""

from flask import Blueprint, jsonify

from .. import db
from ..scenario import get_dashboard_payload, get_scenario_status
from ..subsystems import SUBSYSTEMS

bp = Blueprint("system", __name__)


@bp.get("/api/system/self-check")
def self_check():
    payload = get_dashboard_payload()
    health = payload.get("data", {}).get("health", {})
    subsystems = health.get("subsystems") or []
    parameters = health.get("parameters") or []
    scenario = get_scenario_status()
    expected_parameter_count = sum(len(item.get("params", [])) for item in SUBSYSTEMS)
    graph = health.get("graph") or payload.get("data", {}).get("overview", {}).get("graph") or {}
    imported_graph = graph.get("source_type") not in {None, "builtin"}
    graph_nodes = [item for item in graph.get("nodes", []) if not item.get("is_root")]
    expected_subsystem_count = len(graph_nodes) if imported_graph else len(SUBSYSTEMS)
    known_parameter_count = sum(
        1 for item in parameters
        if item.get("subsystem_id") in {subsystem["id"] for subsystem in SUBSYSTEMS}
    )

    with db.get_conn() as conn:
        snapshot_count = conn.execute("SELECT COUNT(*) FROM scenario_snapshots").fetchone()[0]

    checks = [
        {
            "system": "场景引擎",
            "name": "场景引擎运行状态",
            "status": "ok" if scenario.get("running") else "fail",
            "detail": "正在输出快照" if scenario.get("running") else "未运行",
        },
        {
            "system": "协议回放",
            "name": "合成演示快照帧",
            "status": "ok" if payload.get("scenario_record", {}).get("source_type") else "fail",
            "detail": payload.get("scenario_record", {}).get("source_type") or "无当前来源",
        },
        {
            "system": "参数体系",
            "name": "监测参数完整性",
            "status": "ok" if known_parameter_count == expected_parameter_count else "warn",
            "detail": f"当前 {known_parameter_count} 项，目标 {expected_parameter_count} 项",
        },
        {
            "system": "子系统拓扑",
            "name": "子系统健康度计算",
            "status": "ok" if len(subsystems) == expected_subsystem_count else "warn",
            "detail": (
                f"当前 {len(subsystems)} 个，导入拓扑目标 {expected_subsystem_count} 个"
                if imported_graph else
                f"当前 {len(subsystems)} 个，目标 {expected_subsystem_count} 个"
            ),
        },
        {
            "system": "SQLite 快照库",
            "name": "历史快照写入",
            "status": "ok" if snapshot_count > 0 else "warn",
            "detail": f"已保存 {snapshot_count} 条快照",
        },
    ]
    failed = sum(item["status"] == "fail" for item in checks)
    warned = sum(item["status"] == "warn" for item in checks)
    overall_score = health.get("current_score")
    return jsonify({
        "ok": True,
        "data": {
            "items": checks,
            "passed_count": sum(item["status"] == "ok" for item in checks),
            "failed_count": failed + warned,
            "overall_score": overall_score,
            "overall_status": "报废" if failed else ("故障" if warned else "正常"),
            "source": payload.get("scenario_record", {}),
        },
    })
