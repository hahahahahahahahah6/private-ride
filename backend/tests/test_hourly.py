"""包车/按小时计费（hourly）测试。

覆盖：下单 hourly 成功 / 缺 rate 报 400 / finish 小时数取整逻辑 /
非接单司机调 finish-hourly 报 403 / 非 hourly 单调 finish-hourly 报 400。
"""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base, get_db
from app.main import app

# ---------- 测试库 ----------

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
_test_engine = create_engine(
    f"sqlite:///{_tmp.name}", connect_args={"check_same_thread": False}
)
Base.metadata.create_all(bind=_test_engine)
_TestingSession = sessionmaker(
    bind=_test_engine, autoflush=False, expire_on_commit=False
)


def _override_get_db():
    db = _TestingSession()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _use_test_db():
    """模块级覆盖 get_db，跑完恢复，避免污染同进程其他测试模块。"""
    prev = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    if prev is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = prev

_seq = 0


def _next_phone() -> str:
    global _seq
    _seq += 1
    return f"+1566000{_seq:04d}"


def _db():
    return _TestingSession()


def _make_user(db, role="passenger", name="测试用户"):
    u = models.User(phone=_next_phone(), name=name, role=role)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_token(db, user, token=None):
    token = token or f"tok-{uuid4().hex[:12]}"
    db.add(models.AuthToken(
        token=token,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    ))
    db.commit()
    return token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_users():
    """造一个乘客 + 一个司机，返回 (乘客 token, 司机 token)。"""
    db = _db()
    p = _make_user(db, role="passenger", name="乘客")
    d = _make_user(db, role="driver", name="司机")
    ptok, dtok = _make_token(db, p), _make_token(db, d)
    db.close()
    return ptok, dtok


def _create_hourly_ride(ptok, rate_cents=8000):
    r = client.post(
        "/rides",
        json={
            "pickup_text": "上车点",
            "dropoff_text": "下车点",
            "price_mode": "hourly",
            "hourly_rate_cents": rate_cents,
        },
        headers=_auth(ptok),
    )
    assert r.status_code == 201, r.text
    return r.json()


def _drive_to_in_progress(dtok, ride_id):
    """司机接单并一路推进到 in_progress。"""
    r = client.post(f"/rides/{ride_id}/accept", headers=_auth(dtok))
    assert r.status_code == 200, r.text
    for st in ("en_route", "arrived", "in_progress"):
        r = client.post(
            f"/rides/{ride_id}/status", json={"status": st}, headers=_auth(dtok))
        assert r.status_code == 200, r.text
    return r.json()


# ---------- POST /rides ----------

def test_hourly_下单成功():
    ptok, _ = _make_users()
    ride = _create_hourly_ride(ptok, rate_cents=8000)
    assert ride["price_mode"] == "hourly"
    assert ride["hourly_rate_cents"] == 8000
    assert ride["price_final_cents"] is None  # 结算前不算价
    assert ride["price_status"] == "pending"


def test_hourly_下单缺价格报400():
    ptok, _ = _make_users()
    # 不带 hourly_rate_cents
    r = client.post(
        "/rides",
        json={"pickup_text": "A", "dropoff_text": "B", "price_mode": "hourly"},
        headers=_auth(ptok),
    )
    assert r.status_code == 400
    # 0 也算无效
    r = client.post(
        "/rides",
        json={"pickup_text": "A", "dropoff_text": "B",
              "price_mode": "hourly", "hourly_rate_cents": 0},
        headers=_auth(ptok),
    )
    assert r.status_code == 400


# ---------- POST /rides/{id}/finish-hourly ----------

def test_hourly_finish_小时数取整():
    ptok, dtok = _make_users()
    # 2.3 小时 → 向上取整到 2.5 → 2.5 × $80 = $200
    ride = _create_hourly_ride(ptok, rate_cents=8000)
    _drive_to_in_progress(dtok, ride["id"])
    r = client.post(
        f"/rides/{ride['id']}/finish-hourly",
        json={"hours": 2.3},
        headers=_auth(dtok),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["price_final_cents"] == 20000
    assert body["price_status"] == "agreed"

    # 整半小时不取整：2.5 小时 → $200
    ride = _create_hourly_ride(ptok, rate_cents=8000)
    _drive_to_in_progress(dtok, ride["id"])
    r = client.post(
        f"/rides/{ride['id']}/finish-hourly",
        json={"hours": 2.5},
        headers=_auth(dtok),
    )
    assert r.status_code == 200, r.text
    assert r.json()["price_final_cents"] == 20000

    # 2.6 小时 → 向上取整到 3 → $240
    ride = _create_hourly_ride(ptok, rate_cents=8000)
    _drive_to_in_progress(dtok, ride["id"])
    r = client.post(
        f"/rides/{ride['id']}/finish-hourly",
        json={"hours": 2.6},
        headers=_auth(dtok),
    )
    assert r.status_code == 200, r.text
    assert r.json()["price_final_cents"] == 24000


def test_hourly_finish_非接单司机调报403():
    ptok, dtok = _make_users()
    ride = _create_hourly_ride(ptok)
    _drive_to_in_progress(dtok, ride["id"])
    # 另一个司机来结算
    db = _db()
    other = _make_user(db, role="driver", name="陌生司机")
    otok = _make_token(db, other)
    db.close()
    r = client.post(
        f"/rides/{ride['id']}/finish-hourly",
        json={"hours": 2.0},
        headers=_auth(otok),
    )
    assert r.status_code == 403


def test_hourly_finish_非hourly单调报400():
    ptok, dtok = _make_users()
    r = client.post(
        "/rides",
        json={"pickup_text": "A", "dropoff_text": "B",
              "price_mode": "offer", "price_offer_cents": 3000},
        headers=_auth(ptok),
    )
    assert r.status_code == 201
    ride = r.json()
    _drive_to_in_progress(dtok, ride["id"])
    r = client.post(
        f"/rides/{ride['id']}/finish-hourly",
        json={"hours": 2.0},
        headers=_auth(dtok),
    )
    assert r.status_code == 400


def test_hourly_finish_非进行中单报400():
    ptok, dtok = _make_users()
    ride = _create_hourly_ride(ptok)
    # 还没推进到 in_progress（只接单）
    r = client.post(f"/rides/{ride['id']}/accept", headers=_auth(dtok))
    assert r.status_code == 200
    r = client.post(
        f"/rides/{ride['id']}/finish-hourly",
        json={"hours": 2.0},
        headers=_auth(dtok),
    )
    assert r.status_code == 400


def test_hourly_直接状态完成被拦截():
    ptok, dtok = _make_users()
    ride = _create_hourly_ride(ptok)
    _drive_to_in_progress(dtok, ride["id"])
    # 包车单必须走 finish-hourly，不能直接切 completed
    r = client.post(
        f"/rides/{ride['id']}/status",
        json={"status": "completed"},
        headers=_auth(dtok),
    )
    assert r.status_code == 400
    # 走 finish-hourly 才能完成
    r = client.post(
        f"/rides/{ride['id']}/finish-hourly",
        json={"hours": 0.5},
        headers=_auth(dtok),
    )
    assert r.status_code == 200
    assert r.json()["price_final_cents"] == 4000
