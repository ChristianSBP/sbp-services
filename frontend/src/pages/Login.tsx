/* Login / Setup Seite — Apple-minimalistisch */

import { useState } from "react";

interface LoginProps {
  onLogin: (type: "admin" | "musiker", email: string, password: string) => Promise<void>;
  onSetup: (email: string, password: string) => Promise<void>;
  needsSetup: boolean;
  loading: boolean;
  error: string | null;
}

export default function Login({ onLogin, onSetup, needsSetup, loading, error }: LoginProps) {
  const [mode, setMode] = useState<"admin" | "musiker">("admin");
  const [email, setEmail] = useState("saalfrank@sbphil.music");
  const [password, setPassword] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [localError, setLocalError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLocalError("");

    if (needsSetup) {
      if (password !== confirmPw) {
        setLocalError("Passwörter stimmen nicht überein.");
        return;
      }
      if (password.length < 8) {
        setLocalError("Mindestens 8 Zeichen.");
        return;
      }
      try {
        await onSetup(email, password);
      } catch { /* error from hook */ }
    } else {
      try {
        await onLogin(mode, email, password);
      } catch { /* error from hook */ }
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)] px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-semibold tracking-tight text-[var(--color-primary)]">
            Planung SBP
          </h1>
          <p className="mt-2 text-sm text-[var(--color-secondary)]">
            Sächsische Bläserphilharmonie
          </p>
        </div>

        {/* Card */}
        <div className="card p-8">
          {needsSetup ? (
            <>
              <h2 className="text-lg font-medium mb-1">Willkommen</h2>
              <p className="text-sm text-[var(--color-secondary)] mb-6">
                Admin-Passwort festlegen
              </p>
            </>
          ) : (
            <>
              {/* Tab-Umschalter */}
              <div className="flex bg-black/5 rounded-lg p-0.5 mb-6">
                <button
                  type="button"
                  onClick={() => setMode("admin")}
                  className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${
                    mode === "admin"
                      ? "bg-white shadow-sm text-[var(--color-primary)]"
                      : "text-[var(--color-secondary)]"
                  }`}
                >
                  Admin
                </button>
                <button
                  type="button"
                  onClick={() => setMode("musiker")}
                  className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${
                    mode === "musiker"
                      ? "bg-white shadow-sm text-[var(--color-primary)]"
                      : "text-[var(--color-secondary)]"
                  }`}
                >
                  Musiker
                </button>
              </div>
            </>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {(needsSetup || mode === "admin") && (
              <div>
                <label className="block text-xs font-medium text-[var(--color-secondary)] mb-1.5">
                  E-Mail
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3 py-2.5 text-sm border border-[var(--color-border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]/30 focus:border-[var(--color-accent)] transition"
                  required
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-[var(--color-secondary)] mb-1.5">
                Passwort
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2.5 text-sm border border-[var(--color-border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]/30 focus:border-[var(--color-accent)] transition"
                required
              />
            </div>

            {needsSetup && (
              <div>
                <label className="block text-xs font-medium text-[var(--color-secondary)] mb-1.5">
                  Passwort bestätigen
                </label>
                <input
                  type="password"
                  value={confirmPw}
                  onChange={(e) => setConfirmPw(e.target.value)}
                  className="w-full px-3 py-2.5 text-sm border border-[var(--color-border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]/30 focus:border-[var(--color-accent)] transition"
                  required
                />
              </div>
            )}

            {(error || localError) && (
              <p className="text-xs text-[var(--color-error)]">{localError || error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full btn-pill btn-primary py-2.5 text-sm font-medium disabled:opacity-50"
            >
              {loading ? "..." : needsSetup ? "Passwort festlegen" : "Anmelden"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
