import { useEffect, useState } from "react";
import { listGames } from "../api/client";
import type { Game } from "../types";
import PlayerBadge from "./PlayerBadge";

export default function PastGamesView() {
  const [games, setGames] = useState<Game[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listGames("finished")
      .then(setGames)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center text-gray-400 py-8">Loading…</div>;
  if (games.length === 0)
    return <div className="text-center text-gray-400 py-8">No past games yet.</div>;

  return (
    <div className="space-y-4">
      {games.map((game) => (
        <div key={game.id} className="bg-white rounded-2xl shadow p-5">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-bold text-gray-700">Game #{game.id}</h3>
            <span className="text-xs text-gray-400">
              {game.started_at
                ? new Date(game.started_at).toLocaleString()
                : "—"}
              {" → "}
              {game.ended_at ? new Date(game.ended_at).toLocaleString() : "ongoing"}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {game.slots
              .filter((s) => s.status === "confirmed")
              .map((slot) => (
                <PlayerBadge
                  key={slot.id}
                  displayName={slot.display_name}
                  signupNumber={slot.signup_number}
                />
              ))}
          </div>
        </div>
      ))}
    </div>
  );
}
