import { useState } from "react";
import { useGameState } from "../hooks/useGameState";
import { usePlayer } from "../hooks/usePlayer";
import CourtView from "../components/CourtView";
import WaitingListView from "../components/WaitingListView";
import PlayerRegistration from "../components/PlayerRegistration";
import ConfirmationBanner from "../components/ConfirmationBanner";
import PastGamesView from "../components/PastGamesView";
import { joinQueue, startGame, endGame, deregisterPlayer } from "../api/client";
import type { Player } from "../types";

type Tab = "live" | "history";

export default function Home() {
  const { player, setPlayer } = usePlayer();
  const { game, queue, loading, refresh } = useGameState();
  const [tab, setTab] = useState<Tab>("live");
  const [showRegister, setShowRegister] = useState(!player);

  const pendingSlot = player && game
    ? game.slots.find(
        (s) => s.player_id === player.id && s.status === "pending_confirmation"
      )
    : null;

  const inQueue = player ? queue.some((e) => e.player_id === player.id) : false;

  const handleJoin = async () => {
    if (!player) { setShowRegister(true); return; }
    try {
      await joinQueue(player.id, player.secret_token);
      refresh();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Could not join queue.";
      alert(msg);
    }
  };

  const operatorSecret = import.meta.env.VITE_OPERATOR_SECRET as string;

  const handleStart = async () => {
    try {
      await startGame(operatorSecret);
      refresh();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Could not start game.";
      alert(msg);
    }
  };

  const handleEnd = async () => {
    if (!game) return;
    if (!confirm(`End game #${game.id}?`)) return;
    try {
      await endGame(game.id, operatorSecret);
      refresh();
    } catch {
      alert("Could not end game.");
    }
  };

  const handleRegistered = (p: Player) => {
    setPlayer(p);
    setShowRegister(false);
  };

  const handleDeregister = async () => {
    if (!player) return;
    if (!confirm("Permanently delete your account? This cannot be undone.")) return;
    try {
      await deregisterPlayer(player.id, player.secret_token);
      setPlayer(null);
      setShowRegister(true);
      refresh();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Could not deregister.";
      alert(msg);
    }
  };

  const isGameActive = game && (game.status === "open" || game.status === "in_progress");

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-yellow-50">
      {/* Header */}
      <header className="bg-white shadow-sm sticky top-0 z-10">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-2xl">🏐</span>
            <h1 className="font-bold text-gray-800 text-lg">Volleyball Scheduler</h1>
          </div>
          {player ? (
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">{player.display_name}</span>
              <button
                onClick={() => { setPlayer(null); setShowRegister(true); }}
                className="text-xs text-gray-400 hover:text-gray-600 underline"
              >
                Sign Out
              </button>
              <button
                onClick={handleDeregister}
                className="text-xs text-red-400 hover:text-red-600 underline"
              >
                Deregister
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowRegister(true)}
              className="text-sm text-blue-600 font-medium hover:underline"
            >
              Register / Sign In
            </button>
          )}
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-6 space-y-4">
        {/* Registration panel */}
        {showRegister && !player && (
          <PlayerRegistration onRegistered={handleRegistered} />
        )}
        {showRegister && player && (
          <PlayerRegistration
            onRegistered={handleRegistered}
            onCancel={() => setShowRegister(false)}
          />
        )}

        {/* Confirmation banner */}
        {pendingSlot && player && game && (
          <ConfirmationBanner game={game} playerId={player.id} playerToken={player.secret_token} onDone={refresh} />
        )}

        {/* Tab navigation */}
        <div className="flex bg-white rounded-xl shadow overflow-hidden">
          {(["live", "history"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 py-2 text-sm font-medium transition ${
                tab === t
                  ? "bg-blue-600 text-white"
                  : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              {t === "live" ? "Live" : "Past Games"}
            </button>
          ))}
        </div>

        {tab === "live" && (
          <>
            {loading ? (
              <div className="text-center py-12 text-gray-400">Loading…</div>
            ) : (
              <>
                <CourtView game={game} currentPlayerId={player?.id} />
                <WaitingListView
                  queue={queue}
                  currentPlayerId={player?.id}
                  currentPlayer={player}
                  onRefresh={refresh}
                />
              </>
            )}

            {/* Player actions */}
            {player && !inQueue && !pendingSlot && (
              <button
                onClick={handleJoin}
                className="w-full bg-green-500 hover:bg-green-600 text-white font-semibold py-3 rounded-2xl shadow transition"
              >
                Join Waiting List
              </button>
            )}

            {/* Operator controls */}
            <div className="border-t border-dashed border-gray-200 pt-4">
              <p className="text-xs text-gray-400 mb-2 text-center">Operator Controls</p>
              <div className="flex gap-3">
                {!isGameActive && (
                  <button
                    onClick={handleStart}
                    className="flex-1 bg-volleyball-blue hover:bg-blue-800 text-white text-sm font-medium py-2 rounded-xl transition"
                  >
                    Start New Game
                  </button>
                )}
                {isGameActive && (
                  <button
                    onClick={handleEnd}
                    className="flex-1 bg-gray-600 hover:bg-gray-700 text-white text-sm font-medium py-2 rounded-xl transition"
                  >
                    End Game #{game?.id}
                  </button>
                )}
              </div>
            </div>
          </>
        )}

        {tab === "history" && <PastGamesView />}
      </main>

      {/* Footer */}
      <footer className="max-w-2xl mx-auto px-4 py-8 text-center space-y-3">
        <div className="border-t border-gray-200 pt-6">
          <p className="text-sm text-gray-500">
            This app was built by a teenager. If it made your game day easier, consider buying her a coffee!
          </p>
          <button
            onClick={() => {
              const el = document.getElementById("donate-info");
              if (el) el.classList.toggle("hidden");
            }}
            className="mt-3 inline-flex items-center gap-2 bg-pink-500 hover:bg-pink-600 text-white font-semibold px-5 py-2 rounded-2xl shadow transition"
          >
            ❤️ Donate
          </button>
          <div id="donate-info" className="hidden mt-4 bg-pink-50 border border-pink-200 rounded-2xl p-5 text-sm text-gray-700 space-y-2 text-left">
            <p className="font-semibold text-pink-700">Support Allison Zhang 🏐</p>
            <p>
              Any amount is hugely appreciated and goes directly to a teenager who
              spent her time building this for the community.
            </p>
            <ul className="space-y-1 mt-2">
              <li>💸 <span className="font-medium">Zelle</span> — allisonazhang@gmail.com</li>
              <li>💳 <span className="font-medium">PayPal</span> — <a href="https://paypal.me/allisonazhang" target="_blank" rel="noreferrer" className="text-blue-600 underline">paypal.me/allisonazhang</a></li>
              <li>📱 <span className="font-medium">Venmo</span> — <a href="https://venmo.com/allisonazhang" target="_blank" rel="noreferrer" className="text-blue-600 underline">@allisonazhang</a></li>
              <li>🍎 <span className="font-medium">Apple Pay / Cash App</span> — allisonazhang@gmail.com</li>
            </ul>
            <p className="text-xs text-gray-400 mt-2">Thank you so much! 🙏</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
