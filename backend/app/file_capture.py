"""逐行跟读外部数据文件，并复用 ScenarioEngine 的统一快照链路。

支持两种输入：历史兼容的 JSONL 场景记录，以及私有工程原始的
``YYYY/M/D HH:MM:SS.mmm: HEX BYTE ...`` 演示快照 文本。后者不先转换成 JSON，
而是直接由 authority_raw_capture 解码；非 演示快照 行和不完整帧会被分类跳过。
"""
from __future__ import annotations

import fnmatch
import json
import threading
from pathlib import Path

from .authority_raw_capture import RawCaptureSkip, decode_authority_raw_line, decoder_status
from .config import logger
from .db import get_setting
from .scenario import ENGINE


def _pattern_matches(name: str, pattern: str) -> bool:
    patterns = [item.strip() for item in str(pattern or "").replace(";", ",").split(",") if item.strip()]
    return any(fnmatch.fnmatch(name, item) for item in patterns) if patterns else False


class FileCapture:
    def __init__(self):
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self._offsets = {}
        self._status = {
            "running": False, "input_dir": None, "pattern": "*.txt,*.asc", "file": None,
            "line_no": 0, "rows_read": 0, "total_lines_seen": 0, "valid_f104_rows": 0,
            "rows_ingested": 0, "skipped_non_f104": 0, "skipped_invalid": 0,
            "skipped_insynthetic_demo": 0, "last_source_timestamp": None,
            "last_error": None, "decoder": None,
        }

    def _config(self):
        try:
            return json.loads(get_setting("data_paths") or "{}")
        except (TypeError, json.JSONDecodeError):
            return {}

    def _decode_line(self, line, filename=None, line_no=None):
        """解析一行 JSONL 或私有工程原始文本；保留旧接口供路由 test-read 使用。"""
        if line.lstrip().startswith("{"):
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError("行数据必须是 JSON 对象")
            nested = item.get("scenario_record")
            record = item if isinstance(item.get("values"), dict) else (nested if isinstance(nested, dict) else item)
            if not isinstance(record, dict) or not record.get("timestamp"):
                raise ValueError("JSON 行缺少 timestamp 或 values")
            return record
        if filename is None or line_no is None:
            raise ValueError("解析私有工程原始行需要 filename 和 line_no")
        return decode_authority_raw_line(line, str(filename), int(line_no), "send")

    def _files(self, root, pattern):
        root = Path(root).expanduser()
        if not root.is_dir():
            return []
        return sorted((p for p in root.rglob("*") if p.is_file() and _pattern_matches(p.name, pattern)), key=lambda p: str(p))

    def _record_skip(self, skip: RawCaptureSkip, path: Path, line_no: int):
        with self._lock:
            self._status.update({"file": str(path), "line_no": line_no, "last_error": None})
            if skip.code == "non_f104":
                self._status["skipped_non_f104"] += 1
            elif skip.code == "insynthetic_demo":
                self._status["skipped_insynthetic_demo"] += 1
            else:
                self._status["skipped_invalid"] += 1

    def _read_once(self, root, pattern):
        for path in self._files(root, pattern):
            key = str(path)
            state = self._offsets.get(key, {"offset": 0, "line_no": 0})
            if isinstance(state, int):
                state = {"offset": state, "line_no": 0}
            offset, line_no = int(state.get("offset", 0)), int(state.get("line_no", 0))
            try:
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    if path.stat().st_size < offset:
                        offset, line_no = 0, 0
                    handle.seek(offset)
                    while True:
                        line = handle.readline()
                        if not line:
                            break
                        line_no += 1
                        self._offsets[key] = {"offset": handle.tell(), "line_no": line_no}
                        with self._lock:
                            self._status["total_lines_seen"] += 1
                            self._status.update({"file": str(path), "line_no": line_no})
                        if not line.strip():
                            continue
                        try:
                            record = self._decode_line(line, str(path), line_no)
                        except RawCaptureSkip as exc:
                            self._record_skip(exc, path, line_no)
                            continue
                        except (ValueError, json.JSONDecodeError) as exc:
                            with self._lock:
                                self._status.update({"last_error": str(exc), "file": str(path), "line_no": line_no})
                                self._status["skipped_invalid"] += 1
                            continue
                        is_raw = record.get("source_type") == "authority_raw_file"
                        with self._lock:
                            self._status.update({
                                "rows_read": self._status["rows_read"] + 1,
                                "valid_f104_rows": self._status["valid_f104_rows"] + int(is_raw),
                                "last_source_timestamp": record.get("decoded_timestamp") or record.get("raw_timestamp"),
                                "last_error": None,
                            })
                        if isinstance(record.get("values"), dict):
                            ENGINE.ingest_external_record(record, str(path), line_no)
                            with self._lock:
                                self._status["rows_ingested"] += 1
                        logger.debug("[capture] read %s:%s source=%s", path, line_no, record.get("source_type"))
            except OSError as exc:
                with self._lock:
                    self._status["last_error"] = str(exc)

    def _run(self, root, pattern, interval):
        while not self._stop.is_set():
            try:
                self._read_once(root, pattern)
            except Exception as exc:  # pragma: no cover - defensive thread boundary
                with self._lock:
                    self._status["last_error"] = str(exc)
                logger.exception("[capture] read failed")
            self._stop.wait(max(0.1, interval))

    def start(self, input_dir=None, pattern=None, interval=None):
        config = self._config()
        input_dir = str(input_dir or config.get("capture_input_dir") or "").strip()
        pattern = str(pattern or config.get("file_pattern") or "*.txt,*.asc")
        if not input_dir:
            raise ValueError("请先配置数据抓取位置")
        path = Path(input_dir).expanduser()
        if not path.is_dir():
            raise ValueError(f"数据抓取目录不存在：{path}")
        with self._lock:
            if self._thread and self._thread.is_alive():
                return self.status()
            self._stop.clear()
            self._offsets = {}
            self._status.update({"running": True, "input_dir": str(path), "pattern": pattern,
                                 "file": None, "line_no": 0, "rows_read": 0,
                                 "total_lines_seen": 0, "valid_f104_rows": 0, "rows_ingested": 0,
                                 "skipped_non_f104": 0, "skipped_invalid": 0,
                                 "skipped_insynthetic_demo": 0, "last_source_timestamp": None, "last_error": None,
                                 "decoder": decoder_status()})
            ENGINE.set_external_capture_active(True, "file_capture")
            capture_interval = float(interval if interval is not None else config.get("poll_interval_seconds") or 1.0)
            self._thread = threading.Thread(target=self._run, args=(path, pattern, max(0.1, capture_interval)), daemon=True, name="file-capture")
            self._thread.start()
            return self.status()

    def stop(self):
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=3)
        with self._lock:
            self._thread = None
            self._status["running"] = False
            ENGINE.set_external_capture_active(False)
            return self.status()

    def status(self):
        with self._lock:
            result = dict(self._status)
            result["running"] = bool(self._thread and self._thread.is_alive())
            result["external_capture"] = ENGINE.get_status().get("external_capture")
            return result

    def test_read(self, input_dir, pattern="*.txt,*.asc"):
        path = Path(input_dir).expanduser()
        files = self._files(path, pattern)
        checked, first = [], None
        for file_path in files[:10]:
            try:
                with file_path.open("r", encoding="utf-8", errors="replace") as handle:
                    for line_no, line in enumerate(handle, 1):
                        if not line.strip():
                            continue
                        try:
                            first = self._decode_line(line, str(file_path), line_no)
                            checked.append({"file": str(file_path), "line_no": line_no, "timestamp": first.get("timestamp"),
                                            "source_type": first.get("source_type"), "unit_count": first.get("unit_count"),
                                            "value_count": len(first.get("values") or {})})
                        except RawCaptureSkip as exc:
                            checked.append({"file": str(file_path), "line_no": line_no, "skipped": exc.code, "detail": str(exc)})
                        except (OSError, ValueError, json.JSONDecodeError) as exc:
                            checked.append({"file": str(file_path), "line_no": line_no, "error": str(exc)})
                        break
            except OSError as exc:
                checked.append({"file": str(file_path), "error": str(exc)})
        return {"directory": str(path), "pattern": pattern, "files": len(files), "first": first,
                "checked": checked, "decoder": decoder_status()}


FILE_CAPTURE = FileCapture()
