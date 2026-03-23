import React from "react";
import { View, Text, TouchableOpacity, Alert, StyleSheet } from "react-native";
import PlayerBadge from "./PlayerBadge";
import { leaveQueue } from "../services/api";

interface Props {
  queue: any[];
  currentPlayerId?: number | null;
  onRefresh: () => void;
}

export default function WaitingListView({ queue, currentPlayerId, onRefresh }: Props) {
  const handleLeave = (playerId: number) => {
    Alert.alert("Leave Queue?", "Are you sure you want to leave the waiting list?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Leave",
        style: "destructive",
        onPress: async () => {
          try {
            await leaveQueue(playerId);
            onRefresh();
          } catch {
            Alert.alert("Error", "Could not leave queue. Try again.");
          }
        },
      },
    ]);
  };

  return (
    <View style={styles.card}>
      <Text style={styles.title}>Waiting List ({queue.length})</Text>

      {queue.length === 0 ? (
        <Text style={styles.empty}>No players waiting.</Text>
      ) : (
        queue.map((entry, idx) => (
          <View key={entry.player_id} style={styles.row}>
            <Text style={styles.position}>{idx + 1}.</Text>
            <View style={styles.badge}>
              <PlayerBadge
                displayName={entry.display_name}
                signupNumber={entry.signup_number}
                highlight={entry.player_id === currentPlayerId}
              />
            </View>
            {entry.player_id === currentPlayerId && (
              <TouchableOpacity onPress={() => handleLeave(entry.player_id)} style={styles.leaveBtn}>
                <Text style={styles.leaveBtnText}>Leave</Text>
              </TouchableOpacity>
            )}
          </View>
        ))
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
  title: { fontWeight: "700", fontSize: 16, color: "#1f2937", marginBottom: 12 },
  empty: { color: "#9ca3af", textAlign: "center", paddingVertical: 16, fontSize: 14 },
  row: { flexDirection: "row", alignItems: "center", marginBottom: 4 },
  position: { fontSize: 12, color: "#9ca3af", width: 20, textAlign: "right", marginRight: 4 },
  badge: { flex: 1 },
  leaveBtn: {
    borderWidth: 1,
    borderColor: "#fca5a5",
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 4,
    marginLeft: 6,
  },
  leaveBtnText: { fontSize: 12, color: "#ef4444" },
});
