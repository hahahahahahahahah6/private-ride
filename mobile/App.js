import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, SafeAreaView, StyleSheet, Text, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import * as Notifications from "expo-notifications";
import Login from "./src/screens/Login";
import PassengerHome from "./src/screens/PassengerHome";
import DriverHome from "./src/screens/DriverHome";
import MeScreen from "./src/screens/MeScreen";
import { api, loadToken, setAuthToken } from "./src/lib/api";
import { initI18n, useI18n } from "./src/lib/i18n";
import { registerForPushNotificationsAsync } from "./src/lib/push";
import { C } from "./src/lib/theme";

function TabBar({ tabs, tab, setTab }) {
  return (
    <View style={s.tabbar}>
      {tabs.map((x) => (
        <Pressable key={x.key} style={s.tab} onPress={() => setTab(x.key)}>
          <Text style={s.tabIcon}>{x.icon}</Text>
          <Text style={[s.tabText, tab === x.key && { color: C.gold }]}>{x.label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

export default function App() {
  const { t } = useI18n();
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState(null);
  const [tab, setTab] = useState("ride");
  const [pushOk, setPushOk] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const notifSub = useRef(null);

  // 启动：读语言 + 读上次的登录 token，有就直接进
  useEffect(() => {
    (async () => {
      await initI18n();
      const token = await loadToken();
      if (token) {
        try {
          const me = await api.me();
          setUser(me);
          if (me.role !== "passenger") setTab("drive");
        } catch (e) {
          if (e.status === 401) await setAuthToken(null);
        }
      }
      setReady(true);
    })();
  }, []);

  // 登录后注册推送；收到推送就刷新当前页面
  useEffect(() => {
    if (!user) return;
    registerForPushNotificationsAsync()
      .then((tok) => setPushOk(!!tok))
      .catch(() => setPushOk(false));
    notifSub.current = Notifications.addNotificationReceivedListener(() => setReloadKey((k) => k + 1));
    const tapSub = Notifications.addNotificationResponseReceivedListener((resp) => {
      const type = resp?.notification?.request?.content?.data?.type || "";
      setTab(type === "new_ride" ? "drive" : "ride");
      setReloadKey((k) => k + 1);
    });
    return () => {
      notifSub.current?.remove();
      tapSub.remove();
    };
  }, [user?.id]);

  const onLogin = useCallback((u) => {
    setUser(u);
    setTab(u.role === "passenger" ? "ride" : "drive");
  }, []);

  const onLogout = useCallback(async () => {
    await api.logout().catch(() => {});
    setUser(null);
  }, []);

  if (!ready) {
    return (
      <View style={[s.root, { justifyContent: "center" }]}>
        <ActivityIndicator color={C.gold} />
      </View>
    );
  }

  if (!user) {
    return (
      <View style={s.root}>
        <StatusBar style="light" />
        <Login onLogin={onLogin} />
      </View>
    );
  }

  const isDriver = user.role === "driver" || user.role === "admin";
  const tabs = [
    { key: "ride", icon: "🚕", label: t("tab.ride") },
    ...(isDriver ? [{ key: "drive", icon: "🧭", label: t("tab.drive") }] : []),
    { key: "me", icon: "👤", label: t("tab.me") },
  ];

  return (
    <SafeAreaView style={s.root}>
      <StatusBar style="light" />
      <View style={{ flex: 1 }}>
        {tab === "ride" ? <PassengerHome key={`p${reloadKey}`} /> : null}
        {tab === "drive" && isDriver ? <DriverHome key={`d${reloadKey}`} /> : null}
        {tab === "me" ? (
          <MeScreen user={user} onUser={setUser} onLogout={onLogout} pushOk={pushOk} />
        ) : null}
      </View>
      <TabBar tabs={tabs} tab={tab} setTab={setTab} />
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  tabbar: {
    flexDirection: "row",
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: C.line,
    backgroundColor: "#131313",
    paddingTop: 6,
    paddingBottom: 6,
  },
  tab: { flex: 1, alignItems: "center", paddingVertical: 4 },
  tabIcon: { fontSize: 20 },
  tabText: { color: C.muted, fontSize: 12, marginTop: 2, fontWeight: "600" },
});
