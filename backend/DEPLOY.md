# 后端部署说明（private-ride API）

目标：`https://ride.haocoach.com` ← Cloudflare Tunnel ← 本机/服务器上的 uvicorn。

## 1. 环境变量（`.env`，不要进 git）

```bash
# 数据库：默认 SQLite（./dev.db）。生产填 Neon 连接串：
DATABASE_URL=<redacted>
# 生产必须关掉开发模式（关掉验证码回显）：
DEV_MODE=0
# 生产验证码改成真短信前，先换掉默认值：
DEV_TEST_CODE=一串随机字串
```

`.env.example` 里有模板。

## 2. 安装与启动（systemd，推荐）

```bash
cd ~/workspace/private-ride/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# 切 Postgres 时：.venv/bin/pip install "psycopg[binary]"
```

把 `deploy/private-ride.service` 拷到 `/etc/systemd/system/`，
改里面的 `User=` / `WorkingDirectory=` / `EnvironmentFile=` 路径：

```bash
sudo cp deploy/private-ride.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now private-ride
curl localhost:8000/health   # 应返回 {"ok": true, ...}
```

服务跑在 `127.0.0.1:8000`，只监听本地，不直接暴露公网。

## 3. Cloudflare Tunnel（只做配置，不碰线上 DNS）

`deploy/cloudflared-config.yml` 是模板：

```yaml
tunnel: <TUNNEL_ID>
credentials-file: /root/.cloudflared/<TUNNEL_ID>.json
ingress:
  - hostname: ride.haocoach.com
    service: http://127.0.0.1:8000
  - service: http_status:404
```

步骤（在已装 cloudflared 的机器上，一次性）：

```bash
cloudflared tunnel create private-ride
# 把返回的 TUNNEL_ID 填进 deploy/cloudflared-config.yml
cloudflared tunnel route dns private-ride ride.haocoach.com
sudo cloudflared service install --config deploy/cloudflared-config.yml
sudo systemctl enable --now cloudflared
```

验证：`curl https://ride.haocoach.com/health`

## 4. 数据库

- **先行方案 SQLite**：零运维，`./dev.db` 一个文件。司机+熟客的小圈子完全够用。
  备份就是拷文件：`cp dev.db dev.db.$(date +%F).bak`。
- **生产选项 Neon**：把连接串填进 `DATABASE_URL` 即可，代码里的 GUID
  类型在 Postgres 下自动用原生 UUID，无需改代码。

## 5. 上线前检查单

- [ ] `DEV_MODE=0`（验证码不再回显）
- [ ] `DEV_TEST_CODE` 已换成随机值（或已接真短信）
- [ ] 防火墙只开 tunnel 出站，8000 端口不对外
- [ ] `dev.db` 定期备份（cron 每天拷一份）
- [ ] Expo app 里 `EXPO_PUBLIC_API_URL=https://ride.haocoach.com` 重新打生产包

## 6. 日志

```bash
journalctl -u private-ride -f        # 后端日志
journalctl -u cloudflared -f         # tunnel 日志
```
