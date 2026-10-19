import { useCallback, useEffect, useState } from "react";
import { Alert, Linking, Pressable, RefreshControl, ScrollView, Share, StyleSheet, Text, View } from "react-native";
import { API_URL, api } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { C, money } from "../lib/theme";
import { Btn, Card, Field, H, Hint, RideCard, Segmented } from "../components/ui";

const ACTIVE = ["requested", "accepted", "en_route", "arrived", "in_progress"];

/** "10-25 08:30" → 本地时间 Date；格式不对返回 null。已过去的日期算明年。 */
export function parseWhen(text) {
  const m = /^\s*(\d{1,2})[-/](\d{1,2})\s+(\d{1,2}):(\d{2})\s*$/.exec(text || "");
  if (!m) return null;
  const [mo, d, h, mi] = m.slice(1).map(Number);
  if (mo < 1 || mo > 12 || d < 1 || d > 31 || h > 23 || mi > 59) return null;
  const now = new Date();
  let dt = new Date(now.getFullYear(), mo - 1, d, h, mi);
  if (dt.getMonth() !== mo - 1) return null; // 2-31 这种
  if (dt < now - 24 * 3600 * 1000) dt = new Date(now.getFullYear() + 1, mo - 1, d, h, mi);
  return dt;
}

function Stars({ onPick }) {
  return (
    <View style={{ flexDirection: "row", marginTop: 8 }}>
      {[1, 2, 3, 4, 5].map((n) => (
        <Pressable key={n} onPress={() => onPick(n)} hitSlop={6} style={{ marginRight: 10 }}>
          <Text style={{ fontSize: 26, color: C.gold }}>★</Text>
        </Pressable>
      ))}
    </View>
  );
}

export default function PassengerHome() {
  const { t, lang } = useI18n();
  const [pickup, setPickup] = useState("");
  const [dropoff, setDropoff] = useState("");
  const [seats, setSeats] = useState(1);
  const [note, setNote] = useState("");
  const [whenMode, setWhenMode] = useState("now");
  const [whenText, setWhenText] = useState("");
  const [priceMode, setPriceMode] = useState("offer");
  const [offer, setOffer] = useState("");
  const [rides, setRides] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const errText = (e) => (e.status === 0 ? t("common.netErr") : e.message);

  const load = useCallback(async () => {
    try {
      const [rs, ds] = await Promise.all([api.myRides(), api.driversStatus().catch(() => [])]);
      setRides(rs);
      setDrivers(ds);
    } catch (e) {
      setMsg(errText(e));
    }
  }, [lang]);

  useEffect(() => {
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const submit = async () => {
    if (!pickup.trim() || !dropoff.trim()) return setMsg(t("book.need"));
    let scheduled_at = null;
    if (whenMode === "later") {
      const dt = parseWhen(whenText);
      if (!dt) return setMsg(t("book.badTime"));
      scheduled_at = dt.toISOString();
    }
    const body = {
      pickup_text: pickup.trim(),
      dropoff_text: dropoff.trim(),
      seats_needed: seats,
      note: note.trim(),
      scheduled_at,
      price_mode: priceMode,
      pay_mode: "offline",
    };
    if (priceMode === "offer") {
      const dollars = parseFloat(offer);
      if (!(dollars > 0)) return setMsg(t("book.needOffer"));
      body.price_offer_cents = Math.round(dollars * 100);
    }
    setBusy(true);
    setMsg("");
    try {
      await api.createRide(body);
      setPickup("");
      setDropoff("");
      setNote("");
      setOffer("");
      setWhenText("");
      setMsg(t("book.ok"));
      load();
    } catch (e) {
      setMsg(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const act = async (fn) => {
    try {
      await fn();
      load();
    } catch (e) {
      Alert.alert(t("common.error"), errText(e));
    }
  };

  const cancel = (r) =>
    Alert.alert(t("rides.cancelConfirm"), "", [
      { text: t("common.cancel"), style: "cancel" },
      { text: t("rides.cancel"), style: "destructive", onPress: () => act(() => api.cancelRide(r.id)) },
    ]);

  const share = (r) =>
    act(async () => {
      const out = await api.shareRide(r.id);
      await Share.share({ message: `${API_URL}${out.url}` });
    });

  const active = rides.filter((r) => ACTIVE.includes(r.status));
  const past = rides.filter((r) => !ACTIVE.includes(r.status)).slice(0, 10);

  const activeActions = (r) => {
    const out = [];
    if (r.driver_phone)
      out.push(<Btn key="call" small kind="secondary" title={t("rides.callDriver")} onPress={() => Linking.openURL(`tel:${r.driver_phone}`)} />);
    if (r.status !== "requested")
      out.push(<Btn key="share" small kind="secondary" title={t("rides.share")} onPress={() => share(r)} />);
    if (["requested", "accepted", "en_route", "arrived"].includes(r.status))
      out.push(<Btn key="cancel" small kind="danger" title={t("rides.cancel")} onPress={() => cancel(r)} />);
    return out;
  };

  const quoteBox = (r) =>
    r.price_mode === "quote" && r.price_status === "pending" && r.price_quote_cents != null ? (
      <View style={{ marginTop: 10 }}>
        <Text style={{ color: C.gold, fontWeight: "700" }}>{t("rides.quoteAsk", { p: money(r.price_quote_cents) })}</Text>
        <View style={{ flexDirection: "row", gap: 8, marginTop: 8 }}>
          <Btn small title={t("rides.accept")} onPress={() => act(() => api.confirmQuote(r.id, true))} />
          <Btn small kind="secondary" title={t("rides.reject")} onPress={() => act(() => api.confirmQuote(r.id, false))} />
        </View>
      </View>
    ) : null;

  return (
    <ScrollView
      style={s.wrap}
      contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
      keyboardShouldPersistTaps="handled"
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.gold} />}
    >
      {active.length ? (
        <>
          <H>{t("rides.mine")}</H>
          {active.map((r) => (
            <RideCard key={r.id} ride={r} t={t} lang={lang} extra={quoteBox(r)} actions={activeActions(r)} />
          ))}
        </>
      ) : null}

      <H>{t("book.title")}</H>
      <Card>
        <Field value={pickup} onChangeText={setPickup} placeholder={t("book.pickup")} />
        <Field value={dropoff} onChangeText={setDropoff} placeholder={t("book.dropoff")} />
        <Hint>{t("book.seats")}</Hint>
        <Segmented
          value={seats}
          onChange={setSeats}
          options={[1, 2, 3, 4, 5, 6].map((n) => ({ value: n, label: String(n) }))}
        />
        <Hint>{t("book.when")}</Hint>
        <Segmented
          value={whenMode}
          onChange={setWhenMode}
          options={[
            { value: "now", label: t("book.now") },
            { value: "later", label: t("book.later") },
          ]}
        />
        {whenMode === "later" ? (
          <Field value={whenText} onChangeText={setWhenText} placeholder={t("book.laterHint")} />
        ) : null}
        <Hint>{t("book.priceMode")}</Hint>
        <Segmented
          value={priceMode}
          onChange={setPriceMode}
          options={[
            { value: "offer", label: t("book.offer") },
            { value: "quote", label: t("book.quote") },
          ]}
        />
        {priceMode === "offer" ? (
          <Field value={offer} onChangeText={setOffer} placeholder={t("book.offerPh")} keyboardType="decimal-pad" />
        ) : null}
        <Field value={note} onChangeText={setNote} placeholder={t("book.note")} />
        <Hint>{t("book.pay")}</Hint>
        {msg ? <Hint style={{ color: C.gold }}>{msg}</Hint> : null}
        <Btn title={t("book.submit")} onPress={submit} busy={busy} />
      </Card>

      {drivers.length ? (
        <Hint>
          {t("book.drivers")}：
          {drivers.map((d) => `${d.is_active ? "🟢" : "🔴"} ${d.name}`).join("  ")}
        </Hint>
      ) : null}

      {past.length ? (
        <>
          <H style={{ marginTop: 16 }}>{t("rides.history")}</H>
          {past.map((r) => (
            <RideCard
              key={r.id}
              ride={r}
              t={t}
              lang={lang}
              extra={
                r.status === "completed" && r.rating_stars == null ? (
                  <View>
                    <Text style={{ color: C.muted, marginTop: 8 }}>{t("rate.title")}</Text>
                    <Stars onPick={(n) => act(() => api.rateRide(r.id, n))} />
                  </View>
                ) : r.rating_stars ? (
                  <Text style={{ color: C.muted, marginTop: 6 }}>{t("rides.rated", { n: r.rating_stars })}</Text>
                ) : null
              }
              actions={[
                <Btn key="again" small kind="secondary" title={t("rides.rebook")} onPress={() => act(() => api.rebook(r.id))} />,
              ]}
            />
          ))}
        </>
      ) : !active.length ? (
        <Hint style={{ textAlign: "center", marginTop: 12 }}>{t("rides.empty")}</Hint>
      ) : null}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: C.bg },
});
