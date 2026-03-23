import { useState } from "react";
import { confirm } from "../api/client";
import type { Game } from "../types";

interface Props {
  game: Game;
  playerId: number;
  playerToken: string;
  onDone: () => void;
}

export default function ConfirmationBanner({ game, playerId, playerToken, onDone }: Props) {
  const [loading, setLoading] = useState(false);

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
    <div className="bg-yellow-50 border-2 border-yellow-400 rounded-2xl p-5 mb-4 shadow-lg animate-pulse-once">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-2xl">🏐</span>
        <div>
          <p className="font-bold text-yellow-800 text-lg">You're up for Game #{game.id}!</p>
          <p className="text-yellow-700 text-sm">Confirm your spot to play.</p>
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
          Defer — Keep my spot
        </button>
      </div>
      <p className="text-xs text-yellow-600 mt-3 text-center">
        You have {Math.floor(game.id)} minutes to respond. No response = moved to end of queue.
      </p>
    </div>
  );
}
