"""推送模块测试：全部 mock 网络，只验证载荷格式与分发逻辑。"""
from __future__ import annotations

import io
import json
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import push as push_mod


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeRide:
    id = uuid.uuid4()
    pickup_text = "LAX T1"
    dropoff_text = "迪士尼"
    seats_needed = 4
    note = ""


class FakeUser:
    _seq = 0

    def __init__(self, role, token):
        FakeUser._seq += 1
        self.id = f"u-{FakeUser._seq}"
        self.role = role
        self.push_token = token


class FakeQuery:
    def __init__(self, users):
        self._users = users

    def filter(self, *a):
        return self

    def all(self):
        # 模拟 SQL：role in (driver, admin) 且 push_token 非空
        return [
            u
            for u in self._users
            if u.role in ("driver", "admin") and u.push_token
        ]


class FakeDB:
    def __init__(self, users, drivers=None):
        self._users = users
        self._drivers = drivers or []

    def query(self, *a):
        from app.models import Driver
        if a and a[0] is Driver:
            return FakeDriverQuery(self._drivers)
        return FakeQuery(self._users)


class FakeDriver:
    def __init__(self, user_id, is_active):
        self.user_id = user_id
        self.is_active = is_active


class FakeDriverQuery:
    def __init__(self, drivers):
        self._drivers = drivers

    def all(self):
        return self._drivers


def test_token_validation():
    assert push_mod.is_expo_push_token("ExponentPushToken[abc123]")
    assert push_mod.is_expo_push_token("ExpoPushToken[xyz]")
    assert not push_mod.is_expo_push_token(None)
    assert not push_mod.is_expo_push_token("")
    assert not push_mod.is_expo_push_token("fcm-token-abc")
    assert not push_mod.is_expo_push_token("ExponentPushToken[abc")  # 缺右括号


def test_send_expo_push_payload_format():
    sent = {}

    def fake_urlopen(req, timeout=None):
        sent["url"] = req.full_url
        sent["body"] = json.loads(req.data.decode())
        sent["headers"] = dict(req.header_items())
        return FakeResp({"data": [{"status": "ok", "id": "ticket-1"}]})

    with patch.object(push_mod.urllib.request, "urlopen", fake_urlopen):
        tickets = push_mod.send_expo_push(
            [{"to": "ExponentPushToken[a]", "title": "t", "body": "b"}]
        )

    assert sent["url"] == "https://exp.host/--/api/v2/push/send"
    assert sent["body"][0]["to"] == "ExponentPushToken[a]"
    assert tickets == [{"status": "ok", "id": "ticket-1"}]


def test_notify_drivers_only_drivers_with_valid_tokens():
    users = [
        FakeUser("driver", "ExponentPushToken[driver1]"),
        FakeUser("driver", None),  # 没注册 token，跳过
        FakeUser("driver", "garbage"),  # 非法 token，跳过
        FakeUser("passenger", "ExponentPushToken[pax1]"),  # 乘客不收司机推送
        FakeUser("admin", "ExpoPushToken[admin1]"),
    ]
    db = FakeDB(users)
    bodies = []

    def fake_urlopen(req, timeout=None):
        bodies.append(json.loads(req.data.decode()))
        n = len(json.loads(req.data.decode()))
        return FakeResp({"data": [{"status": "ok"}] * n})

    with patch.object(push_mod.urllib.request, "urlopen", fake_urlopen):
        stat = push_mod.notify_drivers_of_new_ride(db, FakeRide())

    assert stat["sent"] == 2
    tos = {m["to"] for m in bodies[0]}
    assert tos == {"ExponentPushToken[driver1]", "ExpoPushToken[admin1]"}
    msg = bodies[0][0]
    assert msg["title"] == "🚕 新订单"
    assert "LAX T1" in msg["body"] and "迪士尼" in msg["body"]
    assert "4 位" in msg["body"]
    assert msg["data"]["type"] == "new_ride"


def test_notify_no_drivers_no_http():
    db = FakeDB([FakeUser("driver", None)])
    with patch.object(
        push_mod.urllib.request, "urlopen", side_effect=AssertionError("不应发请求")
    ):
        stat = push_mod.notify_drivers_of_new_ride(db, FakeRide())
    assert stat["sent"] == 0
    assert stat["reason"] == "no valid push tokens"


def test_notify_push_failure_does_not_raise():
    users = [FakeUser("driver", "ExponentPushToken[d1]")]
    db = FakeDB(users)
    with patch.object(
        push_mod.urllib.request, "urlopen", side_effect=OSError("断网")
    ):
        stat = push_mod.notify_drivers_of_new_ride(db, FakeRide())
    assert stat["sent"] == 0
    assert "push error" in stat["reason"]


def test_notify_skips_offline_drivers():
    users = [
        FakeUser("driver", "ExponentPushToken[online1]"),
        FakeUser("driver", "ExponentPushToken[offline1]"),
    ]
    users[0].id = "u-online"
    users[1].id = "u-offline"
    drivers = [FakeDriver("u-offline", 0)]  # 休息中
    db = FakeDB(users, drivers)
    bodies = []

    def fake_urlopen(req, timeout=None):
        bodies.append(json.loads(req.data.decode()))
        n = len(json.loads(req.data.decode()))
        return FakeResp({"data": [{"status": "ok"}] * n})

    with patch.object(push_mod.urllib.request, "urlopen", fake_urlopen):
        stat = push_mod.notify_drivers_of_new_ride(db, FakeRide())
    assert stat["sent"] == 1
    assert bodies[0][0]["to"] == "ExponentPushToken[online1]"
