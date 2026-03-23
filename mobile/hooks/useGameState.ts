import { useEffect, useState, useCallback } from "react";
import { getCurrentGame, getQueue } from "../services/api";

export function useGameState() {
  const [game, setGame] = useState<any>(null);
  const [queue, setQueue] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [g, q] = await Promise.all([getCurrentGame(), getQueue()]);
      setGame(g);
      setQueue(q);
      setError(null);
    } catch {
      setError("Failed to load game state.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  return { game, queue, loading, error, refresh };
}
