"""Expo Push 通知：新订单创建时推送给所有司机。

用 Python 标准库 urllib 直接调 Expo 官方推送服务，
不引入第三方依赖。失败永远不影响主流程（调用方包 try/except）。
"""
from __future__ import annotations

import json
import logging
import urllib.request

log = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
_TIMEOUT = 8


def is_expo_push_token(token: str | None) -> bool:
    """Expo push token 形如 ExponentPushToken[xxx] 或 ExpoPushToken[xxx]。"""
    if not token or not isinstance(token, str):
        return False
    t = token.strip()
    return (
        t.startswith("ExponentPushToken[") or t.startswith("ExpoPushToken[")
    ) and t.endswith("]")


def send_expo_push(messages: list[dict]) -> list[dict]:
    """发一批推送，返回 Expo 的 ticket 列表（每条含 status / id 或 error）。"""
    if not messages:
        return []
    body = json.dumps(messages).encode("utf-8")
    req = urllib.request.Request(
        EXPO_PUSH_URL,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload.get("data", [])


def notify_drivers_of_new_ride(db, ride) -> dict:
    """新订单 → 推送给所有有 push_token 的司机。返回统计，不抛异常。"""
    from .models import User  # 避免循环导入

    drivers = (
        db.query(User)
        .filter(User.role.in_(("driver", "admin")))
        .filter(User.push_token.isnot(None))
        .all()
    )
    tokens = [d.push_token for d in drivers if is_expo_push_token(d.push_token)]
    if not tokens:
        return {"sent": 0, "skipped": len(drivers), "reason": "no valid push tokens"}

    title = "🚕 新订单"
    text = f"{ride.pickup_text} → {ride.dropoff_text}"
    if ride.seats_needed and ride.seats_needed > 1:
        text += f"（{ride.seats_needed} 位）"
    messages = [
        {
            "to": tok,
            "sound": "default",
            "title": title,
            "body": text,
            "data": {"ride_id": str(ride.id), "type": "new_ride"},
        }
        for tok in tokens
    ]
    try:
        tickets = send_expo_push(messages)
    except Exception as exc:  # 网络/Expo 故障不影响下单
        log.warning("expo push failed: %s", exc)
        return {"sent": 0, "skipped": len(tokens), "reason": f"push error: {exc}"}

    ok = sum(1 for t in tickets if t.get("status") == "ok")
    errors = [t for t in tickets if t.get("status") != "ok"]
    if errors:
        log.warning("expo push partial failure: %s", errors)

    # 清理死 token：Expo 明确说设备已注销（通常是卸载 App），
    # 就把该司机的 push_token 置空，下次不再打扰 Expo。
    # tickets 与发送的 tokens 顺序一一对应，可 zip。
    dead = 0
    for tok, ticket in zip(tokens, tickets):
        details = ticket.get("details") or {}
        if ticket.get("status") != "ok" and details.get("error") == "DeviceNotRegistered":
            user = next((d for d in drivers if d.push_token == tok), None)
            if user is not None:
                user.push_token = None
                dead += 1
    if dead:
        db.commit()
        log.info("cleared %d dead push tokens", dead)
    return {"sent": ok, "skipped": len(tokens) - ok, "errors": errors, "dead_cleared": dead}
