import { useEffect, useState } from "react";
import { KeyboardAvoidingView, Platform, StyleSheet, Text, View } from "react-native";
import { api } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { C } from "../lib/theme";
import { Btn, Field, Hint, Segmented } from "../components/ui";

export default function Login({ onLogin }) {
  const { t } = useI18n();
  const [mode, setMode] = useState("phone");
  const [ident, setIdent] = useState("");
  const [code, setCode] = useState("");
  const [wait, setWait] = useState(0);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (wait <= 0) return;
    const id = setTimeout(() => setWait(wait - 1), 1000);
    return () => clearTimeout(id);
  }, [wait]);

  const identBody = () => (mode === "phone" ? { phone: ident.trim() } : { email: ident.trim() });
  const errText = (e) => (e.status === 0 ? t("common.netErr") : e.message);

  const sendCode = async () => {
    if (!ident.trim()) return setMsg(t("auth.needIdent"));
    setBusy(true);
    setMsg("");
    try {
      const out = await api.requestCode(identBody());
      setWait(60);
      setMsg(out.dev_code ? t("auth.devCode", { code: out.dev_code }) : t("auth.codeSent"));
    } catch (e) {
      setMsg(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const login = async () => {
    if (!code.trim()) return setMsg(t("auth.needCode"));
    setBusy(true);
    setMsg("");
    try {
      const out = await api.verifyCode(identBody(), code.trim());
      onLogin(out.user);
    } catch (e) {
      setMsg(errText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView style={s.wrap} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <View style={s.brand}>
        <Text style={s.logo}>🚕</Text>
        <Text style={s.title}>{t("app.title")}</Text>
        <Text style={s.tag}>{t("app.tagline")}</Text>
      </View>
      <Segmented
        value={mode}
        onChange={(m) => {
          setMode(m);
          setIdent("");
          setMsg("");
        }}
        options={[
          { value: "phone", label: t("auth.phone") },
          { value: "email", label: t("auth.email") },
        ]}
      />
      <Field
        value={ident}
        onChangeText={setIdent}
        placeholder={mode === "phone" ? t("auth.phone") : t("auth.email")}
        keyboardType={mode === "phone" ? "phone-pad" : "email-address"}
        autoCapitalize="none"
        autoComplete={mode === "phone" ? "tel" : "email"}
      />
      <View style={s.row}>
        <Field
          value={code}
          onChangeText={setCode}
          placeholder={t("auth.code")}
          keyboardType="number-pad"
          maxLength={6}
          textContentType="oneTimeCode"
          style={{ flex: 1, minWidth: 0, marginRight: 8 }}
        />
        <Btn
          kind="secondary"
          title={wait > 0 ? t("auth.resend", { s: wait }) : t("auth.getCode")}
          onPress={sendCode}
          disabled={wait > 0}
          small
          style={{ marginBottom: 10, minWidth: 110, paddingVertical: 14 }}
        />
      </View>
      {msg ? <Hint>{msg}</Hint> : null}
      <Btn title={t("auth.login")} onPress={login} busy={busy} style={{ marginTop: 6 }} />
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, justifyContent: "center", padding: 24, backgroundColor: C.bg },
  brand: { alignItems: "center", marginBottom: 32 },
  logo: { fontSize: 56 },
  title: { color: C.text, fontSize: 30, fontWeight: "800", marginTop: 8 },
  tag: { color: C.gold, fontSize: 14, marginTop: 6, letterSpacing: 2 },
  row: { flexDirection: "row", alignItems: "center" },
});
