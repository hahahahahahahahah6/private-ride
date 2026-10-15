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
    if (!res.ok) throw new Error(body.detail || t("api.fail", { s: res.status }));
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
  quoteRide: (id, cents) =>
    api.req(`/rides/${id}/quote`, { method: "POST", body: JSON.stringify({ price_quote_cents: cents }) }),
  confirmQuote: (id, accept) =>
    api.req(`/rides/${id}/quote/confirm`, { method: "POST", body: JSON.stringify({ accept }) }),
  rateRide: (id, stars, comment = "") =>
    api.req(`/rides/${id}/rate`, { method: "POST", body: JSON.stringify({ stars, comment }) }),
  getDriverProfile: () => api.req("/me/driver-profile"),
  saveDriverProfile: (data) =>
    api.req("/me/driver-profile", { method: "PUT", body: JSON.stringify(data) }),
};

// 价格展示：分 → $x.xx
function fmtPrice(cents) {
  if (cents == null) return "";
  return "$" + (cents / 100).toFixed(2);
}
function priceLabel(r) {
  if (r.price_mode === "offer") return t("price.offer", { p: fmtPrice(r.price_offer_cents) });
  if (r.price_mode === "mileage") return t("price.mileage", { p: fmtPrice(r.price_final_cents), m: r.price_miles });
  if (r.price_mode === "quote") {
    if (r.price_status === "agreed") return t("price.quoted_agreed", { p: fmtPrice(r.price_final_cents) });
    if (r.price_quote_cents != null) return t("price.quoted_pending", { p: fmtPrice(r.price_quote_cents) });
    return t("price.waiting_quote");
  }
  return "";
}
function payLabel(r) {
  const mode = r.pay_mode === "online" ? t("pay.online") : t("pay.offline");
  if (r.pay_mode === "offline") return mode;
  const st = r.pay_status === "paid" ? t("pay.paid") : r.pay_status === "failed" ? t("pay.failed") : t("pay.pending");
  return `${mode} · ${st}`;
}

function badgeClass(status) {
  if (status === "requested") return "badge b-requested";
  if (status === "cancelled") return "badge b-cancel";
  if (status === "completed") return "badge b-done";
  return "badge b-active";
}

function rideCard(r, actionsHtml = "") {
  const when = r.scheduled_at
    ? new Date(r.scheduled_at).toLocaleString(dateLocale(), { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })
    : t("card.now");
  return `<div class="card">
    <div class="card-head"><span class="${badgeClass(r.status)}">${statusLabel(r.status)}</span>
    <span class="time">${when}</span></div>
    <div class="route"><span class="pdot from"></span><span>${esc(r.pickup_text)}</span></div>
    <div class="route"><span class="pdot to"></span><span>${esc(r.dropoff_text)}</span></div>
    <div class="meta">${riders(r.seats_needed)}${r.note ? " · " + esc(r.note) : ""}</div>
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
  el._loginOnOk = onOk;
  el.innerHTML = `
    <div class="pr-screen">
      <header class="pr-brand">
        <div class="pr-brand-badge" aria-hidden="true">🚕</div>
        <h1 class="pr-brand-name">${t("brand.name")}</h1>
        <p class="pr-brand-en">PRIVATE RIDE</p>
      </header>
      <section class="pr-card" aria-label="${t("auth.signin_aria")}">
        <div class="pr-tabs" role="tablist" data-mode="phone" id="pr-tabs">
          <button class="pr-tab" id="tab-phone" role="tab" aria-selected="true" data-mode="phone">${t("auth.tab_phone")}</button>
          <button class="pr-tab" id="tab-email" role="tab" aria-selected="false" data-mode="email">${t("auth.tab_email")}</button>
          <span class="pr-tab-ink" aria-hidden="true"></span>
        </div>
        <label class="pr-field">
          <input id="login-ident" type="tel" inputmode="numeric" autocomplete="tel" placeholder="${t("auth.ph_phone")}" aria-label="${t("auth.aria_phone")}" />
        </label>
        <div class="pr-code-row">
          <label class="pr-field">
            <input id="login-code" type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="${t("auth.ph_code")}" aria-label="${t("auth.aria_code")}" />
          </label>
          <button class="pr-btn-code" id="btn-code" type="button">${t("auth.get_code")}</button>
        </div>
        <p class="pr-msg" id="login-msg" aria-live="polite"></p>
        <button class="pr-btn-login" id="btn-login" type="button">${t("auth.login")}</button>
      </section>
      <footer class="pr-slogan">${t("auth.slogan")}</footer>
    </div>`;
  const msg = (txt) => (el.querySelector("#login-msg").textContent = txt);
  const identInput = () => el.querySelector("#login-ident");
  const tabs = () => el.querySelector("#pr-tabs");
  const modes = {
    phone: { ph: t("auth.ph_phone"), type: "tel", im: "numeric", ac: "tel", label: t("auth.aria_phone") },
    email: { ph: t("auth.ph_email"), type: "email", im: "email", ac: "email", label: t("auth.aria_email") },
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
    if (!v) return msg(mode === "phone" ? t("auth.need_phone") : t("auth.need_email"));
    try {
      const r = await api.requestCode(mode === "phone" ? v : null, mode === "email" ? v : null);
      msg(r.dev_code ? t("auth.dev_code", { code: r.dev_code }) : t("auth.code_sent"));
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

/* 语言切换时重渲染登录组件（仅当登录屏可见时） */
window.addEventListener("pr:langchange", () => {
  document.querySelectorAll("#login.pr-auth").forEach((el) => {
    if (el._loginOnOk && el.style.display !== "none") mountLogin(el, el._loginOnOk);
  });
});
