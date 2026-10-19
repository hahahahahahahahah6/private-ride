import { useState } from "react";
import { Alert, Linking, ScrollView, StyleSheet, Text, View } from "react-native";
import { API_URL, api } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { C } from "../lib/theme";
import { Btn, Card, Field, H, Hint, Segmented } from "../components/ui";

export default function MeScreen({ user, onUser, onLogout, pushOk }) {
  const { t, lang, setLang } = useI18n();
  const [name, setName] = useState(user.name || "");
  const [invite, setInvite] = useState("");
  const [msg, setMsg] = useState("");

  const errText = (e) => (e.status === 0 ? t("common.netErr") : e.message);

  const save = async () => {
    try {
      onUser(await api.updateMe({ name: name.trim(), lang }));
      setMsg(t("me.saved"));
    } catch (e) {
      setMsg(errText(e));
    }
  };

  const changeLang = async (l) => {
    await setLang(l);
    api.updateMe({ name: user.name || "", lang: l }).catch(() => {});
  };

  const redeem = async () => {
    if (!invite.trim()) return;
    try {
      onUser(await api.redeemInvite(invite.trim()));
      setInvite("");
      setMsg("✅");
    } catch (e) {
      setMsg(errText(e));
    }
  };

  const logout = () =>
    Alert.alert(t("me.logout"), "", [
      { text: t("common.cancel"), style: "cancel" },
      { text: t("me.logout"), style: "destructive", onPress: onLogout },
    ]);

  const ident = user.email || user.phone;

  return (
    <ScrollView style={s.wrap} contentContainerStyle={{ padding: 16, paddingBottom: 40 }} keyboardShouldPersistTaps="handled">
      <H>{t("me.title")}</H>
      <Card>
        <Text style={s.big}>{user.name || ident}</Text>
        <Hint>
          {ident} · {t(`me.role.${user.role}`)}
        </Hint>
        <Field value={name} onChangeText={setName} placeholder={t("me.name")} maxLength={64} />
        <Btn small title={t("me.save")} onPress={save} />
        {msg ? <Hint style={{ marginTop: 8, color: C.gold }}>{msg}</Hint> : null}
      </Card>

      <Card>
        <Hint>{t("me.lang")}</Hint>
        <Segmented
          value={lang}
          onChange={changeLang}
          options={[
            { value: "zh", label: "中文" },
            { value: "en", label: "English" },
          ]}
        />
        <View style={s.row}>
          <Text style={s.label}>{t("me.push")}</Text>
          <Text style={{ color: pushOk ? C.green : C.muted }}>{pushOk ? t("me.pushOn") : t("me.pushOff")}</Text>
        </View>
      </Card>

      {user.role === "passenger" ? (
        <Card>
          <Hint>{t("me.invite")}</Hint>
          <Field value={invite} onChangeText={setInvite} placeholder="ABCD2345" autoCapitalize="characters" />
          <Btn small kind="secondary" title={t("me.redeem")} onPress={redeem} />
        </Card>
      ) : null}

      <Btn kind="danger" title={t("me.logout")} onPress={logout} style={{ marginTop: 8 }} />
      <Text style={s.links} onPress={() => Linking.openURL(`${API_URL}/web/privacy.html`)}>
        Privacy · Terms
      </Text>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: C.bg },
  big: { color: C.text, fontSize: 22, fontWeight: "800", marginBottom: 4 },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 4 },
  label: { color: C.text, fontSize: 16 },
  links: { color: C.faint, textAlign: "center", marginTop: 24 },
});
