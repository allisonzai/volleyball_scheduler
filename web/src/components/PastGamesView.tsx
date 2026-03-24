import { useEffect, useState } from "react";
import { listGames, clearHistory } from "../api/client";
import type { Game, SlotStatus } from "../types";
import PlayerBadge from "./PlayerBadge";

const STATUS_TAG: Record<
  SlotStatus,
  { label: string; className: string } | null
> = {
  confirmed:            { label: "Playing",     className: "bg-green-100 text-green-700" },
  withdrawn:            { label: "Left",         className: "bg-orange-100 text-orange-700" },
  declined:             { label: "Declined",     className: "bg-red-100 text-red-600" },
  deferred:             { label: "Deferred",     className: "bg-blue-100 text-blue-700" },
  timed_out:            { label: "No response",  className: "bg-gray-100 text-gray-500" },
  pending_confirmation: null,
};

export default function PastGamesView() {
  const [games, setGames] = useState<Game[]>([]);
  const [loading, setLoading] = useState(true);
  const operatorSecret = import.meta.env.VITE_OPERATOR_SECRET as string;

  const load = () => {
    setLoading(true);
    listGames("finished")
      .then(setGames)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

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
          {games.map((game) => {
            const slots = game.slots.filter(
              (s) => s.status !== "pending_confirmation"
            );
            return (
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
                    {game.ended_at
                      ? new Date(game.ended_at + "Z").toLocaleString()
                      : "ongoing"}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {slots.map((slot) => {
                    const tag = STATUS_TAG[slot.status];
                    return (
                      <div key={slot.id} className="flex items-center gap-1.5">
                        <div className="flex-1 min-w-0">
                          <PlayerBadge
                            displayName={slot.display_name}
                            signupNumber={slot.signup_number}
                          />
                        </div>
                        {tag && (
                          <span
                            className={`shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded ${tag.className}`}
                          >
                            {tag.label}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}
