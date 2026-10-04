# private-ride

A private ride-hailing app for a small circle: drivers (family + friends) and passengers (regulars). A shared FastAPI backend serves both the web client and the Expo mobile app. First version has no in-app payments — passengers pay drivers directly (cash / Zelle / WeChat).

## Layout

```
private-ride/
  PLAN.md            Technical plan (Chinese; MVP scope, stack, data model, store checklists)
  backend/           FastAPI: auth, ride booking, driver accept, status machine, push tokens
  web/               Static Chinese UI served by the backend (passenger + driver pages)
  mobile/            Expo (React Native) app, Chinese UI
  deploy/            systemd unit + cloudflared tunnel config template
```

## Quick start (backend)

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # defaults to local SQLite; set DEV_MODE=0 in production
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## License

MIT — see [LICENSE](LICENSE).
