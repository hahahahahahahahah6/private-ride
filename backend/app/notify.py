"""订单状态变更邮件通知（Resend）。

乘客有邮箱时才发；发送失败永远不影响主流程（调用方包 try/except）。
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)


def _send(to_email: str, subject: str, text: str) -> None:
    import json
    import urllib.request

    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        return
    body = json.dumps({
        "from": os.getenv("EMAIL_FROM", "onboarding@resend.dev"),
        "to": [to_email],
        "subject": subject,
        "text": text,
    }).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "private-ride/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        json.load(resp)


def notify_status_change(to_email: str | None, status: str, pickup: str, dropoff: str) -> None:
    """司机接单/到达/完成时邮件通知乘客。无邮箱或发送失败时静默跳过。"""
    if not to_email:
        return
    subjects = {
        "accepted": "司机已接单",
        "arrived": "司机已到达上车点",
        "in_progress": "行程已开始",
        "completed": "行程已完成",
        "cancelled": "订单已取消",
    }
    subject = subjects.get(status)
    if not subject:
        return
    bodies = {
        "accepted": f"您的司机已接单，正在赶来。\n\n上车：{pickup}\n下车：{dropoff}\n\n司机稍后会与您联系。",
        "arrived": f"司机已到达上车点，请准备上车。\n\n上车：{pickup}\n下车：{dropoff}",
        "in_progress": f"行程已开始，祝您一路顺利。\n\n上车：{pickup}\n下车：{dropoff}",
        "completed": f"行程已完成，感谢乘坐私人专车。\n\n上车：{pickup}\n下车：{dropoff}",
        "cancelled": f"您的订单已取消。\n\n上车：{pickup}\n下车：{dropoff}\n\n如需重新叫车请再下一单。",
    }
    try:
        _send(to_email, f"私人专车：{subject}", bodies[status])
    except Exception as e:
        log.warning("notify email failed: %s", e)


def notify_driver_new_ride(pickup: str, dropoff: str, price_label: str,
                           passenger_contact: str | None) -> None:
    """新订单邮件通知司机（DRIVER_NOTIFY_EMAIL）。"""
    to_email = os.getenv("DRIVER_NOTIFY_EMAIL", "")
    if not to_email:
        return
    try:
        _send(
            to_email,
            "私人专车：有新订单",
            f"有新的叫车订单，请打开司机端查看接单。\n\n"
            f"上车：{pickup}\n下车：{dropoff}\n"
            f"价格：{price_label}\n"
            f"乘客联系：{passenger_contact or '（接单后可见）'}\n\n"
            f"https://ride.haocoach.com/web/driver.html",
        )
    except Exception as e:
        log.warning("driver notify failed: %s", e)
