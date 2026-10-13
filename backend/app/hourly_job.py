"""后台定时任务：每整点记录系统健康状态快照到数据库。

=== STAGE ② 教学内容 ===

【为什么选 threading？】

Python 有 3 种方式做周期性后台任务：

1️⃣  threading（纯标准库）—— 我们的选择 ✅
   ├─ 优：零依赖，跨平台，单机部署无额外环保负担
   ├─ 缺：没有分布式调度，不支持集群，手工同步逻辑
   └─ 适用：单机 Windows 部署，任务简单，不涉及分布式

2️⃣  APScheduler（第三方库）—— 在骨架期可选
   ├─ 优：接近 cron 的 API，支持多种触发器，更灵活
   ├─ 缺：又一个依赖，需要维护后台进程，依赖可靠性
   └─ 适用：任务复杂（多触发规则），中等规模部署

3️⃣  Celery + Redis（企业级）—— 不用
   ├─ 优：分布式，支持集群/消息队列
   ├─ 缺：复杂，需要 Redis/RabbitMQ，Windows 兼容性差
   └─ 适用：多机器、高并发、需要可靠性，但你的需求不够

【为什么是 threading？】

你的需求：
  • 单机 Windows 部署 ← 约束
  • 任务简单：每整点抓一次数据，写入数据库
  • 不涉及分布式或集群
  • 对外部依赖敏感（嵌入式环境不想装太多东西）

→ threading 是完美的"足够用、零成本"解决方案。

【核心思路】

1. 用 threading.Thread + time.sleep 实现
2. 定时器线程在后台跑，不阻塞主线程（Socket.IO、HTTP 照常工作）
3. 到整点时，调用 build_dashboard_payload() 抓数据
4. 写入 hourly_snapshots 表
5. 线程生命周期：app 创建 → 启动线程 → app 关闭时自动停止

【对比示例】

# APScheduler 的样子（更花哨但多一个依赖）：
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler()
scheduler.add_job(snapshot_hour, 'cron', hour='*')  # 每整点
scheduler.start()

# 我们的 threading 样子（朴素但够用）：
def _hourly_loop():
    while not stop_event.is_set():
        secs_to_hour = calc_secs_to_next_hour()
        if stop_event.wait(secs_to_hour):  # 睡眠，直到下一整点或被中止
            break
        snapshot_hour()

thread = threading.Thread(target=_hourly_loop, daemon=True)
thread.start()
"""

import threading
import time
import json
import sqlite3
from datetime import datetime
from contextlib import contextmanager

from .config import logger
from .scenario import get_dashboard_payload

_stop_event = threading.Event()
_job_thread = None


def _get_fault_count():
    """查询本小时的故障数。"""
    from .db import get_fault_conn
    try:
        with get_fault_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM fault_errors WHERE timestamp >= datetime('now', 'start of hour')"
            ).fetchone()
            return row["cnt"] if row else 0
    except Exception as e:
        logger.error(f"[hourly_job] get_fault_count error: {e}", exc_info=True)
        return 0


def _snapshot_hour():
    """定时任务：抓取当前健康状态快照，写入数据库。"""
    from .db import get_health_conn
    try:
        # 复用最近一次推给前端的实时快照，而不是独立再抽样一次——否则整点落库的数字会
        # 和当时页面上实际显示的值不一致（没有缓存时，例如刚启动还没推送过，才退回独立生成）。
        payload = get_dashboard_payload()

        health_data = payload["data"]["health"]
        overall_score = health_data["current_score"]
        overall_status = health_data["overall_status"]

        # 将 subsystems 列表转为 JSON 字符串存储(字段沿用旧列名 category_scores,
        # 避免一次额外的 DB 迁移;内容语义已从"大类"变为"子系统")
        category_scores = json.dumps([
            {"subsystem": s["subsystem"], "score": s["score"]}
            for s in health_data["subsystems"]
        ])

        fault_count = _get_fault_count()

        # 当前小时的整点时间（格式：YYYY-MM-DD HH:00:00）
        hour_str = datetime.now().strftime("%Y-%m-%d %H:00:00")
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 写入数据库
        with get_health_conn() as conn:
            conn.execute(
                """
                INSERT INTO hourly_snapshots (hour, overall_score, overall_status, category_scores, fault_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(hour) DO UPDATE SET
                    overall_score = excluded.overall_score,
                    overall_status = excluded.overall_status,
                    category_scores = excluded.category_scores,
                    fault_count = excluded.fault_count,
                    created_at = excluded.created_at
                """,
                (hour_str, overall_score, overall_status, category_scores, fault_count, created_at)
            )

        logger.info(f"[hourly_job] snapshot recorded: {hour_str} score={overall_score} status={overall_status} faults={fault_count}")
    except Exception as e:
        logger.error(f"[hourly_job] snapshot error: {e}", exc_info=True)


def _calc_secs_to_next_hour():
    """计算距离下一个整点还有多少秒。"""
    from datetime import timedelta

    now = datetime.now()
    # 下一整点 = 当前小时 + 1 小时，设为 00 分 00 秒
    next_hour_dt = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    # 秒数差
    delta = (next_hour_dt - now).total_seconds()
    return delta


def _hourly_loop():
    """后台循环：每到整点就执行一次快照，直到 stop_event 被置位。"""
    logger.info("[hourly_job] background loop started")

    while not _stop_event.is_set():
        secs_to_wait = _calc_secs_to_next_hour()

        # wait() 在 timeout 秒后返回 False，或 event 被置位时返回 True
        if _stop_event.wait(secs_to_wait):
            # 被置位了，退出循环
            logger.info("[hourly_job] background loop stopped by signal")
            break

        # 整点到了，执行快照
        _snapshot_hour()


def start_hourly_job():
    """启动后台定时任务线程。在 app 初始化时调用。"""
    global _job_thread

    if _job_thread is not None:
        logger.info("[hourly_job] already running, skipped")
        return

    _stop_event.clear()
    _job_thread = threading.Thread(target=_hourly_loop, daemon=True, name="hourly_snapshot")
    _job_thread.start()
    logger.info("[hourly_job] started")


def stop_hourly_job():
    """停止后台定时任务。在 app shutdown 时调用。"""
    global _job_thread

    if _job_thread is None:
        return

    _stop_event.set()
    _job_thread.join(timeout=5)  # 等待最多 5 秒
    _job_thread = None
    logger.info("[hourly_job] stopped")
