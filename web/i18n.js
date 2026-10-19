/* Private Ride 网页版 i18n：中英双语字典 + 语言切换
 *
 * 用法：
 *  - 静态文案：<span data-i18n="nav.home"></span>
 *    富文本：  <p data-i18n-html="index.hero_sub"></p>
 *    placeholder：<input data-i18n-ph="p.pickup_ph" />
 *    aria-label： <input data-i18n-aria="auth.aria_phone" />
 *  - JS 动态文案：t("key") / t("key", {name: "x"})（支持 {name} 插值）
 *  - 日期 locale：dateLocale()；状态文案：statusLabel(s)；人数：riders(n)
 *  - 语言存在 localStorage "pr_lang"；首次按 navigator.language 判断（en 开头默认英文）
 *  - 切换后派发 window "pr:langchange" 事件，页面监听后重渲染动态内容
 */
(function () {
  "use strict";

  var DICT = {
    zh: {
      "meta.title.index": "私人专车",
      "meta.title.passenger": "乘客 · 私人专车",
      "meta.title.driver": "司机 · 私人专车",
      "meta.title.track": "行程分享 · 私人专车",
      "meta.title.privacy": "隐私政策 · 私人专车",
      "meta.title.terms": "服务条款 · 私人专车",

      "brand.name": "私人专车",

      "nav.switch": "切换身份",
      "nav.signout": "退出",
      "nav.home": "首页",
      "nav.account": "账号",

      "acct.title": "账号设置",
      "acct.profile": "我的资料",
      "acct.phone": "手机号",
      "acct.email": "邮箱",
      "acct.role": "身份",
      "acct.role.passenger": "乘客",
      "acct.role.driver": "司机",
      "acct.role.admin": "管理员",
      "acct.name": "昵称",
      "acct.name_ph": "输入昵称",
      "acct.save": "保存",
      "acct.saved": "已保存",
      "acct.language": "语言",
      "acct.danger": "危险操作",
      "acct.signout": "退出登录",
      "acct.signout_done": "已退出",
      "acct.delete": "注销账号",
      "acct.delete_warn": "注销后账号、常用地址、分享链接将被删除，订单记录会匿名保留。不可恢复。",
      "acct.delete_confirm1": "确定要注销账号吗？此操作不可恢复。",
      "acct.delete_confirm2": "最后确认：真的要注销吗？",
      "acct.deleted": "账号已注销",
      "acct.loading": "加载中…",
      "acct.login_required": "请先登录",

      "index.kicker": "家人朋友 · 专属叫车",
      "index.hero1": "一键叫车",
      "index.hero2": "司机马上到",
      "index.hero_sub": "TCP 持牌运营，家人朋友的私人车队。<br />网页与 App 共用同一后端。",
      "index.rider_t": "我是乘客",
      "index.rider_s": "输入上下车地点，一键叫车，实时看订单状态",
      "index.driver_t": "我是司机",
      "index.driver_s": "查看待接订单，一键接单，全程状态管理",

      "status.requested": "待接单",
      "status.accepted": "司机已接单",
      "status.en_route": "司机正在赶来",
      "status.arrived": "司机已到达",
      "status.in_progress": "行程中",
      "status.completed": "已完成",
      "status.cancelled": "已取消",

      "next.head_to_pickup": "出发接客",
      "next.arrived_pickup": "已到达上车点",
      "next.start_trip": "开始行程",
      "next.complete_trip": "完成行程",

      "price.offer": "乘客出价 {p}",
      "price.mileage": "里程计价 {p}（约{m}英里）",
      "price.quoted_agreed": "已确认 {p}",
      "price.quoted_pending": "司机报价 {p}（待确认）",
      "price.waiting_quote": "等司机报价",
      "price.hourly": "包车 {p}/小时",
      "price.hourly_done": "包车结算 {p}",

      "pay.offline": "线下当面付",
      "pay.online": "线上付款",
      "pay.paid": "已扣款",
      "pay.failed": "扣款失败",
      "pay.pending": "待扣款",

      "card.now": "现在用车",

      "auth.signin_aria": "登录",
      "auth.tab_phone": "手机号登录",
      "auth.tab_email": "邮箱登录",
      "auth.ph_phone": "手机号，如 6268660555",
      "auth.ph_email": "邮箱，如 you@gmail.com",
      "auth.ph_code": "验证码",
      "auth.aria_phone": "手机号",
      "auth.aria_email": "邮箱",
      "auth.aria_code": "验证码",
      "auth.get_code": "获取验证码",
      "auth.login": "登录",
      "auth.slogan": "每一程，皆从容",
      "auth.need_phone": "请先填手机号",
      "auth.need_email": "请先填邮箱",
      "auth.dev_code": "开发模式验证码：{code}",
      "auth.code_sent": "验证码已发送",

      "api.fail": "请求失败 {s}",

      "p.title": "乘客约车",
      "p.book": "叫车",
      "p.driver_checking": "正在查看司机状态…",
      "p.no_driver": "暂无司机信息",
      "p.online": "在线",
      "p.offline": "休息中",
      "p.pickup": "上车地点",
      "p.pickup_ph": "例如：家里小区门口",
      "p.dropoff": "下车地点",
      "p.dropoff_ph": "例如：罗兰岗大华超市",
      "p.add_stop": "＋ 经停点（最多 3 个）",
      "p.stop_ph": "经停点 {n}（可选）",
      "p.seats": "人数",
      "p.when": "用车时间",
      "p.note": "备注（可选）",
      "p.note_ph": "如：有大件行李、带小孩",
      "p.book_other": "🧑‍🤝‍🧑 帮别人叫车（可选）",
      "p.rider_name": "乘车人姓名",
      "p.rider_name_ph": "如：妈妈",
      "p.rider_phone": "乘车人电话",
      "p.rider_phone_ph": "司机联系乘车人用",
      "p.pricing": "价格方式",
      "p.mode_offer": "我出价",
      "p.mode_mileage": "里程计价",
      "p.mode_quote": "司机报价",
      "p.offer_label": "你的出价（美元）",
      "p.offer_ph": "如：25",
      "p.miles_label": "预估里程（英里）",
      "p.miles_ph": "如：10",
      "p.mileage_base": "起步 $8 + $3/英里",
      "p.mileage_est": "预估 {e}（起步 $8 + $3/英里）",
      "p.quote_hint": "司机接单后会报价，你再确认。",
      "p.mode_hourly": "包车/按小时",
      "p.hourly_label": "每小时价格（美元）",
      "p.hourly_ph": "如：80",
      "p.need_hourly": "请填写每小时价格",
      "p.payment": "付款方式",
      "p.pay_offline": "线下当面付",
      "p.pay_online": "线上付款",
      "p.card_na": "线上付款暂未开通，请选择线下当面付",
      "p.card_onfile": "已绑卡：{b} ****{l}",
      "p.card_none": "还未绑卡，请添加一张卡用于线上付款",
      "p.bind_card": "绑定这张卡",
      "p.binding": "绑定中…",
      "p.bound": "✓ 已绑定 {b} ****{l}",
      "p.book_now": "叫车",
      "p.need_places": "请填写上车和下车地点",
      "p.need_offer": "请填写你的出价",
      "p.need_miles": "请填写预估里程",
      "p.booked_ok": "✓ 下单成功，等待司机接单",
      "p.places": "常用地址",
      "p.places_empty": "还没有常用地址，在下面添加（如：家、面馆）。",
      "p.place_label_ph": "名称，如：家",
      "p.place_addr_ph": "地址",
      "p.save": "保存",
      "p.set_pickup": "设为上车点",
      "p.set_dropoff": "设为下车点",
      "p.del": "删",
      "p.del_place": "删除这个常用地址？",
      "p.need_place_fields": "请填写名称和地址",
      "p.my_rides": "我的订单",
      "p.rides_count": "共 {n} 单",
      "p.no_rides": "还没有订单",
      "p.no_rides_sub": "在上面填好地点，一键叫车",
      "p.cancel_ride": "取消订单",
      "p.confirm_cancel": "确定取消这单吗？",
      "p.quote_accept_q": "司机报价 {p}，接受吗？",
      "p.accept": "接受 {p}",
      "p.decline": "拒绝",
      "p.decline_q": "拒绝报价？订单会回到待接单，司机可重新报价。",
      "p.tip_q": "给 {p} 小费？",
      "p.tip": "给小费：",
      "p.tip_other": "其他",
      "p.tip_prompt": "小费金额（美元，至少 $1）：",
      "p.tip_min": "至少 $1",
      "p.tipped": "💰 已给小费 {p}",
      "p.share": "🔗 分享行程给家人",
      "p.share_copied": "分享链接已复制（7 天有效）：\n{url}",
      "p.nudge": "📣 催一下司机",
      "p.nudged": "已提醒司机尽快出发",
      "p.receipt": "🧾 收据",
      "p.receipt_title": "行程收据",
      "p.fare": "车费",
      "p.tip_line": "小费",
      "p.total": "合计",
      "p.vehicle": "🚙 车辆：",
      "p.ratings": "⭐{a}（{c}评）",
      "p.driver_phone": "📞 司机电话：",
      "p.driver_loc_loading": "📍 司机位置加载中…",
      "p.driver_loc_none": "📍 司机暂未共享位置",
      "p.driver_loc": "📍 司机位置（{w}更新）· <a href=\"{u}\" target=\"_blank\">看路线和预计到达时间</a>",
      "p.just_now": "刚刚",
      "p.min_ago": "{m} 分钟前",
      "p.rated": "⭐ 你给了 {s} 星",
      "p.rate_driver": "给司机打分：",
      "p.rate_tags": "选几个标签（可选，最多 3 个）：",
      "p.submit": "提交",
      "p.stops": "📍 经停：",
      "p.booked_for": "🧑‍🤝‍🧑 代叫：",

      "flight.label": "航班号（可选）",
      "flight.ph": "UA 857",
      "flight.hint": "机场接送可填；落地发现晚点，可直接在订单里延后预约时间。",
      "flight.show": "✈️ 航班：",
      "flight.delay": "✈️ 航班晚点",
      "flight.delay_unit": "分钟",
      "flight.delay_q": "航班晚点 {m} 分钟，预约时间延后 {m} 分钟？",
      "flight.delayed_ok": "✓ 已延后 {m} 分钟，司机已收到通知",

      "notes.title": "📝 熟客便签",
      "notes.add": "添加便签",
      "notes.save": "保存",
      "notes.saving": "保存中…",
      "notes.saved": "✓ 已保存",
      "notes.deleted": "✓ 已删除",
      "notes.ph": "如：张阿姨晕车，开慢点；李叔爱听戏曲",
      "notes.clear_hint": "清空后保存即删除这条便签",

      "rebook.btn": "🔁 再来一单",
      "rebook.confirm": "用相同的线路和价格再来一单？",
      "rebook.ok": "✓ 已重新下单（现在用车），新订单在列表最上方",

      "d.title": "司机接单",
      "d.invite": "司机邀请码",
      "d.invite_hint": "你是乘客身份。输入司机邀请码即可成为司机、查看并接受订单。",
      "d.invite_ph": "8 位邀请码",
      "d.redeem": "兑换",
      "d.need_code": "请输入邀请码",
      "d.became_driver": "✓ 已成为司机",
      "d.duty": "接单状态",
      "d.online": "🟢 在线接单中",
      "d.offline": "🔴 休息中（不接新单）",
      "d.toggle": "切换",
      "d.duty_hint": "休息时切换为离线，新订单不会再推送给你。",
      "d.earnings": "收入统计",
      "d.d7": "近 7 天",
      "d.d30": "近 30 天",
      "d.loading": "加载中…",
      "d.earn_line": "完成 {c} 单 · 车费 {f} · 小费 {tp} · 合计 {tt}{r}",
      "d.vehicle": "我的车辆",
      "d.v_model": "车型",
      "d.v_model_ph": "例如：Toyota Sienna",
      "d.v_seats": "座位数",
      "d.v_plate": "车牌",
      "d.v_plate_ph": "例如：8ABC123",
      "d.save_vehicle": "保存车辆信息",
      "d.need_vehicle": "请至少填写车型或车牌",
      "d.saving": "保存中…",
      "d.saved": "✓ 已保存，乘客在进行中的订单里能看到你的车",
      "d.rating_line": "⭐ 平均 {a} 分（{c} 条评价）{tags}",
      "d.rating_tags": " · 乘客常夸：{t}",
      "d.loc_denied": "⚠️ 位置权限被拒，乘客看不到你的实时位置",
      "d.loc_sharing": "📍 正在共享位置给乘客",
      "d.open": "待接订单",
      "d.open_count": "{n} 单待接",
      "d.no_open": "暂无待接订单",
      "d.no_open_sub": "有新订单会实时出现在这里",
      "d.accept": "接单",
      "d.mine": "我的行程",
      "d.mine_count": "{n} 单进行中",
      "d.no_mine": "暂无进行中的行程",
      "d.nav_trip": "导航行程路线",
      "d.nav_pickup": "导航到上车点",
      "d.quote_ph": "报价 $",
      "d.quote": "报价",
      "d.need_quote": "请填写报价",
      "d.quoted_wait": "⏳ 已报价 {p}，等乘客确认",
      "d.hourly_hours": "包车单：请输入实际服务小时数（0.5–24，支持小数，0.5 小时向上取整）",
      "d.hourly_hours_bad": "小时数须在 0.5–24 之间",
      "d.cancel": "退回订单",
      "d.confirm_cancel": "去不了这单？订单会退回给其他司机接，乘客不用重新下单。",
      "d.passenger": "📞 乘客：",

      "tr.title": "行程分享",
      "tr.loading": "加载中…",
      "tr.note": "此链接由乘客分享，仅显示行程状态和司机位置，不含乘客隐私信息。",
      "tr.bad_link": "链接无效：缺少分享 token。",
      "tr.fail": "加载失败",
      "tr.map": "在地图上看",
      "tr.driver_loc": "📍 司机位置（{w}更新）· <a href=\"{u}\" target=\"_blank\">在地图上看</a>",

      "pp.title": "隐私政策",
      "pp.h1": "我们收集什么",
      "pp.p1": "为完成叫车服务，我们收集：手机号码或邮箱（用于登录与通知）、上车/下车地址、行程时间与价格、付款所需的卡片信息（由 Stripe 安全处理，我们不存储完整卡号）。",
      "pp.h2": "信息如何使用",
      "pp.p2": "仅用于：撮合订单、联系乘客与司机、发送行程通知、完成付款。除法律要求外，不出售、不共享给第三方营销。",
      "pp.h3": "谁能看到您的联系方式",
      "pp.p3": "您的电话/邮箱仅对接单的司机、您本人和平台管理员可见。订单完成或取消后，司机端不再显示您的联系方式。",
      "pp.h4": "数据安全",
      "pp.p4": "登录凭证加密存储，敏感接口仅限授权用户访问。如发现账号异常请立即联系我们。",
      "pp.h5": "联系我们",
      "pp.p5": "如需查看、更正或删除您的个人信息，请通过站内联系方式与我们联系。",
      "pp.updated": "更新日期：2026-10-04",

      "tm.title": "服务条款",
      "tm.intro": "欢迎使用私人专车预约服务。使用本服务即表示您同意以下条款。",
      "tm.h1": "1. 服务内容",
      "tm.p1": "本服务为乘客与司机之间的行程预约撮合平台。行程由注册司机实际承运，价格、时间以双方在订单中确认为准。",
      "tm.h2": "2. 订单与取消",
      "tm.p2": "司机接单后如需取消，请尽早通过电话或短信联系乘客。乘客在司机出发前取消不收费；司机到达后取消或爽约，平台保留收取取消费用的权利。",
      "tm.h3": "3. 付款",
      "tm.p3": "支持线下当面付款与线上付款。线上付款在行程完成后按最终确认价格扣款。扣款失败时请联系客服人工处理。",
      "tm.h4": "4. 用户责任",
      "tm.p4": "请提供真实准确的联系方式与上车信息。乘车时请遵守法律法规，系好安全带。",
      "tm.h5": "5. 责任限制",
      "tm.p5": "行程中的意外与纠纷由承运方依法承担相应责任。平台仅提供信息撮合与技术支持。",
      "tm.h6": "6. 条款变更",
      "tm.p6": "本条款可能不时更新，继续使用即视为接受更新后的条款。",
      "tm.updated": "更新日期：2026-10-04"
    },
    en: {
      "meta.title.index": "Private Ride",
      "meta.title.passenger": "Passenger · Private Ride",
      "meta.title.driver": "Driver · Private Ride",
      "meta.title.track": "Shared Ride · Private Ride",
      "meta.title.privacy": "Privacy Policy · Private Ride",
      "meta.title.terms": "Terms of Service · Private Ride",

      "brand.name": "Private Ride",

      "nav.switch": "Switch role",
      "nav.signout": "Sign out",
      "nav.home": "Home",
      "nav.account": "Account",

      "acct.title": "Account Settings",
      "acct.profile": "My Profile",
      "acct.phone": "Phone",
      "acct.email": "Email",
      "acct.role": "Role",
      "acct.role.passenger": "Passenger",
      "acct.role.driver": "Driver",
      "acct.role.admin": "Admin",
      "acct.name": "Nickname",
      "acct.name_ph": "Enter nickname",
      "acct.save": "Save",
      "acct.saved": "Saved",
      "acct.language": "Language",
      "acct.danger": "Danger Zone",
      "acct.signout": "Sign out",
      "acct.signout_done": "Signed out",
      "acct.delete": "Delete account",
      "acct.delete_warn": "Deleting will remove your account, saved places and share links. Ride records are kept anonymized. This cannot be undone.",
      "acct.delete_confirm1": "Delete your account? This cannot be undone.",
      "acct.delete_confirm2": "Final confirmation: really delete?",
      "acct.deleted": "Account deleted",
      "acct.loading": "Loading…",
      "acct.login_required": "Please sign in first",

      "index.kicker": "Family & friends · Private rides",
      "index.hero1": "One-tap booking",
      "index.hero2": "Driver on the way",
      "index.hero_sub": "A TCP-licensed private fleet for family and friends.<br />Web and app share the same backend.",
      "index.rider_t": "I'm a rider",
      "index.rider_s": "Enter pickup & drop-off, book in one tap, track live",
      "index.driver_t": "I'm a driver",
      "index.driver_s": "See open orders, accept in one tap, manage the whole trip",

      "status.requested": "Awaiting driver",
      "status.accepted": "Driver accepted",
      "status.en_route": "Driver en route",
      "status.arrived": "Driver arrived",
      "status.in_progress": "In progress",
      "status.completed": "Completed",
      "status.cancelled": "Cancelled",

      "next.head_to_pickup": "Head to pickup",
      "next.arrived_pickup": "Arrived at pickup",
      "next.start_trip": "Start trip",
      "next.complete_trip": "Complete trip",

      "price.offer": "Passenger offer {p}",
      "price.mileage": "Mileage rate {p} (about {m} mi)",
      "price.quoted_agreed": "Confirmed {p}",
      "price.quoted_pending": "Driver quote {p} (pending)",
      "price.waiting_quote": "Waiting for driver quote",
      "price.hourly": "Charter {p}/hour",
      "price.hourly_done": "Charter {p}",

      "pay.offline": "Pay in person",
      "pay.online": "Online payment",
      "pay.paid": "Charged",
      "pay.failed": "Charge failed",
      "pay.pending": "Pending charge",

      "card.now": "Ride now",

      "auth.signin_aria": "Sign in",
      "auth.tab_phone": "Phone sign-in",
      "auth.tab_email": "Email sign-in",
      "auth.ph_phone": "Phone, e.g. 6268660555",
      "auth.ph_email": "Email, e.g. you@gmail.com",
      "auth.ph_code": "Code",
      "auth.aria_phone": "Phone number",
      "auth.aria_email": "Email",
      "auth.aria_code": "Verification code",
      "auth.get_code": "Get code",
      "auth.login": "Sign in",
      "auth.slogan": "Every ride, at ease",
      "auth.need_phone": "Enter your phone number first",
      "auth.need_email": "Enter your email first",
      "auth.dev_code": "Dev mode code: {code}",
      "auth.code_sent": "Code sent",

      "api.fail": "Request failed {s}",

      "p.title": "Book a ride",
      "p.book": "Book a ride",
      "p.driver_checking": "Checking driver status…",
      "p.no_driver": "No driver info",
      "p.online": "Online",
      "p.offline": "Offline",
      "p.pickup": "Pickup",
      "p.pickup_ph": "e.g. home gate",
      "p.dropoff": "Drop-off",
      "p.dropoff_ph": "e.g. Rowland Heights 99 Ranch",
      "p.add_stop": "+ Add stop (max 3)",
      "p.stop_ph": "Stop {n} (optional)",
      "p.seats": "Riders",
      "p.when": "Pickup time",
      "p.note": "Notes (optional)",
      "p.note_ph": "e.g. large luggage, kids",
      "p.book_other": "🧑‍🤝‍🧑 Book for someone else (optional)",
      "p.rider_name": "Rider name",
      "p.rider_name_ph": "e.g. Mom",
      "p.rider_phone": "Rider phone",
      "p.rider_phone_ph": "For the driver to reach them",
      "p.pricing": "Pricing",
      "p.mode_offer": "I'll offer",
      "p.mode_mileage": "By mileage",
      "p.mode_quote": "Driver quotes",
      "p.offer_label": "Your offer (USD)",
      "p.offer_ph": "e.g. 25",
      "p.miles_label": "Estimated miles",
      "p.miles_ph": "e.g. 10",
      "p.mileage_base": "Base $8 + $3/mi",
      "p.mileage_est": "Est. {e} (base $8 + $3/mi)",
      "p.quote_hint": "The driver quotes after accepting — you confirm.",
      "p.mode_hourly": "Hourly charter",
      "p.hourly_label": "Hourly rate (USD)",
      "p.hourly_ph": "e.g. 80",
      "p.need_hourly": "Enter the hourly rate",
      "p.payment": "Payment",
      "p.pay_offline": "Pay in person",
      "p.pay_online": "Pay online",
      "p.card_na": "Online payment isn't set up yet — please pay in person",
      "p.card_onfile": "Card on file: {b} ****{l}",
      "p.card_none": "No card yet — add one for online payment",
      "p.bind_card": "Link this card",
      "p.binding": "Linking…",
      "p.bound": "✓ Linked {b} ****{l}",
      "p.book_now": "Book ride",
      "p.need_places": "Enter pickup and drop-off",
      "p.need_offer": "Enter your offer",
      "p.need_miles": "Enter estimated miles",
      "p.booked_ok": "✓ Booked — waiting for a driver",
      "p.places": "Saved places",
      "p.places_empty": "No saved places yet — add one below (e.g. Home, Noodle shop).",
      "p.place_label_ph": "Name, e.g. Home",
      "p.place_addr_ph": "Address",
      "p.save": "Save",
      "p.set_pickup": "Set as pickup",
      "p.set_dropoff": "Set as drop-off",
      "p.del": "Delete",
      "p.del_place": "Delete this saved place?",
      "p.need_place_fields": "Enter a name and address",
      "p.my_rides": "My rides",
      "p.rides_count": "{n} rides",
      "p.no_rides": "No rides yet",
      "p.no_rides_sub": "Fill in your trip above and book in one tap",
      "p.cancel_ride": "Cancel ride",
      "p.confirm_cancel": "Cancel this ride?",
      "p.quote_accept_q": "Driver quoted {p}. Accept?",
      "p.accept": "Accept {p}",
      "p.decline": "Decline",
      "p.decline_q": "Decline? The ride reopens and the driver can quote again.",
      "p.tip_q": "Tip {p}?",
      "p.tip": "Tip:",
      "p.tip_other": "Other",
      "p.tip_prompt": "Tip amount (USD, min $1):",
      "p.tip_min": "Minimum $1",
      "p.tipped": "💰 Tipped {p}",
      "p.share": "🔗 Share trip with family",
      "p.share_copied": "Share link copied (valid 7 days):\n{url}",
      "p.nudge": "📣 Nudge driver",
      "p.nudged": "Driver nudged — on the way",
      "p.receipt": "🧾 Receipt",
      "p.receipt_title": "Trip receipt",
      "p.fare": "Fare",
      "p.tip_line": "Tip",
      "p.total": "Total",
      "p.vehicle": "🚙 Vehicle:",
      "p.ratings": "⭐{a} ({c} ratings)",
      "p.driver_phone": "📞 Driver:",
      "p.driver_loc_loading": "📍 Loading driver location…",
      "p.driver_loc_none": "📍 Driver isn't sharing location",
      "p.driver_loc": "📍 Driver location (updated {w}) · <a href=\"{u}\" target=\"_blank\">route & ETA</a>",
      "p.just_now": "just now",
      "p.min_ago": "{m} min ago",
      "p.rated": "⭐ You rated {s}",
      "p.rate_driver": "Rate your driver:",
      "p.rate_tags": "Pick tags (optional, up to 3):",
      "p.submit": "Submit",
      "p.stops": "📍 Stops:",
      "p.booked_for": "🧑‍🤝‍🧑 For:",

      "flight.label": "Flight number (optional)",
      "flight.ph": "UA 857",
      "flight.hint": "For airport rides — if your flight is late, push the pickup time back right from the order.",
      "flight.show": "✈️ Flight: ",
      "flight.delay": "✈️ Flight delayed",
      "flight.delay_unit": "min",
      "flight.delay_q": "Flight delayed {m} min — push pickup time back {m} min?",
      "flight.delayed_ok": "✓ Pushed back {m} min — driver notified",

      "notes.title": "📝 Rider notes",
      "notes.add": "Add note",
      "notes.save": "Save",
      "notes.saving": "Saving…",
      "notes.saved": "✓ Saved",
      "notes.deleted": "✓ Deleted",
      "notes.ph": "e.g. Mrs. Zhang gets carsick — drive slowly; Mr. Li loves opera",
      "notes.clear_hint": "Save empty to delete this note",

      "rebook.btn": "🔁 Book again",
      "rebook.confirm": "Book the same route and price again?",
      "rebook.ok": "✓ Rebooked (ride now) — the new order is at the top",

      "d.title": "Drive",
      "d.invite": "Driver invite code",
      "d.invite_hint": "You're signed in as a rider. Enter a driver invite code to accept orders.",
      "d.invite_ph": "8-character code",
      "d.redeem": "Redeem",
      "d.need_code": "Enter the invite code",
      "d.became_driver": "✓ You're now a driver",
      "d.duty": "Duty status",
      "d.online": "🟢 Online — accepting rides",
      "d.offline": "🔴 Offline — not taking rides",
      "d.toggle": "Toggle",
      "d.duty_hint": "Go offline when resting — new orders stop here.",
      "d.earnings": "Earnings",
      "d.d7": "Last 7 days",
      "d.d30": "Last 30 days",
      "d.loading": "Loading…",
      "d.earn_line": "{c} trips · Fares {f} · Tips {tp} · Total {tt}{r}",
      "d.vehicle": "My vehicle",
      "d.v_model": "Vehicle",
      "d.v_model_ph": "e.g. Toyota Sienna",
      "d.v_seats": "Seats",
      "d.v_plate": "Plate",
      "d.v_plate_ph": "e.g. 8ABC123",
      "d.save_vehicle": "Save vehicle",
      "d.need_vehicle": "Enter a vehicle model or plate",
      "d.saving": "Saving…",
      "d.saved": "✓ Saved — riders see it on active trips",
      "d.rating_line": "⭐ {a} avg ({c} reviews){tags}",
      "d.rating_tags": " · Riders often say: {t}",
      "d.loc_denied": "⚠️ Location denied — riders can't see you live",
      "d.loc_sharing": "📍 Sharing live location with riders",
      "d.open": "Open orders",
      "d.open_count": "{n} open",
      "d.no_open": "No open orders",
      "d.no_open_sub": "New orders appear here live",
      "d.accept": "Accept",
      "d.mine": "My trips",
      "d.mine_count": "{n} active",
      "d.no_mine": "No active trips",
      "d.nav_trip": "Navigate trip",
      "d.nav_pickup": "Navigate to pickup",
      "d.quote_ph": "Quote $",
      "d.quote": "Quote",
      "d.need_quote": "Enter a quote",
      "d.quoted_wait": "⏳ Quoted {p} — waiting for rider",
      "d.hourly_hours": "Charter ride: enter actual service hours (0.5–24, decimals allowed, rounds up to 0.5h)",
      "d.hourly_hours_bad": "Hours must be between 0.5 and 24",
      "d.cancel": "Release ride",
      "d.confirm_cancel": "Can't make it? The ride goes back to the queue for other drivers.",
      "d.passenger": "📞 Rider:",

      "tr.title": "Shared ride",
      "tr.loading": "Loading…",
      "tr.note": "Shared by the rider — trip status and driver location only, no rider personal info.",
      "tr.bad_link": "Invalid link: missing share token.",
      "tr.fail": "Failed to load",
      "tr.map": "View on map",
      "tr.driver_loc": "📍 Driver location (updated {w}) · <a href=\"{u}\" target=\"_blank\">View on map</a>",

      "pp.title": "Privacy Policy",
      "pp.h1": "What we collect",
      "pp.p1": "To provide rides, we collect: your phone number or email (for sign-in and notifications), pickup and drop-off addresses, trip times and fares, and card details for payment (handled securely by Stripe — we never store full card numbers).",
      "pp.h2": "How we use it",
      "pp.p2": "Used only to: match orders, connect riders and drivers, send trip notifications, and process payments. Never sold or shared with third-party marketers, except as required by law.",
      "pp.h3": "Who can see your contact info",
      "pp.p3": "Your phone/email is visible only to the driver who accepted your ride, to you, and to platform admins. After a trip is completed or cancelled, drivers can no longer see your contact info.",
      "pp.h4": "Data security",
      "pp.p4": "Sign-in credentials are stored encrypted, and sensitive endpoints are restricted to authorized users. Contact us immediately if you notice anything unusual with your account.",
      "pp.h5": "Contact us",
      "pp.p5": "To view, correct, or delete your personal info, reach us through the contact options on this site.",
      "pp.updated": "Updated: 2026-10-04",

      "tm.title": "Terms of Service",
      "tm.intro": "Welcome to Private Ride. By using this service you agree to the terms below.",
      "tm.h1": "1. What this service is",
      "tm.p1": "This service connects riders with drivers for trip bookings. Registered drivers fulfill the trips; price and timing are as agreed in the order.",
      "tm.h2": "2. Orders & cancellation",
      "tm.p2": "If a driver must cancel after accepting, please call or text the rider ASAP. Riders cancel free before the driver heads out; after arrival, we may charge a cancellation fee for no-shows.",
      "tm.h3": "3. Payment",
      "tm.p3": "Pay in person or online. Online payments are charged after the trip at the confirmed final price. If a charge fails, contact support and we'll sort it out.",
      "tm.h4": "4. Your responsibilities",
      "tm.p4": "Please provide accurate contact and pickup info. Follow local laws on every ride — and buckle up.",
      "tm.h5": "5. Liability",
      "tm.p5": "The carrier is liable for incidents and disputes during a trip as required by law. The platform provides matching and tech support only.",
      "tm.h6": "6. Changes",
      "tm.p6": "These terms may be updated from time to time; continued use means you accept the latest version.",
      "tm.updated": "Updated: 2026-10-04"
    }
  };

  var KEY = "pr_lang";
  var lang = "zh";

  function detect() {
    try {
      var saved = localStorage.getItem(KEY);
      if (saved === "zh" || saved === "en") return saved;
    } catch (e) { /* ignore */ }
    try {
      if (String(navigator.language || "").toLowerCase().indexOf("en") === 0) return "en";
    } catch (e) { /* ignore */ }
    return "zh";
  }
  lang = detect();

  /* 取文案：t("key") / t("key", {name: "x"})；缺 key 时回退中文，再缺则原样返回 key */
  function t(key, vars) {
    var d = DICT[lang] || {};
    var s = d[key];
    if (s == null) s = (DICT.zh || {})[key];
    if (s == null) return key;
    if (vars) {
      s = String(s).replace(/\{(\w+)\}/g, function (_, k) {
        return vars[k] != null ? vars[k] : "{" + k + "}";
      });
    }
    return s;
  }

  function dateLocale() { return lang === "en" ? "en-US" : "zh-CN"; }
  function prLang() { return lang; }

  function statusLabel(s) {
    var v = t("status." + s);
    return v === "status." + s ? s : v;
  }

  function riders(n) {
    n = +n || 0;
    if (lang === "en") return n === 1 ? "1 rider" : n + " riders";
    return n + " 人";
  }

  function nextStatus(status) {
    var m = {
      accepted: ["en_route", t("next.head_to_pickup")],
      en_route: ["arrived", t("next.arrived_pickup")],
      arrived: ["in_progress", t("next.start_trip")],
      in_progress: ["completed", t("next.complete_trip")]
    };
    return m[status];
  }

  function applyI18n() {
    try { document.documentElement.lang = lang === "en" ? "en" : "zh-CN"; } catch (e) {}
    var apply = function (sel, fn) {
      var els;
      try { els = document.querySelectorAll(sel); } catch (e) { return; }
      for (var i = 0; i < els.length; i++) { try { fn(els[i]); } catch (e) {} }
    };
    apply("[data-i18n]", function (el) { el.textContent = t(el.getAttribute("data-i18n")); });
    apply("[data-i18n-html]", function (el) { el.innerHTML = t(el.getAttribute("data-i18n-html")); });
    apply("[data-i18n-ph]", function (el) { el.setAttribute("placeholder", t(el.getAttribute("data-i18n-ph"))); });
    apply("[data-i18n-aria]", function (el) { el.setAttribute("aria-label", t(el.getAttribute("data-i18n-aria"))); });
    apply(".lang-toggle", function (b) {
      b.textContent = lang === "en" ? "中文" : "EN";
      b.setAttribute("aria-label", lang === "en" ? "Switch to Chinese" : "Switch to English");
    });
    try { window.dispatchEvent(new CustomEvent("pr:langchange", { detail: { lang: lang } })); } catch (e) {}
  }

  function setLang(l) {
    if (l !== "zh" && l !== "en") return;
    lang = l;
    try { localStorage.setItem(KEY, l); } catch (e) {}
    applyI18n();
  }

  function toggleLang() { setLang(lang === "en" ? "zh" : "en"); }

  /* 切换按钮用事件委托，动态加入的也生效 */
  if (typeof document !== "undefined" && document.addEventListener) {
    document.addEventListener("click", function (e) {
      var b = e.target && e.target.closest ? e.target.closest(".lang-toggle") : null;
      if (b) { if (e.preventDefault) e.preventDefault(); toggleLang(); }
    });
  }

  var api = { t: t, setLang: setLang, toggleLang: toggleLang, prLang: prLang,
    dateLocale: dateLocale, statusLabel: statusLabel, riders: riders,
    nextStatus: nextStatus, applyI18n: applyI18n, dict: DICT };
  window.I18N = api;
  /* 给页面内联脚本用的全局快捷方式 */
  window.t = t;
  window.prLang = prLang;
  window.dateLocale = dateLocale;
  window.statusLabel = statusLabel;
  window.riders = riders;
  window.nextStatus = nextStatus;

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", applyI18n);
    } else {
      applyI18n();
    }
  }
})();
