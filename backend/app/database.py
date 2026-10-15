"""Database setup: SQLite locally, Postgres (Neon) in production via DATABASE_URL."""
from __future__ import annotations

import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
if DATABASE_URL.startswith("sqlite"):
    # Fail-fast writes ("database is locked") under thread-pool concurrency
    # without this; WAL also lets readers proceed during a write.
    connect_args["timeout"] = 30
engine = create_engine(DATABASE_URL, connect_args=connect_args)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401  (register tables)

    Base.metadata.create_all(bind=engine)
    # 已有表不会自动补索引（create_all 只建缺的表），这里幂等补上
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_rides_driver_id ON rides (driver_id)"))
        # 老库补列：drivers 表加实时位置字段
        from sqlalchemy import inspect

        cols = {c["name"] for c in inspect(conn).get_columns("drivers")}
        for col in ("last_lat", "last_lng"):
            if col not in cols:
                conn.execute(text(f"ALTER TABLE drivers ADD COLUMN {col} FLOAT"))
        if "last_loc_at" not in cols:
            conn.execute(text("ALTER TABLE drivers ADD COLUMN last_loc_at TIMESTAMP"))
        # 老库补列：rides 表加评分字段
        ride_cols = {c["name"] for c in inspect(conn).get_columns("rides")}
        if "rating_stars" not in ride_cols:
            conn.execute(text("ALTER TABLE rides ADD COLUMN rating_stars INTEGER"))
        if "rating_comment" not in ride_cols:
            conn.execute(text("ALTER TABLE rides ADD COLUMN rating_comment TEXT"))
        if "rated_at" not in ride_cols:
            conn.execute(text("ALTER TABLE rides ADD COLUMN rated_at TIMESTAMP"))
        # 老库补列：rides 表加小费和经停点字段
        if "tip_cents" not in ride_cols:
            conn.execute(text("ALTER TABLE rides ADD COLUMN tip_cents INTEGER"))
        if "tip_at" not in ride_cols:
            conn.execute(text("ALTER TABLE rides ADD COLUMN tip_at TIMESTAMP"))
        if "stops_json" not in ride_cols:
            conn.execute(text("ALTER TABLE rides ADD COLUMN stops_json TEXT"))
        # 老库补列：代叫车/评价标签/提醒标记
        if "booked_for_name" not in ride_cols:
            conn.execute(text("ALTER TABLE rides ADD COLUMN booked_for_name VARCHAR(64) DEFAULT ''"))
        if "booked_for_phone" not in ride_cols:
            conn.execute(text("ALTER TABLE rides ADD COLUMN booked_for_phone VARCHAR(32) DEFAULT ''"))
        if "rating_tags_json" not in ride_cols:
            conn.execute(text("ALTER TABLE rides ADD COLUMN rating_tags_json TEXT"))
        if "reminder_sent" not in ride_cols:
            conn.execute(text("ALTER TABLE rides ADD COLUMN reminder_sent INTEGER DEFAULT 0"))
        # 老库补列：users 表加语言字段（通知文案用）
        user_cols = {c["name"] for c in inspect(conn).get_columns("users")}
        if "lang" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN lang VARCHAR(8) DEFAULT 'zh'"))
        # 老库结构变更：rides.passenger_id 改为可空
        # （账号注销时订单要匿名化：关联置空但订单保留给司机对账）
        col_nullable = {
            c["name"]: c.get("nullable", True)
            for c in inspect(conn).get_columns("rides")
        }
        if not col_nullable.get("passenger_id", True):
            if DATABASE_URL.startswith("sqlite"):
                # SQLite 不支持直接改列可空：重建表，数据原样复制
                old_indexes = [
                    r[0]
                    for r in conn.execute(text(
                        "SELECT name FROM sqlite_master "
                        "WHERE type = 'index' AND tbl_name IN ('rides', 'rides_old')"
                    ))
                ]
                conn.execute(text("ALTER TABLE rides RENAME TO rides_old"))
                for ix in old_indexes:
                    conn.execute(text(f'DROP INDEX IF EXISTS "{ix}"'))
                models.Ride.__table__.create(bind=conn)
                old_cols = [c["name"] for c in inspect(conn).get_columns("rides_old")]
                csv = ", ".join(old_cols)
                conn.execute(text(f"INSERT INTO rides ({csv}) SELECT {csv} FROM rides_old"))
                conn.execute(text("DROP TABLE rides_old"))
            else:
                # Postgres：直接放开 NOT NULL
                conn.execute(text(
                    "ALTER TABLE rides ALTER COLUMN passenger_id DROP NOT NULL"
                ))
