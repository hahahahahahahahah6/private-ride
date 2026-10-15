"""司机熟客便签测试：增改删、乘客 403、只能看自己的、RideOut 可见性。

用临时 SQLite 库 + TestClient 跑真实接口，不碰生产 dev.db 的数据。
注意：test_account.py 在模块级覆盖了 app.dependency_overrides[get_db]，
这里用 fixture 按用例覆盖、用完恢复，避免互相污染。
"""
from __future__ import annotations

import os
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


@pytest.fixture()
def tclient():
    """每用例一个临时库，覆盖 get_db 后恢复原覆盖。"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    engine = create_engine(
        f"sqlite:///{tmp.name}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )

    def _override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    prev = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app), TestingSession
    finally:
        if prev is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = prev
        os.unlink(tmp.name)


_seq = 0


def _next_phone() -> str:
    global _seq
    _seq += 1
    return f"+1666000{_seq:04d}"


def _make_user(db, role="passenger", name="测试用户"):
    u = models.User(phone=_next_phone(), name=name, role=role)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_token(db, user):
    token = f"tok-{uuid4().hex[:12]}"
    db.add(models.AuthToken(
        token=token,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    ))
    db.commit()
    return token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _setup(tclient):
    """一个司机 + 一个乘客，各自 token。返回 (client, Session, driver, passenger, d_tok, p_tok)。"""
    client, Session = tclient
    db = Session()
    driver = _make_user(db, role="driver", name="司机老王")
    passenger = _make_user(db, role="passenger", name="张阿姨")
    d_tok = _make_token(db, driver)
    p_tok = _make_token(db, passenger)
    db.close()
    return client, Session, driver, passenger, d_tok, p_tok


# ---------- 增改删 ----------

def test_司机新增便签成功(tclient):
    client, Session, driver, passenger, d_tok, _ = _setup(tclient)

    r = client.put(f"/drivers/notes/{passenger.id}",
                   json={"note": "张阿姨晕车，开慢点"},
                   headers=_auth(d_tok))
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["deleted"] is False
    assert body["note"]["passenger_id"] == str(passenger.id)
    assert body["note"]["passenger_name"] == "张阿姨"
    assert body["note"]["note"] == "张阿姨晕车，开慢点"

    # 列表里能看到
    r2 = client.get("/drivers/notes", headers=_auth(d_tok))
    assert r2.status_code == 200
    items = r2.json()
    assert len(items) == 1
    assert items[0]["note"] == "张阿姨晕车，开慢点"
    assert items[0]["passenger_name"] == "张阿姨"

    # 库里 driver+passenger 唯一：只有一行
    db = Session()
    assert db.query(models.PassengerNote).count() == 1
    db.close()


def test_司机更新便签覆盖旧内容(tclient):
    client, Session, driver, passenger, d_tok, _ = _setup(tclient)

    client.put(f"/drivers/notes/{passenger.id}", json={"note": "旧内容"},
               headers=_auth(d_tok))
    r = client.put(f"/drivers/notes/{passenger.id}", json={"note": "  新内容  "},
                   headers=_auth(d_tok))
    assert r.status_code == 200
    assert r.json()["note"]["note"] == "新内容"  # 自动去空格

    db = Session()
    assert db.query(models.PassengerNote).count() == 1  # 还是同一行，不是新增
    assert db.query(models.PassengerNote).first().note == "新内容"
    db.close()


def test_司机传空字符串删除便签(tclient):
    client, Session, driver, passenger, d_tok, _ = _setup(tclient)

    client.put(f"/drivers/notes/{passenger.id}", json={"note": "要删掉"},
               headers=_auth(d_tok))
    r = client.put(f"/drivers/notes/{passenger.id}", json={"note": "   "},
                   headers=_auth(d_tok))
    assert r.status_code == 200
    assert r.json() == {"ok": True, "deleted": True}

    assert client.get("/drivers/notes", headers=_auth(d_tok)).json() == []
    db = Session()
    assert db.query(models.PassengerNote).count() == 0
    db.close()


def test_便签目标乘客不存在404(tclient):
    client, _, _, _, d_tok, _ = _setup(tclient)
    r = client.put(f"/drivers/notes/{uuid4()}", json={"note": "x"},
                   headers=_auth(d_tok))
    assert r.status_code == 404


def test_便签超长422(tclient):
    client, _, _, passenger, d_tok, _ = _setup(tclient)
    r = client.put(f"/drivers/notes/{passenger.id}", json={"note": "字" * 1001},
                   headers=_auth(d_tok))
    assert r.status_code == 422  # pydantic max_length=1000 校验


def test_未登录401(tclient):
    client, _, _, passenger, _, _ = _setup(tclient)
    assert client.get("/drivers/notes").status_code == 401
    assert client.put(f"/drivers/notes/{passenger.id}",
                      json={"note": "x"}).status_code == 401


# ---------- 权限 ----------

def test_乘客调便签接口403(tclient):
    client, _, driver, passenger, d_tok, p_tok = _setup(tclient)

    assert client.get("/drivers/notes", headers=_auth(p_tok)).status_code == 403
    r = client.put(f"/drivers/notes/{driver.id}", json={"note": "x"},
                   headers=_auth(p_tok))
    assert r.status_code == 403
    # 司机自己的接口不受影响
    assert client.get("/drivers/notes", headers=_auth(d_tok)).status_code == 200


def test_司机只能看到自己写的便签(tclient):
    client, Session, driver, passenger, d_tok, _ = _setup(tclient)
    db = Session()
    other_driver = _make_user(db, role="driver", name="司机老李")
    o_tok = _make_token(db, other_driver)
    db.close()

    client.put(f"/drivers/notes/{passenger.id}", json={"note": "老王写的"},
               headers=_auth(d_tok))

    # 另一个司机看不到老王的便签
    assert client.get("/drivers/notes", headers=_auth(o_tok)).json() == []
    # 老李自己写一条，两人互不干扰
    client.put(f"/drivers/notes/{passenger.id}", json={"note": "老李写的"},
               headers=_auth(o_tok))
    assert client.get("/drivers/notes", headers=_auth(d_tok)).json()[0]["note"] == "老王写的"
    assert client.get("/drivers/notes", headers=_auth(o_tok)).json()[0]["note"] == "老李写的"


# ---------- RideOut 可见性 ----------

def _make_ride(client, Session, p_tok, d_tok):
    """乘客下单 → 司机接单，返回 ride_id。"""
    r = client.post("/rides", json={
        "pickup_text": "面馆", "dropoff_text": "机场",
        "price_mode": "offer", "price_offer_cents": 2500,
    }, headers=_auth(p_tok))
    assert r.status_code == 201
    ride_id = r.json()["id"]
    r2 = client.post(f"/rides/{ride_id}/accept", headers=_auth(d_tok))
    assert r2.status_code == 200
    return ride_id


def test_RideOut司机能看到便签乘客看不到(tclient):
    client, Session, driver, passenger, d_tok, p_tok = _setup(tclient)
    ride_id = _make_ride(client, Session, p_tok, d_tok)

    client.put(f"/drivers/notes/{passenger.id}", json={"note": "李叔爱听戏曲"},
               headers=_auth(d_tok))

    # 司机查单条订单：能看到便签
    rd = client.get(f"/rides/{ride_id}", headers=_auth(d_tok))
    assert rd.status_code == 200
    assert rd.json()["passenger_note"] == "李叔爱听戏曲"

    # 乘客查同一单：看不到便签字段内容
    rp = client.get(f"/rides/{ride_id}", headers=_auth(p_tok))
    assert rp.status_code == 200
    assert rp.json()["passenger_note"] is None

    # 司机自己的行程列表里也能看到（批量预加载路径）
    mine = client.get("/rides?mine=true", headers=_auth(d_tok)).json()
    assert mine[0]["passenger_note"] == "李叔爱听戏曲"
    # 乘客的行程列表里看不到
    pmine = client.get("/rides?mine=true", headers=_auth(p_tok)).json()
    assert pmine[0]["passenger_note"] is None


def test_待接单池里司机只看到自己写的便签(tclient):
    client, Session, driver, passenger, d_tok, p_tok = _setup(tclient)
    db = Session()
    other_driver = _make_user(db, role="driver", name="司机老李")
    o_tok = _make_token(db, other_driver)
    db.close()

    # 乘客下一单（待接单）
    r = client.post("/rides", json={
        "pickup_text": "学校", "dropoff_text": "商场",
        "price_mode": "offer", "price_offer_cents": 1800,
    }, headers=_auth(p_tok))
    ride_id = r.json()["id"]

    # 只有老王写过便签
    client.put(f"/drivers/notes/{passenger.id}", json={"note": "晕车开慢点"},
               headers=_auth(d_tok))

    open_wang = client.get("/rides?mine=false&open=true",
                           headers=_auth(d_tok)).json()
    assert open_wang[0]["id"] == ride_id
    assert open_wang[0]["passenger_note"] == "晕车开慢点"

    # 老李没写过：看不到
    open_li = client.get("/rides?mine=false&open=true",
                         headers=_auth(o_tok)).json()
    assert open_li[0]["passenger_note"] is None


def test_无关司机查单条订单403(tclient):
    client, Session, driver, passenger, d_tok, p_tok = _setup(tclient)
    ride_id = _make_ride(client, Session, p_tok, d_tok)

    db = Session()
    stranger = _make_user(db, role="driver", name="路人司机")
    s_tok = _make_token(db, stranger)
    db.close()

    assert client.get(f"/rides/{ride_id}", headers=_auth(s_tok)).status_code == 403
    assert client.get(f"/rides/{uuid4()}", headers=_auth(d_tok)).status_code == 404
