# private-ride

A private ride-hailing app for a small circle: drivers (family + friends) and passengers (regulars). A shared FastAPI backend serves both the web client and the Expo mobile app. First version has no in-app payments — passengers pay drivers directly (cash / Zelle / WeChat).

**Bilingual (中文/EN)** — web, mobile app, push notifications and emails all support Chinese and English, with a language toggle and per-user language preference.

## Layout

```
private-ride/
  PLAN.md            Technical plan (Chinese; MVP scope, stack, data model, store checklists)
  backend/           FastAPI: auth, ride booking, driver accept, status machine, push tokens
  web/               Static bilingual UI served by the backend (passenger + driver + account pages)
  mobile/            Expo (React Native) app, bilingual UI
  deploy/            systemd unit + cloudflared tunnel config template
```

## Features

- Phone/email OTP login, invite-code driver onboarding, roles (passenger/driver/admin)
- Ride lifecycle: request → accept → en_route → arrived → in_progress → completed/cancelled
- Pricing modes: passenger offer, mileage-based, driver quote; offline or Stripe online payment
- Ratings, tips, saved places, ride sharing links, driver live location
- Account page: edit nickname, language preference, sign out (revokes token), delete account
- Bilingual push (Expo) and email notifications follow each user's language

## Quick start (backend)

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # defaults to local SQLite; set DEV_MODE=0 in production
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## License

MIT — see [LICENSE](LICENSE).
