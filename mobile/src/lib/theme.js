/** 和网页版一样的黑金配色。 */
export const C = {
  bg: "#0e0e0e",
  card: "#1b1b1b",
  cardHigh: "#242424",
  line: "#2e2e2e",
  gold: "#f2ca50",
  goldInk: "#3c2f00",
  text: "#f5f1e8",
  muted: "#a39e93",
  faint: "#6e6a61",
  green: "#7bc98a",
  red: "#e5736b",
};

export const STATUS_COLOR = {
  requested: C.gold,
  accepted: C.green,
  en_route: C.green,
  arrived: C.green,
  in_progress: C.green,
  completed: C.muted,
  cancelled: C.faint,
};

export function money(cents) {
  if (cents == null) return "";
  return `$${(cents / 100).toFixed(cents % 100 === 0 ? 0 : 2)}`;
}

/** 后端时间是 UTC（带 Z），这里转成手机本地时间显示。 */
export function fmtTime(iso, lang) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString(lang === "en" ? "en-US" : "zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
