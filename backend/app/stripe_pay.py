"""Stripe 线上付款：绑卡（SetupIntent）+ 行程完成时扣款（PaymentIntent）。

全部用标准库 urllib 调 Stripe API，不引入 SDK。
卡号等敏感信息只经过 Stripe.js，不进我们服务器（PCI 合规）。
"""
from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

log = logging.getLogger(__name__)

STRIPE_API = "https://api.stripe.com/v1"


class StripeError(Exception):
    pass


def _secret() -> str:
    key = os.getenv("STRIPE_SECRET_KEY", "")
    if not key:
        raise StripeError("Stripe 未配置")
    return key


def _configured() -> bool:
    return bool(os.getenv("STRIPE_SECRET_KEY"))


def _api(method: str, path: str, params: dict) -> dict:
    secret = _secret()
    creds = base64.b64encode(f"{secret}:".encode()).decode()
    data = urllib.parse.urlencode(params).encode() if params else None
    req = urllib.request.Request(
        STRIPE_API + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "private-ride/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            err = json.load(e).get("error", {})
            msg = err.get("message", str(e))
        except Exception:
            msg = str(e)
        raise StripeError(msg)
    except Exception as e:
        raise StripeError(str(e))


def publishable_key() -> str:
    return os.getenv("STRIPE_PUBLISHABLE_KEY", "")


def ensure_customer(existing_id: str | None, email: str | None = None) -> str:
    """有则复用，无则创建 Stripe Customer。返回 customer id。"""
    if existing_id:
        return existing_id
    params = {}
    if email:
        params["email"] = email
    cus = _api("POST", "/customers", params)
    return cus["id"]


def create_setup_intent(customer_id: str) -> str:
    """创建绑卡用的 SetupIntent，返回 client_secret 给前端 Stripe.js。"""
    si = _api("POST", "/setup_intents", {
        "customer": customer_id,
        "payment_method_types[]": "card",
        "usage": "off_session",
    })
    return si["client_secret"]


def get_payment_method(pm_id: str) -> dict:
    """读取 PaymentMethod 的卡品牌和后四位（绑卡成功后调用）。"""
    pm = _api("GET", f"/payment_methods/{pm_id}", {})
    card = pm.get("card", {})
    return {"brand": card.get("brand", ""), "last4": card.get("last4", "")}


def charge(customer_id: str, pm_id: str, amount_cents: int,
           description: str = "") -> dict:
    """off_session 扣款。返回 PaymentIntent 结果。"""
    pi = _api("POST", "/payment_intents", {
        "amount": str(amount_cents),
        "currency": "usd",
        "customer": customer_id,
        "payment_method": pm_id,
        "off_session": "true",
        "confirm": "true",
        "description": description[:200],
    })
    return pi
