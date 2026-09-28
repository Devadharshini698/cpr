import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Activity, ArrowLeft, User, CheckCircle, Copy } from "lucide-react";
import "../components/dashboard/dashboard.css";

const API = (import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

export default function ForgotPasswordPage() {
  const [username, setUsername] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [resetLink, setResetLink] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API}/auth/request-password-reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username }),
      });
      const data = await res.json().catch(() => ({}));
      if (data.token) {
        setResetLink(`${window.location.origin}/reset-password?token=${data.token}`);
      } else {
        setResetLink(null);
      }
      setSubmitted(true);
    } catch (err) {
      setError("Could not reach the server. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!resetLink) return;
    await navigator.clipboard.writeText(resetLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-slate-100 p-4 font-sans text-slate-900">
      <div className="w-full max-w-md bg-white rounded-2xl border border-slate-200 shadow-xl p-8 space-y-6">
        <div className="flex justify-center">
          <div className="w-12 h-12 rounded-xl bg-teal-50 border border-teal-200 flex items-center justify-center text-teal-700">
            <Activity className="w-7 h-7 stroke-[2.2]" />
          </div>
        </div>

        <div className="text-center">
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Reset Your Password
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Enter your instructor username to generate a password reset link
          </p>
        </div>

        {!submitted ? (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">
                Username
              </label>
              <div className="medsim-input-wrapper">
                <User className="medsim-input-icon" />
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="instructor"
                  className="medsim-input-field"
                  style={{ paddingLeft: "42px" }}
                />
              </div>
            </div>

            {error && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 font-semibold text-center">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full h-11 bg-teal-700 hover:bg-teal-800 text-white font-semibold text-sm rounded-xl cursor-pointer shadow-xs transition-colors disabled:opacity-60"
            >
              {loading ? "Generating link…" : "Generate Reset Link →"}
            </button>
          </form>
        ) : (
          <div className="p-4 rounded-xl bg-teal-50 border border-teal-200 text-center space-y-3">
            <CheckCircle className="w-8 h-8 text-teal-700 mx-auto" />
            {resetLink ? (
              <>
                <h3 className="font-bold text-sm text-teal-900">Reset Link Ready</h3>
                <p className="text-xs text-teal-700">
                  This node has no email server configured, so here's your one-time reset link directly. It expires in 30 minutes.
                </p>
                <div className="flex items-center gap-2 bg-white border border-teal-200 rounded-lg p-2">
                  <input
                    readOnly
                    value={resetLink}
                    className="flex-1 text-[11px] text-slate-600 outline-none bg-transparent"
                    onFocus={(e) => e.target.select()}
                  />
                  <button
                    onClick={handleCopy}
                    type="button"
                    className="shrink-0 flex items-center gap-1 text-[11px] font-semibold text-teal-700 hover:text-teal-900"
                  >
                    <Copy className="w-3.5 h-3.5" /> {copied ? "Copied" : "Copy"}
                  </button>
                </div>
                <button
                  onClick={() => navigate(resetLink.replace(window.location.origin, ""))}
                  className="mt-1 w-full py-2 bg-teal-700 hover:bg-teal-800 text-white rounded-lg text-xs font-semibold cursor-pointer"
                >
                  Continue to Reset Password →
                </button>
              </>
            ) : (
              <>
                <h3 className="font-bold text-sm text-teal-900">Check the Username</h3>
                <p className="text-xs text-teal-700">
                  If <strong>{username}</strong> exists, a reset link was generated for it. Double-check the username and try again.
                </p>
              </>
            )}
          </div>
        )}

        <div className="pt-4 border-t border-slate-100 text-center">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-teal-700 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to Sign In
          </Link>
        </div>
      </div>
    </div>
  );
}
