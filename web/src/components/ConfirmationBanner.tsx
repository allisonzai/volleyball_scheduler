import { useState, useEffect } from "react";
import { confirm } from "../api/client";
import type { Game, Slot } from "../types";

function useCountdown(notifiedAt: string | null, timeoutSeconds: number): number {
  const getSecondsLeft = () => {
    if (!notifiedAt) return timeoutSeconds;
    const elapsed = Math.floor((Date.now() - new Date(notifiedAt + "Z").getTime()) / 1000);
    return Math.max(0, timeoutSeconds - elapsed);
  };

  const [secondsLeft, setSecondsLeft] = useState(getSecondsLeft);

  useEffect(() => {
    setSecondsLeft(getSecondsLeft());
  }, [notifiedAt, timeoutSeconds]);

  useEffect(() => {
    if (secondsLeft <= 0) return;
    const id = setInterval(() => setSecondsLeft(getSecondsLeft()), 1000);
    return () => clearInterval(id);
  }, [notifiedAt, timeoutSeconds]);

  return secondsLeft;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

interface Props {
  game: Game;
  slot: Slot;
  playerId: number;
  playerToken: string;
  timeoutSeconds: number;
  onDone: () => void;
}

export default function ConfirmationBanner({ game, slot, playerId, playerToken, timeoutSeconds, onDone }: Props) {
  const [loading, setLoading] = useState(false);
  const secondsLeft = useCountdown(slot.notified_at, timeoutSeconds);

  const urgent = secondsLeft <= 60;

  const handleResponse = async (response: "yes" | "no" | "defer") => {
    setLoading(true);
    try {
      await confirm(playerId, game.id, response, playerToken);
      onDone();
    } catch {
      alert("Failed to submit response. Try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`border-2 rounded-2xl p-5 mb-4 shadow-lg ${urgent ? "bg-red-50 border-red-400" : "bg-yellow-50 border-yellow-400"}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🏐</span>
          <div>
            <p className={`font-bold text-lg ${urgent ? "text-red-800" : "text-yellow-800"}`}>
              You're up for Game #{game.id}!
            </p>
            <p className={`text-sm ${urgent ? "text-red-700" : "text-yellow-700"}`}>
              Confirm your spot to play.
            </p>
          </div>
        </div>
        <div className={`text-2xl font-mono font-bold tabular-nums ${urgent ? "text-red-600 animate-pulse" : "text-yellow-700"}`}>
          {formatTime(secondsLeft)}
        </div>
      </div>
      <div className="flex gap-3 flex-wrap">
        <button
          disabled={loading}
          onClick={() => handleResponse("yes")}
          className="flex-1 bg-green-500 hover:bg-green-600 text-white font-semibold py-2 px-4 rounded-xl transition disabled:opacity-50"
        >
          Yes — I'm playing
        </button>
        <button
          disabled={loading}
          onClick={() => handleResponse("no")}
          className="flex-1 bg-red-400 hover:bg-red-500 text-white font-semibold py-2 px-4 rounded-xl transition disabled:opacity-50"
        >
          No — Skip me
        </button>
        <button
          disabled={loading}
          onClick={() => handleResponse("defer")}
          className="flex-1 bg-blue-400 hover:bg-blue-500 text-white font-semibold py-2 px-4 rounded-xl transition disabled:opacity-50"
        >
          Defer — Swap with next
        </button>
      </div>
      <p className={`text-xs mt-3 text-center ${urgent ? "text-red-500 font-medium" : "text-yellow-600"}`}>
        {secondsLeft <= 0
          ? "Time's up — you've been moved to the end of the queue."
          : "No response = treated as No (moved to end of queue)."}
      </p>
    </div>
  );
}
