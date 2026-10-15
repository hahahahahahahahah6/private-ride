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

    "passenger.title": "乘客端",
    "passenger.subtitle": "约车 / 看订单状态（M2 接入）",
    "passenger.backendOk": "后端连接正常 ✅ {service}",
    "passenger.backendFail": "后端连不上：{error}",

    "push.channelName": "订单通知",
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

    "passenger.title": "Passenger",
    "passenger.subtitle": "Book rides & check status (M2 coming soon)",
    "passenger.backendOk": "Server connected ✅ {service}",
    "passenger.backendFail": "Can't reach the server: {error}",

    "push.channelName": "Ride notifications",
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
