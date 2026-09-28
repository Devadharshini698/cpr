import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Activity, ArrowLeft, User, Mail, Building, Lock, CheckCircle } from "lucide-react";
import "../components/dashboard/dashboard.css";

const API = (import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

export default function RegistrationRequestPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [institution, setInstitution] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("instructor");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, role }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data.detail || "Registration failed. That username may already be taken.");
        setLoading(false);
        return;
      }
      setSubmitted(true);
    } catch (err) {
      setError("Could not reach the server. Please try again.");
    } finally {
      setLoading(false);
    }
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
            Request Access
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Create your instructor account for this clinical simulation node
          </p>
        </div>

        {!submitted ? (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">
                Full Name
              </label>
              <div className="medsim-input-wrapper">
                <User className="medsim-input-icon" />
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Dr. Jane Smith"
                  className="medsim-input-field"
                  style={{ paddingLeft: "42px" }}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">
                Institutional Email
              </label>
              <div className="medsim-input-wrapper">
                <Mail className="medsim-input-icon" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="jane.smith@hospital.org"
                  className="medsim-input-field"
                  style={{ paddingLeft: "42px" }}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">
                Hospital / Academic Institution
              </label>
              <div className="medsim-input-wrapper">
                <Building className="medsim-input-icon" />
                <input
                  type="text"
                  required
                  value={institution}
                  onChange={(e) => setInstitution(e.target.value)}
                  placeholder="St. Jude Medical Center"
                  className="medsim-input-field"
                  style={{ paddingLeft: "42px" }}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">
                Username
              </label>
              <div className="medsim-input-wrapper">
                <User className="medsim-input-icon" />
                <input
                  type="text"
                  required
                  minLength={3}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="jane.smith"
                  className="medsim-input-field"
                  style={{ paddingLeft: "42px" }}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">
                Password
              </label>
              <div className="medsim-input-wrapper">
                <Lock className="medsim-input-icon" />
                <input
                  type="password"
                  required
                  minLength={6}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="medsim-input-field"
                  style={{ paddingLeft: "42px" }}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase text-slate-500 mb-1">
                Requested Role
              </label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="w-full h-11 px-3 bg-slate-50 border border-slate-200 focus:border-teal-700 focus:bg-white rounded-xl text-sm outline-none transition-all"
              >
                <option value="instructor">Clinical Instructor</option>
                <option value="admin">Simulation Lab Admin</option>
              </select>
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
              {loading ? "Creating account…" : "Create Account →"}
            </button>
          </form>
        ) : (
          <div className="p-4 rounded-xl bg-teal-50 border border-teal-200 text-center space-y-2">
            <CheckCircle className="w-8 h-8 text-teal-700 mx-auto" />
            <h3 className="font-bold text-sm text-teal-900">Account Created</h3>
            <p className="text-xs text-teal-700">
              Thanks{name ? `, ${name}` : ""}. Your account <strong>{username}</strong> ({role}) is ready — sign in now with the username and password you just chose.
            </p>
            <button
              onClick={() => navigate("/")}
              className="mt-2 w-full py-2 bg-teal-700 hover:bg-teal-800 text-white rounded-lg text-xs font-semibold cursor-pointer"
            >
              Sign In Now →
            </button>
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
