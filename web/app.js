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
  requestCode: (phone, email) =>
    api.req("/auth/request-code", { method: "POST", body: JSON.stringify(phone ? { phone } : { email }) }),
  verify: (phone, email, code) =>
    api.req("/auth/verify", { method: "POST", body: JSON.stringify(phone ? { phone, code } : { email, code }) }),
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

/* 登录小组件：黑金沉浸式全屏，挂到 #login 容器上，成功后调 onOk(user) */
function mountLogin(el, onOk) {
  let mode = "phone"; // phone | email
  el.classList.add("pr-auth");
  el.innerHTML = `
    <div class="pr-screen">
      <header class="pr-brand">
        <div class="pr-brand-badge" aria-hidden="true">🚕</div>
        <h1 class="pr-brand-name">私人专车</h1>
        <p class="pr-brand-en">PRIVATE RIDE</p>
      </header>
      <section class="pr-card" aria-label="登录">
        <div class="pr-tabs" role="tablist" data-mode="phone" id="pr-tabs">
          <button class="pr-tab" id="tab-phone" role="tab" aria-selected="true" data-mode="phone">手机号登录</button>
          <button class="pr-tab" id="tab-email" role="tab" aria-selected="false" data-mode="email">邮箱登录</button>
          <span class="pr-tab-ink" aria-hidden="true"></span>
        </div>
        <label class="pr-field">
          <input id="login-ident" type="tel" inputmode="numeric" autocomplete="tel" placeholder="手机号，如 6268660555" aria-label="手机号" />
        </label>
        <div class="pr-code-row">
          <label class="pr-field">
            <input id="login-code" type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="验证码" aria-label="验证码" />
          </label>
          <button class="pr-btn-code" id="btn-code" type="button">获取验证码</button>
        </div>
        <p class="pr-msg" id="login-msg" aria-live="polite"></p>
        <button class="pr-btn-login" id="btn-login" type="button">登录</button>
      </section>
      <footer class="pr-slogan">每一程，皆从容</footer>
    </div>`;
  const msg = (t) => (el.querySelector("#login-msg").textContent = t);
  const identInput = () => el.querySelector("#login-ident");
  const tabs = () => el.querySelector("#pr-tabs");
  const modes = {
    phone: { ph: "手机号，如 6268660555", type: "tel", im: "numeric", ac: "tel", label: "手机号" },
    email: { ph: "邮箱，如 you@gmail.com", type: "email", im: "email", ac: "email", label: "邮箱" },
  };
  const setMode = (m) => {
    mode = m;
    const cfg = modes[m];
    tabs().dataset.mode = m;
    el.querySelectorAll(".pr-tab").forEach((t) =>
      t.setAttribute("aria-selected", t.dataset.mode === m));
    const inp = identInput();
    inp.value = "";
    inp.type = cfg.type;
    inp.inputMode = cfg.im;
    inp.autocomplete = cfg.ac;
    inp.placeholder = cfg.ph;
    inp.setAttribute("aria-label", cfg.label);
    msg("");
  };
  el.querySelector("#tab-phone").onclick = () => setMode("phone");
  el.querySelector("#tab-email").onclick = () => setMode("email");
  setMode("phone");
  const ident = () => identInput().value.trim();
  el.querySelector("#btn-code").onclick = async () => {
    const v = ident();
    if (!v) return msg(mode === "phone" ? "请先填手机号" : "请先填邮箱");
    try {
      const r = await api.requestCode(mode === "phone" ? v : null, mode === "email" ? v : null);
      msg(r.dev_code ? `开发模式验证码：${r.dev_code}` : "验证码已发送");
    } catch (e) { msg(e.message); }
  };
  el.querySelector("#btn-login").onclick = async () => {
    const v = ident();
    const code = el.querySelector("#login-code").value.trim();
    try {
      const r = await api.verify(mode === "phone" ? v : null, mode === "email" ? v : null, code);
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
