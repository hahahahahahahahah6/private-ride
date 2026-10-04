import { useState } from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import PassengerHome from "./src/screens/PassengerHome";
import DriverHome from "./src/screens/DriverHome";

export default function App() {
  const [role, setRole] = useState(null); // null | 'passenger' | 'driver'

  if (!role) {
    return (
      <View style={styles.container}>
        <StatusBar style="auto" />
        <Text style={styles.title}>私人专车</Text>
        <Text style={styles.sub}>请选择你的身份</Text>
        <TouchableOpacity style={styles.button} onPress={() => setRole("passenger")}>
          <Text style={styles.buttonText}>我是乘客</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.button} onPress={() => setRole("driver")}>
          <Text style={styles.buttonText}>我是司机</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={{ flex: 1 }}>
      <StatusBar style="auto" />
      {role === "passenger" ? <PassengerHome /> : <DriverHome />}
      <TouchableOpacity style={styles.switch} onPress={() => setRole(null)}>
        <Text style={styles.switchText}>切换身份</Text>
      </TouchableOpacity>
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
});
