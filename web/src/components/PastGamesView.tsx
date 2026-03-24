import { useEffect, useState } from "react";
import { listGames, clearHistory } from "../api/client";
import type { Game } from "../types";
import PlayerBadge from "./PlayerBadge";

export default function PastGamesView() {
  const [games, setGames] = useState<Game[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    listGames("finished")
      .then(setGames)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const operatorSecret = import.meta.env.VITE_OPERATOR_SECRET as string;

  const handleClearHistory = async () => {
    if (!confirm("Delete all past game records? This cannot be undone.")) return;
    try {
      await clearHistory(operatorSecret);
      setGames([]);
    } catch {
      alert("Could not clear history.");
    }
  };

  if (loading) return <div className="text-center text-gray-400 py-8">Loading…</div>;

  return (
    <div className="space-y-4">
      {games.length === 0 ? (
        <div className="text-center text-gray-400 py-8">No past games yet.</div>
      ) : (
        <>
          <div className="flex justify-end">
            <button
              onClick={handleClearHistory}
              className="text-xs text-red-400 hover:text-red-600 underline"
            >
              Clear History
            </button>
          </div>
          {games.map((game) => (
            <div key={game.id} className="bg-white rounded-2xl shadow p-5">
              <div className="flex justify-between items-center mb-3">
                <h3 className="font-bold text-gray-700">
                  Game #{game.game_number ?? game.id}
                </h3>
                <span className="text-xs text-gray-400">
                  {game.started_at
                    ? new Date(game.started_at + "Z").toLocaleString()
                    : "—"}
                  {" → "}
                  {game.ended_at ? new Date(game.ended_at + "Z").toLocaleString() : "ongoing"}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {game.slots
                  .filter((s) => s.status === "confirmed" || s.status === "withdrawn")
                  .map((slot) => (
                    <div key={slot.id} className="relative">
                      <PlayerBadge
                        displayName={slot.display_name}
                        signupNumber={slot.signup_number}
                      />
                      {slot.status === "withdrawn" && (
                        <span className="absolute top-1 right-1 text-[10px] text-red-400 font-medium">
                          left
                        </span>
                      )}
                    </div>
                  ))}
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
