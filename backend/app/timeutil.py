"""时间工具：数据库里存不带时区的 UTC，给人看的时候转成本地时区。

服务器一般跑在 UTC，直接 strftime 会把 UTC 时间发给司机/乘客，
所以推送、邮件、报错提示里的时间统一走 fmt_local。
本地时区用环境变量 APP_TZ 配，默认洛杉矶。
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def app_tz() -> ZoneInfo:
    try:
        return ZoneInfo(os.getenv("APP_TZ", "America/Los_Angeles"))
    except Exception:
        return ZoneInfo("UTC")


def as_utc(dt: datetime) -> datetime:
    """不带时区的当 UTC，带时区的转成 UTC。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_db(dt: datetime | None) -> datetime | None:
    """写库前统一成不带时区的 UTC（SQLite 和 Postgres timestamp 都一致）。"""
    if dt is None:
        return None
    return as_utc(dt).replace(tzinfo=None)


def fmt_local(dt: datetime | None, pattern: str = "%m-%d %H:%M") -> str:
    if dt is None:
        return ""
    return as_utc(dt).astimezone(app_tz()).strftime(pattern)
