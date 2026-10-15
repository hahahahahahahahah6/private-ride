import { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { api } from "../lib/api";
import { useI18n } from "../lib/i18n";

export default function PassengerHome() {
  const { t } = useI18n();
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{t("passenger.title")}</Text>
      <Text style={styles.sub}>{t("passenger.subtitle")}</Text>
      {health ? (
        <Text style={styles.ok}>{t("passenger.backendOk", { service: health.service })}</Text>
      ) : error ? (
        <Text style={styles.err}>{t("passenger.backendFail", { error })}</Text>
      ) : (
        <ActivityIndicator />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
  title: { fontSize: 28, fontWeight: "bold", marginBottom: 8 },
  sub: { fontSize: 16, color: "#666", marginBottom: 24 },
  ok: { color: "green" },
  err: { color: "red" },
});
