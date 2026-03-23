import React, { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { router } from "expo-router";
import { registerPlayer } from "../services/api";
import { registerForPushNotifications } from "../services/notifications";

export default function RegisterScreen() {
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    phone: "",
    email: "",
  });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!form.first_name || !form.last_name || !form.phone || !form.email) {
      Alert.alert("Missing fields", "Please fill in all fields.");
      return;
    }
    setLoading(true);
    try {
      const player = await registerPlayer(form);
      await AsyncStorage.setItem("vb_player", JSON.stringify(player));
      await registerForPushNotifications(player.id);
      router.replace("/");
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? "Registration failed. Try again.";
      Alert.alert("Error", msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <Text style={styles.heading}>Create your account</Text>
        <Text style={styles.sub}>You only need to register once.</Text>

        <View style={styles.row}>
          <TextInput
            style={[styles.input, { flex: 1, marginRight: 8 }]}
            placeholder="First Name"
            value={form.first_name}
            onChangeText={(v) => setForm((f) => ({ ...f, first_name: v }))}
          />
          <TextInput
            style={[styles.input, { flex: 1 }]}
            placeholder="Last Name"
            value={form.last_name}
            onChangeText={(v) => setForm((f) => ({ ...f, last_name: v }))}
          />
        </View>

        <TextInput
          style={styles.input}
          placeholder="Phone (e.g. +12125551234)"
          keyboardType="phone-pad"
          value={form.phone}
          onChangeText={(v) => setForm((f) => ({ ...f, phone: v }))}
        />

        <TextInput
          style={styles.input}
          placeholder="Email"
          keyboardType="email-address"
          autoCapitalize="none"
          value={form.email}
          onChangeText={(v) => setForm((f) => ({ ...f, email: v }))}
        />

        <TouchableOpacity
          style={[styles.submitBtn, loading && styles.disabled]}
          onPress={handleSubmit}
          disabled={loading}
        >
          <Text style={styles.submitText}>{loading ? "Registering…" : "Register"}</Text>
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  content: { padding: 20, paddingTop: 32 },
  heading: { fontSize: 24, fontWeight: "700", color: "#1f2937", marginBottom: 4 },
  sub: { fontSize: 14, color: "#6b7280", marginBottom: 24 },
  row: { flexDirection: "row", marginBottom: 12 },
  input: {
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    backgroundColor: "#fff",
    marginBottom: 12,
  },
  submitBtn: {
    backgroundColor: "#1e40af",
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 8,
  },
  submitText: { color: "#fff", fontWeight: "700", fontSize: 16 },
  disabled: { opacity: 0.6 },
});
