import type { Game, Player } from "../types";
import PlayerBadge from "./PlayerBadge";
import { leaveGame } from "../api/client";

interface Props {
  game: Game | null;
  currentPlayerId?: number | null;
  currentPlayer?: Player | null;
  onRefresh: () => void;
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  open: { label: "Confirming players…", color: "text-yellow-600" },
  in_progress: { label: "Game in progress", color: "text-green-600" },
  finished: { label: "Game finished", color: "text-gray-400" },
};

export default function CourtView({ game, currentPlayerId, currentPlayer, onRefresh }: Props) {
  const handleLeaveGame = async () => {
    if (!currentPlayer || !game) return;
    if (!confirm("Leave the current game? You'll be removed from the game and waiting list.")) return;
    try {
      await leaveGame(game.id, currentPlayer.secret_token);
      onRefresh();
    } catch {
      alert("Could not leave the game.");
    }
  };
  if (!game) {
    return (
      <div className="bg-white rounded-2xl shadow p-6 text-center text-gray-400">
        No active game. Sign up and an operator can start one.
      </div>
    );
  }

  const slots = Array.isArray(game.slots) ? game.slots : [];
  const confirmed = slots.filter((s) => s.status === "confirmed");
  const pending = slots.filter((s) => s.status === "pending_confirmation");
  const statusInfo = STATUS_LABELS[game.status] ?? { label: game.status, color: "text-gray-500" };

  return (
    <div className="bg-white rounded-2xl shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-gray-800">Current Game #{game.id}</h2>
        <span className={`text-sm font-medium ${statusInfo.color}`}>{statusInfo.label}</span>
      </div>

      {confirmed.length > 0 && (
        <div className="mb-4">
          <h3 className="text-xs uppercase tracking-wide text-gray-500 mb-2">
            On Court ({confirmed.length}/{game.max_players})
          </h3>
          <div className="grid grid-cols-2 gap-2">
            {confirmed.map((slot) => (
              <div key={slot.id} className="flex items-center gap-2">
                <div className="flex-1">
                  <PlayerBadge
                    displayName={slot.display_name}
                    signupNumber={slot.signup_number}
                    highlight={slot.player_id === currentPlayerId}
                  />
                </div>
                {slot.player_id === currentPlayerId && (
                  <button
                    onClick={handleLeaveGame}
                    className="text-xs text-red-400 hover:text-red-600 px-2 py-1 rounded border border-red-200 hover:border-red-400 transition"
                  >
                    Leave
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {pending.length > 0 && (
        <div>
          <h3 className="text-xs uppercase tracking-wide text-yellow-500 mb-2">
            Awaiting Confirmation ({pending.length})
          </h3>
          <div className="grid grid-cols-2 gap-2">
            {pending.map((slot) => (
              <div key={slot.id} className="flex items-center gap-2">
                <div className="flex-1">
                  <PlayerBadge
                    displayName={slot.display_name}
                    signupNumber={slot.signup_number}
                    highlight={slot.player_id === currentPlayerId}
                  />
                </div>
                <span className="text-xs text-yellow-500 animate-pulse">waiting…</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
