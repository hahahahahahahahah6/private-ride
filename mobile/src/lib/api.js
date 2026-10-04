/** Backend API client.
 *  本地开发：EXPO_PUBLIC_API_URL=http://<你的电脑IP>:8000（真机 Expo Go 不能用 localhost）
 *  生产：https://ride.haocoach.com（Cloudflare tunnel，见 backend/DEPLOY.md）
 */
const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

let authToken = null;

export function setAuthToken(token) {
  authToken = token;
}

async function req(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers ?? {}) };
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

export const api = {
  health: () => req("/health"),

  // 手机号验证码登录（开发模式后端直接回显 dev_code）
  requestCode: (phone) =>
    req("/auth/request-code", {
      method: "POST",
      body: JSON.stringify({ phone }),
    }),
  verifyCode: async (phone, code) => {
    const out = await req("/auth/verify", {
      method: "POST",
      body: JSON.stringify({ phone, code }),
    });
    setAuthToken(out.token);
    return out;
  },

  me: () => req("/me"),

  // 上报 Expo push token（司机端登录后调用）
  setPushToken: (push_token) =>
    req("/me/push-token", {
      method: "PUT",
      body: JSON.stringify({ push_token }),
    }),

  // 乘客下单
  createRide: (ride) =>
    req("/rides", { method: "POST", body: JSON.stringify(ride) }),

  // 司机看待接单
  openRides: () => req("/rides?mine=false&open=true"),

  // 司机抢单 / 推进状态
  acceptRide: (id) => req(`/rides/${id}/accept`, { method: "POST" }),
  setRideStatus: (id, status) =>
    req(`/rides/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    }),
};
