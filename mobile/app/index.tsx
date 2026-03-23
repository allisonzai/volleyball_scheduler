import React, { useEffect, useRef, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  Alert,
  RefreshControl,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { router } from "expo-router";
import * as Notifications from "expo-notifications";

import { useGameState } from "../hooks/useGameState";
import { usePushToken } from "../hooks/usePushToken";
import CourtView from "../components/CourtView";
import WaitingListView from "../components/WaitingListView";
import ConfirmationModal from "../components/ConfirmationModal";
import { joinQueue, startGame, endGame } from "../services/api";

export default function HomeScreen() {
  const [player, setPlayer] = useState<any>(null);
  const { game, queue, loading, refresh } = useGameState();
  const [refreshing, setRefreshing] = useState(false);
  const [pendingGameId, setPendingGameId] = useState<number | null>(null);
  usePushToken(player?.id ?? null);

  // Load stored player
  useEffect(() => {
    AsyncStorage.getItem("vb_player").then((raw) => {
      if (raw) setPlayer(JSON.parse(raw));
    });
  }, []);

  // Listen for push notification taps
  const notifListener = useRef<any>();
  useEffect(() => {
    notifListener.current = Notifications.addNotificationResponseReceivedListener(
      (response) => {
        const data = response.notification.request.content.data as any;
        if (data?.action === "confirm" && data?.game_id) {
          setPendingGameId(data.game_id);
        }
      }
    );
    return () => notifListener.current?.remove();
  }, []);

  // Also detect pending slot from live game state
  const pendingSlot =
    player && game
      ? game.slots.find(
          (s: any) => s.player_id === player.id && s.status === "pending_confirmation"
        )
      : null;

  const effectiveGameId = pendingGameId ?? (pendingSlot ? game?.id : null);
  const inQueue = player ? queue.some((e: any) => e.player_id === player.id) : false;
  const isGameActive = game && (game.status === "open" || game.status === "in_progress");

  const onRefresh = async () => {
    setRefreshing(true);
    await refresh();
    setRefreshing(false);
  };

  const handleJoin = async () => {
    if (!player) { router.push("/register"); return; }
    try {
      await joinQueue(player.id);
      refresh();
    } catch (err: any) {
      Alert.alert("Error", err?.response?.data?.detail ?? "Could not join queue.");
    }
  };

  const handleStart = async () => {
    try {
      await startGame();
      refresh();
    } catch (err: any) {
      Alert.alert("Error", err?.response?.data?.detail ?? "Could not start game.");
    }
  };

  const handleEnd = async () => {
    if (!game) return;
    Alert.alert("End Game?", `End game #${game.id}?`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "End Game",
        style: "destructive",
        onPress: async () => {
          try {
            await endGame(game.id);
            refresh();
          } catch {
            Alert.alert("Error", "Could not end game.");
          }
        },
      },
    ]);
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      {/* Header player info */}
      {player ? (
        <View style={styles.playerBanner}>
          <Text style={styles.playerName}>Playing as: {player.display_name}</Text>
          <TouchableOpacity onPress={() => router.push("/register")}>
            <Text style={styles.switchLink}>Switch</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <TouchableOpacity style={styles.registerBtn} onPress={() => router.push("/register")}>
          <Text style={styles.registerBtnText}>Register / Sign In →</Text>
        </TouchableOpacity>
      )}

      {loading && !game ? (
        <View style={styles.center}>
          <Text style={styles.grey}>Loading…</Text>
        </View>
      ) : (
        <>
          <CourtView game={game} currentPlayerId={player?.id} />
          <WaitingListView queue={queue} currentPlayerId={player?.id} onRefresh={refresh} />
        </>
      )}

      {/* Join queue button */}
      {player && !inQueue && !pendingSlot && (
        <TouchableOpacity style={styles.joinBtn} onPress={handleJoin}>
          <Text style={styles.joinBtnText}>Join Waiting List</Text>
        </TouchableOpacity>
      )}

      {/* Past games link */}
      <TouchableOpacity onPress={() => router.push("/history")} style={styles.historyLink}>
        <Text style={styles.historyLinkText}>View Past Games →</Text>
      </TouchableOpacity>

      {/* Operator controls */}
      <View style={styles.operatorSection}>
        <Text style={styles.operatorLabel}>Operator Controls</Text>
        {!isGameActive && (
          <TouchableOpacity style={styles.operatorBtn} onPress={handleStart}>
            <Text style={styles.operatorBtnText}>Start New Game</Text>
          </TouchableOpacity>
        )}
        {isGameActive && (
          <TouchableOpacity style={[styles.operatorBtn, styles.endBtn]} onPress={handleEnd}>
            <Text style={styles.operatorBtnText}>End Game #{game?.id}</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Confirmation modal */}
      {effectiveGameId && player && (
        <ConfirmationModal
          visible={true}
          gameId={effectiveGameId}
          playerId={player.id}
          onDone={() => {
            setPendingGameId(null);
            refresh();
          }}
        />
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f0f4ff" },
  content: { padding: 16, paddingBottom: 40 },
  playerBanner: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
  },
  playerName: { fontSize: 14, color: "#374151", fontWeight: "500" },
  switchLink: { fontSize: 13, color: "#3b82f6" },
  registerBtn: {
    backgroundColor: "#1e40af",
    borderRadius: 12,
    padding: 14,
    alignItems: "center",
    marginBottom: 12,
  },
  registerBtnText: { color: "#fff", fontWeight: "600", fontSize: 15 },
  center: { alignItems: "center", paddingVertical: 40 },
  grey: { color: "#9ca3af" },
  joinBtn: {
    backgroundColor: "#22c55e",
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: "center",
    marginBottom: 12,
  },
  joinBtnText: { color: "#fff", fontWeight: "700", fontSize: 16 },
  historyLink: { alignItems: "center", paddingVertical: 8, marginBottom: 16 },
  historyLinkText: { color: "#3b82f6", fontSize: 14 },
  operatorSection: {
    borderTopWidth: 1,
    borderTopColor: "#e5e7eb",
    borderStyle: "dashed",
    paddingTop: 16,
  },
  operatorLabel: { fontSize: 12, color: "#9ca3af", textAlign: "center", marginBottom: 8 },
  operatorBtn: {
    backgroundColor: "#1e40af",
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
  },
  endBtn: { backgroundColor: "#4b5563" },
  operatorBtnText: { color: "#fff", fontWeight: "600", fontSize: 15 },
});
