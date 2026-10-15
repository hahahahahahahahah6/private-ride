import { useEffect, useState } from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import PassengerHome from "./src/screens/PassengerHome";
import DriverHome from "./src/screens/DriverHome";
import { initI18n, useI18n } from "./src/lib/i18n";

function LangToggle() {
  const { lang, setLang } = useI18n();
  return (
    <View style={styles.langRow}>
      {["zh", "en"].map((l) => (
        <TouchableOpacity
          key={l}
          style={[styles.langBtn, lang === l && styles.langBtnActive]}
          onPress={() => setLang(l)}
        >
          <Text style={[styles.langText, lang === l && styles.langTextActive]}>
            {l === "zh" ? "中文" : "EN"}
          </Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

function RoleSelect({ onPick }) {
  const { t } = useI18n();
  return (
    <View style={styles.container}>
      <StatusBar style="auto" />
      <Text style={styles.title}>{t("app.title")}</Text>
      <Text style={styles.sub}>{t("app.chooseRole")}</Text>
      <TouchableOpacity style={styles.button} onPress={() => onPick("passenger")}>
        <Text style={styles.buttonText}>{t("app.iAmPassenger")}</Text>
      </TouchableOpacity>
      <TouchableOpacity style={styles.button} onPress={() => onPick("driver")}>
        <Text style={styles.buttonText}>{t("app.iAmDriver")}</Text>
      </TouchableOpacity>
      <LangToggle />
    </View>
  );
}

export default function App() {
  const [ready, setReady] = useState(false);
  const [role, setRole] = useState(null); // null | 'passenger' | 'driver'
  const { t } = useI18n();

  useEffect(() => {
    initI18n().then(() => setReady(true));
  }, []);

  if (!ready) return null;

  if (!role) {
    return <RoleSelect onPick={setRole} />;
  }

  return (
    <View style={{ flex: 1 }}>
      <StatusBar style="auto" />
      {role === "passenger" ? <PassengerHome /> : <DriverHome />}
      <View style={styles.bottomBar}>
        <TouchableOpacity style={styles.switch} onPress={() => setRole(null)}>
          <Text style={styles.switchText}>{t("app.switchRole")}</Text>
        </TouchableOpacity>
        <LangToggle />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
  title: { fontSize: 32, fontWeight: "bold", marginBottom: 8 },
  sub: { fontSize: 16, color: "#666", marginBottom: 32 },
  button: {
    backgroundColor: "#1a73e8",
    borderRadius: 12,
    marginVertical: 8,
    paddingHorizontal: 48,
    paddingVertical: 16,
    width: "80%",
    alignItems: "center",
  },
  buttonText: { color: "#fff", fontSize: 18, fontWeight: "600" },
  switch: { padding: 16, alignItems: "center" },
  switchText: { color: "#1a73e8", fontSize: 14 },
  bottomBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingBottom: 8,
  },
  langRow: { flexDirection: "row", marginTop: 16 },
  langBtn: {
    borderWidth: 1,
    borderColor: "#1a73e8",
    borderRadius: 16,
    paddingHorizontal: 16,
    paddingVertical: 6,
    marginHorizontal: 4,
  },
  langBtnActive: { backgroundColor: "#1a73e8" },
  langText: { color: "#1a73e8", fontSize: 14, fontWeight: "600" },
  langTextActive: { color: "#fff" },
});
