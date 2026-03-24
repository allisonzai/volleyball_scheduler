import { useState } from "react";
import { confirm } from "../api/client";
import type { Game, Slot } from "../types";
import { useCountdown, formatCountdown } from "../hooks/useCountdown";

interface Props {
  game: Game;
  slot: Slot;
  playerId: number;
  playerToken: string;
  timeoutSeconds: number;
  onDone: () => void;
  onResponse?: (r: "yes" | "no" | "defer") => void;
}

const CHOICE_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  yes:   { label: "✓ You're in — see you on the court!",  color: "text-green-700", bg: "bg-green-50 border-green-400" },
  no:    { label: "✗ Skipped — you've been removed from the game and waiting list.", color: "text-red-600",   bg: "bg-red-50 border-red-300"   },
  defer: { label: "⇄ Deferred — you've been swapped with the next player.",          color: "text-blue-700",  bg: "bg-blue-50 border-blue-400"  },
};

export default function ConfirmationBanner({ game, slot, playerId, playerToken, timeoutSeconds, onDone, onResponse }: Props) {
  const [loading, setLoading] = useState(false);
  const [chosen, setChosen] = useState<"yes" | "no" | "defer" | null>(null);
  const secondsLeft = useCountdown(slot.notified_at, timeoutSeconds);

  const urgent = secondsLeft <= 60;

  const handleResponse = async (response: "yes" | "no" | "defer") => {
    setLoading(true);
    try {
      await confirm(playerId, game.id, response, playerToken);
      setChosen(response);
      onResponse?.(response);
      setTimeout(onDone, 1500);
    } catch {
      alert("Failed to submit response. Try again.");
      setLoading(false);
    }
  };

  if (chosen) {
    const { label, color, bg } = CHOICE_LABELS[chosen];
    return (
      <div className={`border-2 rounded-2xl p-5 mb-4 shadow-lg ${bg}`}>
        <div className="flex items-center gap-3">
          <span className="text-2xl">🏐</span>
          <p className={`font-semibold text-base ${color}`}>{label}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`border-2 rounded-2xl p-5 mb-4 shadow-lg ${urgent ? "bg-red-50 border-red-400" : "bg-yellow-50 border-yellow-400"}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🏐</span>
          <div>
            <p className={`font-bold text-lg ${urgent ? "text-red-800" : "text-yellow-800"}`}>
              You're up for the next game!
            </p>
            <p className={`text-sm ${urgent ? "text-red-700" : "text-yellow-700"}`}>
              Confirm your spot to play.
            </p>
          </div>
        </div>
        <div className={`text-2xl font-mono font-bold tabular-nums ${urgent ? "text-red-600 animate-pulse" : "text-yellow-700"}`}>
          {formatCountdown(secondsLeft)}
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
          ? "Time's up — you've been removed from the game and waiting list."
          : "No response = treated as No — you'll be removed from the game and waiting list."}
      </p>
    </div>
  );
}
