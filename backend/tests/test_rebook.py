"""一键再来一单测试：POST /rides/{ride_id}/rebook。

用临时 SQLite 库 + TestClient 跑真实接口，不碰生产 dev.db。
"""
from __future__ import annotations

import json
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
    return f"+1666000{_seq:04d}"


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


def _make_completed_ride(db, passenger, **over):
    """造一条"执行过"的历史订单：带司机、报价、评分、小费、预约时间。"""
    kw = dict(
        passenger_id=passenger.id,
        pickup_text="面馆",
        dropoff_text="LAX 机场",
        seats_needed=3,
        note="后备箱要放两个行李箱",
        flight_no="UA857",
        scheduled_at=datetime.now(timezone.utc) - timedelta(days=1),
        status="completed",
        price_mode="offer",
        price_offer_cents=4500,
        price_quote_cents=5000,
        price_final_cents=5000,
        price_status="agreed",
        pay_mode="offline",
        stops_json=json.dumps(["加油站", "超市"], ensure_ascii=False),
        booked_for_name="张三",
        booked_for_phone="+16265550100",
        rating_stars=5,
        rating_comment="开车稳",
        rated_at=datetime.now(timezone.utc),
        tip_cents=300,
        tip_at=datetime.now(timezone.utc),
    )
    kw.update(over)
    r = models.Ride(**kw)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


# ---------- 复购成功 ----------

def test_rebook_成功_字段复制正确():
    db = _db()
    me = _make_user(db)
    driver = _make_user(db, role="driver", name="司机")
    tok = _make_token(db, me)
    old = _make_completed_ride(db, me, driver_id=driver.id)
    old_id = old.id
    db.close()

    r = client.post(f"/rides/{old_id}/rebook", headers=_auth(tok))
    assert r.status_code == 201
    data = r.json()

    # 新单 id 不同，状态 requested
    assert data["id"] != str(old_id)
    assert data["status"] == "requested"
    assert data["passenger_id"] == str(me.id)

    # 复制的字段
    assert data["pickup_text"] == "面馆"
    assert data["dropoff_text"] == "LAX 机场"
    assert data["seats_needed"] == 3
    assert data["note"] == "后备箱要放两个行李箱"
    assert data["flight_no"] == "UA857"
    assert data["stops"] == ["加油站", "超市"]
    assert data["price_mode"] == "offer"
    assert data["price_offer_cents"] == 4500
    assert data["pay_mode"] == "offline"
    assert data["booked_for_name"] == "张三"
    assert data["booked_for_phone"] == "+16265550100"

    # 不复制的字段：时间/司机/报价/成交价/评分/小费 全部归零
    assert data["scheduled_at"] is None
    assert data["driver_id"] is None
    assert data["price_quote_cents"] is None
    assert data["rating_stars"] is None
    assert data["tip_cents"] is None

    db = _db()
    new = db.get(models.Ride, data["id"])
    assert new is not None
    assert new.scheduled_at is None  # 默认"现在用车"
    assert new.price_final_cents == 4500  # 出价模式：初始成交价=出价
    assert new.price_status == "agreed"
    db.close()


def test_rebook_已取消的单也可以复购():
    db = _db()
    me = _make_user(db)
    tok = _make_token(db, me)
    old = _make_completed_ride(db, me, status="cancelled")
    old_id = old.id
    db.close()

    r = client.post(f"/rides/{old_id}/rebook", headers=_auth(tok))
    assert r.status_code == 201
    assert r.json()["status"] == "requested"
    assert r.json()["pickup_text"] == "面馆"


def test_rebook_里程模式按里程重算初始价():
    db = _db()
    me = _make_user(db)
    tok = _make_token(db, me)
    old = _make_completed_ride(
        db, me, price_mode="mileage", price_offer_cents=None,
        price_miles=10.0, price_final_cents=3800)
    old_id = old.id
    db.close()

    r = client.post(f"/rides/{old_id}/rebook", headers=_auth(tok))
    assert r.status_code == 201
    data = r.json()
    assert data["price_mode"] == "mileage"
    assert data["price_miles"] == 10.0

    db = _db()
    new = db.get(models.Ride, data["id"])
    # 里程计价：按当前公式重算（8 + 3*10 = $38）
    assert new.price_final_cents == 800 + 300 * 10
    db.close()


def test_rebook_quote模式等司机重新报价():
    db = _db()
    me = _make_user(db)
    tok = _make_token(db, me)
    old = _make_completed_ride(db, me, price_mode="quote", price_offer_cents=None)
    old_id = old.id
    db.close()

    r = client.post(f"/rides/{old_id}/rebook", headers=_auth(tok))
    assert r.status_code == 201
    data = r.json()
    assert data["price_quote_cents"] is None
    assert data["price_final_cents"] is None
    assert data["price_status"] == "pending"


def test_rebook_hourly模式_费率复制_成交价待结算():
    db = _db()
    me = _make_user(db)
    tok = _make_token(db, me)
    old = _make_completed_ride(
        db, me, price_mode="hourly", price_offer_cents=None,
        hourly_rate_cents=8000, price_final_cents=20000)
    old_id = old.id
    db.close()

    r = client.post(f"/rides/{old_id}/rebook", headers=_auth(tok))
    assert r.status_code == 201
    data = r.json()
    assert data["price_mode"] == "hourly"
    assert data["hourly_rate_cents"] == 8000
    # 包车成交价不复制：等行程结束按实际小时数结算
    assert data["price_final_cents"] is None
    assert data["price_status"] == "pending"


# ---------- 权限与状态限制 ----------

def test_rebook_别人的单403():
    db = _db()
    me = _make_user(db, name="我")
    other = _make_user(db, name="别人")
    tok = _make_token(db, me)
    old = _make_completed_ride(db, other)
    old_id = old.id
    db.close()

    r = client.post(f"/rides/{old_id}/rebook", headers=_auth(tok))
    assert r.status_code == 403
    assert "自己" in r.json()["detail"]


def test_rebook_司机不能复购自己接过的单():
    db = _db()
    me = _make_user(db, name="乘客")
    driver = _make_user(db, role="driver", name="司机")
    driver_tok = _make_token(db, driver)
    old = _make_completed_ride(db, me, driver_id=driver.id)
    old_id = old.id
    db.close()

    # 接过这单的司机也不是下单人，不能复购
    r = client.post(f"/rides/{old_id}/rebook", headers=_auth(driver_tok))
    assert r.status_code == 403


def test_rebook_进行中订单400():
    db = _db()
    me = _make_user(db)
    tok = _make_token(db, me)
    ids = []
    for status in ("requested", "accepted", "en_route", "arrived", "in_progress"):
        old = _make_completed_ride(db, me, status=status)
        ids.append(old.id)
    db.close()

    for rid in ids:
        r = client.post(f"/rides/{rid}/rebook", headers=_auth(tok))
        assert r.status_code == 400, f"status={status}"
        assert "已完成或已取消" in r.json()["detail"]


def test_rebook_订单不存在404():
    db = _db()
    me = _make_user(db)
    tok = _make_token(db, me)
    db.close()

    r = client.post(f"/rides/{uuid4()}/rebook", headers=_auth(tok))
    assert r.status_code == 404


def test_rebook_未登录401():
    db = _db()
    me = _make_user(db)
    old = _make_completed_ride(db, me)
    old_id = old.id
    db.close()

    r = client.post(f"/rides/{old_id}/rebook")
    assert r.status_code == 401
