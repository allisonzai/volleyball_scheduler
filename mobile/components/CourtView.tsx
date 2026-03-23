import React from "react";
import { View, Text, StyleSheet } from "react-native";
import PlayerBadge from "./PlayerBadge";

interface Props {
  game: any;
  currentPlayerId?: number | null;
}

export default function CourtView({ game, currentPlayerId }: Props) {
  if (!game) {
    return (
      <View style={styles.card}>
        <Text style={styles.empty}>No active game. Sign up and an operator can start one.</Text>
      </View>
    );
  }

  const confirmed = game.slots.filter((s: any) => s.status === "confirmed");
  const pending = game.slots.filter((s: any) => s.status === "pending_confirmation");

  const statusMap: Record<string, { label: string; color: string }> = {
    open: { label: "Confirming players…", color: "#d97706" },
    in_progress: { label: "Game in progress", color: "#16a34a" },
    finished: { label: "Game finished", color: "#9ca3af" },
  };
  const statusInfo = statusMap[game.status] ?? { label: game.status, color: "#6b7280" };

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.title}>Current Game #{game.id}</Text>
        <Text style={[styles.status, { color: statusInfo.color }]}>{statusInfo.label}</Text>
      </View>

      {confirmed.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>On Court ({confirmed.length}/{game.max_players})</Text>
          {confirmed.map((slot: any) => (
            <PlayerBadge
              key={slot.id}
              displayName={slot.display_name}
              signupNumber={slot.signup_number}
              highlight={slot.player_id === currentPlayerId}
            />
          ))}
        </View>
      )}

      {pending.length > 0 && (
        <View style={styles.section}>
          <Text style={[styles.sectionLabel, { color: "#d97706" }]}>
            Awaiting Confirmation ({pending.length})
          </Text>
          {pending.map((slot: any) => (
            <View key={slot.id} style={styles.pendingItem}>
              <Text style={styles.pendingName}>{slot.display_name}</Text>
              <Text style={styles.pendingDot}>waiting…</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 16,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 4,
    elevation: 2,
    marginBottom: 12,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  title: { fontWeight: "700", fontSize: 16, color: "#1f2937" },
  status: { fontSize: 13, fontWeight: "500" },
  section: { marginBottom: 12 },
  sectionLabel: {
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    color: "#9ca3af",
    marginBottom: 6,
  },
  empty: { color: "#9ca3af", textAlign: "center", paddingVertical: 16 },
  pendingItem: {
    flexDirection: "row",
    justifyContent: "space-between",
    backgroundColor: "#fefce8",
    borderRadius: 10,
    padding: 10,
    marginBottom: 6,
  },
  pendingName: { fontSize: 14, color: "#374151" },
  pendingDot: { fontSize: 12, color: "#d97706" },
});
