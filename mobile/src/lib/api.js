/** Backend API client.
 *  本地开发：EXPO_PUBLIC_API_URL=http://<你的电脑IP>:8000（真机 Expo Go 不能用 localhost）
 *  默认连线上：https://ride.haocoach.com
 */
import AsyncStorage from "@react-native-async-storage/async-storage";

export const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "https://ride.haocoach.com";
const TOKEN_KEY = "private-ride:token";

let authToken = null;

export async function loadToken() {
  try {
    authToken = await AsyncStorage.getItem(TOKEN_KEY);
  } catch (e) {
    authToken = null;
  }
  return authToken;
}

export async function setAuthToken(token) {
  authToken = token;
  try {
    if (token) await AsyncStorage.setItem(TOKEN_KEY, token);
    else await AsyncStorage.removeItem(TOKEN_KEY);
  } catch (e) {
    // 存不了就只在这次打开里有效
  }
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function req(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers ?? {}) };
  if (authToken) headers["Authorization"] = `Bearer ${authToken}`;
  let res;
  try {
    res = await fetch(`${API_URL}${path}`, { ...options, headers });
  } catch (e) {
    throw new ApiError(0, "network");
  }
  if (!res.ok) {
    // 后端报错是 {"detail": "中文提示"}，直接拿来给用户看
    let msg = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") msg = body.detail;
      else if (Array.isArray(body.detail) && body.detail[0]?.msg) msg = body.detail[0].msg;
    } catch (e) {
      // 不是 JSON 就用状态码
    }
    throw new ApiError(res.status, msg);
  }
  return res.json();
}

const post = (path, body) =>
  req(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  health: () => req("/health"),

  // 登录：手机号或邮箱二选一
  requestCode: (ident) => post("/auth/request-code", ident),
  verifyCode: async (ident, code) => {
    const out = await post("/auth/verify", { ...ident, code });
    await setAuthToken(out.token);
    return out;
  },
  logout: async () => {
    try {
      await post("/auth/logout");
    } finally {
      await setAuthToken(null);
    }
  },

  me: () => req("/me"),
  updateMe: (data) => req("/me", { method: "PATCH", body: JSON.stringify(data) }),
  setPushToken: (push_token, lang) =>
    req("/me/push-token", {
      method: "PUT",
      body: JSON.stringify(lang ? { push_token, lang } : { push_token }),
    }),
  redeemInvite: (code) => post("/invites/redeem", { code }),

  // 乘客
  createRide: (ride) => post("/rides", ride),
  myRides: () => req("/rides?mine=true&limit=50"),
  cancelRide: (id) => post(`/rides/${id}/cancel`),
  confirmQuote: (id, accept) => post(`/rides/${id}/quote/confirm`, { accept }),
  rateRide: (id, stars) => post(`/rides/${id}/rate`, { stars, comment: "", tags: [] }),
  rebook: (id) => post(`/rides/${id}/rebook`),
  shareRide: (id) => post(`/rides/${id}/share`),
  driversStatus: () => req("/drivers/status"),

  // 司机
  openRides: () => req("/rides?mine=false&open=true"),
  acceptRide: (id) => post(`/rides/${id}/accept`),
  setRideStatus: (id, status) => post(`/rides/${id}/status`, { status }),
  quoteRide: (id, cents) => post(`/rides/${id}/quote`, { price_quote_cents: cents }),
  finishHourly: (id, hours) => post(`/rides/${id}/finish-hourly`, { hours }),
  getOnline: () => req("/me/online"),
  setOnline: (online) => post("/me/online", { online }),
  sendLocation: (lat, lng) => post("/me/location", { lat, lng }),
};
