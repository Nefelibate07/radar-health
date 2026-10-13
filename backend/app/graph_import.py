"""关系图导入与规范化。

支持两类不需要第三方运行时的文件：

* ``.xlsx``：读取工作簿中的表格，自动识别“上级/下级/权重”和节点表头；
* ``.vsdx``：读取 Visio 页面中的 Shape/Text/Connect，提取节点和连接线。

``.xls`` 通过可选的 xlrd 读取。这样源码开发环境没有 xlrd 时仍可运行 xlsx/vsdx，
桌面版安装 requirements-desktop.txt 后则可以同时处理旧式 Excel 文件。
解析结果不直接写入源码配置，而是作为运行时关系图覆盖层交给场景引擎。
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from collections import OrderedDict, defaultdict
from pathlib import PurePosixPath
from xml.etree import ElementTree as ET

from .subsystems import SUBSYSTEMS


class GraphImportError(ValueError):
    """用户文件不能被识别为有效关系图时抛出的错误。"""


def _text(value):
    if value is None:
        return ""
    return str(value).strip()


def _key(value):
    return re.sub(r"[\s_\-—–:：/\\()（）\[\]【】.]+", "", _text(value).lower())


HEADER_ALIASES = {
    "source": {"source", "from", "fromnode", "parent", "upstream", "上级", "父节点", "起点", "来源", "上游", "父系统", "上级节点"},
    "target": {"target", "to", "tonode", "child", "downstream", "下级", "子节点", "终点", "去向", "下游", "子系统"},
    "node": {"node", "name", "nodename", "节点", "名称", "节点名称", "子系统名称", "设备", "部件"},
    "id": {"id", "nodeid", "节点id", "编号", "编码", "子系统id", "系统id"},
    "weight": {"weight", "edgeweight", "权重", "边权重", "权值", "系数", "比例"},
    "node_weight": {"nodeweight", "节点权重", "重要度", "优先级", "节点系数"},
    "param_name": {"mainparam", "primaryparam", "主要参数", "参数", "参数名称", "测点", "测点名称", "主参数"},
    "param_value": {"paramvalue", "参数值", "当前值", "数值", "值"},
    "unit": {"unit", "单位"},
}


def _header_type(value):
    normalized = _key(value)
    for kind, aliases in HEADER_ALIASES.items():
        if normalized in {_key(item) for item in aliases}:
            return kind
    return None


def _number(value, default=1.0):
    try:
        result = float(str(value).replace(",", ""))
        return result if result > 0 else default
    except (TypeError, ValueError):
        return default


def _safe_id(value):
    raw = _text(value)
    ascii_id = re.sub(r"[^a-zA-Z0-9_.-]+", "-", raw).strip("-._").lower()
    if ascii_id and len(ascii_id) <= 80:
        return ascii_id
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"imported-{digest}"


def _known_aliases():
    aliases = {}
    for item in SUBSYSTEMS:
        for value in (item.get("id"), item.get("code"), item.get("name")):
            if value:
                aliases[_key(value)] = item
    return aliases


def _canonical_graph(rows, source_type):
    """把不同文件格式的行统一成 nodes/edges 结构。"""
    known = _known_aliases()
    nodes = OrderedDict()
    aliases = {}
    edge_weights = OrderedDict()

    def register(value, explicit_id=None, display_name=None, fields=None):
        raw = _text(value or display_name or explicit_id)
        if not raw:
            return None
        known_item = known.get(_key(raw))
        if known_item:
            node_id = known_item["id"]
            name = known_item["name"]
            mapped_id = known_item["id"]
        else:
            explicit = _text(explicit_id)
            node_id = _safe_id(explicit or raw)
            if node_id in known:
                node_id = _safe_id(raw)
            name = _text(display_name) or raw
            mapped_id = None

        alias_values = [raw, explicit_id, display_name, node_id]
        for alias in alias_values:
            if _text(alias):
                aliases[_key(alias)] = node_id

        item = nodes.get(node_id)
        if item is None:
            item = {
                "id": node_id,
                "name": name,
                "weight": 1.0,
                "mapped_subsystem_id": mapped_id,
                "primary_parameter": None,
                "imported": mapped_id is None,
            }
            nodes[node_id] = item
        if fields:
            item["weight"] = _number(fields.get("node_weight"), item["weight"])
            parameter_name = _text(fields.get("param_name"))
            if parameter_name:
                item["primary_parameter"] = {
                    "name": parameter_name,
                    "value": _text(fields.get("param_value")) or "--",
                    "display_value": _text(fields.get("param_value")) or "--",
                    "unit": _text(fields.get("unit")),
                }
        return node_id

    # 先建立节点别名，再处理关系边。这样“关系表”放在第一个工作表、
    # “节点表”放在第二个工作表时，边上的中文名称仍能正确映射到显式节点 ID。
    for row in rows:
        node_value = row.get("node") or row.get("name") or row.get("id")
        if _text(node_value):
            register(node_value, row.get("id"), row.get("name") or node_value, row)

    for row in rows:
        source = row.get("source")
        target = row.get("target")
        if _text(source) and _text(target):
            parent_id = aliases.get(_key(source)) or register(source)
            child_id = aliases.get(_key(target)) or register(target)
            if parent_id and child_id and parent_id != child_id:
                edge_weights[(parent_id, child_id)] = edge_weights.get((parent_id, child_id), 0.0) + _number(row.get("weight"))

    if not nodes:
        raise GraphImportError("没有识别到任何节点。请提供节点名称，或提供上级/下级两列。")

    parents = {parent for parent, _child in edge_weights}
    children = {child for _parent, child in edge_weights}
    roots = [node_id for node_id in nodes if node_id not in children]
    if not roots:
        roots = list(nodes)[:1]

    root_id = "imported-root"
    nodes[root_id] = {
        "id": root_id,
        "name": "导入关系图",
        "weight": 1.0,
        "mapped_subsystem_id": None,
        "primary_parameter": None,
        "imported": True,
        "is_root": True,
    }
    for root in roots:
        edge_weights[(root_id, root)] = edge_weights.get((root_id, root), 1.0)

    return {
        "source_type": source_type,
        "nodes": list(nodes.values()),
        "edges": [
            {"parent": parent, "child": child, "weight": round(weight, 4)}
            for (parent, child), weight in edge_weights.items()
        ],
        "roots": roots,
        "root_id": root_id,
    }


def _find_header(rows):
    best = None
    for index, row in enumerate(rows[:15]):
        kinds = [_header_type(item) for item in row]
        score = sum(kind is not None for kind in kinds)
        has_edge = "source" in kinds and "target" in kinds
        has_node = "node" in kinds or "name" in kinds or "id" in kinds
        if (has_edge or has_node) and (best is None or score > best[0]):
            best = (score, index, kinds)
    if best is None:
        raise GraphImportError("无法识别表头。Excel 至少需要‘上级/下级’，或‘节点/名称’列。")
    _, index, kinds = best
    headers = []
    used = defaultdict(int)
    for column_index, kind in enumerate(kinds):
        if not kind:
            headers.append(f"column_{column_index}")
            continue
        used[kind] += 1
        headers.append(kind if used[kind] == 1 else f"{kind}_{used[kind]}")
    return index, headers


def _rows_from_matrix(matrix):
    matrix = [[_text(value) for value in row] for row in matrix if any(_text(value) for value in row)]
    if not matrix:
        return []
    header_index, headers = _find_header(matrix)
    result = []
    for values in matrix[header_index + 1:]:
        row = {header: values[index] if index < len(values) else "" for index, header in enumerate(headers)}
        if any(_text(value) for value in row.values()):
            result.append(row)
    return result


def _xlsx_matrix(data):
    ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = set(archive.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("main:si", ns):
                shared.append("".join(node.text or "" for node in item.findall(".//main:t", ns)))

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {
            item.attrib.get("Id"): item.attrib.get("Target", "")
            for item in relationships.findall(f"{{{rel_ns}}}Relationship")
        }
        sheets = []
        for sheet in workbook.findall("main:sheets/main:sheet", ns):
            target = targets.get(sheet.attrib.get(f"{{{ns['rel']}}}id"), "")
            target = target.lstrip("/")
            if not target.startswith("xl/"):
                target = f"xl/{target}"
            if target in names:
                sheets.append((sheet.attrib.get("name", "Sheet"), target))

        matrices = []
        for sheet_name, target in sheets:
            root = ET.fromstring(archive.read(target))
            matrix = []
            for row in root.findall(".//main:sheetData/main:row", ns):
                values = []
                for cell in row.findall("main:c", ns):
                    ref = cell.attrib.get("r", "A1")
                    match = re.match(r"([A-Z]+)", ref)
                    column = 0
                    if match:
                        for char in match.group(1):
                            column = column * 26 + ord(char) - 64
                        column -= 1
                    while len(values) <= column:
                        values.append("")
                    value = cell.find("main:v", ns)
                    inline = cell.find("main:is", ns)
                    if inline is not None:
                        text_value = "".join(node.text or "" for node in inline.findall(".//main:t", ns))
                    else:
                        text_value = value.text if value is not None else ""
                        if cell.attrib.get("t") == "s" and text_value.isdigit():
                            text_value = shared[int(text_value)] if int(text_value) < len(shared) else text_value
                    values[column] = text_value
                matrix.append(values)
            if matrix:
                matrices.append((sheet_name, matrix))
        return matrices


def _parse_xlsx(data):
    all_rows = []
    for _sheet_name, matrix in _xlsx_matrix(data):
        try:
            all_rows.extend(_rows_from_matrix(matrix))
        except GraphImportError:
            continue
    if not all_rows:
        raise GraphImportError("Excel 中没有找到可识别的关系表或节点表。")
    return _canonical_graph(all_rows, "xlsx")


def _parse_csv(data):
    text = None
    for encoding in ("utf-8-sig", "gb18030", "utf-8"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise GraphImportError("CSV 文件编码无法识别。")
    matrix = list(csv.reader(io.StringIO(text)))
    return _canonical_graph(_rows_from_matrix(matrix), "csv")


def _parse_xls(data):
    try:
        import xlrd
    except ImportError as exc:
        raise GraphImportError("当前环境缺少 xlrd，无法读取旧式 .xls。请安装 requirements-desktop.txt 后重试。") from exc
    workbook = xlrd.open_workbook(file_contents=data)
    rows = []
    for sheet in workbook.sheets():
        matrix = [sheet.row_values(index) for index in range(sheet.nrows)]
        rows.extend(_rows_from_matrix(matrix))
    return _canonical_graph(rows, "xls")


def _parse_vsdx(data):
    ns = "http://schemas.microsoft.com/office/visio/2012/main"
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        page_names = [name for name in archive.namelist() if re.match(r"visio/pages/page[^/]*\.xml$", name)]
        if not page_names:
            raise GraphImportError("VSDX 中没有找到 Visio 页面。")
        nodes = []
        direct_connections = []
        connector_connections = defaultdict(list)
        for page_name in page_names:
            root = ET.fromstring(archive.read(page_name))
            shape_map = {}
            one_d = set()
            for shape in root.findall(f".//{{{ns}}}Shape"):
                shape_id = shape.attrib.get("ID")
                if not shape_id:
                    continue
                text = "".join("".join(node.itertext()) for node in shape.findall(f".//{{{ns}}}Text"))
                name = _text(text) or _text(shape.attrib.get("NameU")) or _text(shape.attrib.get("Name"))
                if shape.attrib.get("OneD") == "1":
                    one_d.add(shape_id)
                if name and shape_id not in one_d:
                    shape_map[shape_id] = name

            for connection in root.findall(f".//{{{ns}}}Connect"):
                from_id = connection.attrib.get("FromSheet")
                to_id = connection.attrib.get("ToSheet")
                if not from_id or not to_id:
                    continue
                from_cell = connection.attrib.get("FromCell", "")
                if from_id in one_d:
                    connector_connections[from_id].append((to_id, from_cell))
                else:
                    direct_connections.append((from_id, to_id))

            for shape_id, name in shape_map.items():
                nodes.append({"node": name, "id": shape_id})

        rows = list(nodes)
        for parent, child in direct_connections:
            if parent in {item["id"] for item in nodes} and child in {item["id"] for item in nodes}:
                rows.append({"source": parent, "target": child, "weight": 1})
        for endpoints in connector_connections.values():
            unique = []
            for endpoint, cell in endpoints:
                if endpoint in {item["id"] for item in nodes} and endpoint not in [item[0] for item in unique]:
                    unique.append((endpoint, cell))
            if len(unique) >= 2:
                begin = next((item[0] for item in unique if "begin" in item[1].lower()), unique[0][0])
                end = next((item[0] for item in unique if "end" in item[1].lower()), unique[1][0])
                # Visio 的 BeginX 是连线起点（子节点），EndX 是终点（上级节点）。
                rows.append({"source": end, "target": begin, "weight": 1})

    graph = _canonical_graph(rows, "vsdx")
    if not graph["edges"] and len(graph["nodes"]) < 2:
        raise GraphImportError("VSDX 中没有识别到至少两个带文字的节点和连接线。")
    return graph


def parse_graph_file(filename, data):
    name = _text(filename).lower()
    if not data:
        raise GraphImportError("上传文件为空。")
    if name.endswith(".vsdx"):
        return _parse_vsdx(data)
    if name.endswith(".xlsx"):
        return _parse_xlsx(data)
    if name.endswith(".xls"):
        return _parse_xls(data)
    if name.endswith(".csv"):
        return _parse_csv(data)
    raise GraphImportError("暂不支持该文件类型，请上传 .vsdx、.xlsx、.xls 或 .csv 文件。")
