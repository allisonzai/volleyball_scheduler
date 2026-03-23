import React, { useState } from "react";
import {
  Modal,
  View,
  Text,
  TouchableOpacity,
  ActivityIndicator,
  StyleSheet,
} from "react-native";
import { confirm } from "../services/api";

interface Props {
  visible: boolean;
  gameId: number;
  playerId: number;
  onDone: () => void;
}

export default function ConfirmationModal({ visible, gameId, playerId, onDone }: Props) {
  const [loading, setLoading] = useState(false);

  const handleResponse = async (response: "yes" | "no" | "defer") => {
    setLoading(true);
    try {
      await confirm(playerId, gameId, response);
      onDone();
    } catch {
      // show inline error
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal visible={visible} transparent animationType="slide">
      <View style={styles.overlay}>
        <View style={styles.sheet}>
          <Text style={styles.emoji}>🏐</Text>
          <Text style={styles.title}>You're up for Game #{gameId}!</Text>
          <Text style={styles.subtitle}>Confirm your spot to play.</Text>

          {loading ? (
            <ActivityIndicator color="#1e40af" style={{ marginTop: 20 }} />
          ) : (
            <View style={styles.buttons}>
              <TouchableOpacity
                style={[styles.btn, styles.yes]}
                onPress={() => handleResponse("yes")}
              >
                <Text style={styles.btnText}>Yes — I'm playing</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.btn, styles.no]}
                onPress={() => handleResponse("no")}
              >
                <Text style={styles.btnText}>No — Skip me</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.btn, styles.defer]}
                onPress={() => handleResponse("defer")}
              >
                <Text style={styles.btnText}>Defer — Keep my spot</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: "#fff",
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    alignItems: "center",
  },
  emoji: { fontSize: 40, marginBottom: 8 },
  title: { fontSize: 20, fontWeight: "700", color: "#1f2937", marginBottom: 4 },
  subtitle: { fontSize: 14, color: "#6b7280", marginBottom: 20 },
  buttons: { width: "100%", gap: 10 },
  btn: {
    paddingVertical: 14,
    borderRadius: 14,
    alignItems: "center",
  },
  yes: { backgroundColor: "#22c55e" },
  no: { backgroundColor: "#f87171" },
  defer: { backgroundColor: "#60a5fa" },
  btnText: { color: "#fff", fontWeight: "600", fontSize: 16 },
});
