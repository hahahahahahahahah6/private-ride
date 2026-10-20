import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, Linking, Platform, RefreshControl, ScrollView, StyleSheet, Switch, Text, View } from "react-native";
import { api } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { C, money } from "../lib/theme";
import { Btn, Card, Field, H, Hint, RideCard } from "../components/ui";

// 状态按钮：当前状态 → [下一个状态, 按钮文案 key]
const NEXT = {
  accepted: ["en_route", "driver.go"],
  en_route: ["arrived", "driver.arrive"],
  arrived: ["in_progress", "driver.start"],
  in_progress: ["completed", "driver.finish"],
};

function mapsUrl(address) {
  const q = encodeURIComponent(address);
  return Platform.OS === "ios" ? `http://maps.apple.com/?daddr=${q}` : `https://www.google.com/maps/dir/?api=1&destination=${q}`;
}

export default function DriverHome() {
  const { t, lang } = useI18n();
  const [open, setOpen] = useState([]);
  const [mine, setMine] = useState([]);
  const [online, setOnline] = useState(true);
  const [quotes, setQuotes] = useState({});
  const [refreshing, setRefreshing] = useState(false);
  const [msg, setMsg] = useState("");
  const locTimer = useRef(null);

  const errText = (e) => (e.status === 0 ? t("common.netErr") : e.message);

  const load = useCallback(async () => {
    try {
      const [o, m] = await Promise.all([api.openRides(), api.myRides()]);
      setOpen(o);
      setMine(m.filter((r) => !["completed", "cancelled"].includes(r.status)));
      setMsg("");
    } catch (e) {
      setMsg(errText(e));
    }
  }, [lang]);

  useEffect(() => {
    load();
    api.getOnline().then((x) => setOnline(!!x.online)).catch(() => {});
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [load]);

  // 有进行中的单时，App 开着就每 30 秒上报一次位置给乘客看
  const onTrip = mine.some((r) => ["en_route", "arrived", "in_progress"].includes(r.status));
  useEffect(() => {
    let cancelled = false;
    async function tick() {
      try {
        const Location = await import("expo-location");
        const { status } = await Location.requestForegroundPermissionsAsync();
        if (status !== "granted" || cancelled) return;
        const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
        await api.sendLocation(pos.coords.latitude, pos.coords.longitude);
      } catch (e) {
        // 定位失败不打扰司机
      }
    }
    if (onTrip) {
      tick();
      locTimer.current = setInterval(tick, 30000);
    }
    return () => {
      cancelled = true;
      if (locTimer.current) clearInterval(locTimer.current);
    };
  }, [onTrip]);

  const act = async (fn) => {
    try {
      await fn();
      load();
    } catch (e) {
      Alert.alert(t("common.error"), errText(e));
    }
  };

  const toggleOnline = (v) => {
    setOnline(v);
    api.setOnline(v).catch(() => setOnline(!v));
  };

  const advance = (r) => {
    const [next] = NEXT[r.status];
    if (next === "completed" && r.price_mode === "hourly") {
      // 包车单：问实际小时数
      if (Alert.prompt) {
        Alert.prompt(t("driver.hours"), "", (h) => {
          const hours = parseFloat(h);
          if (hours > 0) act(() => api.finishHourly(r.id, hours));
        }, "plain-text", "", "decimal-pad");
      } else {
        const hours = parseFloat(quotes[r.id] || "");
        if (hours > 0) act(() => api.finishHourly(r.id, hours));
        else Alert.alert(t("driver.hours"));
      }
      return;
    }
    act(() => api.setRideStatus(r.id, next));
  };

  const release = (r) =>
    Alert.alert(t("driver.releaseConfirm"), "", [
      { text: t("common.cancel"), style: "cancel" },
      { text: t("driver.release"), style: "destructive", onPress: () => act(() => api.cancelRide(r.id)) },
    ]);

  const sendQuote = (r) => {
    const dollars = parseFloat(quotes[r.id] || "");
    if (!(dollars > 0)) return;
    act(() => api.quoteRide(r.id, Math.round(dollars * 100)));
  };

  const mineCard = (r) => {
    const needQuote =
      r.price_mode === "quote" &&
      ["accepted", "en_route", "arrived"].includes(r.status) &&
      !(r.price_status === "pending" && r.price_quote_cents != null) &&
      r.price_status !== "agreed";
    const waiting = r.price_mode === "quote" && r.price_status === "pending" && r.price_quote_cents != null;
    const needHours = r.price_mode === "hourly" && r.status === "in_progress" && !Alert.prompt;
    const target = ["accepted", "en_route"].includes(r.status) ? r.pickup_text : r.dropoff_text;
    const actions = [];
    if (NEXT[r.status]) actions.push(<Btn key="next" small title={t(NEXT[r.status][1])} onPress={() => advance(r)} />);
    actions.push(<Btn key="nav" small kind="secondary" title={t("driver.navigate")} onPress={() => Linking.openURL(mapsUrl(target))} />);
    const phone = r.booked_for_phone || (r.passenger_contact || "").split(" / ")[0];
    if (phone && /\d/.test(phone))
      actions.push(<Btn key="call" small kind="secondary" title={t("driver.call")} onPress={() => Linking.openURL(`tel:${phone}`)} />);
    if (["accepted", "en_route", "arrived"].includes(r.status))
      actions.push(<Btn key="rel" small kind="danger" title={t("driver.release")} onPress={() => release(r)} />);
    return (
      <RideCard
        key={r.id}
        ride={r}
        t={t}
        lang={lang}
        actions={actions}
        extra={
          <View>
            {r.passenger_note ? <Text style={s.note}>📝 {r.passenger_note}</Text> : null}
            {r.booked_for_name ? <Text style={s.note}>👤 {r.booked_for_name} {r.booked_for_phone}</Text> : null}
            {waiting ? <Text style={s.note}>{t("driver.waitQuote", { p: money(r.price_quote_cents) })}</Text> : null}
            {needQuote || needHours ? (
              <View style={s.quoteRow}>
                <Field
                  value={quotes[r.id] || ""}
                  onChangeText={(v) => setQuotes({ ...quotes, [r.id]: v })}
                  placeholder={needHours ? t("driver.hours") : t("driver.quotePh")}
                  keyboardType="decimal-pad"
                  style={{ flex: 1, marginBottom: 0, marginRight: 8 }}
                />
                {needQuote ? <Btn small title={t("driver.quote")} onPress={() => sendQuote(r)} /> : null}
              </View>
            ) : null}
          </View>
        }
      />
    );
  };

  return (
    <ScrollView
      style={s.wrap}
      contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
      keyboardShouldPersistTaps="handled"
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          tintColor={C.gold}
          onRefresh={async () => {
            setRefreshing(true);
            await load();
            setRefreshing(false);
          }}
        />
      }
    >
      <Card style={s.onlineCard}>
        <Text style={[s.onlineText, { color: online ? C.green : C.muted }]}>
          {online ? `🟢 ${t("driver.online")}` : `🔴 ${t("driver.offline")}`}
        </Text>
        <Switch value={online} onValueChange={toggleOnline} trackColor={{ true: C.gold }} />
      </Card>
      {msg ? <Hint style={{ color: C.red }}>{msg}</Hint> : null}

      <H>{t("driver.mine")}</H>
      {mine.length ? mine.map(mineCard) : <Hint>{t("driver.noMine")}</Hint>}

      <H style={{ marginTop: 12 }}>{t("driver.open")}</H>
      {open.length ? (
        open.map((r) => (
          <RideCard
            key={r.id}
            ride={r}
            t={t}
            lang={lang}
            extra={r.passenger_note ? <Text style={s.note}>📝 {r.passenger_note}</Text> : null}
            actions={[<Btn key="acc" small title={t("driver.accept")} onPress={() => act(() => api.acceptRide(r.id))} />]}
          />
        ))
      ) : (
        <Hint>{t("driver.noOpen")}</Hint>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: C.bg },
  onlineCard: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  onlineText: { fontSize: 17, fontWeight: "700" },
  note: { color: C.gold, marginTop: 6, fontSize: 14 },
  quoteRow: { flexDirection: "row", alignItems: "center", marginTop: 10 },
});
