/** 中英双语字典 + t(key, vars) + 语言状态。
 *
 *  - 默认中文，可切换英文；选择经 AsyncStorage 持久化（已安装
 *    @react-native-async-storage/async-storage）。
 *  - 用法：在组件里 `const { t } = useI18n();` 然后 `t("driver.accept")`；
 *    带插值：`t("driver.note", { note: item.note })`。
 *  - 非组件场景（push.js）直接用模块级 `t()` / `getLang()`。
 */
import { useEffect, useState } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";

const LANG_KEY = "private-ride:lang";

const STRINGS = {
  zh: {
    "app.title": "私人专车",
    "app.chooseRole": "请选择你的身份",
    "app.iAmPassenger": "我是乘客",
    "app.iAmDriver": "我是司机",
    "app.switchRole": "切换身份",

    "common.login": "登录",

    "driver.loginTitle": "司机登录",
    "driver.phonePlaceholder": "手机号",
    "driver.codePlaceholder": "验证码",
    "driver.getCode": "获取验证码",
    "driver.openOrders": "待接订单",
    "driver.pushStatus": "推送状态：{state}",
    "driver.pushUnregistered": "未注册",
    "driver.pushEnabled": "已开启 ✅ 新订单会推送到这台手机",
    "driver.pushFailed": "注册失败：{error}",
    "driver.noOrders": "暂无待接订单",
    "driver.note": "备注：{note}",
    "driver.accept": "接单",

    "price.hourly": "包车 {p}/小时",
    "price.hourly_done": "包车结算 {p}",

    "passenger.title": "乘客端",
    "passenger.subtitle": "约车 / 看订单状态（M2 接入）",
    "passenger.backendOk": "后端连接正常 ✅ {service}",
    "passenger.backendFail": "后端连不上：{error}",

    "push.channelName": "订单通知",

    "flight.label": "航班号（可选）",
    "flight.ph": "UA 857",
    "flight.hint": "机场接送可填；落地发现晚点，可直接在订单里延后预约时间。",
    "flight.show": "✈️ 航班：",
    "flight.delay": "✈️ 航班晚点",
    "flight.delay_unit": "分钟",
    "flight.delay_q": "航班晚点 {m} 分钟，预约时间延后 {m} 分钟？",
    "flight.delayed_ok": "✓ 已延后 {m} 分钟，司机已收到通知",

    "rebook.btn": "🔁 再来一单",
    "rebook.confirm": "用相同的线路和价格再来一单？",
    "rebook.ok": "✓ 已重新下单（现在用车），新订单在列表最上方",

    "notes.title": "📝 熟客便签",
    "notes.add": "添加便签",
    "notes.save": "保存",
    "notes.saving": "保存中…",
    "notes.saved": "✓ 已保存",
    "notes.deleted": "✓ 已删除",
    "notes.ph": "如：张阿姨晕车，开慢点；李叔爱听戏曲",
    "notes.clear_hint": "清空后保存即删除这条便签",
  },
  en: {
    "app.title": "Private Ride",
    "app.chooseRole": "Choose your role",
    "app.iAmPassenger": "I'm a Passenger",
    "app.iAmDriver": "I'm a Driver",
    "app.switchRole": "Switch Role",

    "common.login": "Sign In",

    "driver.loginTitle": "Driver Sign In",
    "driver.phonePlaceholder": "Phone number",
    "driver.codePlaceholder": "Verification code",
    "driver.getCode": "Send Code",
    "driver.openOrders": "Open Ride Requests",
    "driver.pushStatus": "Push status: {state}",
    "driver.pushUnregistered": "Not registered",
    "driver.pushEnabled": "On ✅ — new ride requests will be pushed to this phone",
    "driver.pushFailed": "Push registration failed: {error}",
    "driver.noOrders": "No open ride requests right now",
    "driver.note": "Note: {note}",
    "driver.accept": "Accept",

    "price.hourly": "Charter {p}/hour",
    "price.hourly_done": "Charter {p}",

    "passenger.title": "Passenger",
    "passenger.subtitle": "Book rides & check status (M2 coming soon)",
    "passenger.backendOk": "Server connected ✅ {service}",
    "passenger.backendFail": "Can't reach the server: {error}",

    "push.channelName": "Ride notifications",

    "flight.label": "Flight number (optional)",
    "flight.ph": "UA 857",
    "flight.hint": "For airport rides — if your flight is late, push the pickup time back right from the order.",
    "flight.show": "✈️ Flight: ",
    "flight.delay": "✈️ Flight delayed",
    "flight.delay_unit": "min",
    "flight.delay_q": "Flight delayed {m} min — push pickup time back {m} min?",
    "flight.delayed_ok": "✓ Pushed back {m} min — driver notified",

    "rebook.btn": "🔁 Book again",
    "rebook.confirm": "Book the same route and price again?",
    "rebook.ok": "✓ Rebooked (ride now) — the new order is at the top",

    "notes.title": "📝 Rider notes",
    "notes.add": "Add note",
    "notes.save": "Save",
    "notes.saving": "Saving…",
    "notes.saved": "✓ Saved",
    "notes.deleted": "✓ Deleted",
    "notes.ph": "e.g. Mrs. Zhang gets carsick — drive slowly; Mr. Li loves opera",
    "notes.clear_hint": "Save empty to delete this note",
  },
};

let lang = "zh";
const listeners = new Set();

export function getLang() {
  return lang;
}

/** 取文案；key 缺失时回退中文，再缺失则原样返回 key。支持 {var} 插值。 */
export function t(key, vars) {
  const dict = STRINGS[lang] || STRINGS.zh;
  let s = dict[key] ?? STRINGS.zh[key] ?? key;
  if (vars) {
    for (const k of Object.keys(vars)) {
      s = s.split(`{${k}}`).join(String(vars[k]));
    }
  }
  return s;
}

export async function setLang(next) {
  if ((next !== "zh" && next !== "en") || next === lang) return;
  lang = next;
  try {
    await AsyncStorage.setItem(LANG_KEY, next);
  } catch (e) {
    // 持久化失败不影响本次会话
  }
  listeners.forEach((fn) => fn(next));
}

/** App 启动时调用一次，读回上次保存的语言。 */
export async function initI18n() {
  try {
    const saved = await AsyncStorage.getItem(LANG_KEY);
    if (saved === "zh" || saved === "en") lang = saved;
  } catch (e) {
    // 读不到就用默认中文
  }
  return lang;
}

/** 组件里订阅语言变化：语言切换时自动重渲染。 */
export function useI18n() {
  const [, setTick] = useState(0);
  useEffect(() => {
    const fn = () => setTick((x) => x + 1);
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  }, []);
  return { lang, setLang, t };
}
