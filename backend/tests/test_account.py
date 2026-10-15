"""账号体系测试：PATCH /me、POST /auth/logout、DELETE /me。

用临时 SQLite 库 + TestClient 跑真实接口（只覆盖账号相关接口，
不碰生产 dev.db 的数据）。
"""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base, get_db
from app.main import app

# ---------- 测试库：一人一个临时文件，互不干扰 ----------

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


app.dependency_overrides[get_db] = _override_get_db
client = TestClient(app)

_seq = 0


def _next_phone() -> str:
    global _seq
    _seq += 1
    return f"+1555000{_seq:04d}"


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


# ---------- PATCH /me ----------

def test_patch_me_更新昵称成功():
    db = _db()
    u = _make_user(db, name="老名字")
    tok = _make_token(db, u)
    db.close()

    r = client.patch("/me", json={"name": "  新名字  "}, headers=_auth(tok))
    assert r.status_code == 200
    assert r.json()["name"] == "新名字"  # 自动去空格
    assert r.json()["role"] == "passenger"

    db = _db()
    assert db.get(models.User, u.id).name == "新名字"
    db.close()


def test_patch_me_拒绝自己改role():
    db = _db()
    u = _make_user(db)
    tok = _make_token(db, u)
    db.close()

    r = client.patch("/me", json={"name": "x", "role": "admin"}, headers=_auth(tok))
    assert r.status_code == 403
    assert "role" in r.json()["detail"]

    db = _db()
    assert db.get(models.User, u.id).role == "passenger"  # 没被改掉
    db.close()


def test_patch_me_未登录401():
    r = client.patch("/me", json={"name": "x"})
    assert r.status_code == 401


def test_patch_me_昵称超长400():
    db = _db()
    u = _make_user(db)
    tok = _make_token(db, u)
    db.close()

    r = client.patch("/me", json={"name": "名" * 65}, headers=_auth(tok))
    assert r.status_code == 400


# ---------- POST /auth/logout ----------

def test_logout_撤销当前token后立即失效():
    db = _db()
    u = _make_user(db)
    tok = _make_token(db, u)
    db.close()

    r = client.post("/auth/logout", headers=_auth(tok))
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    # token 已从表里删除
    db = _db()
    assert db.get(models.AuthToken, tok) is None
    db.close()

    # 再用这个 token 调接口：401
    r2 = client.get("/me", headers=_auth(tok))
    assert r2.status_code == 401


def test_logout_只撤销当前token不影响其他登录():
    db = _db()
    u = _make_user(db)
    tok_a = _make_token(db, u)
    tok_b = _make_token(db, u)
    db.close()

    r = client.post("/auth/logout", headers=_auth(tok_a))
    assert r.status_code == 200

    # 另一个 token 还能用
    r2 = client.get("/me", headers=_auth(tok_b))
    assert r2.status_code == 200


def test_logout_未登录401():
    r = client.post("/auth/logout")
    assert r.status_code == 401


# ---------- DELETE /me ----------

def test_delete_me_需要二次确认():
    db = _db()
    u = _make_user(db)
    tok = _make_token(db, u)
    uid = u.id
    db.close()

    r = client.delete("/me", headers=_auth(tok))
    assert r.status_code == 400
    r = client.delete("/me?confirm=false", headers=_auth(tok))
    assert r.status_code == 400

    # 人还在
    db = _db()
    assert db.get(models.User, uid) is not None
    db.close()


def test_delete_me_完整注销流程():
    db = _db()
    me = _make_user(db, role="driver", name="要注销的司机")
    other = _make_user(db, role="passenger", name="无关乘客")
    tok = _make_token(db, me)
    _make_token(db, me)  # 第二个 token，也要被清掉
    db.add(models.SavedPlace(user_id=me.id, label="家", address_text="某小区"))
    db.add(models.Driver(user_id=me.id, vehicle_model="Model 3", plate="ABC123"))
    # 我当乘客的一单（带金额，对账用）
    my_ride = models.Ride(
        passenger_id=me.id, pickup_text="面馆", dropoff_text="机场",
        price_final_cents=2500, status="completed",
    )
    db.add(my_ride)
    db.flush()
    db.add(models.ShareToken(
        token="share-xyz", ride_id=my_ride.id, created_by=me.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    ))
    # 我当司机的一单
    drv_ride = models.Ride(
        passenger_id=other.id, driver_id=me.id,
        pickup_text="学校", dropoff_text="商场",
        price_final_cents=1800, status="completed",
    )
    db.add(drv_ride)
    # 无关用户的单：不能动
    other_ride = models.Ride(
        passenger_id=other.id, pickup_text="A", dropoff_text="B",
        price_final_cents=900, status="requested",
    )
    db.add(other_ride)
    db.commit()
    my_ride_id, drv_ride_id, other_ride_id = my_ride.id, drv_ride.id, other_ride.id
    me_id = me.id
    db.close()

    r = client.delete("/me?confirm=true", headers=_auth(tok))
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    db = _db()
    # 用户行没了
    assert db.get(models.User, me_id) is None
    # 所有 token / 常用地址 / 分享链接 / 司机档案都没了
    assert db.query(models.AuthToken).filter_by(user_id=me_id).count() == 0
    assert db.query(models.SavedPlace).filter_by(user_id=me_id).count() == 0
    assert db.query(models.ShareToken).filter_by(created_by=me_id).count() == 0
    assert db.get(models.Driver, me_id) is None
    # 订单保留：关联置空，金额还在
    mr = db.get(models.Ride, my_ride_id)
    assert mr is not None
    assert mr.passenger_id is None
    assert mr.price_final_cents == 2500
    dr = db.get(models.Ride, drv_ride_id)
    assert dr is not None
    assert dr.driver_id is None
    assert dr.price_final_cents == 1800
    # 无关用户的单原样保留
    oride = db.get(models.Ride, other_ride_id)
    assert oride.passenger_id == other.id
    assert oride.price_final_cents == 900
    db.close()

    # 旧 token 已失效
    assert client.get("/me", headers=_auth(tok)).status_code == 401


def test_delete_me_未登录401():
    r = client.delete("/me?confirm=true")
    assert r.status_code == 401
