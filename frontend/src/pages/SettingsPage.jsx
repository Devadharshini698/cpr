import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/dashboard/Navbar";
import Sidebar from "../components/dashboard/Sidebar";
import DashboardModals from "../components/dashboard/DashboardModals";
import { Settings, Bell, Shield, Volume2, Monitor, Check } from "lucide-react";
import "../components/dashboard/dashboard.css";

const API = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

export default function SettingsPage() {
  const navigate = useNavigate();
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [activeModal, setActiveModal] = useState(null);

  const [prefs, setPrefs] = useState({ audio_alarms: true, nibp_tones: true, auto_debrief: true });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const token = sessionStorage.getItem("token");
    fetch(`${API}/api/user/preferences`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => data && setPrefs(data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const togglePref = (key) => setPrefs((p) => ({ ...p, [key]: !p[key] }));

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    const token = sessionStorage.getItem("token");
    try {
      const res = await fetch(`${API}/api/user/preferences`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(prefs),
      });
      if (res.ok) {
        const data = await res.json();
        setPrefs(data);
        setSaved(true);
        setTimeout(() => setSaved(false), 2500);
      }
    } catch (err) {
      console.error("[SettingsPage] Failed to save preferences:", err);
    } finally {
      setSaving(false);
    }
  };

  const handleStartSimulation = () => {
    navigate("/initializing");
  };

  const handleLogout = () => {
    sessionStorage.clear();
    navigate("/");
  };

  return (
    <div className="medsim-dashboard-page">
      <Navbar
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        showNotifications={showNotifications}
        setShowNotifications={setShowNotifications}
        showProfileMenu={showProfileMenu}
        setShowProfileMenu={setShowProfileMenu}
        handleStartSimulation={handleStartSimulation}
        handleLogout={handleLogout}
        onOpenSettings={() => navigate("/settings")}
      />

      <div style={{ display: "flex", flex: 1, overflow: "hidden", position: "relative" }}>
        <Sidebar
          sidebarExpanded={sidebarExpanded}
          setSidebarExpanded={setSidebarExpanded}
          activeTab="settings"
          setActiveTab={(tab) => {
            if (tab === "dashboard") navigate("/dashboard");
          }}
          handleStartSimulation={handleStartSimulation}
          onOpenModal={(modalType) => setActiveModal(modalType)}
        />

        <main className="medsim-main-content">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              Application Settings
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              Configure simulator telemetry, audio alarms, and instructor preferences
            </p>
          </div>

          <div className={`bg-white rounded-2xl border border-slate-200 shadow-xs p-6 max-w-3xl space-y-6 ${loading ? "opacity-60 pointer-events-none" : ""}`}>
            {/* Audio Alarms */}
            <div className="space-y-3 pb-6 border-b border-slate-100">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Volume2 className="w-4 h-4 text-teal-700" />
                Audio & Telemetry Alarms
              </h3>

              <div className="space-y-3 text-xs text-slate-700">
                <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
                  <div>
                    <div className="font-semibold text-slate-900">Enable High-Priority Audio Alarms</div>
                    <div className="text-slate-500 text-[11px]">Play audio tones on Critical Ventricular Fibrillation & Asystole</div>
                  </div>
                  <input
                    type="checkbox"
                    checked={prefs.audio_alarms}
                    onChange={() => togglePref("audio_alarms")}
                    className="accent-teal-700 w-4 h-4"
                  />
                </div>

                <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
                  <div>
                    <div className="font-semibold text-slate-900">NIBP Auto-Cycle Warning Tones</div>
                    <div className="text-slate-500 text-[11px]">Chime when non-invasive blood pressure measurement cycles complete</div>
                  </div>
                  <input
                    type="checkbox"
                    checked={prefs.nibp_tones}
                    onChange={() => togglePref("nibp_tones")}
                    className="accent-teal-700 w-4 h-4"
                  />
                </div>
              </div>
            </div>

            {/* AI Debrief */}
            <div className="space-y-3 pb-6 border-b border-slate-100">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Shield className="w-4 h-4 text-teal-700" />
                AI Debrief & Performance Engine
              </h3>

              <div className="space-y-3 text-xs text-slate-700">
                <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
                  <div>
                    <div className="font-semibold text-slate-900">Automatic Post-Session Debrief Generation</div>
                    <div className="text-slate-500 text-[11px]">Generate instant LLM debrief transcript upon ending simulation</div>
                  </div>
                  <input
                    type="checkbox"
                    checked={prefs.auto_debrief}
                    onChange={() => togglePref("auto_debrief")}
                    className="accent-teal-700 w-4 h-4"
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end items-center gap-3">
              {saved && (
                <span className="text-xs font-semibold text-emerald-600 flex items-center gap-1">
                  <Check className="w-3.5 h-3.5" /> Saved
                </span>
              )}
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-6 py-2.5 bg-teal-700 hover:bg-teal-800 text-white font-semibold text-xs rounded-xl shadow-xs cursor-pointer disabled:opacity-60"
              >
                {saving ? "Saving…" : "Save Preferences"}
              </button>
            </div>
          </div>
        </main>
      </div>

      <DashboardModals
        activeModal={activeModal}
        onClose={() => setActiveModal(null)}
        handleStartSimulation={handleStartSimulation}
        initialSessions={[]}
      />
    </div>
  );
}
