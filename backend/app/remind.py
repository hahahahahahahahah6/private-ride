"""预约行程提醒：每 15 分钟跑一次（cron），找出接下来 15~45 分钟内
要出发的预约单，发推送/邮件提醒司机和乘客。提醒过一次就不再发。
"""
import logging
from datetime import datetime, timedelta, timezone

log = logging.getLogger("remind")

# 提醒窗口：预约时间在 [现在, 现在+40分钟] 内的单
REMIND_BEFORE_MIN = 40


def _fmt_time(dt) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone()
    return local.strftime("%m-%d %H:%M")


def sweep(db) -> dict:
    """扫一次预约单，返回 {reminded: n}。不抛异常（cron 场景吞掉错误只记日志）。"""
    from .models import Ride, User
    from . import push as push_mod
    from . import notify as notify_mod

    now = datetime.now(timezone.utc)
    deadline = now + timedelta(minutes=REMIND_BEFORE_MIN)
    # SQLite 存的 naive UTC；保险起见同时按 naive 比
    rides = (
        db.query(Ride)
        .filter(Ride.status.in_(("requested", "accepted")),
                Ride.reminder_sent == 0,
                Ride.scheduled_at.isnot(None),
                Ride.scheduled_at <= deadline,
                Ride.scheduled_at >= now - timedelta(minutes=30))
        .all()
    )
    reminded = 0
    for ride in rides:
        try:
            when = _fmt_time(ride.scheduled_at)
            text = f"{ride.pickup_text} → {ride.dropoff_text}（{when}）"
            # 提醒司机：已接单就只推给该司机，否则推给所有在线司机
            if ride.driver_id:
                drv = db.get(User, ride.driver_id)
                tokens = [drv.push_token] if drv and drv.push_token else []
            else:
                drivers = (
                    db.query(User)
                    .filter(User.role.in_(("driver", "admin")),
                            User.push_token.isnot(None))
                    .all()
                )
                tokens = [d.push_token for d in drivers]
            tokens = [t for t in tokens if push_mod.is_expo_push_token(t)]
            if tokens:
                push_mod.send_expo_push([{
                    "to": t,
                    "title": "⏰ 预约行程提醒",
                    "body": f"半小时内要出发：{text}",
                    "sound": "default",
                } for t in tokens])
            # 提醒乘客：发邮件
            pax = db.get(User, ride.passenger_id)
            if pax and pax.email:
                notify_mod._send(
                    pax.email, "预约行程提醒",
                    f"您预约的行程（{when}）即将开始：{ride.pickup_text} → {ride.dropoff_text}。"
                    + (f" 司机已接单。" if ride.driver_id else " 司机暂未接单，请留意。"),
                )
            ride.reminder_sent = 1
            reminded += 1
        except Exception:
            log.warning("remind failed for ride %s", ride.id, exc_info=True)
    db.commit()
    return {"reminded": reminded}


def main() -> None:
    import argparse
    from .database import SessionLocal

    ap = argparse.ArgumentParser(description="预约行程提醒扫单")
    ap.add_argument("--dry-run", action="store_true", help="只列出将要提醒的单，不发")
    args = ap.parse_args()
    db = SessionLocal()
    try:
        if args.dry_run:
            now = datetime.now(timezone.utc)
            from .models import Ride
            rides = (
                db.query(Ride)
                .filter(Ride.status.in_(("requested", "accepted")),
                        Ride.reminder_sent == 0,
                        Ride.scheduled_at.isnot(None),
                        Ride.scheduled_at <= now + timedelta(minutes=REMIND_BEFORE_MIN),
                        Ride.scheduled_at >= now - timedelta(minutes=30))
                .all()
            )
            print(f"dry-run: {len(rides)} ride(s) would be reminded")
            for r in rides:
                print(f"  {r.id} {r.status} scheduled={r.scheduled_at} {r.pickup_text}")
        else:
            res = sweep(db)
            print(res)
    finally:
        db.close()


if __name__ == "__main__":
    main()
