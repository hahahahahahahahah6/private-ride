"""2026-10 bug 修复的回归测试。

覆盖：预约时间带 UTC 时区返回 / 过去的预约时间被拒 / 没绑卡不能选线上付 /
司机取消 = 退回待接单池 / 报价未确认不能开始行程 / 司机列表不暴露手机号。
"""
from __future__ import annotations

import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base, get_db
from app.main import app

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
_engine = create_engine(f"sqlite:///{_tmp.name}", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=_engine)
_Session = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)


def _override_get_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[get_db] = _override_get_db
    with patch("app.main._notify_new_ride_bg", lambda ride_id: None), \
            patch("app.push.send_expo_push", lambda msgs: []):
        yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def _user(role="passenger", name="", phone=None):
    db = _Session()
    u = models.User(phone=phone or f"+1626{uuid.uuid4().int % 10**7:07d}", name=name, role=role)
    db.add(u)
    db.commit()
    tok = uuid.uuid4().hex
    db.add(models.AuthToken(token=tok, user_id=u.id,
                            expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
    db.commit()
    db.close()
    return u, {"Authorization": f"Bearer {tok}"}


def _ride(client, h, **kw):
    body = {"pickup_text": "Arcadia", "dropoff_text": "LAX", "price_mode": "offer",
            "price_offer_cents": 5000}
    body.update(kw)
    return client.post("/rides", json=body, headers=h)


def test_预约时间返回带UTC时区(client):
    _, h = _user()
    when = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
    r = _ride(client, h, scheduled_at=when.isoformat())
    assert r.status_code == 201, r.text
    out = r.json()["scheduled_at"]
    assert out.endswith("Z") or out.endswith("+00:00")
    assert datetime.fromisoformat(out.replace("Z", "+00:00")) == when


def test_带时区偏移的预约时间按UTC存(client):
    _, h = _user()
    local = (datetime.now(timezone(timedelta(hours=-7))) + timedelta(days=1)).replace(microsecond=0)
    r = _ride(client, h, scheduled_at=local.isoformat())
    assert r.status_code == 201
    got = datetime.fromisoformat(r.json()["scheduled_at"].replace("Z", "+00:00"))
    assert got == local


def test_过去的预约时间被拒(client):
    _, h = _user()
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    assert _ride(client, h, scheduled_at=past.isoformat()).status_code == 400


def test_没绑卡不能选线上付(client):
    _, h = _user()
    with patch("app.stripe_pay._configured", lambda: True):
        r = _ride(client, h, pay_mode="online")
    assert r.status_code == 400


def test_司机取消是退回待接单(client):
    _, ph = _user()
    _, dh = _user(role="driver", name="老李")
    rid = _ride(client, ph).json()["id"]
    assert client.post(f"/rides/{rid}/accept", headers=dh).status_code == 200
    r = client.post(f"/rides/{rid}/cancel", headers=dh)
    assert r.status_code == 200
    assert r.json()["status"] == "requested"
    assert r.json()["driver_id"] is None


def test_乘客取消还是真取消(client):
    _, ph = _user()
    _, dh = _user(role="driver")
    rid = _ride(client, ph).json()["id"]
    client.post(f"/rides/{rid}/accept", headers=dh)
    r = client.post(f"/rides/{rid}/cancel", headers=ph)
    assert r.json()["status"] == "cancelled"


def test_报价没确认不能开始行程(client):
    _, ph = _user()
    _, dh = _user(role="driver")
    rid = _ride(client, ph, price_mode="quote", price_offer_cents=None).json()["id"]
    client.post(f"/rides/{rid}/accept", headers=dh)
    for st in ("en_route", "arrived"):
        assert client.post(f"/rides/{rid}/status", json={"status": st}, headers=dh).status_code == 200
    r = client.post(f"/rides/{rid}/status", json={"status": "in_progress"}, headers=dh)
    assert r.status_code == 400
    # 报价 + 乘客确认后就可以开始
    client.post(f"/rides/{rid}/quote", json={"price_quote_cents": 4000}, headers=dh)
    assert client.post(f"/rides/{rid}/quote/confirm", json={"accept": True}, headers=ph).status_code == 200
    r = client.post(f"/rides/{rid}/status", json={"status": "in_progress"}, headers=dh)
    assert r.status_code == 200


def test_司机列表不暴露手机号(client):
    _, ph = _user()
    _user(role="driver", name="", phone="+16265559999")
    names = [d["name"] for d in client.get("/drivers/status", headers=ph).json()]
    assert "+16265559999" not in names
