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
    return auth.request_code(payload.phone)


@app.post("/auth/verify", response_model=TokenOut)
def verify(payload: VerifyIn, db: Session = Depends(get_db)) -> dict:
    user, token = auth.verify_code(payload.phone, payload.code, db)
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

def _ride_out(ride: Ride) -> Ride:
    return ride


@app.post("/rides", response_model=RideOut, status_code=201)
def create_ride(payload: RideCreate, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)) -> Ride:
    ride = Ride(
        passenger_id=user.id,
        pickup_text=payload.pickup_text,
        dropoff_text=payload.dropoff_text,
        seats_needed=payload.seats_needed,
        note=payload.note,
        scheduled_at=payload.scheduled_at,
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
    return _ride_out(ride)


@app.get("/rides", response_model=list[RideOut])
def list_rides(mine: bool = Query(default=True), open: bool = Query(default=False),
               user: User = Depends(get_current_user),
               db: Session = Depends(get_db)) -> list[Ride]:
    q = db.query(Ride).order_by(Ride.created_at.desc())
    if open:
        if user.role not in ("driver", "admin"):
            raise HTTPException(status_code=403, detail="仅司机可查看待接单")
        return [_ride_out(r) for r in q.filter_by(status="requested").all()]
    if mine:
        if user.role in ("driver", "admin"):
            q = q.filter(Ride.driver_id == user.id)
        else:
            q = q.filter(Ride.passenger_id == user.id)
    return [_ride_out(r) for r in q.all()]


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
    return _ride_out(db.get(Ride, ride_id))


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
    return _ride_out(ride)


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
    return _ride_out(ride)


# ---------- web static (mount last so API routes win) ----------

if WEB_DIR.is_dir():
    app.mount("/web", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
