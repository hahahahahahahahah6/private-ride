"""航班号 + 晚点自助调整测试：POST /rides 带 flight_no、POST /rides/{id}/delay。

用临时 SQLite 库 + TestClient 跑真实接口（不碰生产 dev.db 的数据）。

注意：本模块不用模块级 dependency_overrides（会污染同进程的
test_account），而是用 fixture 临时替换、用完恢复；另外用 autouse
fixture 把下单的后台通知（_notify_new_ride_bg）屏蔽掉，避免测试打到
生产库或真实推送网络。
"""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app import push as push_mod
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


@pytest.fixture()
def client():
    """临时替换 get_db 依赖，跑完恢复（不污染其他测试模块）。"""
    prev = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        if prev is not None:
            app.dependency_overrides[get_db] = prev
        else:
            app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def _no_bg_notify():
    """屏蔽下单后台通知：不碰生产库、不发真实推送。"""
    with patch("app.main._notify_new_ride_bg", lambda ride_id: None):
        yield


_seq = 0


def _next_phone() -> str:
    global _seq
    _seq += 1
    return f"+1666000{_seq:04d}"


def _db():
    return _TestingSession()


def _make_user(db, role="passenger", **kw):
    kw.setdefault("name", "测试用户")
    u = models.User(phone=_next_phone(), role=role, **kw)
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


def _make_ride(db, passenger, **kw):
    """直接建订单行（绕开接口），默认 requested + 有预约时间。"""
    base = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=2)
    kw.setdefault("pickup_text", "LAX T1")
    kw.setdefault("dropoff_text", "迪士尼")
    kw.setdefault("scheduled_at", base)
    kw.setdefault("status", "requested")
    kw.setdefault("flight_no", "UA857")
    ride = models.Ride(passenger_id=passenger.id, **kw)
    db.add(ride)
    db.commit()
    db.refresh(ride)
    return ride, kw["scheduled_at"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------- 下单带航班号 ----------

def test_下单航班号去空格转大写(client):
    db = _db()
    u = _make_user(db)
    tok = _make_token(db, u)
    db.close()

    r = client.post("/rides", json={
        "pickup_text": "LAX T1",
        "dropoff_text": "迪士尼",
        "price_mode": "offer",
        "price_offer_cents": 3000,
        "flight_no": "ua 857",
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
    }, headers=_auth(tok))
    assert r.status_code == 201
    assert r.json()["flight_no"] == "UA857"

    db = _db()
    ride = db.query(models.Ride).filter_by(passenger_id=u.id).one()
    assert ride.flight_no == "UA857"
    db.close()


def test_下单不带航班号默认为空(client):
    db = _db()
    u = _make_user(db)
    tok = _make_token(db, u)
    db.close()

    r = client.post("/rides", json={
        "pickup_text": "面馆",
        "dropoff_text": "机场",
        "price_mode": "offer",
        "price_offer_cents": 2500,
    }, headers=_auth(tok))
    assert r.status_code == 201
    assert r.json()["flight_no"] == ""


def test_下单航班号超长被拒绝(client):
    db = _db()
    u = _make_user(db)
    tok = _make_token(db, u)
    db.close()

    r = client.post("/rides", json={
        "pickup_text": "面馆",
        "dropoff_text": "机场",
        "price_mode": "offer",
        "price_offer_cents": 2500,
        "flight_no": "A" * 20,
    }, headers=_auth(tok))
    assert r.status_code == 422


# ---------- delay：时长校验 ----------

def test_delay只允许30_60_120(client):
    db = _db()
    u = _make_user(db)
    tok = _make_token(db, u)
    db.close()

    for minutes in (30, 60, 120):
        db = _db()
        ride, base = _make_ride(db, u)
        rid = ride.id
        db.close()

        r = client.post(f"/rides/{rid}/delay",
                        json={"minutes": minutes}, headers=_auth(tok))
        assert r.status_code == 200, r.text
        got = datetime.fromisoformat(r.json()["scheduled_at"])
        assert abs((got - (base + timedelta(minutes=minutes))).total_seconds()) < 5

        # 库里的时间也确实用的是延后后的时间
        db = _db()
        stored = db.get(models.Ride, rid).scheduled_at
        assert abs((stored - (base + timedelta(minutes=minutes))).total_seconds()) < 5
        db.close()


def test_delay非法时长400(client):
    db = _db()
    u = _make_user(db)
    tok = _make_token(db, u)
    ride, base = _make_ride(db, u)
    rid = ride.id
    db.close()

    for minutes in (0, 45, 90, 180, -30):
        r = client.post(f"/rides/{rid}/delay",
                        json={"minutes": minutes}, headers=_auth(tok))
        assert r.status_code == 400, minutes
    # 非法调用不能动预约时间
    db = _db()
    got = db.get(models.Ride, rid).scheduled_at
    assert abs((got - base).total_seconds()) < 5
    db.close()


def test_delay可累加(client):
    db = _db()
    u = _make_user(db)
    tok = _make_token(db, u)
    ride, base = _make_ride(db, u)
    rid = ride.id
    db.close()

    r = client.post(f"/rides/{rid}/delay",
                    json={"minutes": 30}, headers=_auth(tok))
    assert r.status_code == 200
    r = client.post(f"/rides/{rid}/delay",
                    json={"minutes": 60}, headers=_auth(tok))
    assert r.status_code == 200
    got = datetime.fromisoformat(r.json()["scheduled_at"])
    assert abs((got - (base + timedelta(minutes=90))).total_seconds()) < 5


# ---------- delay：权限与状态 ----------

def test_delay非本人403(client):
    db = _db()
    owner = _make_user(db)
    other = _make_user(db)
    tok_other = _make_token(db, other)
    ride, _ = _make_ride(db, owner)
    rid = ride.id
    db.close()

    r = client.post(f"/rides/{rid}/delay",
                    json={"minutes": 60}, headers=_auth(tok_other))
    assert r.status_code == 403


def test_delay已完成订单400(client):
    db = _db()
    u = _make_user(db)
    tok = _make_token(db, u)
    ride, base = _make_ride(db, u, status="completed")
    rid = ride.id
    db.close()

    r = client.post(f"/rides/{rid}/delay",
                    json={"minutes": 60}, headers=_auth(tok))
    assert r.status_code == 400
    db = _db()
    got = db.get(models.Ride, rid).scheduled_at
    assert abs((got - base).total_seconds()) < 5
    db.close()


def test_delay行程中状态400(client):
    db = _db()
    u = _make_user(db)
    tok = _make_token(db, u)
    ride, _ = _make_ride(db, u, status="in_progress")
    rid = ride.id
    db.close()

    r = client.post(f"/rides/{rid}/delay",
                    json={"minutes": 60}, headers=_auth(tok))
    assert r.status_code == 400


def test_delay无预约时间400(client):
    db = _db()
    u = _make_user(db)
    tok = _make_token(db, u)
    ride, _ = _make_ride(db, u, scheduled_at=None)
    rid = ride.id
    db.close()

    r = client.post(f"/rides/{rid}/delay",
                    json={"minutes": 60}, headers=_auth(tok))
    assert r.status_code == 400


def test_delay订单不存在404(client):
    db = _db()
    u = _make_user(db)
    tok = _make_token(db, u)
    db.close()

    r = client.post(f"/rides/{uuid4()}/delay",
                    json={"minutes": 60}, headers=_auth(tok))
    assert r.status_code == 404


def test_delay未登录401(client):
    r = client.post(f"/rides/{uuid4()}/delay", json={"minutes": 60})
    assert r.status_code == 401


# ---------- delay：司机推送 ----------

def test_delay给司机发推送中英文(client):
    db = _db()
    u = _make_user(db)
    tok = _make_token(db, u)
    # 中文司机收到中文文案
    drv_zh = _make_user(db, role="driver",
                        push_token="ExponentPushToken[drvzh]",
                        lang="zh", name="中文司机")
    db.close()

    sent = []
    with patch.object(push_mod, "send_expo_push",
                      lambda msgs: sent.extend(msgs) or []):
        # 场景 1：中文司机
        db = _db()
        ride, _ = _make_ride(db, u, status="accepted", driver_id=drv_zh.id)
        rid = ride.id
        db.close()
        r = client.post(f"/rides/{rid}/delay",
                        json={"minutes": 60}, headers=_auth(tok))
        assert r.status_code == 200

    assert len(sent) == 1
    msg = sent[0]
    assert msg["to"] == "ExponentPushToken[drvzh]"
    assert "乘客航班晚点" in msg["title"]
    assert "60" in msg["body"]
    assert msg["data"]["type"] == "ride_delayed"
    assert msg["data"]["ride_id"] == str(rid)


def test_delay英文司机收到英文推送(client):
    db = _db()
    u = _make_user(db)
    tok = _make_token(db, u)
    drv_en = _make_user(db, role="driver",
                        push_token="ExpoPushToken[drven]",
                        lang="en", name="English driver")
    ride, _ = _make_ride(db, u, status="accepted", driver_id=drv_en.id)
    rid = ride.id
    db.close()

    sent = []
    with patch.object(push_mod, "send_expo_push",
                      lambda msgs: sent.extend(msgs) or []):
        r = client.post(f"/rides/{rid}/delay",
                        json={"minutes": 30}, headers=_auth(tok))
        assert r.status_code == 200

    assert len(sent) == 1
    assert "Flight delayed" in sent[0]["title"]


def test_delay未接单不发推送但成功(client):
    db = _db()
    u = _make_user(db)
    tok = _make_token(db, u)
    ride, _ = _make_ride(db, u, status="requested")  # 还没司机
    rid = ride.id
    db.close()

    with patch.object(push_mod, "send_expo_push",
                      side_effect=AssertionError("不应发推送")):
        r = client.post(f"/rides/{rid}/delay",
                        json={"minutes": 120}, headers=_auth(tok))
        assert r.status_code == 200
