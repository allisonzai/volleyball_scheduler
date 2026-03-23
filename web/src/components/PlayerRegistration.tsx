import { useState } from "react";
import { registerPlayer, signIn, requestVerification, submitVerification } from "../api/client";
import type { Player } from "../types";

interface Props {
  onRegistered: (player: Player) => void;
  onCancel?: () => void;
}

type Step = "form" | "verify";

export default function PlayerRegistration({ onRegistered, onCancel }: Props) {
  const [mode, setMode] = useState<"signin" | "register">("signin");
  const [step, setStep] = useState<Step>("form");
  const [pendingPlayer, setPendingPlayer] = useState<Player | null>(null);

  const [registerForm, setRegisterForm] = useState({
    first_name: "",
    last_name: "",
    phone: "",
    email: "",
    password: "",
    password2: "",
  });
  const [signinForm, setSigninForm] = useState({ phone: "", password: "" });

  const [verifyChannel, setVerifyChannel] = useState<"email" | "sms">("email");
  const [verifyCode, setVerifyCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const errMsg = (err: unknown) =>
    (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Something went wrong.";

  // ── Register ──────────────────────────────────────────────────────────────

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (registerForm.password !== registerForm.password2) {
      setError("Passwords do not match.");
      return;
    }
    if (registerForm.password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }
    setLoading(true);
    try {
      const player = await registerPlayer({
        first_name: registerForm.first_name,
        last_name: registerForm.last_name,
        phone: registerForm.phone,
        email: registerForm.email,
        password: registerForm.password,
      });
      setPendingPlayer(player);
      setStep("verify");
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setLoading(false);
    }
  };

  // ── Sign In ───────────────────────────────────────────────────────────────

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const player = await signIn(signinForm.phone.trim(), signinForm.password);
      if (!player.is_verified) {
        setPendingPlayer(player);
        setStep("verify");
      } else {
        onRegistered(player);
      }
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setLoading(false);
    }
  };

  // ── Verification ──────────────────────────────────────────────────────────

  const handleSendCode = async () => {
    if (!pendingPlayer) return;
    if (verifyChannel === "sms") {
      setError("SMS verification is under development. Please use Email to verify.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      await requestVerification(pendingPlayer.id, verifyChannel);
      setCodeSent(true);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pendingPlayer) return;
    setError(null);
    setLoading(true);
    try {
      await submitVerification(pendingPlayer.id, verifyCode.trim());
      onRegistered({ ...pendingPlayer, is_verified: true });
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setLoading(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  if (step === "verify" && pendingPlayer) {
    return (
      <div className="bg-white rounded-2xl shadow p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-800">Verify your account</h2>
          <button
            onClick={() => { setStep("form"); setCodeSent(false); setVerifyCode(""); setError(null); }}
            className="text-sm text-gray-400 hover:text-gray-600 underline"
          >
            ← Back
          </button>
        </div>
        <p className="text-sm text-gray-500">
          Choose how to receive your 6-digit verification code.
        </p>

        {/* Channel selector */}
        <div className="flex rounded-xl overflow-hidden border border-gray-200">
          {(["email", "sms"] as const).map((ch) => (
            <button
              key={ch}
              onClick={() => { setVerifyChannel(ch); setCodeSent(false); setVerifyCode(""); setError(null); }}
              className={`flex-1 py-2 text-sm font-medium transition ${
                verifyChannel === ch ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              {ch === "email" ? "📧 Email" : "💬 SMS"}
            </button>
          ))}
        </div>

        <p className="text-xs text-gray-400">
          {verifyChannel === "email"
            ? `Code will be sent to ${pendingPlayer.email}`
            : `Code will be sent to ${pendingPlayer.phone}`}
        </p>

        {!codeSent ? (
          <>
            {error && <p className="text-sm text-red-500">{error}</p>}
            <button
              onClick={handleSendCode}
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 rounded-xl transition disabled:opacity-50"
            >
              {loading ? "Sending…" : "Send Code"}
            </button>
          </>
        ) : (
          <form onSubmit={handleVerify} className="space-y-3">
            <p className="text-sm text-green-600">Code sent! Check your {verifyChannel}.</p>
            <input
              required
              maxLength={6}
              placeholder="Enter 6-digit code"
              value={verifyCode}
              onChange={(e) => setVerifyCode(e.target.value)}
              className="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm text-center tracking-widest text-lg focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
            {error && <p className="text-sm text-red-500">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-2 rounded-xl transition disabled:opacity-50"
            >
              {loading ? "Verifying…" : "Verify"}
            </button>
            <button
              type="button"
              onClick={() => { setCodeSent(false); setError(null); }}
              className="w-full text-sm text-gray-400 hover:text-gray-600 underline"
            >
              Resend code
            </button>
          </form>
        )}
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl shadow p-6">
      {/* Mode toggle */}
      <div className="flex rounded-xl overflow-hidden border border-gray-200 mb-5">
        {(["signin", "register"] as const).map((m) => (
          <button
            key={m}
            onClick={() => { setMode(m); setError(null); }}
            className={`flex-1 py-2 text-sm font-medium transition ${
              mode === m ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-50"
            }`}
          >
            {m === "signin" ? "Sign In" : "Register"}
          </button>
        ))}
      </div>

      {onCancel && (
        <div className="flex justify-end mb-1">
          <button
            onClick={onCancel}
            className="text-sm text-gray-400 hover:text-gray-600 underline"
          >
            Cancel
          </button>
        </div>
      )}

      {mode === "signin" ? (
        <form onSubmit={handleSignIn} className="space-y-3">
          <input
            required
            type="tel"
            placeholder="Phone (e.g. +12125551234)"
            value={signinForm.phone}
            onChange={(e) => setSigninForm((f) => ({ ...f, phone: e.target.value }))}
            className="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          <input
            required
            type="password"
            placeholder="Password"
            value={signinForm.password}
            onChange={(e) => setSigninForm((f) => ({ ...f, password: e.target.value }))}
            className="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          {error && <p className="text-sm text-red-500">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 rounded-xl transition disabled:opacity-50"
          >
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </form>
      ) : (
        <form onSubmit={handleRegister} className="space-y-3">
          <div className="flex gap-3">
            <input
              required
              name="first_name"
              placeholder="First Name"
              value={registerForm.first_name}
              onChange={(e) => setRegisterForm((f) => ({ ...f, first_name: e.target.value }))}
              className="flex-1 border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
            <input
              required
              name="last_name"
              placeholder="Last Name"
              value={registerForm.last_name}
              onChange={(e) => setRegisterForm((f) => ({ ...f, last_name: e.target.value }))}
              className="flex-1 border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </div>
          <input
            required
            type="tel"
            placeholder="Phone (e.g. +12125551234)"
            value={registerForm.phone}
            onChange={(e) => setRegisterForm((f) => ({ ...f, phone: e.target.value }))}
            className="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          <input
            required
            type="email"
            placeholder="Email"
            value={registerForm.email}
            onChange={(e) => setRegisterForm((f) => ({ ...f, email: e.target.value }))}
            className="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          <input
            required
            type="password"
            placeholder="Password (min 6 characters)"
            value={registerForm.password}
            onChange={(e) => setRegisterForm((f) => ({ ...f, password: e.target.value }))}
            className="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          <input
            required
            type="password"
            placeholder="Confirm Password"
            value={registerForm.password2}
            onChange={(e) => setRegisterForm((f) => ({ ...f, password2: e.target.value }))}
            className="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          {error && <p className="text-sm text-red-500">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 rounded-xl transition disabled:opacity-50"
          >
            {loading ? "Registering…" : "Register"}
          </button>
        </form>
      )}
    </div>
  );
}
