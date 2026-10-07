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
