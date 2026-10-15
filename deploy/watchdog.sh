#!/bin/bash
# private-ride 探活自愈（加固版）
# 根因：运行时会频繁替换 VM（今晚已三次），每次替换清空 /etc/systemd，三个服务随之消失。
# 对策：本脚本由 cron 每 1 分钟运行一次；健康检查失败则重装 unit 并拉起，校验三服务均为 active。
set -u

HEALTH_URL="https://ride.haocoach.com/health"
DEPLOY_DIR="/home/hatch/workspace/private-ride/deploy"
LOG="/home/hatch/workspace/private-ride/deploy/watchdog.log"
LOCK="/tmp/private-ride-watchdog.lock"
SERVICES="edge-relay pr-cloudflared private-ride"

# 防重叠：上一次运行还没结束则直接退出
exec 9>"$LOCK"
flock -n 9 || exit 0

code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$HEALTH_URL" 2>/dev/null || echo "000")
if [ "$code" = "200" ]; then
  exit 0
fi

ts() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }
echo "$(ts) health=$code, reinstalling services" >> "$LOG"

reinstall() {
  sudo cp "$DEPLOY_DIR/edge-relay.service" "$DEPLOY_DIR/pr-cloudflared.service" \
          "$DEPLOY_DIR/private-ride.service" /etc/systemd/system/ 2>>"$LOG" \
    && sudo systemctl daemon-reload 2>>"$LOG" \
    && sudo systemctl enable --now $SERVICES 2>>"$LOG"
}

all_active() {
  for s in $SERVICES; do
    [ "$(systemctl is-active "$s" 2>/dev/null)" = "active" ] || return 1
  done
  return 0
}

reinstall
sleep 15
if ! all_active; then
  echo "$(ts) services not all active after reinstall, retrying once" >> "$LOG"
  sudo systemctl daemon-reload 2>>"$LOG"
  sudo systemctl restart $SERVICES 2>>"$LOG"
  sleep 15
fi

if all_active; then
  state="active"
else
  state="NOT-ALL-ACTIVE"
fi
code2="000"
for i in 1 2 3; do
  code2=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$HEALTH_URL" 2>/dev/null || echo "000")
  [ "$code2" = "200" ] && break
  echo "$(ts) after reinstall health=$code2 services=$state (attempt $i/3)" >> "$LOG"
  sleep 20
done
echo "$(ts) after reinstall health=$code2 services=$state" >> "$LOG"

# 日志只留最后 200 行
tail -n 200 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"

# 健康恢复则静默；仍失败则返回非零，让 cron worker 感知
[ "$code2" = "200" ] && [ "$state" = "active" ]
