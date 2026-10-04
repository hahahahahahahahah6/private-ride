"""Auth: v0.1 手机号 + 测试验证码登录，签发 token。

生产替换为真实短信（Twilio）时，只改 request_code 里发码的部分，
verify 的比对逻辑不变。
"""
from __future__ import annotations

import os
import secrets
import time
from datetime import datetime, timedelta

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuthToken, User

# 开发/测试验证码（生产必须换成真短信 + 关掉 dev_code 回显）
DEV_TEST_CODE = os.getenv("DEV_TEST_CODE", "123456")
CODE_TTL_SECONDS = 600
TOKEN_TTL_DAYS = 30

_codes: dict[str, tuple[str, float]] = {}  # phone -> (code, expires_ts)


def request_code(phone: str) -> dict:
    _codes[phone] = (DEV_TEST_CODE, time.time() + CODE_TTL_SECONDS)
    out: dict = {"ok": True}
    if os.getenv("DEV_MODE", "1") == "1":
        out["dev_code"] = DEV_TEST_CODE  # 开发模式直接回显，生产关掉
    return out


def verify_code(phone: str, code: str, db: Session) -> tuple[User, str]:
    saved = _codes.get(phone)
    if not saved or saved[1] < time.time() or saved[0] != code:
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
        expires_at=datetime.utcnow() + timedelta(days=TOKEN_TTL_DAYS),
    ))
    db.commit()
    return user, token


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少登录凭证")
    tok = db.get(AuthToken, authorization[7:])
    if tok is None or tok.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    user = db.get(User, tok.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


def require_driver(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("driver", "admin"):
        raise HTTPException(status_code=403, detail="仅司机可操作")
    return user
