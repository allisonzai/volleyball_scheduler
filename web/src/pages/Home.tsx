import { useState, useEffect } from "react";
import { QRCodeSVG } from "qrcode.react";
import { useGameState } from "../hooks/useGameState";
import { usePlayer } from "../hooks/usePlayer";
import CourtView from "../components/CourtView";
import WaitingListView from "../components/WaitingListView";
import PlayerRegistration from "../components/PlayerRegistration";
import ConfirmationBanner from "../components/ConfirmationBanner";
import PastGamesView from "../components/PastGamesView";
import ActivityView from "../components/ActivityView";
import { joinQueue, startGame, beginGame, endGame, deregisterPlayer, resetAll, updateSettings } from "../api/client";
import type { Player } from "../types";

type Tab = "live" | "history" | "events";

export default function Home() {
  const { player, setPlayer } = usePlayer();
  const { game, queue, loading, refresh, timeoutSeconds, fillWaitSeconds } = useGameState();
  const [tab, setTab] = useState<Tab>("live");
  const [showRegister, setShowRegister] = useState(!player);
  const [showQR, setShowQR] = useState(false);
  const [playerResponse, setPlayerResponse] = useState<"yes" | "no" | "defer" | null>(null);
  const [timeoutInput, setTimeoutInput] = useState("5");
  const [fillWaitInput, setFillWaitInput] = useState("1");
  const [now, setNow] = useState(new Date());
  const pageUrl = window.location.href;

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  // Keep input fields in sync when server values change (e.g. after a fill_wait)
  useEffect(() => {
    setTimeoutInput(String(Math.round((timeoutSeconds / 60) * 10) / 10));
  }, [timeoutSeconds]);

  useEffect(() => {
    setFillWaitInput(String(Math.round((fillWaitSeconds / 60) * 10) / 10));
  }, [fillWaitSeconds]);

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

  const handleSaveTimeout = async () => {
    const mins = parseFloat(timeoutInput);
    if (isNaN(mins) || mins < 0.5) {
      alert("Minimum timeout is 0.5 minutes (30 seconds).");
      return;
    }
    const fillMins = parseFloat(fillWaitInput);
    if (isNaN(fillMins) || fillMins < 0) {
      alert("Fill wait must be >= 0 minutes.");
      return;
    }
    try {
      await updateSettings(
        Math.round(mins * 60),
        Math.round(fillMins * 60),
        operatorSecret,
      );
      refresh();
    } catch {
      alert("Could not update settings.");
    }
  };

  const handleReset = async () => {
    if (!confirm("Start Over? This will cancel the current game and clear the waiting list. Player accounts are kept.")) return;
    try {
      await resetAll(operatorSecret);
      refresh();
    } catch {
      alert("Could not reset.");
    }
  };

  const handleBegin = async () => {
    if (!game) return;
    if (!confirm(`Begin game #${game.id} now? Unconfirmed players will be removed.`)) return;
    try {
      await beginGame(game.id, operatorSecret);
      refresh();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Could not begin game.";
      alert(msg);
    }
  };

  const handleEnd = async () => {
    if (!game) return;
    if (!confirm(`End game #${game.game_number}?`)) return;
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

  const isStaging = game?.status === "open";
  const isPlaying = game?.status === "in_progress";
  const isGameActive = isStaging || isPlaying;

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-yellow-50">
      {/* Header */}
      <header className="bg-white shadow-sm sticky top-0 z-10">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-2xl">🏐</span>
            <h1 className="font-bold text-gray-800 text-lg">Volleyball Scheduler</h1>
            <button
              onClick={() => setShowQR((v) => !v)}
              title="Share QR code"
              className="ml-1 text-gray-400 hover:text-blue-500 transition"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
                <rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="3" height="3" />
                <rect x="19" y="14" width="2" height="2" /><rect x="14" y="19" width="2" height="2" />
                <rect x="18" y="18" width="3" height="3" />
              </svg>
            </button>
          </div>
          <div className="bg-gray-900 text-green-400 font-mono text-sm font-bold px-3 py-1 rounded-lg tracking-widest tabular-nums shadow-inner border border-gray-700 select-none">
            {now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })}
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

      {showQR && (
        <div className="bg-white border-b border-gray-100 shadow-sm">
          <div className="max-w-2xl mx-auto px-4 py-4 flex flex-col items-center gap-2">
            <p className="text-sm text-gray-500">Scan to join on your phone</p>
            <QRCodeSVG value={pageUrl} size={180} />
            <p className="text-xs text-gray-400 break-all">{pageUrl}</p>
          </div>
        </div>
      )}

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
          <ConfirmationBanner game={game} slot={pendingSlot} playerId={player.id} playerToken={player.secret_token} timeoutSeconds={timeoutSeconds} onDone={() => { setPlayerResponse(null); refresh(); }} onResponse={setPlayerResponse} />
        )}

        {/* Tab navigation */}
        <div className="flex bg-white rounded-xl shadow overflow-hidden">
          {(["live", "history", "events"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 py-2 text-sm font-medium transition ${
                tab === t
                  ? "bg-blue-600 text-white"
                  : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              {t === "live" ? "Live" : t === "history" ? "Past Games" : "Events"}
            </button>
          ))}
        </div>

        {tab === "live" && (
          <>
            {loading ? (
              <div className="text-center py-12 text-gray-400">Loading…</div>
            ) : (
              <>
                <CourtView game={game} currentPlayerId={player?.id} currentPlayer={player} timeoutSeconds={timeoutSeconds} currentPlayerResponse={playerResponse} onRefresh={refresh} />
                <WaitingListView
                  queue={queue}
                  currentPlayerId={player?.id}
                  currentPlayer={player}
                  currentPlayerResponse={playerResponse}
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
              <div className="flex flex-wrap items-center gap-2 mb-3">
                <label className="text-xs text-gray-500 whitespace-nowrap">Timeout</label>
                <input
                  type="number"
                  min="0.5"
                  step="0.5"
                  value={timeoutInput}
                  onChange={(e) => setTimeoutInput(e.target.value)}
                  className="w-14 text-sm border border-gray-300 rounded-lg px-2 py-1 text-center"
                />
                <span className="text-xs text-gray-500">min</span>
                <span className="text-xs text-gray-300">|</span>
                <label className="text-xs text-gray-500 whitespace-nowrap">Fill wait</label>
                <input
                  type="number"
                  min="0"
                  step="0.5"
                  value={fillWaitInput}
                  onChange={(e) => setFillWaitInput(e.target.value)}
                  className="w-14 text-sm border border-gray-300 rounded-lg px-2 py-1 text-center"
                />
                <span className="text-xs text-gray-500">min</span>
                <button
                  onClick={handleSaveTimeout}
                  className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-1 rounded-lg border border-gray-300 transition"
                >
                  Save
                </button>
              </div>
              <div className="flex gap-3 flex-wrap">
                {!isGameActive && (
                  <button
                    onClick={handleStart}
                    className="flex-1 bg-volleyball-blue hover:bg-blue-800 text-white text-sm font-medium py-2 rounded-xl transition"
                  >
                    Start Staging
                  </button>
                )}
                {isStaging && (
                  <button
                    onClick={handleBegin}
                    className="flex-1 bg-green-600 hover:bg-green-700 text-white text-sm font-medium py-2 rounded-xl transition"
                  >
                    Begin Game #{game?.id}
                  </button>
                )}
                {isPlaying && (
                  <button
                    onClick={handleEnd}
                    className="flex-1 bg-gray-600 hover:bg-gray-700 text-white text-sm font-medium py-2 rounded-xl transition"
                  >
                    End Game #{game?.game_number}
                  </button>
                )}
                <button
                  onClick={handleReset}
                  className="flex-1 bg-red-500 hover:bg-red-600 text-white text-sm font-medium py-2 rounded-xl transition"
                >
                  Start Over
                </button>
              </div>
            </div>
          </>
        )}

        {tab === "history" && <PastGamesView />}

        {tab === "events" && <ActivityView />}
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
