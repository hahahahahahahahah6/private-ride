import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Button,
  FlatList,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { api } from "../lib/api";
import { registerForPushNotificationsAsync } from "../lib/push";

export default function DriverHome() {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [user, setUser] = useState(null);
  const [pushState, setPushState] = useState("未注册");
  const [rides, setRides] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadOpenRides = async () => {
    try {
      setRides(await api.openRides());
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => {
    if (!user) return;
    (async () => {
      try {
        await registerForPushNotificationsAsync();
        setPushState("已开启 ✅ 新订单会推送到这台手机");
      } catch (e) {
        setPushState(`注册失败：${e.message}`);
      }
      loadOpenRides();
    })();
  }, [user]);

  const sendCode = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.requestCode(phone);
      setCodeSent(true);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const login = async () => {
    setBusy(true);
    setError(null);
    try {
      const out = await api.verifyCode(phone, code);
      setUser(out.user);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const accept = async (id) => {
    setBusy(true);
    try {
      await api.acceptRide(id);
      loadOpenRides();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!user) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>司机登录</Text>
        <TextInput
          style={styles.input}
          placeholder="手机号"
          keyboardType="phone-pad"
          value={phone}
          onChangeText={setPhone}
        />
        {codeSent && (
          <TextInput
            style={styles.input}
            placeholder="验证码"
            keyboardType="number-pad"
            value={code}
            onChangeText={setCode}
          />
        )}
        {busy ? (
          <ActivityIndicator />
        ) : codeSent ? (
          <Button title="登录" onPress={login} />
        ) : (
          <Button title="获取验证码" onPress={sendCode} />
        )}
        {error && <Text style={styles.err}>{error}</Text>}
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>待接订单</Text>
      <Text style={styles.hint}>推送状态：{pushState}</Text>
      <FlatList
        data={rides}
        keyExtractor={(r) => r.id}
        ListEmptyComponent={<Text style={styles.hint}>暂无待接订单</Text>}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Text style={styles.route}>
              {item.pickup_text} → {item.dropoff_text}
            </Text>
            {item.note ? <Text style={styles.hint}>备注：{item.note}</Text> : null}
            <Button title="接单" onPress={() => accept(item.id)} />
          </View>
        )}
      />
      {error && <Text style={styles.err}>{error}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, paddingTop: 64 },
  title: { fontSize: 24, fontWeight: "bold", marginBottom: 16 },
  hint: { fontSize: 14, color: "#666", marginBottom: 12 },
  input: {
    borderWidth: 1,
    borderColor: "#ccc",
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
    fontSize: 16,
  },
  err: { color: "red", marginTop: 12 },
  card: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  route: { fontSize: 16, fontWeight: "600", marginBottom: 8 },
});
