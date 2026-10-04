# private-ride — 私人专车 App 技术规划

> ✅ **更新（2026-10-03）：hao 爸爸持有加州 TCP 牌照，法律 blocker 已清除。** 以下风险说明保留作记录，项目可正常推进收费运营。

> ⚠️ **法律风险提醒（先读这段）**
>
> 在加州，没有 TCP（Transportation Charter-Party）牌照、用 App 调度并收取费用的载客行为属于**非法营运**。CPUC 可处以罚款、扣车；出事故时个人车险通常拒赔营运期间的损失。
>
> - 牌照：向 CPUC 申请 TCP permit，申请费约 $1,000；要求 commercial liability 保额至少 $100 万（保额≠保费，实际保费约 $2,000–6,000/车/年）。
> - Uber 司机是挂在 Uber 的 TCP 下开的；**脱离 Uber 自己接单必须自己持牌**。
> - 本规划只覆盖技术工作，不构成法律建议；上线前请咨询持牌律师 / 熟悉 TCP 的保险经纪。
> - 灰色地带提示：纯熟人免费搭车分摊油费与"收费营运"的界限由执法认定，不要自己脑补豁免。
>
> 技术工作不被这段阻断，但 App 公开发布/收费运营前必须解决牌照问题。

---

## 1. 项目一句话

给爸爸（Uber Escalade 专车司机）+ 几个司机朋友 + 熟客的小圈子约车工具：乘客下单、司机抢单、全程状态跟踪、中文界面。第一版**不做应用内支付**——乘客线下直接付司机（现金 / Zelle / 微信）。

## 2. MVP 范围（v0.1）

**三端共用同一个 FastAPI 后端**：`mobile/`（Expo App，上架用）+ `web/`（手机浏览器直接打开，免安装，熟客先用这个）。

### 网页版（web/，静态页面 + 直调 API）
- [ ] 中文界面，手机浏览器打开即用（`https://ride.haocoach.com/web/`）
- [ ] 乘客：手机号登录 → 下单（上车点/下车点/时间/人数/备注）→ 看订单状态 → 取消
- [ ] 司机：手机号登录 → 待接订单池抢单 → 推进状态（出发/到达/开始/完成）
- [ ] 免构建：纯 HTML/CSS/JS，后端直接托管静态文件，改完即生效

### 乘客端（App，下单为主）
- [ ] 手机号注册/登录（短信验证码；第一版可用测试码跳过）
- [ ] 下单：上车点、下车点（地址输入 + 地图选点二期）、用车时间（现在 / 预约）、人数、备注
- [ ] 订单状态实时看：待接单 → 司机已接单 → 司机正在来 → 已到达 → 行程中 → 已完成 / 已取消
- [ ] 推送通知：司机接单、司机到达
- [ ] 历史订单列表

### 司机端
- [ ] 司机资料：姓名、车型（如 Cadillac Escalade）、车牌、座位数
- [ ] 待接订单池：看到所有待接单，抢单（先到先得）
- [ ] 我的行程：接单后更新状态（出发 → 到达 → 开始行程 → 完成）
- [ ] 推送通知：新订单、乘客取消

### 明确不做（v0.1）
- 应用内支付 / 计价 / 抽成
- 实时地图车辆轨迹（用状态 + 电话/短信兜底）
- 评分系统、客服工单
- 多语言（只做简体中文）

## 3. 技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| App | **Expo + React Native** | 一套代码同时出 iOS + Android；hao 熟悉 JS；Expo Push 免费 |
| 后端 | **Python FastAPI** | hao 熟悉 Python；异步、文档自动生成 |
| 数据库 | **Postgres via Neon**（本地开发用 SQLite） | Serverless Postgres，免费 tier 够小圈子；SQLAlchemy 切换只需改 `DATABASE_URL` |
| ORM | SQLAlchemy 2.0 |  |
| 推送 | **Expo Push Notifications** | 后端调 Expo HTTP API 按 push token 发，免费 |
| 登录 | 手机号 + 短信验证码（二期）；v0.1 用可配置测试码 |  |

### 备选（现在不用，记下来）
- 地图/路线：Google Maps SDK（要绑信用卡）→ 二期再说
- 短信：Twilio（有免费试用额度）

## 4. 数据模型

```
users              乘客+司机都在这张表（role 区分）
  id            UUID PK
  phone         唯一，登录用
  name
  role          passenger | driver | admin
  push_token    Expo push token（登录/刷新时上报）
  created_at

drivers            司机扩展信息（users.role='driver' 才有）
  user_id       FK → users.id
  vehicle_model 如 "Cadillac Escalade"
  plate         车牌
  seats         座位数
  is_active     是否接单中

rides              订单
  id            UUID PK
  passenger_id  FK → users.id
  driver_id     FK → users.id（可空，待接单时）
  pickup_text / pickup_lat / pickup_lng
  dropoff_text / dropoff_lat / dropoff_lng
  scheduled_at  预约时间（可空=现在用车）
  seats_needed
  note
  status        requested → accepted → en_route → arrived
                → in_progress → completed | cancelled
  created_at / updated_at
```

状态机规则：只有接单司机能推进自己订单的状态；乘客只能取消 `requested` 状态的单。

## 5. API 草稿（v0.1）

```
POST /auth/request-code   {phone} → 发验证码（v0.1 返回测试码）
POST /auth/verify         {phone, code} → {token, user}
GET  /me                  当前用户
PUT  /me/push-token       上报 Expo push token
PATCH /users/{id}/role    管理员改用户角色（v0.1 暂不鉴权，生产需收紧）

POST /rides               下单
GET  /rides?mine=1        我的订单（乘客：我下的；司机：我接的）
GET  /rides/open          待接订单池（司机）
POST /rides/{id}/accept   抢单（司机，先到先得，DB 锁防并发）
POST /rides/{id}/status   {status} 推进状态
POST /rides/{id}/cancel   取消

WebSocket /ws/rides/{id}  二期：状态实时推送（v0.1 用轮询+推送通知）
```

认证：Bearer JWT（python-jose），有效期 30 天。

## 6. 推送方案（Expo Push）

1. App 启动后 `Notifications.getExpoPushTokenAsync()` 拿 token，上报 `PUT /me/push-token`。
2. 后端在关键事件（接单、到达、取消）调 `https://exp.host/--/api/v2/push/send` 发通知。
3. 中文文案写死在后端模板里。

## 7. 上架清单

### Apple App Store（$99/年）
- [ ] 注册 Apple Developer Program（$99/年，按年续）
- [ ] Bundle ID：建议 `com.haocoach.privateride`（或你爸公司名）
- [ ] 隐私政策 URL（必须，审核会查；放 haocoach.com 一个静态页就行）
- [ ] 审核注意 4.2（最低功能）：小圈子 App 易被以"功能太简单/受众过小"打回——**先走 TestFlight 内测**（100 人内免完整审核），熟客圈子够用了
- [ ] 提供测试账号给审核员（审核备注里写）
- [ ] 位置权限：v0.1 只用地址文本，**不要申请定位权限**（少一个被拒理由）；二期要轨迹再加

### Google Play（$25 一次性）
- [ ] 注册 Google Play Console（$25 一次性）
- [ ] **新个人账号强制要求**：正式发布前跑 14 天封闭测试 + 至少 12 名测试人员——规划进时间表
- [ ] 目标 API 级别跟随当年要求（2026 年应为 API 35+）
- [ ] 同样先走内部测试轨道（internal testing），不经完整审核

### 上架前技术准备
- [ ] App 图标、启动屏（Expo config 里配）
- [ ] EAS Build 出包（`eas build`），不用自己配 Xcode/Android Studio
- [ ] 后端部署：Neon 数据库 + API 域名 `ride.haocoach.com`（haocoach.com 现有域名的子域名，**不用新买域名**；Cloudflare tunnel 方案，之前 FitLog 用过同一套），HTTPS 经 Cloudflare
- [ ] DNS：在 Cloudflare 给 haocoach.com 加 `ride` 子域名的 tunnel 记录（参考现有 `app.`/`mcp.` 记录的做法）
- [ ] 网页版随后端一起部署（`/web/`），乘客不用装 App 也能约车

## 8. 里程碑

1. **M1 脚手架**（本周）：后端 healthcheck + 用户模型跑通；Expo 空壳双角色入口可跑 —— ✅ 完成
2. **M2 认证+下单**：短信码登录、乘客下单、司机抢单 API + 界面 —— ✅ 完成（dev 验证码模式）
3. **M3 状态+推送**：状态机、Expo Push、中文文案 —— ✅ 完成（2026-10-03：`backend/app/push.py` 新订单自动推送全部司机，DriverHome 登录后注册上报 push token；5 个推送单元测试全过；真机链路用 Expo 官方 API 验证通过）
4. **M4 内测**：TestFlight + Play 内部测试，爸爸+朋友真机跑一周
5. **M5 牌照**：~~TCP 申请提交~~ → 已持有，无需申请（2026-10-03 确认）

部署准备（2026-10-03）：`backend/DEPLOY.md` + `deploy/private-ride.service`（systemd）
+ `deploy/cloudflared-config.yml`（ride.haocoach.com 模板）；requirements 已锁定版本；
`.env.example` 补齐生产变量。未动线上 DNS/Cloudflare。

## 9. 本地运行

```bash
# 后端
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# 健康检查：curl localhost:8000/health

# 前端
cd mobile
npm install
npx expo start          # 扫码用 Expo Go 真机预览
```

后端默认 SQLite（`./dev.db`）；生产切 Neon：`DATABASE_URL=postgresql+psycopg://... uvicorn app.main:app`。
