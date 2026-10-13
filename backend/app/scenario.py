"""连续场景模拟引擎。

场景是第三部分的唯一数据源：每秒推进一次，生成 演示子系统、演示
参数和对应健康度；Socket.IO、主界面和小时快照都读取同一份最新快照，
避免各处各自随机生成导致页面数字互相矛盾。

默认输出到 backend/data/scenarios/，可用 SCENARIO_OUTPUT_DIR 重定向。
文件采用 JSON Lines 格式，扩展名为 .asc，每个小时自动切换一个文件。
"""
import json
import os
import threading
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

from .config import logger
from .db import get_conn, write_fault_records, write_health_record
from .graph_import import parse_graph_file
from .paths import get_backend_data_dir
from .authority_replay import (
    AUTHORITY_REPLAY,
    AUTHORITY_SCORE_UNMAPPED_STATUS,
    AUTHORITY_UNIT_HEALTH_SCOPE,
)
from .subsystem_topology import (
    CHILDREN,
    EDGES,
    ROOT_ID,
    TOP_LEVEL_IDS,
    cascade_health_score,
    propagate_health_scores,
)
from .subsystems import SUBSYSTEMS


SCENARIO_MODES = {
    "normal": {"label": "正常运行", "affected": set(), "target_score": 92.0, "overall_factor": 1.0},
    "azimuth_fault": {
        "label": "方位驱动故障",
        "affected": {"drive-adu", "azimuth-motor-1", "azimuth-motor-2", "azimuth-encoder-unit", "azimuth-limit-sensor", "azimuth-axis-lock"},
        "target_score": 42.0,
        "overall_factor": 0.65,
    },
    "elevation_fault": {
        "label": "俯仰驱动故障",
        "affected": {"drive-adu", "elevation-motor-1", "elevation-motor-2", "elevation-encoder-unit", "elevation-limit-sensor", "elevation-axis-lock"},
        "target_score": 40.0,
        "overall_factor": 0.65,
    },
    "tracking_fault": {
        "label": "演示控制器故障",
        "affected": {"antenna-monitor-unit"},
        "target_score": 38.0,
        "overall_factor": 0.65,
    },
    "environment_fault": {
        "label": "环控故障",
        "affected": {"environment-control-device"},
        "target_score": 36.0,
        "overall_factor": 0.65,
    },
    "global_degradation": {
        "label": "全局退化",
        "affected": set(),
        "target_score": 72.0,
        "overall_factor": 0.72,
    },
}

ALL_SUBSYSTEM_IDS = [item["id"] for item in SUBSYSTEMS]
SUBSYSTEM_BY_ID = {item["id"]: item for item in SUBSYSTEMS}
PARAMETERS = [(subsystem, parameter) for subsystem in SUBSYSTEMS for parameter in subsystem.get("params", [])]
def _number(value, default=1.0):
    try:
        number = float(value)
        return number if number > 0 else default
    except (TypeError, ValueError):
        return default


def score_status(score):
    if float(score) >= 60:
        return "正常"
    if float(score) >= 30:
        return "故障"
    return "报废"


def status_code(status):
    return {"正常": 1, "故障": 2, "报废": 3}.get(status, 0)


def _cascade(own_score, child_scores):
    """兼容旧调用方，统一委托到公共拓扑健康度规则。"""
    return cascade_health_score(own_score, child_scores)


def _propagate(raw_scores):
    """兼容旧调用方，统一委托到公共拓扑健康度规则。"""
    scores, overall = propagate_health_scores(raw_scores)
    return {subsystem_id: {"score": score} for subsystem_id, score in scores.items()}, overall


def _fault_enum_code(parameter):
    values = parameter.get("enum") or {}
    for code, label in values.items():
        label = str(label)
        if label != "未限位" and any(word in label for word in ("告警", "失锁", "不到位", "限位", "失步")):
            return int(code)
    return int(next(iter(values), 1))


def _format_value(value, parameter):
    if value is None:
        return "--"
    if parameter.get("dtype") == "enum":
        try:
            key = str(int(value))
        except (TypeError, ValueError):
            return "--"
        return (parameter.get("enum") or {}).get(key, key)
    precision = parameter.get("precision")
    if precision and precision < 0.01:
        return f"{float(value):.3f}"
    if precision and precision < 1:
        return f"{float(value):.1f}"
    return f"{float(value):.2f}"


class ScenarioEngine:
    def __init__(self):
        self.interval = max(0.2, float(os.environ.get("SCENARIO_INTERVAL", "1")))
        configured_dir = os.environ.get("SCENARIO_OUTPUT_DIR")
        self.output_dir = Path(configured_dir).expanduser() if configured_dir else get_backend_data_dir() / "scenarios"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread = None
        self._mode = "normal"
        self._changed_at = datetime.now()
        self._sequence = 0
        self._latest = None
        self._latest_timestamp = None
        self._history = deque(maxlen=48)
        self._file_path = None
        self._file_handle = None
        self._pending_alarm = None
        self._imported_graph = None
        self._imported_filename = None
        self._imported_at = None
        self._authority_frame = None
        # 文件抓取启动后，外部原始帧是唯一推进源；场景线程只保留最新快照，
        # 不能在下一秒用内置 fixture 覆盖刚刚摄取的真实记录。
        self._external_capture_active = False
        self._external_capture_source = None

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True, name="scenario-generator")
            self._thread.start()
            logger.info("[scenario] generator started: interval=%ss output=%s", self.interval, self.output_dir)

    def stop(self):
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=3)
        with self._lock:
            self._close_file()
            self._thread = None

    def is_running(self):
        return bool(self._thread and self._thread.is_alive())

    def set_mode(self, mode):
        if mode not in SCENARIO_MODES:
            raise ValueError(f"未知场景模式: {mode}")
        with self._lock:
            if mode != self._mode:
                self._mode = mode
                self._changed_at = datetime.now()
                self._latest = None
                if mode != "normal":
                    self._pending_alarm = self._make_alarm()
                    self._record_fault(self._pending_alarm)
                logger.info("[scenario] mode changed to %s (%s)", mode, SCENARIO_MODES[mode]["label"])
            return self._status_locked()

    def get_status(self):
        with self._lock:
            return self._status_locked()

    def consume_pending_alarm(self):
        with self._lock:
            alarm = self._pending_alarm
            self._pending_alarm = None
            return alarm

    def get_payload(self):
        with self._lock:
            if self._latest is None:
                self._latest = self._generate_snapshot(datetime.now())
            return self._latest

    def set_external_capture_active(self, active: bool, source: str | None = None):
        """切换外部文件优先模式，不清空最近一条可展示快照。"""
        with self._lock:
            self._external_capture_active = bool(active)
            self._external_capture_source = source if active else None
            logger.info("[scenario] external capture %s source=%s", "enabled" if active else "disabled", source)
            return self._status_locked()

    def ingest_external_record(self, record, source_file=None, source_line_no=None):
        """把文件抓取的一条 演示快照 派生记录送入同一个页面/数据库链路。"""
        if not isinstance(record, dict) or not isinstance(record.get('values'), dict):
            raise ValueError('外部记录缺少 values 字段，无法作为 演示快照 快照处理')
        frame = json.loads(json.dumps(record, ensure_ascii=False))
        # 保留底层来源（authority_raw_file / 旧 JSONL 的 file_capture 等），
        # 另由抓取器状态说明 transport，便于从页面回溯真实文件。
        frame.setdefault('source_type', 'file_capture')
        if source_file:
            frame['source_file'] = str(source_file)
        if source_line_no:
            frame['source_line_no'] = source_line_no
        mode = (frame.get('scenario_record') or {}).get('mode') or frame.get('mode') or 'normal'
        if mode not in SCENARIO_MODES:
            mode = 'normal'
        with self._lock:
            self._mode = mode
            self._authority_frame = frame
            self._latest = self._generate_snapshot(datetime.now(), authority_frame=frame)
            self._write_record(self._latest)
            return self._latest

    def import_graph(self, filename, data):
        graph = parse_graph_file(filename, data)
        with self._lock:
            self._imported_graph = graph
            self._imported_filename = filename
            self._imported_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._latest = None
            logger.info(
                "[scenario] graph imported: file=%s source=%s nodes=%s edges=%s",
                filename,
                graph["source_type"],
                len(graph["nodes"]),
                len(graph["edges"]),
            )
            return self._graph_status_locked()

    def reset_graph(self):
        with self._lock:
            self._imported_graph = None
            self._imported_filename = None
            self._imported_at = None
            self._latest = None
            logger.info("[scenario] graph reset to built-in topology")
            return self._graph_status_locked()

    def get_graph_status(self):
        with self._lock:
            return self._graph_status_locked()

    def _builtin_graph_locked(self):
        names = {item["id"]: item["name"] for item in SUBSYSTEMS}
        nodes = [
            {
                "id": item["id"],
                "name": item["name"],
                "weight": 1.0,
                "mapped_subsystem_id": item["id"],
                "primary_parameter": None,
                "imported": False,
            }
            for item in SUBSYSTEMS
        ]
        nodes.insert(0, {
            "id": ROOT_ID,
            "name": "监控计算机",
            "weight": 1.0,
            "mapped_subsystem_id": None,
            "primary_parameter": None,
            "imported": False,
            "is_root": True,
        })
        return {
            "source_type": "builtin",
            "filename": None,
            "imported_at": None,
            "nodes": nodes,
            "edges": [{"parent": parent, "child": child, "weight": 1.0} for parent, child in EDGES],
            "root_id": ROOT_ID,
            "roots": TOP_LEVEL_IDS,
        }

    def _graph_status_locked(self):
        if self._imported_graph is None:
            return self._builtin_graph_locked()
        return {
            **self._imported_graph,
            "filename": self._imported_filename,
            "imported_at": self._imported_at,
        }

    def _imported_scores(self, raw_scores):
        """按导入边权重自底向上聚合节点健康度。

        节点自身健康度作为一份“自有权重”，子节点使用导入边的 weight；
        因此同一张图中既能表达层级，又能表达不同子系统对上级的影响程度。
        发生环路时跳过回到当前递归栈的边，保证用户图不会让推送线程崩溃。
        """
        graph = self._imported_graph
        if not graph:
            return None, None
        nodes = {item["id"]: item for item in graph["nodes"]}
        children = defaultdict(list)
        for edge in graph["edges"]:
            if edge["parent"] in nodes and edge["child"] in nodes:
                children[edge["parent"]].append((edge["child"], _number(edge.get("weight"), 1.0)))
        scores = {}
        visiting = set()

        def own_score(node):
            mapped = node.get("mapped_subsystem_id")
            if mapped in raw_scores:
                return raw_scores[mapped]
            # 导入图里的自定义逻辑节点可能没有对应的实时测点。它们没有
            # “未知即故障”的依据，按中性健康度参与加权，避免合法导入图
            # 产生 None 并让 Socket.IO 推送线程崩溃；一旦节点映射到参数
            # 配置，仍然使用真实回放数据计算。
            return 100.0

        def visit(node_id):
            if node_id in scores:
                return scores[node_id]
            if node_id in visiting:
                return own_score(nodes[node_id])
            visiting.add(node_id)
            node = nodes[node_id]
            child_scores = []
            for child_id, weight in children.get(node_id, []):
                if child_id == node_id:
                    continue
                child_scores.append((visit(child_id), weight))
            child_scores = [(value, weight) for value, weight in child_scores if value is not None]
            own = own_score(node)
            if node.get("is_root"):
                score = sum(value * weight for value, weight in child_scores) / sum(weight for _value, weight in child_scores) if child_scores else own
            elif child_scores:
                child_average = sum(value * weight for value, weight in child_scores) / sum(weight for _value, weight in child_scores)
                # 导入关系图可以包含尚未映射到 config/params.json 的逻辑父节点。
                # 这类节点没有可直接观测的自身健康度，只能使用子节点的加权结果；
                # 不能把 None 当作数值参与加权，否则一次合法的 Excel/VSDX 导入
                # 会在生成 dashboard 快照时触发 TypeError。
                child_weight = sum(weight for _value, weight in child_scores)
                if own is None:
                    score = child_average
                else:
                    own_weight = _number(node.get("weight"), 1.0)
                    total_weight = own_weight + child_weight
                    score = (own * own_weight + child_average * child_weight) / total_weight
            else:
                score = own
            if score is None:
                visiting.discard(node_id)
                scores[node_id] = None
                return None
            score = round(max(0.0, min(100.0, score)), 1)
            visiting.discard(node_id)
            scores[node_id] = score
            return score

        for node_id in nodes:
            visit(node_id)
        return graph, scores

    def _run(self):
        next_tick = time.monotonic()
        while not self._stop_event.is_set():
            now = datetime.now()
            with self._lock:
                if not self._external_capture_active:
                    self._latest = self._generate_snapshot(now)
                    self._write_record(self._latest)
            next_tick += self.interval
            if self._stop_event.wait(max(0.0, next_tick - time.monotonic())):
                break

    def _generate_snapshot(self, now, authority_frame=None):
        if authority_frame is None and self._authority_frame is None and not AUTHORITY_REPLAY.enabled:
            raise RuntimeError(
                "合成演示快照缓存不可用：请检查 config/authority_replay_fixture.jsonl.gz"
            )
        mode_config = SCENARIO_MODES[self._mode]
        self._sequence += 1
        self._authority_frame = authority_frame if authority_frame is not None else AUTHORITY_REPLAY.next()
        raw_scores = {}
        for subsystem in SUBSYSTEMS:
            subsystem_id = subsystem["id"]
            authority_score = self._authority_score(subsystem)
            if subsystem_id in mode_config["affected"]:
                target = mode_config["target_score"]
            elif self._mode == "global_degradation":
                target = authority_score * mode_config["overall_factor"]
            else:
                target = authority_score
            raw_scores[subsystem_id] = round(max(0.0, min(100.0, target)), 1)

        imported_graph, imported_scores = self._imported_scores(raw_scores)
        if imported_graph:
            propagated = {
                subsystem_id: {"score": score}
                for subsystem_id, score in imported_scores.items()
                if subsystem_id != imported_graph["root_id"]
            }
            # Imported graphs use their own weighted bottom-up aggregation.
            # The raw scores already include the selected scenario, including
            # global degradation, so applying overall_factor again here would
            # count the same scenario effect twice.
            overall_score = imported_scores.get(imported_graph["root_id"], 0.0)
        else:
            propagated, topology_overall = _propagate(raw_scores)
            # The built-in topology is the authoritative system-health
            # calculation: each parent combines its own score with the mean
            # of its direct children, then the root combines the nine
            # top-level subsystems and applies the fault-state constraints.
            # Do not replace this with an arithmetic mean of all 33 nodes;
            # that would dilute or bypass the topology fault propagation.
            overall_score = topology_overall
        overall_status = score_status(overall_score)

        parameters = []
        abnormal_parameters = []
        for subsystem, parameter in PARAMETERS:
            subsystem_score = propagated.get(subsystem["id"], {"score": raw_scores[subsystem["id"]]})["score"]
            affected = subsystem["id"] in mode_config["affected"]
            value, source_type = self._parameter_value_with_source(parameter, affected)
            item = {
                "id": f"{subsystem['id']}-{parameter.get('appendix_no') or parameter['id']}",
                "param_id": parameter["id"],
                "subsystem_id": subsystem["id"],
                "subsystem": subsystem["name"],
                "name": parameter["name"],
                "dtype": parameter.get("dtype"),
                "unit": parameter.get("unit", ""),
                "value": value,
                "display_value": _format_value(value, parameter),
                "enum_label": _format_value(value, parameter) if parameter.get("dtype") == "enum" else None,
                "threshold": self._threshold(parameter),
                "status": score_status(subsystem_score),
                "abnormal": subsystem_score < 60,
                "source_type": source_type,
            }
            if self._authority_frame is not None:
                item["source_file"] = self._authority_frame.get("source_file")
                item["source_line_no"] = self._authority_frame.get("source_line_no")
                item["source_timestamp"] = self._authority_frame.get("decoded_timestamp")
            parameters.append(item)
            if item["abnormal"]:
                abnormal_parameters.append(item)

        graph = imported_graph or self._builtin_graph_locked()
        graph_nodes = {item["id"]: item for item in graph["nodes"]}
        for node_id, node in graph_nodes.items():
            if node.get("is_root"):
                continue
            if node.get("mapped_subsystem_id"):
                continue
            primary = node.get("primary_parameter")
            score = propagated.get(node_id, {}).get("score")
            if primary:
                parameter = {
                    "id": f"{node_id}-primary",
                    "param_id": f"{node_id}-primary",
                    "subsystem_id": node_id,
                    "subsystem": node["name"],
                    "name": primary["name"],
                    "dtype": "float",
                    "unit": primary.get("unit", ""),
                    "value": None,
                    "display_value": "--",
                    "enum_label": None,
                    "threshold": None,
                    "status": score_status(score) if score is not None else "--",
                    "abnormal": score is not None and score < 60,
                    "source_type": "authority_unmapped",
                }
                parameters.append(parameter)
                if parameter["abnormal"]:
                    abnormal_parameters.append(parameter)

        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        self._latest_timestamp = timestamp
        subsystem_rows = []
        signals = {}
        for node in graph["nodes"]:
            subsystem_id = node["id"]
            if node.get("is_root"):
                continue
            score = propagated.get(subsystem_id, {}).get("score")
            if score is None:
                continue
            status = score_status(score)
            subsystem_rows.append({"id": subsystem_id, "name": node["name"], "status": status_code(status), "health_score": score})
            first_numeric = next((item for item in parameters if item["subsystem_id"] == subsystem_id and item["dtype"] != "enum"), None)
            signals[subsystem_id] = first_numeric["value"] if first_numeric else score

        self._history.append({"time": timestamp, "score": overall_score})
        mode_summary = {"mode": self._mode, "label": mode_config["label"], "affected_subsystems": sorted(mode_config["affected"])}
        radar_dimensions = ["跟踪精度", "驱动稳定性", "传动状态", "通信质量", "环控水平"]
        radar_groups = [
            {"antenna-monitor-unit", "encoder-pdu", "azimuth-encoder-unit", "elevation-encoder-unit", "tilt-encoder-unit"},
            {"drive-adu", "azimuth-motor-1", "azimuth-motor-2", "elevation-motor-1", "elevation-motor-2", "tilt-motor-1", "tilt-motor-2"},
            {"azimuth-limit-sensor", "elevation-limit-sensor", "tilt-limit-sensor", "azimuth-axis-lock", "elevation-axis-lock", "tilt-axis-lock"},
            {"ttc-receiver", "feed-receiver", "down-converter", "ttc-tracking-down-converter", "feed-tracking-down-converter"},
            {"environment-control-device"},
        ]
        radar_scores = [round(sum(propagated[item]["score"] for item in group if item in propagated) / max(1, len(group)), 1) for group in radar_groups]
        graph_view = {
            **graph,
            "nodes": [
                {
                    **node,
                    "score": (overall_score if node.get("is_root") else propagated.get(node["id"], {}).get("score")),
                    "status": (score_status(overall_score) if node.get("is_root") else (score_status(propagated[node["id"]]["score"]) if propagated.get(node["id"], {}).get("score") is not None else "--")),
                    "primary_parameter": next((item for item in parameters if item["subsystem_id"] == node["id"] and item["dtype"] != "enum"), node.get("primary_parameter")),
                }
                for node in graph["nodes"]
            ],
        }
        scenario_status = self._status_locked(timestamp)
        return {
            "data": {
                "overview": {
                    "system_mode": "跟踪" if self._mode == "normal" else "故障诊断",
                    "subsystems": subsystem_rows,
                    "signals": signals,
                    "scenario": scenario_status,
                    "graph": graph_view,
                    "history_trend": {"times": [item["time"][-8:] for item in self._history], "values": [item["score"] for item in self._history]},
                },
                "health": {
                    "current_score": overall_score,
                    "overall_status": overall_status,
                    "subsystems": [{"id": item["id"], "subsystem": item["name"], "score": item["health_score"], "status": score_status(item["health_score"])} for item in subsystem_rows],
                    "parameters": parameters,
                    "abnormal_parameters": abnormal_parameters[:24],
                    "scenario": mode_summary,
                    "graph": graph_view,
                    "radar_data": {"dimensions": radar_dimensions, "scores": radar_scores},
                    "authority_replay": AUTHORITY_REPLAY.status(),
                    "protocol_status": [
                        item for item in (self._authority_frame or {}).get("protocol_status", [])
                        if not item.get("project_parameter_id")
                    ],
                },
            },
            "scenario_record": {
                "timestamp": timestamp,
                "sequence": self._sequence,
                "mode": self._mode,
                "mode_label": mode_config["label"],
                "overall_score": overall_score,
                "overall_status": overall_status,
                "subsystems": {item["id"]: item["health_score"] for item in subsystem_rows},
                "parameters": {item["id"]: item["value"] for item in parameters},
                "source_type": self._authority_frame.get("source_type", "synthetic_demo"),
                "source_file": self._authority_frame.get("source_file"),
                "source_line_no": self._authority_frame.get("source_line_no"),
                "source_raw_timestamp": self._authority_frame.get("raw_timestamp"),
                "source_decoded_timestamp": self._authority_frame.get("decoded_timestamp"),
                "source_sequence": self._authority_frame.get("sequence"),
                "source_unit_count": self._authority_frame.get("unit_count"),
                "source_decode_issues": self._authority_frame.get("decode_issues", []),
                "source_quality": "synthetic_demo_with_missing_values" if self._authority_frame.get("decode_issues") else "synthetic_demo",
                "source_transform": "scenario_fault_overlay" if self._mode != "normal" else None,
            },
        }

    def _authority_score(self, subsystem):
        """从真实帧的健康关联枚举计算保守的子系统分。

        协议没有为全部连续量给出健康上下限，因此不把经验范围硬套到真实值；
        只对协议明确语义为正常/告警、锁定/失锁、到位/不到位等字段扣分。
        这使真实回放不会因未知值域被误报，同时保留可解释的健康结果。
        """
        if not self._authority_frame:
            return 92.0
        values = self._authority_frame.get("values", {})
        protocol_status = self._authority_frame.get("protocol_status", [])
        abnormal = 0
        observed = 0
        for item in subsystem.get("params", []):
            if item.get("id") not in values or item.get("dtype") != "enum":
                continue
            labels = [str(label) for label in (item.get("enum") or {}).values()]
            if not any(keyword in label for label in labels for keyword in ("告警", "失锁", "不到位", "限位", "失步")):
                continue
            observed += 1
            raw_value = values[item["id"]]
            if isinstance(raw_value, str):
                label = raw_value
            else:
                label = str((item.get("enum") or {}).get(str(int(raw_value)), raw_value))
            if any(keyword in label for keyword in ("告警", "失锁", "不到位", "限位", "失步")) and label != "未限位":
                abnormal += 1
        # 协议明确但尚未纳入项目参数字典的健康字段默认只保留证据，
        # 私有工程确认完整语义后可通过配置开启评分，不冒充项目参数。
        for protocol_item in protocol_status:
            if not AUTHORITY_SCORE_UNMAPPED_STATUS:
                continue
            if protocol_item.get("project_parameter_id"):
                continue
            unit_id = int(protocol_item.get("unit_id", 0))
            if subsystem["id"] not in AUTHORITY_UNIT_HEALTH_SCOPE.get(unit_id, []):
                continue
            observed += 1
            raw_value = protocol_item.get("raw_value")
            name = str(protocol_item.get("name", ""))
            if isinstance(raw_value, (int, float)) and int(raw_value) == 2 and "限位" not in name:
                abnormal += 1
        if not observed:
            return 100.0
        return round(max(0.0, 100.0 - abnormal * 25.0), 1)

    def _parameter_value_with_source(self, parameter, affected):
        if self._authority_frame is None:
            raise RuntimeError("合成演示快照帧不可用")
        values = self._authority_frame.get("values", {})
        project_id = parameter.get("id")
        if project_id in values and not affected:
            return values[project_id], "synthetic_demo"
        if project_id in values and affected:
            return self._authority_fault_value(parameter, values[project_id]), "synthetic_demo_fault_injected"
        return None, "authority_unmapped"

    def _authority_fault_value(self, parameter, value):
        if parameter.get("dtype") == "enum":
            return _fault_enum_code(parameter)
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return value
        unit = parameter.get("unit", "")
        if unit == "℃":
            numeric += 28.0
        elif unit == "%":
            numeric = 94.0
        elif unit == "V":
            numeric *= 0.45
        elif unit == "A":
            numeric *= 2.2
        elif unit in {"°/s", "mV"}:
            numeric *= 3.0
        elif unit == "°":
            numeric += 8.0 if numeric >= 0 else -8.0
        else:
            numeric *= 1.8
        precision = parameter.get("precision") or 0.01
        return round(round(numeric / precision) * precision, 4)

    def _threshold(self, parameter):
        rng = parameter.get("range")
        if rng and len(rng) == 2:
            low, high = float(rng[0]), float(rng[1])
            return round(max(abs(low), abs(high)) if low < 0 < high else high, 4)
        return None

    def _status_locked(self, timestamp=None):
        return {
            "mode": self._mode,
            "label": SCENARIO_MODES[self._mode]["label"],
            "running": self.is_running(),
            "interval_seconds": self.interval,
            "output_dir": str(self.output_dir),
            "current_file": str(self._file_path) if self._file_path else None,
            "sequence": self._sequence,
            "last_timestamp": timestamp or self._latest_timestamp,
            "changed_at": self._changed_at.strftime("%Y-%m-%d %H:%M:%S"),
            "modes": [{"key": key, "label": value["label"]} for key, value in SCENARIO_MODES.items()],
            "authority_replay": AUTHORITY_REPLAY.status(),
            "external_capture": {
                "active": self._external_capture_active,
                "source": self._external_capture_source,
            },
        }

    def _write_record(self, payload):
        timestamp = payload["scenario_record"]["timestamp"]
        file_path = self.output_dir / f"{timestamp[:10].replace('-', '')}_{timestamp[11:13]}.asc"
        if file_path != self._file_path:
            self._close_file()
            self._file_path = file_path
            self._file_handle = file_path.open("a", encoding="utf-8")
        self._file_handle.write(json.dumps(payload["scenario_record"], ensure_ascii=False, separators=(",", ":")) + "\n")
        self._file_handle.flush()
        # 同一条已经推送到 Socket.IO 的场景快照写入 SQLite。历史查询、趋势和
        # 导出不再从 seed/mock 表取数，确保“看到的、推送的、查询到的”同源。
        record = payload["scenario_record"]
        try:
            from . import db
            db.write_scenario_snapshot(payload)
            write_health_record(record)
            if record.get("overall_status") != "正常":
                health_parameters = payload.get("data", {}).get("health", {}).get("parameters", [])
                affected = [
                    item for item in payload.get("data", {}).get("health", {}).get("subsystems", [])
                    if float(item.get("score", 100)) < 60
                ]
                fault_parameters = [
                    item for item in health_parameters if item.get("abnormal")
                ]
                write_fault_records(
                    record,
                    health_parameters,
                    f"场景模拟：{record.get('mode_label', record.get('mode', '未知'))}",
                    affected,
                    fault_parameters,
                )
        except Exception:
            logger.exception("[scenario] failed to persist scenario snapshot")

    def _close_file(self):
        if self._file_handle:
            try:
                self._file_handle.flush()
                self._file_handle.close()
            finally:
                self._file_handle = None

    def _make_alarm(self):
        config = SCENARIO_MODES[self._mode]
        names = [SUBSYSTEM_BY_ID[item]["name"] for item in sorted(config["affected"]) if item in SUBSYSTEM_BY_ID]
        part = names[0] if names else "全系统"
        severity = "严重故障" if self._mode == "global_degradation" else "一般故障"
        return {
            "故障时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "故障程度": severity,
            "严重等级": severity,
            "故障设备": "三轴测控跟踪天线",
            "故障部件": part,
            "故障类型": "场景模拟：" + config["label"],
            "异常参数": [],
            "turntable_system": config["label"],
            "event_id": f"SCENARIO-{int(time.time())}",
            "scenario_mode": self._mode,
            "source_type": "scenario_engine",
            "affected_subsystems": names,
        }

    def _record_fault(self, alarm):
        try:
            from .db import get_fault_conn
            with get_fault_conn() as conn:
                conn.execute("INSERT INTO fault_errors (timestamp, error_type, fault_report) VALUES (?, ?, ?)", (alarm["故障时间"], alarm["故障程度"], json.dumps(alarm, ensure_ascii=False)))
        except Exception:
            logger.exception("[scenario] failed to record fault event")


ENGINE = ScenarioEngine()


def start_scenario_engine():
    raw_capture_ready = False
    try:
        from .db import get_setting
        config = json.loads(get_setting("data_paths") or "{}")
        capture_dir = Path(str(config.get("capture_input_dir") or "")).expanduser()
        raw_capture_ready = config.get("capture_mode") == "file_capture" and capture_dir.is_dir()
        if raw_capture_ready:
            ENGINE.set_external_capture_active(True, "file_capture")
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        raw_capture_ready = False
    if not AUTHORITY_REPLAY.enabled:
        # 允许纯私有工程原始文件模式启动：工厂随后会启用 FileCapture，
        # 在第一条完整 演示快照 到达前不生成任何非协议遥测。
        try:
            from .db import get_setting
            config = json.loads(get_setting("data_paths") or "{}")
            capture_dir = Path(str(config.get("capture_input_dir") or "")).expanduser()
            raw_capture_ready = config.get("capture_mode") == "file_capture" and capture_dir.is_dir()
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            raw_capture_ready = False
        if not raw_capture_ready:
            raise RuntimeError(
                "合成演示快照缓存不可用：请检查 config/authority_replay_fixture.jsonl.gz，"
                "或配置有效的 file_capture 原始日志目录。"
            )
    ENGINE.start()


def stop_scenario_engine():
    ENGINE.stop()


def get_dashboard_payload():
    return ENGINE.get_payload()


def get_scenario_status():
    return ENGINE.get_status()


def get_graph_status():
    return ENGINE.get_graph_status()


def import_graph(filename, data):
    return ENGINE.import_graph(filename, data)


def reset_graph():
    return ENGINE.reset_graph()


def set_scenario_mode(mode):
    return ENGINE.set_mode(mode)


def consume_pending_alarm():
    return ENGINE.consume_pending_alarm()


def build_scenario_alarm():
    with ENGINE._lock:
        return ENGINE._make_alarm()
