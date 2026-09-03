import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AuthAPI, setToken } from "../api/client";

export function LoginPage() {
  const nav = useNavigate();
  const [email, setEmail] = useState("mlr.admin@mlr-ruleops.local");
  const [password, setPassword] = useState("ChangeMe!Mlr1");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await AuthAPI.login(email, password);
      setToken(res.access_token);
      nav("/");
    } catch (err: any) {
      setError(err.message || "Authentication failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative min-h-screen grid place-items-center bg-ink-950">
      <img
        src="/TCS-logo-white.svg"
        alt="TCS"
        className="absolute left-8 top-8 h-9 w-auto select-none"
      />
      <form onSubmit={onSubmit} className="w-[420px] border border-ink-600 bg-ink-900 p-8">
        <div className="text-[11px] uppercase tracking-[0.22em] text-brass-400">MLR RuleOps</div>
        <h1 className="text-2xl mt-2 mb-1">Sign in</h1>
        <p className="text-sm text-mist-500 mb-6">AI-assisted regulatory rule change & validation.</p>
        <label className="block text-xs text-mist-500 mb-1">Email</label>
        <input
          className="w-full bg-ink-950 border border-ink-600 px-3 py-2 text-sm mb-4 outline-none focus:border-brass-500"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <label className="block text-xs text-mist-500 mb-1">Password</label>
        <input
          type="password"
          className="w-full bg-ink-950 border border-ink-600 px-3 py-2 text-sm mb-4 outline-none focus:border-brass-500"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <div className="text-fail text-sm mb-3">{error}</div>}
        <button disabled={busy} className="w-full bg-brass-500 text-ink-950 py-2 text-sm font-medium">
          {busy ? "Signing in…" : "Continue"}
        </button>
        <p className="text-[11px] text-mist-500 mt-4 leading-relaxed">
          Demo environment. Synthetic Demo Data. Default MLR Admin is pre-filled.
        </p>
      </form>
    </div>
  );
}
