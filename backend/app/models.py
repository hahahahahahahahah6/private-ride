"""Data models: users (passengers + drivers), driver profiles, rides."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR, TypeDecorator

from .database import Base


class GUID(TypeDecorator):
    """UUID that works on both SQLite (CHAR 36) and Postgres (native UUID)."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    phone: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True, default=None)
    name: Mapped[str] = mapped_column(String(64), default="")
    role: Mapped[str] = mapped_column(String(16), default="passenger")  # passenger|driver|admin
    push_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Driver(Base):
    __tablename__ = "drivers"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), primary_key=True)
    vehicle_model: Mapped[str] = mapped_column(String(64), default="")
    plate: Mapped[str] = mapped_column(String(16), default="")
    seats: Mapped[int] = mapped_column(Integer, default=6)
    is_active: Mapped[int] = mapped_column(Integer, default=1)  # 1 = 接单中


class Ride(Base):
    __tablename__ = "rides"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    passenger_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), index=True)
    driver_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    pickup_text: Mapped[str] = mapped_column(Text, default="")
    dropoff_text: Mapped[str] = mapped_column(Text, default="")
    seats_needed: Mapped[int] = mapped_column(Integer, default=1)
    note: Mapped[str] = mapped_column(Text, default="")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # requested → accepted → en_route → arrived → in_progress → completed | cancelled
    status: Mapped[str] = mapped_column(String(16), default="requested", index=True)
    # 价格：offer=乘客出价 / mileage=里程计价 / quote=司机报价
    price_mode: Mapped[str] = mapped_column(String(16), default="offer")
    price_offer_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_miles: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_quote_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_final_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # pending=待确认 / agreed=已确认 / rejected=已拒绝
    price_status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
