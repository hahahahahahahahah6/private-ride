"""Pydantic schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ---------- users ----------

class UserCreate(BaseModel):
    phone: str = Field(min_length=7, max_length=32)
    name: str = Field(default="", max_length=64)
    role: str = Field(default="passenger", pattern="^(passenger|driver|admin)$")


class UserOut(BaseModel):
    id: uuid.UUID
    phone: str
    email: str | None = None
    name: str
    role: str
    # 绑卡信息（只返回品牌和后四位）
    card_brand: str | None = None
    card_last4: str | None = None

    model_config = {"from_attributes": True}


# ---------- auth ----------

class RequestCodeIn(BaseModel):
    phone: str | None = Field(default=None, min_length=7, max_length=32)
    email: str | None = Field(default=None, min_length=5, max_length=128)


class VerifyIn(BaseModel):
    phone: str | None = Field(default=None, min_length=7, max_length=32)
    email: str | None = Field(default=None, min_length=5, max_length=128)
    code: str = Field(min_length=4, max_length=8)


class TokenOut(BaseModel):
    token: str
    user: UserOut


class PushTokenIn(BaseModel):
    push_token: str = Field(min_length=1, max_length=128)


# ---------- rides ----------

RIDE_STATUSES = (
    "requested", "accepted", "en_route", "arrived",
    "in_progress", "completed", "cancelled",
)

# 合法状态推进
TRANSITIONS: dict[str, set[str]] = {
    "requested": {"accepted", "cancelled"},
    "accepted": {"en_route", "cancelled"},
    "en_route": {"arrived", "cancelled"},
    "arrived": {"in_progress", "cancelled"},
    "in_progress": {"completed"},
    "completed": set(),
    "cancelled": set(),
}


class RideCreate(BaseModel):
    pickup_text: str = Field(min_length=1, max_length=500)
    dropoff_text: str = Field(min_length=1, max_length=500)
    seats_needed: int = Field(default=1, ge=1, le=20)
    note: str = Field(default="", max_length=1000)
    scheduled_at: datetime | None = None
    # 价格：offer=乘客出价 / mileage=里程计价 / quote=司机报价
    price_mode: str = Field(default="offer", pattern="^(offer|mileage|quote)$")
    price_offer_cents: int | None = Field(default=None, ge=0)
    price_miles: float | None = Field(default=None, ge=0)
    # 付款：online=线上扣款 / offline=线下当面付
    pay_mode: str = Field(default="offline", pattern="^(online|offline)$")


class QuoteIn(BaseModel):
    price_quote_cents: int = Field(ge=0, description="司机报价（分）")


class QuoteConfirmIn(BaseModel):
    accept: bool = Field(description="乘客是否接受报价")


class RideStatusIn(BaseModel):
    status: str = Field(pattern="^(accepted|en_route|arrived|in_progress|completed|cancelled)$")


class RideOut(BaseModel):
    id: uuid.UUID
    passenger_id: uuid.UUID
    driver_id: uuid.UUID | None
    pickup_text: str
    dropoff_text: str
    seats_needed: int
    note: str
    status: str
    scheduled_at: datetime | None
    created_at: datetime
    # 乘客联系方式：仅乘客本人、接单司机、管理员可见
    passenger_contact: str | None = None
    # 价格
    price_mode: str = "offer"
    price_offer_cents: int | None = None
    price_miles: float | None = None
    price_quote_cents: int | None = None
    price_final_cents: int | None = None
    price_status: str = "pending"
    # 付款
    pay_mode: str = "offline"
    pay_status: str = "unpaid"

    model_config = {"from_attributes": True}
