import { useEffect, useState, useCallback } from "react";
import { getCurrentGame, getQueue } from "../api/client";
import type { Game, QueueEntry } from "../types";

export function useGameState() {
  const [game, setGame] = useState<Game | null>(null);
  const [queue, setQueue] = useState<QueueEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [g, q] = await Promise.all([getCurrentGame(), getQueue()]);
      setGame(g);
      setQueue(q);
      setError(null);
    } catch (e) {
      setError("Failed to load game state.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();

    // SSE for real-time updates
    const es = new EventSource("/api/events");
    es.onmessage = (event) => {
      const data = event.data;
      if (data === "connected") return;
      try {
        const parsed = JSON.parse(data);
        if (parsed.type === "game_update" || parsed.type === "queue_update") {
          refresh();
        }
      } catch {
        refresh();
      }
    };
    es.onerror = () => {
      // Fall back to polling every 5s if SSE fails
    };

    // Polling fallback every 5s
    const poll = setInterval(refresh, 5000);

    return () => {
      es.close();
      clearInterval(poll);
    };
  }, [refresh]);

  return { game, queue, loading, error, refresh };
}
