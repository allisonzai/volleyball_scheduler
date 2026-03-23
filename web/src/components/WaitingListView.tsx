import type { QueueEntry } from "../types";
import PlayerBadge from "./PlayerBadge";
import { leaveQueue } from "../api/client";

interface Props {
  queue: QueueEntry[];
  currentPlayerId?: number | null;
  onRefresh: () => void;
}

export default function WaitingListView({ queue, currentPlayerId, onRefresh }: Props) {
  const handleLeave = async (playerId: number) => {
    if (!confirm("Leave the waiting list?")) return;
    try {
      await leaveQueue(playerId);
      onRefresh();
    } catch {
      alert("Failed to leave queue.");
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
              <div className="flex-1">
                <PlayerBadge
                  displayName={entry.display_name}
                  signupNumber={entry.signup_number}
                  highlight={entry.player_id === currentPlayerId}
                />
              </div>
              {entry.player_id === currentPlayerId && (
                <button
                  onClick={() => handleLeave(entry.player_id)}
                  className="text-xs text-red-400 hover:text-red-600 px-2 py-1 rounded border border-red-200 hover:border-red-400 transition"
                >
                  Leave
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
