import type { QueueEntry, Player } from "../types";
import PlayerBadge from "./PlayerBadge";
import { leaveQueue, deferQueue } from "../api/client";

interface Props {
  queue: QueueEntry[];
  currentPlayerId?: number | null;
  currentPlayer?: Player | null;
  currentPlayerResponse?: "yes" | "no" | "defer" | null;
  onRefresh: () => void;
}

export default function WaitingListView({ queue, currentPlayerId, currentPlayer, currentPlayerResponse, onRefresh }: Props) {
  const handleLeave = async (playerId: number) => {
    if (!currentPlayer) return;
    if (!confirm("Leave the waiting list?")) return;
    try {
      await leaveQueue(playerId, currentPlayer.secret_token);
      onRefresh();
    } catch {
      alert("Failed to leave queue.");
    }
  };

  const handleDefer = async (playerId: number) => {
    if (!currentPlayer) return;
    try {
      await deferQueue(playerId, currentPlayer.secret_token);
      onRefresh();
    } catch {
      alert("Already last in the queue.");
    }
  };

  return (
    <div className="bg-white rounded-2xl shadow p-6">
      <h2 className="text-lg font-bold text-gray-800 mb-4">
        Waiting List ({queue.length})
      </h2>

      {queue.length === 0 ? (
        <p className="text-gray-400 text-sm text-center py-4">No players waiting.</p>
      ) : (
        <div className="space-y-2">
          {queue.map((entry, idx) => (
            <div key={entry.player_id} className="flex items-center gap-2">
              <span className="text-xs text-gray-400 w-5 text-right">{idx + 1}.</span>
              <div className="flex-1 flex items-center gap-1.5">
                <PlayerBadge
                  displayName={entry.display_name}
                  signupNumber={entry.signup_number}
                  highlight={entry.player_id === currentPlayerId}
                />
                {entry.player_id === currentPlayerId && currentPlayerResponse === "defer" && (
                  <span className="text-xs font-bold text-blue-500 border border-blue-300 rounded px-1 py-0.5 leading-none">D</span>
                )}
              </div>
              {entry.player_id === currentPlayerId && (
                <>
                  <button
                    onClick={() => handleDefer(entry.player_id)}
                    className="text-xs text-yellow-500 hover:text-yellow-700 px-2 py-1 rounded border border-yellow-200 hover:border-yellow-400 transition"
                  >
                    Defer
                  </button>
                  <button
                    onClick={() => handleLeave(entry.player_id)}
                    className="text-xs text-red-400 hover:text-red-600 px-2 py-1 rounded border border-red-200 hover:border-red-400 transition"
                  >
                    Leave
                  </button>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
