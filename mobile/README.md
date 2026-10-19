# 私人专车 手机 App（Expo）

乘客叫车 + 司机接单都在一个 App 里。登录后自动按身份显示：乘客只有「叫车」「我的」，司机多一个「接单」。

## 功能

- 手机号 / 邮箱验证码登录，登录状态会记住
- 乘客：叫车（现在或预约）、出价或等司机报价、看行程状态、打电话给司机、分享行程、取消、评分、再来一单
- 司机：在线/休息开关、待接订单、接单、出发 → 到达 → 开始 → 完成、报价、包车结算、导航、打电话、退回订单
- 行程中自动把司机位置报给乘客（App 开着时每 30 秒一次）
- 推送：新订单、司机接单/出发/到达、乘客取消等（真机才收得到）
- 中文 / English

## 本地跑起来（用 Expo Go 扫码）

```bash
cd mobile
npm install
EXPO_PUBLIC_API_URL=https://ride.haocoach.com npx expo start
```

手机装 Expo Go，扫终端里的二维码。连本机后端就把地址换成 `http://你电脑的局域网IP:8000`。

## 打包成真正的 App

需要一个免费的 Expo 账号（expo.dev）。

```bash
npm install -g eas-cli
eas login
eas init            # 第一次：会把 projectId 写进 app.json，推送需要它
```

**Android（不花钱）**：打一个 APK 直接发给爸爸和熟客装：

```bash
eas build -p android --profile preview
```

打完会给一个下载链接，手机打开就能装。

**iPhone**：要先交 Apple 开发者年费 $99。

```bash
eas build -p ios --profile production
eas submit -p ios          # 传到 TestFlight，熟客用 TestFlight 装
```

不想交钱的话，iPhone 用户先用网页版：Safari 打开 ride.haocoach.com，分享 → 添加到主屏幕，效果差不多。
