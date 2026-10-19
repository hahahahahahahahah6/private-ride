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
    "app.tagline": "家人朋友 · 专属叫车",
    "tab.ride": "叫车",
    "tab.drive": "接单",
    "tab.me": "我的",
    "push.channelName": "订单通知",

    "auth.phone": "手机号",
    "auth.email": "邮箱",
    "auth.code": "验证码",
    "auth.getCode": "获取验证码",
    "auth.resend": "{s} 秒后重发",
    "auth.login": "登录",
    "auth.codeSent": "验证码已发送",
    "auth.devCode": "开发模式验证码：{code}",
    "auth.needIdent": "请先填手机号或邮箱",
    "auth.needCode": "请填验证码",

    "book.title": "去哪里？",
    "book.pickup": "上车地点",
    "book.dropoff": "下车地点",
    "book.seats": "人数",
    "book.note": "备注（可选）：有大件行李、带小孩…",
    "book.when": "用车时间",
    "book.now": "现在",
    "book.later": "预约",
    "book.laterHint": "例如 10-25 08:30",
    "book.badTime": "时间格式不对，请写成 月-日 时:分，比如 10-25 08:30",
    "book.priceMode": "价格",
    "book.offer": "我出价",
    "book.quote": "司机报价",
    "book.offerPh": "出价（美元）",
    "book.pay": "付款：当面付给司机（现金 / Zelle / 微信）",
    "book.submit": "叫车",
    "book.need": "请填上车和下车地点",
    "book.needOffer": "请填出价",
    "book.ok": "已下单，司机接单后会通知你",
    "book.drivers": "司机状态",

    "rides.mine": "我的行程",
    "rides.empty": "还没有行程",
    "rides.history": "历史行程",
    "rides.cancel": "取消订单",
    "rides.cancelConfirm": "确定取消这单吗？",
    "rides.callDriver": "打电话给司机",
    "rides.rate": "评分",
    "rides.rated": "已评 {n} 星",
    "rides.rebook": "再来一单",
    "rides.quoteAsk": "司机报价 {p}，接受吗？",
    "rides.accept": "接受",
    "rides.reject": "拒绝",
    "rides.share": "分享行程",
    "rides.price": "价格 {p}",
    "rides.priceTbd": "价格待定",

    "status.requested": "等司机接单",
    "status.accepted": "司机已接单",
    "status.en_route": "司机在路上",
    "status.arrived": "司机已到达",
    "status.in_progress": "行程中",
    "status.completed": "已完成",
    "status.cancelled": "已取消",

    "driver.open": "待接订单",
    "driver.mine": "我接的单",
    "driver.noOpen": "暂时没有新订单",
    "driver.noMine": "没有进行中的订单",
    "driver.accept": "接单",
    "driver.go": "出发",
    "driver.arrive": "已到达",
    "driver.start": "开始行程",
    "driver.finish": "完成",
    "driver.release": "退回订单",
    "driver.releaseConfirm": "去不了这单？订单会退回给其他司机接。",
    "driver.online": "接单中",
    "driver.offline": "休息中",
    "driver.quote": "报价",
    "driver.quotePh": "报价（美元）",
    "driver.waitQuote": "已报价 {p}，等乘客确认",
    "driver.hours": "实际几小时？",
    "driver.call": "打电话给乘客",
    "driver.notDriver": "你还不是司机。有邀请码的话可以在“我的”页面升级。",
    "driver.navigate": "导航",

    "me.title": "我的",
    "me.name": "昵称",
    "me.save": "保存",
    "me.saved": "已保存",
    "me.invite": "司机邀请码",
    "me.redeem": "升级为司机",
    "me.logout": "退出登录",
    "me.lang": "语言",
    "me.push": "通知",
    "me.pushOn": "已开启",
    "me.pushOff": "未开启（真机才能收推送）",
    "me.role.passenger": "乘客",
    "me.role.driver": "司机",
    "me.role.admin": "管理员",

    "rate.title": "给司机评分",
    "rate.send": "提交",

    "common.ok": "好",
    "common.cancel": "算了",
    "common.error": "出错了",
    "common.retry": "重试",
    "common.netErr": "连不上服务器，请检查网络",
  },
  en: {
    "app.title": "Private Ride",
    "app.tagline": "Family & friends · Private rides",
    "tab.ride": "Ride",
    "tab.drive": "Drive",
    "tab.me": "Me",
    "push.channelName": "Ride updates",

    "auth.phone": "Phone",
    "auth.email": "Email",
    "auth.code": "Code",
    "auth.getCode": "Get code",
    "auth.resend": "Resend in {s}s",
    "auth.login": "Sign in",
    "auth.codeSent": "Code sent",
    "auth.devCode": "Dev mode code: {code}",
    "auth.needIdent": "Enter your phone or email first",
    "auth.needCode": "Enter the code",

    "book.title": "Where to?",
    "book.pickup": "Pickup",
    "book.dropoff": "Drop-off",
    "book.seats": "Riders",
    "book.note": "Note (optional): big luggage, kids…",
    "book.when": "When",
    "book.now": "Now",
    "book.later": "Schedule",
    "book.laterHint": "e.g. 10-25 08:30",
    "book.badTime": "Use month-day hour:minute, like 10-25 08:30",
    "book.priceMode": "Price",
    "book.offer": "My offer",
    "book.quote": "Driver quotes",
    "book.offerPh": "Offer (USD)",
    "book.pay": "Pay the driver directly (cash / Zelle / WeChat)",
    "book.submit": "Request ride",
    "book.need": "Enter pickup and drop-off",
    "book.needOffer": "Enter your offer",
    "book.ok": "Requested. We'll notify you when a driver accepts.",
    "book.drivers": "Drivers",

    "rides.mine": "My rides",
    "rides.empty": "No rides yet",
    "rides.history": "Past rides",
    "rides.cancel": "Cancel ride",
    "rides.cancelConfirm": "Cancel this ride?",
    "rides.callDriver": "Call driver",
    "rides.rate": "Rate",
    "rides.rated": "Rated {n}★",
    "rides.rebook": "Book again",
    "rides.quoteAsk": "Driver quoted {p}. Accept?",
    "rides.accept": "Accept",
    "rides.reject": "Decline",
    "rides.share": "Share trip",
    "rides.price": "Price {p}",
    "rides.priceTbd": "Price TBD",

    "status.requested": "Waiting for driver",
    "status.accepted": "Driver accepted",
    "status.en_route": "Driver on the way",
    "status.arrived": "Driver arrived",
    "status.in_progress": "On the trip",
    "status.completed": "Completed",
    "status.cancelled": "Cancelled",

    "driver.open": "Open requests",
    "driver.mine": "My rides",
    "driver.noOpen": "No new requests",
    "driver.noMine": "No active rides",
    "driver.accept": "Accept",
    "driver.go": "Head out",
    "driver.arrive": "Arrived",
    "driver.start": "Start trip",
    "driver.finish": "Finish",
    "driver.release": "Release",
    "driver.releaseConfirm": "Can't make it? The ride goes back to other drivers.",
    "driver.online": "Online",
    "driver.offline": "Resting",
    "driver.quote": "Quote",
    "driver.quotePh": "Quote (USD)",
    "driver.waitQuote": "Quoted {p}, waiting for rider",
    "driver.hours": "Actual hours?",
    "driver.call": "Call rider",
    "driver.notDriver": "You're not a driver yet. Use an invite code on the Me tab.",
    "driver.navigate": "Navigate",

    "me.title": "Me",
    "me.name": "Nickname",
    "me.save": "Save",
    "me.saved": "Saved",
    "me.invite": "Driver invite code",
    "me.redeem": "Become a driver",
    "me.logout": "Sign out",
    "me.lang": "Language",
    "me.push": "Notifications",
    "me.pushOn": "On",
    "me.pushOff": "Off (needs a real phone)",
    "me.role.passenger": "Rider",
    "me.role.driver": "Driver",
    "me.role.admin": "Admin",

    "rate.title": "Rate your driver",
    "rate.send": "Submit",

    "common.ok": "OK",
    "common.cancel": "Never mind",
    "common.error": "Something went wrong",
    "common.retry": "Retry",
    "common.netErr": "Can't reach the server. Check your connection.",
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
