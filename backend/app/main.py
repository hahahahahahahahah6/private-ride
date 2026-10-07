"""private-ride backend: auth + users + rides + web static hosting."""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import auth
from .auth import get_current_user, require_driver
from .database import get_db, init_db
from .models import InviteCode, Ride, User
from .schemas import (
    PushTokenIn,
    QuoteConfirmIn,
    QuoteIn,
    RequestCodeIn,
    RideCreate,
    RideOut,
    RideStatusIn,
    TokenOut,
    TRANSITIONS,
    UserCreate,
    UserOut,
    VerifyIn,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="private-ride API", version="0.1.0", lifespan=lifespan)

log = logging.getLogger(__name__)

# 里程计价：起步价 + 每英里单价（分）。调价只改这里。
MILEAGE_BASE_CENTS = 800   # $8 起步
MILEAGE_PER_MILE_CENTS = 300  # $3 / 英里


def _mileage_price_cents(miles: float) -> int:
    return MILEAGE_BASE_CENTS + round(MILEAGE_PER_MILE_CENTS * miles)

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"


# ---------- meta ----------

@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "private-ride", "version": "0.1.0"}


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/web/")


# ---------- auth ----------

@app.post("/auth/request-code")
def request_code(payload: RequestCodeIn) -> dict:
    return auth.request_code(phone=payload.phone, email=payload.email)


@app.post("/auth/verify", response_model=TokenOut)
def verify(payload: VerifyIn, db: Session = Depends(get_db)) -> dict:
    user, token = auth.verify_code(phone=payload.phone, email=payload.email, code=payload.code, db=db)
    return {"token": token, "user": user}


@app.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@app.put("/me/push-token")
def set_push_token(payload: PushTokenIn, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> dict:
    user.push_token = payload.push_token
    db.commit()
    return {"ok": True}


# ---------- users (admin/seed 用；App 内走 /auth) ----------

@app.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate,
                _admin: User = Depends(auth.require_admin),
                db: Session = Depends(get_db)) -> User:
    if db.query(User).filter_by(phone=payload.phone).first():
        raise HTTPException(status_code=409, detail="phone already registered")
    user = User(phone=payload.phone, name=payload.name, role=payload.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: uuid.UUID,
             _admin: User = Depends(auth.require_admin),
             db: Session = Depends(get_db)) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user


class RoleIn(BaseModel):
    role: str


@app.patch("/users/{user_id}/role", response_model=UserOut)
def set_user_role(user_id: uuid.UUID, payload: RoleIn,
                  _admin: User = Depends(auth.require_admin),
                  db: Session = Depends(get_db)) -> User:
    if payload.role not in ("passenger", "driver", "admin"):
        raise HTTPException(status_code=400, detail="role 非法")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user


# ---------- rides ----------

def _format_contact(passenger: User | None) -> str | None:
    if passenger is None:
        return None
    phone = passenger.phone if not passenger.phone.startswith("email:") else None
    if passenger.email:
        return f"{phone} / {passenger.email}" if phone else passenger.email
    return phone


def _ride_out(ride: Ride, db: Session, viewer: User | None = None,
              pmap: dict | None = None) -> Ride:
    # 乘客联系方式只给相关人看：乘客本人、接单司机、管理员
    # 待接单列表里不暴露；已完成/已取消的订单不再显示（隐私）
    # pmap：批量预加载的 passenger 映射，避免列表页 N+1 查询
    if (
        viewer is not None
        and ride.status not in ("completed", "cancelled")
        and (
            viewer.role == "admin"
            or ride.passenger_id == viewer.id
            or ride.driver_id == viewer.id
        )
    ):
        passenger = pmap.get(ride.passenger_id) if pmap is not None else db.get(User, ride.passenger_id)
        ride.passenger_contact = _format_contact(passenger)
    else:
        ride.passenger_contact = None
    return ride


def _notify_new_ride_bg(ride_id: uuid.UUID) -> None:
    """后台发新订单通知（Expo push + 邮件），用独立 session，不阻塞下单响应。"""
    from .database import SessionLocal

    db = SessionLocal()
    try:
        ride = db.get(Ride, ride_id)
        if ride is None:
            return
        try:
            from . import push as push_mod

            push_mod.notify_drivers_of_new_ride(db, ride)
        except Exception:
            log.warning("bg push failed for ride %s", ride_id, exc_info=True)
        try:
            from . import notify as notify_mod

            price_label = (
                f"${ride.price_final_cents / 100:.2f}"
                if ride.price_final_cents else "待定"
            )
            notify_mod.notify_driver_new_ride(
                ride.pickup_text, ride.dropoff_text, price_label, None)
        except Exception:
            log.warning("bg email failed for ride %s", ride_id, exc_info=True)
    finally:
        db.close()


@app.post("/rides", response_model=RideOut, status_code=201)
def create_ride(payload: RideCreate, background_tasks: BackgroundTasks,
                user: User = Depends(get_current_user),
                db: Session = Depends(get_db)) -> Ride:
    # 按计价方式校验必填项并算出初始成交价
    offer_cents = payload.price_offer_cents
    miles = payload.price_miles
    final_cents: int | None = None
    if payload.price_mode == "offer":
        if offer_cents is None:
            raise HTTPException(status_code=400, detail="出价模式请填写价格")
        final_cents = offer_cents
    elif payload.price_mode == "mileage":
        if miles is None:
            raise HTTPException(status_code=400, detail="里程计价请填写预估里程")
        final_cents = _mileage_price_cents(miles)
    # quote 模式：等司机报价，final 先空着
    ride = Ride(
        passenger_id=user.id,
        pickup_text=payload.pickup_text,
        dropoff_text=payload.dropoff_text,
        seats_needed=payload.seats_needed,
        note=payload.note,
        scheduled_at=payload.scheduled_at,
        price_mode=payload.price_mode,
        price_offer_cents=offer_cents,
        price_miles=miles,
        price_final_cents=final_cents,
        price_status="agreed" if final_cents is not None else "pending",
        pay_mode=payload.pay_mode,
    )
    db.add(ride)
    db.commit()
    db.refresh(ride)
    # 新订单通知走后台任务：Expo push 最长 8s、邮件最长 20s，不能阻塞下单响应
    background_tasks.add_task(_notify_new_ride_bg, ride.id)
    return _ride_out(ride, db, user)


@app.get("/rides", response_model=list[RideOut])
def list_rides(mine: bool = Query(default=True), open: bool = Query(default=False),
               limit: int = Query(default=50, ge=1, le=200),
               offset: int = Query(default=0, ge=0),
               user: User = Depends(get_current_user),
               db: Session = Depends(get_db)) -> list[Ride]:
    q = db.query(Ride).order_by(Ride.created_at.desc())
    if open:
        if user.role not in ("driver", "admin"):
            raise HTTPException(status_code=403, detail="仅司机可查看待接单")
        rides = q.filter_by(status="requested").limit(limit).offset(offset).all()
        return [_ride_out(r, db, user) for r in rides]
    if mine:
        if user.role in ("driver", "admin"):
            # 司机视角：按预约时间正序（临近的在前），无预约时间的沉底
            q = q.filter(Ride.driver_id == user.id).order_by(
                None).order_by(Ride.scheduled_at.is_(None), Ride.scheduled_at.asc())
        else:
            q = q.filter(Ride.passenger_id == user.id)
    rides = q.limit(limit).offset(offset).all()
    # 批量预加载乘客，避免每单一次查询（N+1）
    pmap = None
    if rides:
        pax_ids = {r.passenger_id for r in rides}
        pmap = {u.id: u for u in db.query(User).filter(User.id.in_(pax_ids)).all()}
    return [_ride_out(r, db, user, pmap) for r in rides]


@app.post("/rides/{ride_id}/accept", response_model=RideOut)
def accept_ride(ride_id: uuid.UUID, driver: User = Depends(require_driver),
                db: Session = Depends(get_db)) -> Ride:
    # 先取到这单，判断时间冲突
    ride = db.get(Ride, ride_id)
    if ride is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    if ride.status != "requested":
        raise HTTPException(status_code=409, detail="订单已被接走")

    # 时间冲突检查：只拦真正撞时间的，不拦预约排队
    # - 都有预约时间：前后 90 分钟内算冲突
    # - 新单是即时单（无预约时间）：司机正在路上（en_route/arrived/in_progress）时不接
    others = (
        db.query(Ride)
        .filter(
            Ride.driver_id == driver.id,
            Ride.status.in_(["accepted", "en_route", "arrived", "in_progress"]),
            Ride.id != ride_id,
        )
        .all()
    )
    if ride.scheduled_at is not None:
        for o in others:
            if o.scheduled_at is None:
                continue
            delta = abs((ride.scheduled_at - o.scheduled_at).total_seconds())
            if delta < 90 * 60:
                raise HTTPException(
                    status_code=409,
                    detail=f"时间冲突：您已接了 {o.scheduled_at.strftime('%m-%d %H:%M')} 的单（{o.pickup_text}→{o.dropoff_text}）",
                )
    else:
        busy = [o for o in others if o.status in ("en_route", "arrived", "in_progress")]
        if busy:
            raise HTTPException(
                status_code=409,
                detail="您正在服务另一单，请完成后再接即时单",
            )
    # 原子抢单：只有 status=requested 的才能被更新，防止两人同时抢到
    rows = (
        db.query(Ride)
        .filter(Ride.id == ride_id, Ride.status == "requested")
        .update({"driver_id": driver.id, "status": "accepted"},
                synchronize_session=False)
    )
    db.commit()
    if rows == 0:
        raise HTTPException(status_code=409, detail="该订单已被接走或不存在")
    ride = db.get(Ride, ride_id)
    # 邮件通知乘客：失败不影响接单
    try:
        from . import notify as notify_mod
        passenger = db.get(User, ride.passenger_id)
        notify_mod.notify_status_change(
            passenger.email if passenger else None,
            "accepted", ride.pickup_text, ride.dropoff_text)
    except Exception:
        pass
    return _ride_out(ride, db, driver)


@app.post("/rides/{ride_id}/quote", response_model=RideOut)
def quote_ride(ride_id: uuid.UUID, payload: QuoteIn,
               driver: User = Depends(require_driver),
               db: Session = Depends(get_db)) -> Ride:
    """司机报价（仅 quote 模式，已接单未确认时可报）。"""
    ride = db.get(Ride, ride_id)
    if ride is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    if ride.driver_id != driver.id and driver.role != "admin":
        raise HTTPException(status_code=403, detail="只能操作自己的订单")
    if ride.price_mode != "quote":
        raise HTTPException(status_code=400, detail="该订单不是司机报价模式")
    if ride.status not in ("accepted", "en_route"):
        raise HTTPException(status_code=400, detail="当前状态不能报价")
    ride.price_quote_cents = payload.price_quote_cents
    ride.price_status = "pending"
    db.commit()
    db.refresh(ride)
    # 邮件通知乘客去确认报价
    try:
        from . import notify as notify_mod
        passenger = db.get(User, ride.passenger_id)
        if passenger and passenger.email:
            notify_mod._send(
                passenger.email,
                "私人专车：司机已报价",
                f"司机对您的订单报出了价格：${payload.price_quote_cents / 100:.2f}\n\n"
                f"上车：{ride.pickup_text}\n下车：{ride.dropoff_text}\n\n"
                f"请打开 App 确认或拒绝这个报价。",
            )
    except Exception:
        pass
    return _ride_out(ride, db, driver)


@app.post("/rides/{ride_id}/quote/confirm", response_model=RideOut)
def confirm_quote(ride_id: uuid.UUID, payload: QuoteConfirmIn,
                  user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)) -> Ride:
    """乘客确认/拒绝司机报价。拒绝后订单回到待接单，司机可重新报价。"""
    ride = db.get(Ride, ride_id)
    if ride is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    if ride.passenger_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="只有乘客能确认报价")
    if ride.price_mode != "quote" or ride.price_quote_cents is None:
        raise HTTPException(status_code=400, detail="当前没有待确认的报价")
    if ride.price_status != "pending":
        raise HTTPException(status_code=400, detail="报价已处理过")
    if payload.accept:
        ride.price_status = "agreed"
        ride.price_final_cents = ride.price_quote_cents
    else:
        # 拒绝：回到待接单，司机重新接单报价
        ride.price_status = "rejected"
        ride.price_quote_cents = None
        ride.driver_id = None
        ride.status = "requested"
    db.commit()
    db.refresh(ride)
    return _ride_out(ride, db, user)


@app.post("/rides/{ride_id}/status", response_model=RideOut)
def advance_status(ride_id: uuid.UUID, payload: RideStatusIn,
                   driver: User = Depends(require_driver),
                   db: Session = Depends(get_db)) -> Ride:
    ride = db.get(Ride, ride_id)
    if ride is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    if ride.driver_id != driver.id and driver.role != "admin":
        raise HTTPException(status_code=403, detail="只能操作自己的订单")
    if payload.status not in TRANSITIONS.get(ride.status, set()):
        raise HTTPException(
            status_code=400,
            detail=f"不能从 {ride.status} 直接到 {payload.status}",
        )
    # 出发前检查：同一时间只能有一单在路上（en_route/arrived/in_progress）
    if payload.status == "en_route":
        other_active = (
            db.query(Ride)
            .filter(
                Ride.driver_id == driver.id,
                Ride.id != ride.id,
                Ride.status.in_(["en_route", "arrived", "in_progress"]),
            )
            .first()
        )
        if other_active is not None:
            raise HTTPException(
                status_code=409,
                detail=f"您还有一单正在进行（{other_active.pickup_text}→{other_active.dropoff_text}），请先完成",
            )
    ride.status = payload.status
    db.commit()
    db.refresh(ride)
    # 行程完成：线上付款自动扣款（失败不阻塞）
    if payload.status == "completed":
        try:
            _try_charge_ride(db, ride)
        except Exception:
            pass
    # 邮件通知乘客：失败不影响状态流转
    try:
        from . import notify as notify_mod
        passenger = db.get(User, ride.passenger_id)
        notify_mod.notify_status_change(
            passenger.email if passenger else None,
            payload.status, ride.pickup_text, ride.dropoff_text)
    except Exception:
        pass
    return _ride_out(ride, db, driver)


@app.post("/rides/{ride_id}/cancel", response_model=RideOut)
def cancel_ride(ride_id: uuid.UUID, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)) -> Ride:
    ride = db.get(Ride, ride_id)
    if ride is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    is_owner = ride.passenger_id == user.id
    is_driver = ride.driver_id == user.id
    if not (is_owner or is_driver or user.role == "admin"):
        raise HTTPException(status_code=403, detail="无权取消此订单")
    if ride.status not in ("requested", "accepted", "en_route", "arrived"):
        raise HTTPException(status_code=400, detail=f"{ride.status} 状态不可取消")
    ride.status = "cancelled"
    db.commit()
    db.refresh(ride)
    # 邮件通知乘客：失败不影响取消
    try:
        from . import notify as notify_mod
        passenger = db.get(User, ride.passenger_id)
        notify_mod.notify_status_change(
            passenger.email if passenger else None,
            "cancelled", ride.pickup_text, ride.dropoff_text)
    except Exception:
        pass
    return _ride_out(ride, db, user)


# ---------- 付款（Stripe 线上 / 线下当面） ----------

@app.get("/pay/config")
def pay_config() -> dict:
    from . import stripe_pay as sp
    return {"publishable_key": sp.publishable_key(), "configured": sp._configured()}


@app.post("/pay/setup-intent")
def pay_setup_intent(user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)) -> dict:
    """绑卡第一步：拿 client_secret 给前端 Stripe.js 确认卡片。"""
    from . import stripe_pay as sp
    try:
        customer_id = sp.ensure_customer(user.stripe_customer_id, user.email)
        if user.stripe_customer_id != customer_id:
            user.stripe_customer_id = customer_id
            db.commit()
        client_secret = sp.create_setup_intent(customer_id)
        return {"client_secret": client_secret}
    except sp.StripeError as e:
        raise HTTPException(status_code=502, detail=str(e))


class AttachCardIn(BaseModel):
    payment_method_id: str


class InviteCreateOut(BaseModel):
    code: str


class InviteRedeemIn(BaseModel):
    code: str


@app.post("/pay/attach")
def pay_attach(payload: AttachCardIn, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)) -> dict:
    """绑卡第二步：前端 Stripe.js 确认成功后，把卡存到用户名下。"""
    from . import stripe_pay as sp
    try:
        info = sp.get_payment_method(payload.payment_method_id)
        user.stripe_pm_id = payload.payment_method_id
        user.card_brand = info["brand"]
        user.card_last4 = info["last4"]
        if not user.stripe_customer_id:
            user.stripe_customer_id = sp.ensure_customer(None, user.email)
        db.commit()
        return {"ok": True, "brand": info["brand"], "last4": info["last4"]}
    except sp.StripeError as e:
        raise HTTPException(status_code=502, detail=str(e))


def _try_charge_ride(db: Session, ride: Ride) -> None:
    """行程完成时线上扣款。失败只记日志，不阻塞完成状态。"""
    if ride.pay_mode != "online" or ride.price_final_cents is None:
        return
    from . import stripe_pay as sp
    passenger = db.get(User, ride.passenger_id)
    if not passenger or not passenger.stripe_pm_id or not passenger.stripe_customer_id:
        log.warning("ride %s online pay but no card bound", ride.id)
        return
    try:
        pi = sp.charge(
            passenger.stripe_customer_id, passenger.stripe_pm_id,
            ride.price_final_cents,
            f"私人专车 {ride.pickup_text} → {ride.dropoff_text}",
        )
        ride.stripe_pi_id = pi.get("id")
        ride.pay_status = "paid" if pi.get("status") == "succeeded" else "failed"
        db.commit()
    except Exception as e:
        log.warning("stripe charge failed for ride %s: %s", ride.id, e)
        ride.pay_status = "failed"
        db.commit()


# ---------- 司机邀请码 ----------

_redeem_attempts: dict[str, list[float]] = {}


def _new_invite_code() -> str:
    import secrets
    import string
    alphabet = string.ascii_uppercase + string.digits
    # 去掉易混淆的 0/O/1/I
    alphabet = alphabet.replace("0", "").replace("O", "").replace("1", "").replace("I", "")
    return "".join(secrets.choice(alphabet) for _ in range(8))


@app.post("/invites", response_model=InviteCreateOut)
def create_invite(admin: User = Depends(auth.require_admin),
                  db: Session = Depends(get_db)) -> dict:
    """管理员生成司机邀请码。"""
    for _ in range(5):
        code = _new_invite_code()
        if db.get(InviteCode, code) is None:
            db.add(InviteCode(code=code, role="driver", created_by=admin.id))
            db.commit()
            return {"code": code}
    raise HTTPException(status_code=500, detail="生成失败，请重试")


@app.post("/invites/redeem", response_model=UserOut)
def redeem_invite(payload: InviteRedeemIn,
                  user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)) -> User:
    """用邀请码升级为司机。防暴力猜：每用户每小时最多 10 次。"""
    import time

    now = time.time()
    key = f"redeem:{user.id}"
    attempts = _redeem_attempts.get(key, [])
    attempts = [t for t in attempts if now - t < 3600]
    if len(attempts) >= 10:
        raise HTTPException(status_code=429, detail="尝试太频繁，请一小时后再试")
    attempts.append(now)
    _redeem_attempts[key] = attempts
    # 防止长期运行内存膨胀：key 太多时丢掉最久没动过的
    if len(_redeem_attempts) > 2000:
        for k in sorted(_redeem_attempts,
                        key=lambda k: _redeem_attempts[k][-1] if _redeem_attempts[k] else 0)[:1000]:
            del _redeem_attempts[k]

    code = payload.code.strip().upper()
    inv = db.get(InviteCode, code)
    if inv is None:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    if inv.used_by is not None:
        raise HTTPException(status_code=409, detail="邀请码已被使用")
    inv.used_by = user.id
    inv.used_at = datetime.now(timezone.utc)
    user.role = inv.role
    db.commit()
    db.refresh(user)
    return user


# ---------- web static (mount last so API routes win) ----------

if WEB_DIR.is_dir():
    app.mount("/web", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
