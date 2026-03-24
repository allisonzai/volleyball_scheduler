import { useEffect, useState, useCallback } from "react";
import { getCurrentGame, getQueue, getSettings } from "../api/client";
import type { Game, QueueEntry } from "../types";

export function useGameState() {
  const [game, setGame] = useState<Game | null>(null);
  const [queue, setQueue] = useState<QueueEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeoutSeconds, setTimeoutSeconds] = useState(300);
  const [fillWaitSeconds, setFillWaitSeconds] = useState(60);

  const refresh = useCallback(async () => {
    try {
      const [g, q, s] = await Promise.all([
        getCurrentGame(),
        getQueue(),
        getSettings(),
      ]);
      setGame(g && typeof g === "object" && "id" in g ? g : null);
      setQueue(Array.isArray(q) ? q : []);
      setTimeoutSeconds(s.confirm_timeout_seconds);
      setFillWaitSeconds(s.fill_wait_seconds);
      setError(null);
    } catch (e) {
      setError("Failed to load game state.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();

    // Poll every 5s for updates
    const poll = setInterval(refresh, 5000);

    return () => {
      clearInterval(poll);
    };
  }, [refresh]);

  return { game, queue, loading, error, refresh, timeoutSeconds, fillWaitSeconds };
}
