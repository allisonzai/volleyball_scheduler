import type { Game, Player, Slot } from "../types";
import PlayerBadge from "./PlayerBadge";
import { leaveGame } from "../api/client";
import { useCountdown, formatCountdown } from "../hooks/useCountdown";

interface Props {
  game: Game | null;
  currentPlayerId?: number | null;
  currentPlayer?: Player | null;
  timeoutSeconds: number;
  currentPlayerResponse?: "yes" | "no" | "defer" | null;
  onRefresh: () => void;
}

function SlotTimer({ slot, timeoutSeconds }: { slot: Slot; timeoutSeconds: number }) {
  const secondsLeft = useCountdown(slot.notified_at, timeoutSeconds);
  const urgent = secondsLeft <= 60;
  return (
    <span
      className={`flex items-center gap-1 text-xs font-mono tabular-nums ${
        urgent ? "text-red-500 animate-pulse" : "text-yellow-600"
      }`}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        className="w-3.5 h-3.5 shrink-0"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </svg>
      {formatCountdown(secondsLeft)}
    </span>
  );
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  open: { label: "Confirming players…", color: "text-yellow-600" },
  in_progress: { label: "Game in progress", color: "text-green-600" },
  finished: { label: "Game finished", color: "text-gray-400" },
};

export default function CourtView({ game, currentPlayerId, currentPlayer, timeoutSeconds, currentPlayerResponse, onRefresh }: Props) {
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

  // During confirmation phase (OPEN), merge confirmed + pending so everyone
  // is visible together: confirmed slots show ✓, pending slots show timer.
  const isConfirming = game.status === "open";
  const awaitingSlots = isConfirming ? [...confirmed, ...pending] : [];
  const courtSlots = isConfirming ? [] : confirmed;

  const statusInfo =
    game.status === "open" && pending.length === 0
      ? { label: "Waiting for players…", color: "text-gray-400" }
      : STATUS_LABELS[game.status] ?? { label: game.status, color: "text-gray-500" };

  const Checkmark = () => (
    <span className="text-green-500 shrink-0">
      <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="20 6 9 17 4 12" />
      </svg>
    </span>
  );

  return (
    <div className="bg-white rounded-2xl shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-gray-800">Current Game #{game.id}</h2>
        <span className={`text-sm font-medium ${statusInfo.color}`}>{statusInfo.label}</span>
      </div>

      {/* Confirmation phase: all slots together, confirmed ✓ / pending timer */}
      {awaitingSlots.length > 0 && (
        <div className="mb-4">
          <h3 className="text-xs uppercase tracking-wide text-yellow-500 mb-2">
            Awaiting Confirmation ({confirmed.length}/{game.max_players} confirmed)
          </h3>
          <div className="grid grid-cols-2 gap-2">
            {awaitingSlots.map((slot) => {
              const isConfirmed =
                slot.status === "confirmed" ||
                (slot.player_id === currentPlayerId && currentPlayerResponse === "yes");
              return (
                <div key={slot.id} className="flex items-center gap-2">
                  <div className="flex-1">
                    <PlayerBadge
                      displayName={slot.display_name}
                      signupNumber={slot.signup_number}
                      highlight={slot.player_id === currentPlayerId}
                    />
                  </div>
                  {isConfirmed ? (
                    <Checkmark />
                  ) : (
                    <SlotTimer slot={slot} timeoutSeconds={timeoutSeconds} />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Game in progress: show confirmed players on court */}
      {courtSlots.length > 0 && (
        <div className="mb-4">
          <h3 className="text-xs uppercase tracking-wide text-gray-500 mb-2">
            On Court ({courtSlots.length}/{game.max_players})
          </h3>
          <div className="grid grid-cols-2 gap-2">
            {courtSlots.map((slot) => (
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
    </div>
  );
}
