"""公开版自定义演示拓扑，不包含客户设备关系图。"""
ROOT_ID = "hub"
EDGES = [('hub', 'antenna-monitor-unit'), ('hub', 'environment-control-device'), ('antenna-monitor-unit', 'drive-adu'), ('drive-adu', 'azimuth-motor-1'), ('drive-adu', 'azimuth-motor-2'), ('drive-adu', 'elevation-motor-1'), ('drive-adu', 'elevation-motor-2'), ('drive-adu', 'tilt-motor-1'), ('drive-adu', 'tilt-motor-2')]

CHILDREN = {}
for _parent, _child in EDGES:
    CHILDREN.setdefault(_parent, []).append(_child)

# hub 的直接下级 = 9 个一级子系统，去重保持首次出现的顺序
TOP_LEVEL_IDS = list(dict.fromkeys(child for parent, child in EDGES if parent == ROOT_ID))


# 健康度传播规则与前端展示共用的阈值。分数越高表示越健康：60 及以上为
# 正常，30 到小于 60 为故障，小于 30 为报废。上级节点的健康度先由自身
# 分数和直接下级平均分得到，再应用故障状态约束。
HEALTH_BROKEN_CAP = 29.9
HEALTH_FAULTY_CAP = 59.9


def health_score_status(score):
    """将健康分数转换为项目统一的三态状态。"""
    score = float(score)
    if score >= 60:
        return "正常"
    if score >= 30:
        return "故障"
    return "报废"


def cascade_health_score(own_score, child_scores):
    """按内置拓扑规则计算一个节点的最终健康度。

    ``own_score`` 为节点自身健康度；``child_scores`` 为直接下级的最终
    健康度。无直接下级时，节点保留自身分数；虚拟根节点可将自身分数传
    为 ``None``，此时只聚合一级子系统。两个或以上故障/报废节点会把
    上级限制在故障区间；存在报废节点则限制在报废区间。
    """
    child_scores = list(child_scores)
    child_average = sum(child_scores) / len(child_scores) if child_scores else own_score
    base = (own_score + child_average) / 2 if own_score is not None else child_average
    statuses = [health_score_status(item) for item in child_scores]
    if own_score is not None:
        statuses.append(health_score_status(own_score))
    if "报废" in statuses:
        base = min(base, HEALTH_BROKEN_CAP)
    elif sum(item in ("故障", "报废") for item in statuses) >= 2:
        base = min(base, HEALTH_FAULTY_CAP)
    return round(max(0.0, min(100.0, base)), 1)


def propagate_health_scores(raw_scores):
    """对一组内置子系统自身分数执行完整的自底向上拓扑聚合。"""
    final = {}
    for subsystem_id in topological_order(raw_scores):
        children = CHILDREN.get(subsystem_id, [])
        final[subsystem_id] = cascade_health_score(
            raw_scores[subsystem_id],
            [final[child] for child in children],
        )
    overall = cascade_health_score(None, [final[item] for item in TOP_LEVEL_IDS])
    return final, overall


def topological_order(all_ids):
    """把 all_ids 排成"下级永远排在上级前面"的顺序，供自底向上传播时按顺序处理。

    从虚拟根节点开始深度优先遍历、后序追加（子节点先于父节点入列），天然满足
    "先算末端子系统，再算它们的上级，再算上级的上级"的要求；某节点被两个上级
    共同指向时，只在第一次访问到它时入列一次。拓扑表里没有任何连线的孤立子系统
    （没有关联的演示节点）在遍历完 hub 之后单独补上（顺序无所谓，因为它们
    既没有下级也没有上级，不参与任何聚合）。
    """
    order = []
    visited = set()

    def visit(node):
        if node in visited:
            return
        visited.add(node)
        for child in CHILDREN.get(node, []):
            visit(child)
        if node != ROOT_ID:
            order.append(node)

    visit(ROOT_ID)
    for node_id in all_ids:
        visit(node_id)
    return order
