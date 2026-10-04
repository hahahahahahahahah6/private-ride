"""Auth: v0.1 手机号 + 短信验证码登录，签发 token。

生产替换为真实短信（Twilio）时，只改 request_code 里发码的部分，
verify 的比对逻辑不变。
"""
from __future__ import annotations

import os
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuthToken, User

CODE_TTL_SECONDS = 600
TOKEN_TTL_DAYS = 30
MAX_VERIFY_ATTEMPTS = 5
REQUEST_CODE_INTERVAL_SECONDS = 60


def _dev_mode() -> bool:
    # Fail-closed: production must set DEV_MODE=0 explicitly; default is off.
    return os.getenv("DEV_MODE", "0") == "1"


# phone -> (code, expires_ts, failed_attempts, last_request_ts)
# NOTE: in-memory; single worker only (see deploy/private-ride.service).
# Move to DB with expires_at index when scaling past one worker.
_codes: dict[str, tuple[str, float, int, float]] = {}


def _new_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def request_code(phone: str) -> dict:
    now = time.time()
    saved = _codes.get(phone)
    if saved and now - saved[3] < REQUEST_CODE_INTERVAL_SECONDS:
        raise HTTPException(status_code=429, detail="请求太频繁，请稍后再试")
    code = _new_code()
    _codes[phone] = (code, now + CODE_TTL_SECONDS, 0, now)
    # TODO: send `code` via SMS (Twilio) here in production.
    out: dict = {"ok": True}
    if _dev_mode():
        out["dev_code"] = code  # 开发模式直接回显，生产关掉
    return out


def verify_code(phone: str, code: str, db: Session) -> tuple[User, str]:
    now = time.time()
    saved = _codes.get(phone)
    if not saved or saved[1] < now:
        _codes.pop(phone, None)
        raise HTTPException(status_code=401, detail="验证码错误或已过期")
    expected, _, failed, _ = saved
    if failed >= MAX_VERIFY_ATTEMPTS:
        _codes.pop(phone, None)
        raise HTTPException(status_code=401, detail="尝试次数过多，验证码已作废")
    if expected != code:
        _codes[phone] = (expected, saved[1], failed + 1, saved[3])
        raise HTTPException(status_code=401, detail="验证码错误或已过期")
    _codes.pop(phone, None)

    user = db.query(User).filter_by(phone=phone).first()
    if user is None:
        user = User(phone=phone, name="", role="passenger")
        db.add(user)
        db.commit()
        db.refresh(user)

    token = secrets.token_urlsafe(32)
    db.add(AuthToken(
        token=token,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=TOKEN_TTL_DAYS),
    ))
    db.commit()
    return user, token


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime) -> datetime:
    # Tolerate naive datetimes written by older versions (stored as UTC).
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少登录凭证")
    tok = db.get(AuthToken, authorization[7:])
    if tok is None or _as_aware(tok.expires_at) < _now():
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    user = db.get(User, tok.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


def require_driver(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("driver", "admin"):
        raise HTTPException(status_code=403, detail="仅司机可操作")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
