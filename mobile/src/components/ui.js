import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { C, STATUS_COLOR, fmtTime, money } from "../lib/theme";

export function Btn({ title, onPress, kind = "primary", small, disabled, busy, style }) {
  const s = kind === "primary" ? st.btnPrimary : kind === "danger" ? st.btnDanger : st.btnSecondary;
  const ts = kind === "primary" ? st.btnPrimaryText : kind === "danger" ? st.btnDangerText : st.btnSecondaryText;
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || busy}
      style={({ pressed }) => [
        st.btn,
        small && st.btnSmall,
        s,
        (disabled || busy) && { opacity: 0.5 },
        pressed && { opacity: 0.75 },
        style,
      ]}
    >
      {busy ? (
        <ActivityIndicator color={kind === "primary" ? C.goldInk : C.text} />
      ) : (
        <Text style={[st.btnText, small && st.btnTextSmall, ts]}>{title}</Text>
      )}
    </Pressable>
  );
}

export function Card({ children, style }) {
  return <View style={[st.card, style]}>{children}</View>;
}

export function Field(props) {
  return <TextInput placeholderTextColor={C.faint} {...props} style={[st.input, props.style]} />;
}

export function Segmented({ options, value, onChange }) {
  return (
    <View style={st.seg}>
      {options.map((o) => (
        <Pressable
          key={o.value}
          onPress={() => onChange(o.value)}
          style={[st.segItem, value === o.value && st.segItemOn]}
        >
          <Text style={[st.segText, value === o.value && st.segTextOn]}>{o.label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

export function H({ children, style }) {
  return <Text style={[st.h, style]}>{children}</Text>;
}

export function Hint({ children, style }) {
  return <Text style={[st.hint, style]}>{children}</Text>;
}

/** 一张行程卡：路线、时间、状态、价格；actions 放按钮。 */
export function RideCard({ ride, t, lang, actions, extra }) {
  const price =
    ride.price_final_cents != null
      ? t("rides.price", { p: money(ride.price_final_cents) })
      : t("rides.priceTbd");
  return (
    <Card>
      <View style={st.rowBetween}>
        <View style={[st.badge, { borderColor: STATUS_COLOR[ride.status] || C.muted }]}>
          <Text style={[st.badgeText, { color: STATUS_COLOR[ride.status] || C.muted }]}>
            {t(`status.${ride.status}`)}
          </Text>
        </View>
        <Text style={st.meta}>
          {ride.scheduled_at ? fmtTime(ride.scheduled_at, lang) : fmtTime(ride.created_at, lang)}
        </Text>
      </View>
      <View style={st.route}>
        <View style={[st.dot, { backgroundColor: C.green }]} />
        <Text style={st.place}>{ride.pickup_text}</Text>
      </View>
      {(ride.stops || []).map((s, i) => (
        <View key={i} style={st.route}>
          <View style={[st.dot, { backgroundColor: C.faint }]} />
          <Text style={[st.place, { color: C.muted }]}>{s}</Text>
        </View>
      ))}
      <View style={st.route}>
        <View style={[st.dot, { backgroundColor: C.gold }]} />
        <Text style={st.place}>{ride.dropoff_text}</Text>
      </View>
      <Text style={st.meta}>
        {price}
        {ride.seats_needed > 1 ? ` · ${ride.seats_needed}👤` : ""}
        {ride.flight_no ? ` · ✈︎ ${ride.flight_no}` : ""}
        {ride.note ? ` · ${ride.note}` : ""}
      </Text>
      {ride.driver_vehicle ? (
        <Text style={st.meta}>
          🚗 {ride.driver_vehicle.vehicle_model} {ride.driver_vehicle.plate}
        </Text>
      ) : null}
      {extra}
      {actions ? <View style={st.actions}>{actions}</View> : null}
    </Card>
  );
}

const st = StyleSheet.create({
  btn: {
    borderRadius: 14,
    paddingVertical: 14,
    paddingHorizontal: 18,
    alignItems: "center",
    justifyContent: "center",
  },
  btnSmall: { paddingVertical: 9, paddingHorizontal: 14, borderRadius: 10 },
  btnPrimary: { backgroundColor: C.gold },
  btnSecondary: { backgroundColor: C.cardHigh },
  btnDanger: { backgroundColor: "transparent", borderWidth: 1, borderColor: C.red },
  btnText: { fontSize: 17, fontWeight: "700" },
  btnTextSmall: { fontSize: 14 },
  btnPrimaryText: { color: C.goldInk },
  btnSecondaryText: { color: C.text },
  btnDangerText: { color: C.red },
  card: { backgroundColor: C.card, borderRadius: 18, padding: 16, marginBottom: 12 },
  input: {
    backgroundColor: C.cardHigh,
    color: C.text,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    marginBottom: 10,
  },
  seg: { flexDirection: "row", backgroundColor: C.cardHigh, borderRadius: 12, padding: 3, marginBottom: 10 },
  segItem: { flex: 1, paddingVertical: 9, alignItems: "center", borderRadius: 10 },
  segItemOn: { backgroundColor: C.gold },
  segText: { color: C.muted, fontWeight: "600" },
  segTextOn: { color: C.goldInk },
  h: { color: C.text, fontSize: 20, fontWeight: "800", marginBottom: 10, marginTop: 6 },
  hint: { color: C.muted, fontSize: 14, marginBottom: 8, lineHeight: 20 },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  badge: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 3 },
  badgeText: { fontSize: 12, fontWeight: "700" },
  route: { flexDirection: "row", alignItems: "center", marginVertical: 3 },
  dot: { width: 8, height: 8, borderRadius: 4, marginRight: 10 },
  place: { color: C.text, fontSize: 16, flex: 1 },
  meta: { color: C.muted, fontSize: 13, marginTop: 6 },
  actions: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 12 },
});
