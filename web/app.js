/* URL 免登：链接形如 /driver.html#token=xxx 或 ?token=xxx，打开即登录（家人试用期用，长效 30 天） */
(function bootstrapTokenFromUrl() {
  try {
    const q = new URLSearchParams(location.search);
    const h = new URLSearchParams(location.hash.slice(1));
    const token = h.get("token") || q.get("token");
    if (token) {
      localStorage.setItem("pr_token", token);
      q.delete("token");
      const qs = q.toString();
      history.replaceState(null, "", location.pathname + (qs ? "?" + qs : ""));
    }
  } catch { /* ignore */ }
})();

/* private-ride 网页版：与 FastAPI 后端同源（/web/），API 直接走相对路径 */
const api = {
  async req(path, options = {}) {
    const token = localStorage.getItem("pr_token");
    const res = await fetch(path, {
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: "Bearer " + token } : {}),
      },
      ...options,
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail || ("请求失败 " + res.status));
    return body;
  },
  requestCode: (phone) =>
    api.req("/auth/request-code", { method: "POST", body: JSON.stringify({ phone }) }),
  verify: (phone, code) =>
    api.req("/auth/verify", { method: "POST", body: JSON.stringify({ phone, code }) }),
  me: () => api.req("/me"),
  createRide: (data) =>
    api.req("/rides", { method: "POST", body: JSON.stringify(data) }),
  myRides: () => api.req("/rides?mine=true"),
  openRides: () => api.req("/rides?mine=false&open=true"),
  acceptRide: (id) => api.req(`/rides/${id}/accept`, { method: "POST" }),
  setStatus: (id, status) =>
    api.req(`/rides/${id}/status`, { method: "POST", body: JSON.stringify({ status }) }),
  cancelRide: (id) => api.req(`/rides/${id}/cancel`, { method: "POST" }),
};

const STATUS_LABEL = {
  requested: "待接单",
  accepted: "司机已接单",
  en_route: "司机正在赶来",
  arrived: "司机已到达",
  in_progress: "行程中",
  completed: "已完成",
  cancelled: "已取消",
};

/* 下一步可点的状态按钮（司机用） */
const NEXT_STATUS = {
  accepted: ["en_route", "出发接客"],
  en_route: ["arrived", "已到达上车点"],
  arrived: ["in_progress", "开始行程"],
  in_progress: ["completed", "完成行程"],
};

function badgeClass(status) {
  if (status === "requested") return "badge b-requested";
  if (status === "cancelled") return "badge b-cancel";
  if (status === "completed") return "badge b-done";
  return "badge b-active";
}

function rideCard(r, actionsHtml = "") {
  const when = r.scheduled_at
    ? new Date(r.scheduled_at).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })
    : "现在用车";
  return `<div class="card">
    <div class="card-head"><span class="${badgeClass(r.status)}">${STATUS_LABEL[r.status] || r.status}</span>
    <span class="time">${when}</span></div>
    <div class="route"><span class="pdot from"></span><span>${esc(r.pickup_text)}</span></div>
    <div class="route"><span class="pdot to"></span><span>${esc(r.dropoff_text)}</span></div>
    <div class="meta">${r.seats_needed} 人${r.note ? " · " + esc(r.note) : ""}</div>
    ${actionsHtml}
  </div>`;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* 登录小组件：挂到 #login 容器上，成功后调 onOk(user) */
function mountLogin(el, onOk) {
  el.innerHTML = `
    <div class="card login-card">
      <div class="card_h">手机号登录</div>
      <input id="login-phone" inputmode="tel" placeholder="手机号，如 +16265550100" />
      <div class="row">
        <input id="login-code" inputmode="numeric" placeholder="验证码" style="flex:1" />
        <button id="btn-code" class="secondary">获取验证码</button>
      </div>
      <button id="btn-login" class="primary">登录</button>
      <p class="hint" id="login-msg"></p>
    </div>`;
  const msg = (t) => (el.querySelector("#login-msg").textContent = t);
  el.querySelector("#btn-code").onclick = async () => {
    const phone = el.querySelector("#login-phone").value.trim();
    if (!phone) return msg("请先填手机号");
    try {
      const r = await api.requestCode(phone);
      msg(r.dev_code ? `开发模式验证码：${r.dev_code}` : "验证码已发送");
    } catch (e) { msg(e.message); }
  };
  el.querySelector("#btn-login").onclick = async () => {
    const phone = el.querySelector("#login-phone").value.trim();
    const code = el.querySelector("#login-code").value.trim();
    try {
      const r = await api.verify(phone, code);
      localStorage.setItem("pr_token", r.token);
      onOk(r.user);
    } catch (e) { msg(e.message); }
  };
}

async function ensureSession(loginEl, mainEl, onOk) {
  const token = localStorage.getItem("pr_token");
  if (!token) {
    loginEl.style.display = "";
    mainEl.style.display = "none";
    mountLogin(loginEl, (user) => {
      loginEl.style.display = "none";
      mainEl.style.display = "";
      onOk(user);
    });
    return;
  }
  try {
    const user = await api.me();
    loginEl.style.display = "none";
    mainEl.style.display = "";
    onOk(user);
  } catch {
    localStorage.removeItem("pr_token");
    ensureSession(loginEl, mainEl, onOk);
  }
}

function logout() {
  localStorage.removeItem("pr_token");
  location.reload();
}
