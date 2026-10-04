/** Expo 推送注册：拿 ExpoPushToken 并上报后端。
 *
 *  注意：真机才能拿到 token（模拟器/Expo Go 在模拟器上返回 null）。
 *  后端只给 role=driver/admin 且上报过 token 的用户推送新订单。
 */
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import Constants from "expo-constants";
import { Platform } from "react-native";
import { api } from "./api";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

export async function registerForPushNotificationsAsync() {
  if (!Device.isDevice) {
    console.log("[push] 非真机，跳过推送注册");
    return null;
  }

  const { status: existing } = await Notifications.getPermissionsAsync();
  let status = existing;
  if (status !== "granted") {
    const { status: asked } = await Notifications.requestPermissionsAsync();
    status = asked;
  }
  if (status !== "granted") {
    console.log("[push] 用户拒绝了通知权限");
    return null;
  }

  const projectId =
    Constants.expoConfig?.extra?.eas?.projectId ??
    Constants.easConfig?.projectId;
  const { data: token } = await Notifications.getExpoPushTokenAsync(
    projectId ? { projectId } : undefined
  );

  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync("default", {
      name: "订单通知",
      importance: Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 250, 250, 250],
    });
  }

  // 上报后端（需要已登录，api 会带上 Bearer token）
  await api.setPushToken(token);
  console.log("[push] 已上报 push token");
  return token;
}
