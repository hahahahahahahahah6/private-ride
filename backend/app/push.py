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


def _lang_of(user) -> str:
    """用户语言，非法值回退中文。"""
    return "en" if getattr(user, "lang", "zh") == "en" else "zh"


_PASSENGER_TEXT = {
    "zh": {
        "accepted": ("✅ 司机已接单", "司机接了您的订单：{p} → {d}"),
        "en_route": ("🚗 司机已出发", "司机正在赶往 {p}"),
        "arrived": ("📍 司机已到达", "司机已到上车点：{p}，请准备上车"),
        "in_progress": ("🛣️ 行程开始", "祝您一路顺利：{p} → {d}"),
        "completed": ("🏁 行程完成", "感谢乘坐，欢迎给司机评分"),
        "cancelled": ("订单已取消", "{p} → {d} 的订单已取消"),
        "released": ("司机暂时接不了", "司机退回了订单，正在重新派给其他司机：{p} → {d}"),
        "quoted": ("💰 司机已报价", "司机报价 {price}，请打开 App 确认"),
    },
    "en": {
        "accepted": ("✅ Driver accepted", "Your ride {p} → {d} was accepted"),
        "en_route": ("🚗 Driver on the way", "Your driver is heading to {p}"),
        "arrived": ("📍 Driver arrived", "Your driver is at {p}"),
        "in_progress": ("🛣️ Ride started", "Have a smooth trip: {p} → {d}"),
        "completed": ("🏁 Ride completed", "Thanks for riding. Rate your driver anytime."),
        "cancelled": ("Ride cancelled", "Your ride {p} → {d} was cancelled"),
        "released": ("Driver released the ride", "We're finding another driver: {p} → {d}"),
        "quoted": ("💰 New price quote", "Your driver quoted {price}. Open the app to confirm."),
    },
}


def notify_user(user, kind: str, ride, **extra) -> bool:
    """给单个用户发一条订单状态推送（乘客用）。没 token 或失败返回 False，不抛异常。"""
    if user is None or not is_expo_push_token(getattr(user, "push_token", None)):
        return False
    texts = _PASSENGER_TEXT[_lang_of(user)].get(kind)
    if not texts:
        return False
    fmt = {"p": ride.pickup_text, "d": ride.dropoff_text, **extra}
    try:
        send_expo_push([{
            "to": user.push_token,
            "sound": "default",
            "title": texts[0],
            "body": texts[1].format(**fmt),
            "data": {"ride_id": str(ride.id), "type": f"ride_{kind}"},
        }])
        return True
    except Exception as exc:
        log.warning("user push failed: %s", exc)
        return False


def notify_drivers_of_new_ride(db, ride) -> dict:
    """新订单 → 推送给所有在线且有 push_token 的司机。返回统计，不抛异常。"""
    from .models import Driver, User  # 避免循环导入

    drivers = (
        db.query(User)
        .filter(User.role.in_(("driver", "admin")))
        .filter(User.push_token.isnot(None))
        .all()
    )
    # 跳过挂了"休息中"的司机（没建档案的默认在线）
    profs = {d.user_id: d for d in db.query(Driver).all()} if drivers else {}
    drivers = [d for d in drivers
               if (p := profs.get(d.id)) is None or p.is_active == 1]
    tokens = [d.push_token for d in drivers if is_expo_push_token(d.push_token)]
    if not tokens:
        return {"sent": 0, "skipped": len(drivers), "reason": "no valid push tokens"}

    # 按司机语言分组，各发各的文案
    by_lang: dict[str, list[str]] = {"zh": [], "en": []}
    for d in drivers:
        if is_expo_push_token(d.push_token):
            by_lang[_lang_of(d)].append(d.push_token)
    bodies = {
        "zh": (
            "🚕 新订单",
            f"{ride.pickup_text} → {ride.dropoff_text}"
            + (f"（{ride.seats_needed} 位）" if ride.seats_needed and ride.seats_needed > 1 else ""),
        ),
        "en": (
            "🚕 New ride request",
            f"{ride.pickup_text} → {ride.dropoff_text}"
            + (f" ({ride.seats_needed} passengers)" if ride.seats_needed and ride.seats_needed > 1 else ""),
        ),
    }
    messages = []
    for lang, toks in by_lang.items():
        title, text = bodies[lang]
        for tok in toks:
            messages.append({
                "to": tok,
                "sound": "default",
                "title": title,
                "body": text,
                "data": {"ride_id": str(ride.id), "type": "new_ride"},
            })
    # 保持 token 顺序与 tickets 一一对应，用于清理死 token
    order = [t for toks in by_lang.values() for t in toks]
    tokens = order
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
