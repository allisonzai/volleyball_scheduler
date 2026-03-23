import React, { useEffect, useState } from "react";
import { ScrollView, View, Text, StyleSheet } from "react-native";
import { listGames } from "../services/api";
import PlayerBadge from "../components/PlayerBadge";

export default function HistoryScreen() {
  const [games, setGames] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listGames("finished")
      .then(setGames)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <View style={styles.center}>
        <Text style={styles.grey}>Loading…</Text>
      </View>
    );
  }

  if (games.length === 0) {
    return (
      <View style={styles.center}>
        <Text style={styles.grey}>No past games yet.</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {games.map((game) => (
        <View key={game.id} style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.cardTitle}>Game #{game.id}</Text>
            <Text style={styles.cardDate}>
              {game.started_at ? new Date(game.started_at).toLocaleString() : "—"}
            </Text>
          </View>
          {game.slots
            .filter((s: any) => s.status === "confirmed")
            .map((slot: any) => (
              <PlayerBadge
                key={slot.id}
                displayName={slot.display_name}
                signupNumber={slot.signup_number}
              />
            ))}
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  content: { padding: 16 },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  grey: { color: "#9ca3af", fontSize: 14 },
  card: {
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 4,
    elevation: 2,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 10,
  },
  cardTitle: { fontWeight: "700", fontSize: 15, color: "#1f2937" },
  cardDate: { fontSize: 11, color: "#9ca3af" },
});
