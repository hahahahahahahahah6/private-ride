import { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { api } from "../lib/api";

export default function PassengerHome() {
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
      <Text style={styles.title}>乘客端</Text>
      <Text style={styles.sub}>约车 / 看订单状态（M2 接入）</Text>
      {health ? (
        <Text style={styles.ok}>后端连接正常 ✅ {health.service}</Text>
      ) : error ? (
        <Text style={styles.err}>后端连不上：{error}</Text>
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
