"""Auth: v0.3 手机号 + 短信验证码 / 邮箱 + 邮件验证码登录，签发 token。

短信验证码走 Twilio Verify API；邮箱验证码走 Resend HTTPS API。
开发模式（DEV_MODE=1 且未配 Twilio/Resend）回退到内存验证码。
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


# --- 开发模式内存验证码（仅 DEV_MODE=1 且未配置 Twilio 时用） ---
# phone -> (code, expires_ts, failed_attempts, last_request_ts)
_codes: dict[str, tuple[str, float, int, float]] = {}


def _new_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def _twilio_basic() -> tuple[str, str] | None:
    """(username, password) for Twilio API basic auth, or None."""
    sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    key_sid = os.getenv("TWILIO_API_KEY_SID", "")
    key_secret = os.getenv("TWILIO_API_KEY_SECRET", "")
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    if not sid:
        return None
    if key_sid and key_secret:
        return (key_sid, key_secret)  # API Key 优先，权限最小
    if token:
        return (sid, token)
    return None


def _verify_service_sid() -> str:
    return os.getenv("TWILIO_VERIFY_SERVICE_SID", "")


def _twilio_verify_configured() -> bool:
    return bool(_twilio_basic() and _verify_service_sid())


def _twilio_post(host: str, path: str, params: dict[str, str]) -> dict:
    """stdlib-only POST to a Twilio API.

    Raises _TwilioAPIError (carries the HTTP status) on failure,
    so callers can map 4xx (wrong code etc.) vs 5xx/network properly.
    """
    import base64
    import json
    import urllib.error
    import urllib.parse
    import urllib.request

    basic = _twilio_basic()
    assert basic is not None
    creds = base64.b64encode(f"{basic[0]}:{basic[1]}".encode()).decode()
    req = urllib.request.Request(
        f"https://{host}{path}",
        data=urllib.parse.urlencode(params).encode(),
        method="POST",
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            msg = json.load(e).get("message", "")
        except Exception:
            msg = ""
        raise _TwilioAPIError(e.code, msg or str(e))
    except Exception as e:
        raise _TwilioAPIError(0, str(e))


class _TwilioAPIError(Exception):
    def __init__(self, http_status: int, message: str):
        super().__init__(message)
        self.http_status = http_status
        self.message = message


def _normalize_phone(phone: str) -> str:
    """转成 E.164：10 位美国号自动加 +1；其余原样丢给 Twilio 校验。"""
    p = phone.strip().replace(" ", "").replace("-", "")
    if p.startswith("+"):
        return p
    if len(p) == 10 and p.isdigit():
        return "+1" + p
    if len(p) == 11 and p.startswith("1") and p.isdigit():
        return "+" + p
    return p


# identifier -> last request timestamp（保护短信/邮件额度）
_last_request: dict[str, float] = {}


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _resend_configured() -> bool:
    return bool(os.getenv("RESEND_API_KEY"))


def _send_email_otp(to_email: str, code: str) -> None:
    """Resend HTTPS API 发邮件验证码。失败抛 HTTPException。"""
    import json
    import urllib.error
    import urllib.request

    api_key = os.getenv("RESEND_API_KEY", "")
    sender = os.getenv("EMAIL_FROM", "onboarding@resend.dev")
    body = json.dumps({
        "from": sender,
        "to": [to_email],
        "subject": "您的登录验证码",
        "text": (
            f"您的私人专车登录验证码是 {code}，10 分钟内有效。\n\n"
            f"如果不是您本人操作，请忽略这封邮件。"
        ),
    }).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # Resend 前面有 Cloudflare，大块头的默认 UA 会被 1010 拦截
            "User-Agent": "private-ride/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            detail = json.load(e).get("message", "")
        except Exception:
            detail = ""
        # 不把上游原始异常细节直接丢给客户端
        raise HTTPException(status_code=502, detail=f"邮件发送失败（{detail or e.code}）")
    except Exception:
        raise HTTPException(status_code=502, detail="邮件发送失败，请稍后再试")


def _resolve_identifier(phone: str | None, email: str | None) -> tuple[str, str]:
    """返回 (kind, identifier)；kind 为 "phone" 或 "email"。"""
    if phone and email:
        raise HTTPException(status_code=400, detail="请只提供手机号或邮箱中的一种")
    if email:
        return ("email", _normalize_email(email))
    if phone:
        return ("phone", _normalize_phone(phone))
    raise HTTPException(status_code=400, detail="请提供手机号或邮箱")


def request_code(phone: str | None = None, email: str | None = None) -> dict:
    kind, ident = _resolve_identifier(phone, email)
    now = time.time()
    last = _last_request.get(ident, 0)
    if now - last < REQUEST_CODE_INTERVAL_SECONDS:
        raise HTTPException(status_code=429, detail="请求太频繁，请稍后再试")
    _last_request[ident] = now
    # 防止长期运行内存膨胀：超量时丢掉最旧的记录
    if len(_last_request) > 5000:
        cutoff = now - 3600
        for k in [k for k, t in _last_request.items() if t < cutoff]:
            del _last_request[k]

    if kind == "phone" and _twilio_verify_configured():
        try:
            _twilio_post(
                "verify.twilio.com",
                f"/v2/Services/{_verify_service_sid()}/Verifications",
                {"To": ident, "Channel": "sms"},
            )
        except _TwilioAPIError as e:
            raise HTTPException(status_code=502, detail=f"短信发送失败：{e.message}")
        return {"ok": True}

    if kind == "email" and _resend_configured():
        code = _new_code()
        _codes[ident] = (code, now + CODE_TTL_SECONDS, 0, now)
        try:
            _send_email_otp(ident, code)
        except Exception:
            # 邮件没发出去：删掉刚生成的验证码，别留下用户收不到的码
            _codes.pop(ident, None)
            raise
        # TODO-TEST: 临时回显验证码用于自测，验证完立即删掉
        return {"ok": True}

    if _dev_mode():
        code = _new_code()
        _codes[ident] = (code, now + CODE_TTL_SECONDS, 0, now)
        return {"ok": True, "dev_code": code}  # 开发模式直接回显，生产关掉

    raise HTTPException(status_code=503, detail="短信/邮件服务未配置")


def _verify_code_dev(phone: str, code: str) -> bool:
    now = time.time()
    saved = _codes.get(phone)
    if not saved or saved[1] < now:
        _codes.pop(phone, None)
        return False
    expected, _, failed, _ = saved
    if failed >= MAX_VERIFY_ATTEMPTS:
        _codes.pop(phone, None)
        return False
    if expected != code:
        _codes[phone] = (expected, saved[1], failed + 1, saved[3])
        return False
    _codes.pop(phone, None)
    return True


def verify_code(
    *, phone: str | None = None, email: str | None = None, code: str = "", db: Session
) -> tuple[User, str]:
    kind, ident = _resolve_identifier(phone, email)
    code = code.strip()
    if kind == "phone" and _twilio_verify_configured():
        try:
            result = _twilio_post(
                "verify.twilio.com",
                f"/v2/Services/{_verify_service_sid()}/VerificationCheck",
                {"To": ident, "Code": code},
            )
        except _TwilioAPIError as e:
            if 400 <= e.http_status < 500:
                # 404/400: 验证码错误、过期或已失效 → 401，不是什么系统故障
                raise HTTPException(status_code=401, detail="验证码错误或已过期")
            raise HTTPException(status_code=502, detail=f"短信服务异常：{e.message}")
        if result.get("status") != "approved":
            raise HTTPException(status_code=401, detail="验证码错误或已过期")
    elif _dev_mode() or (kind == "email" and _resend_configured()):
        # 邮箱验证码走内存校验（Twilio 只管短信）；开发模式同理
        if not _verify_code_dev(ident, code):
            raise HTTPException(status_code=401, detail="验证码错误或已过期")
    else:
        raise HTTPException(status_code=503, detail="短信服务未配置")

    if kind == "phone":
        user = db.query(User).filter_by(phone=ident).first()
    else:
        user = db.query(User).filter_by(email=ident).first()
    if user is None:
        user = User(
            phone=ident if kind == "phone" else f"email:{ident}",
            email=ident if kind == "email" else None,
            name="",
            role="passenger",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif kind == "email" and not user.email:
        user.email = ident
        db.commit()

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
