"""private-ride backend: auth + users + rides + web static hosting."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import auth
from .auth import get_current_user, require_driver
from .database import get_db, init_db
from .models import Ride, User
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

app = FastAPI(title="private-ride API", version="0.1.0")

# 里程计价：起步价 + 每英里单价（分）。调价只改这里。
MILEAGE_BASE_CENTS = 800   # $8 起步
MILEAGE_PER_MILE_CENTS = 300  # $3 / 英里


def _mileage_price_cents(miles: float) -> int:
    return MILEAGE_BASE_CENTS + round(MILEAGE_PER_MILE_CENTS * miles)

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"


@app.on_event("startup")
def _startup() -> None:
    init_db()


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
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    if db.query(User).filter_by(phone=payload.phone).first():
        raise HTTPException(status_code=409, detail="phone already registered")
    user = User(phone=payload.phone, name=payload.name, role=payload.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: uuid.UUID, db: Session = Depends(get_db)) -> User:
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

def _passenger_contact(db: Session, ride: Ride) -> str | None:
    passenger = db.get(User, ride.passenger_id)
    if passenger is None:
        return None
    phone = passenger.phone if not passenger.phone.startswith("email:") else None
    if passenger.email:
        return f"{phone} / {passenger.email}" if phone else passenger.email
    return phone


def _ride_out(ride: Ride, db: Session, viewer: User | None = None) -> Ride:
    # 乘客联系方式只给相关人看：乘客本人、接单司机、管理员
    # 待接单列表里不暴露，避免被所有司机看到
    if viewer is not None and (
        viewer.role == "admin"
        or ride.passenger_id == viewer.id
        or ride.driver_id == viewer.id
    ):
        ride.passenger_contact = _passenger_contact(db, ride)
    else:
        ride.passenger_contact = None
    return ride


@app.post("/rides", response_model=RideOut, status_code=201)
def create_ride(payload: RideCreate, user: User = Depends(get_current_user),
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
    )
    db.add(ride)
    db.commit()
    db.refresh(ride)
    # 推送给司机：失败不影响下单（push 模块内部已吞异常）
    try:
        from . import push as push_mod

        push_mod.notify_drivers_of_new_ride(db, ride)
    except Exception:
        pass
    return _ride_out(ride, db, user)


@app.get("/rides", response_model=list[RideOut])
def list_rides(mine: bool = Query(default=True), open: bool = Query(default=False),
               user: User = Depends(get_current_user),
               db: Session = Depends(get_db)) -> list[Ride]:
    q = db.query(Ride).order_by(Ride.created_at.desc())
    if open:
        if user.role not in ("driver", "admin"):
            raise HTTPException(status_code=403, detail="仅司机可查看待接单")
        return [_ride_out(r, db, user) for r in q.filter_by(status="requested").all()]
    if mine:
        if user.role in ("driver", "admin"):
            q = q.filter(Ride.driver_id == user.id)
        else:
            q = q.filter(Ride.passenger_id == user.id)
    return [_ride_out(r, db, user) for r in q.all()]


@app.post("/rides/{ride_id}/accept", response_model=RideOut)
def accept_ride(ride_id: uuid.UUID, driver: User = Depends(require_driver),
                db: Session = Depends(get_db)) -> Ride:
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
    ride.status = payload.status
    db.commit()
    db.refresh(ride)
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


# ---------- web static (mount last so API routes win) ----------

if WEB_DIR.is_dir():
    app.mount("/web", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
