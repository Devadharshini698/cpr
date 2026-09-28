import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Navbar from "../components/dashboard/Navbar";
import Sidebar from "../components/dashboard/Sidebar";
import WelcomeCard from "../components/dashboard/WelcomeCard";
import QuickActions from "../components/dashboard/QuickActions";
import Statistics from "../components/dashboard/Statistics";
import RecentSessions from "../components/dashboard/RecentSessions";
import DashboardModals from "../components/dashboard/DashboardModals";
import "../components/dashboard/dashboard.css";

const API = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

export default function DashboardPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  // State
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [activeTab, setActiveTab] = useState("dashboard");
  const [activeModal, setActiveModal] = useState(null); // 'library', 'reports', 'settings', 'sessions'

  const [sessions, setSessions] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = sessionStorage.getItem("token") || localStorage.getItem("token");
    const headers = token ? { Authorization: `Bearer ${token}` } : {};

    // Try saran's /api/sessions/list endpoint first; fall back to reshma's /dashboard/user-data
    fetch(`${API}/api/sessions/list`, { headers })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data) {
          setSessions(data.sessions || []);
          setStats(data.stats || null);
        } else {
          // Fallback: reshma's endpoint
          return fetch(`${API}/dashboard/user-data`, { headers, credentials: "include" })
            .then((r) => (r.ok ? r.json() : null))
            .then((d) => {
              if (d) {
                if (Array.isArray(d.recent_sessions)) setSessions(d.recent_sessions);
                if (d.stats) {
                  setStats({
                    total: d.stats.total_simulations,
                    today: d.stats.todays_sessions,
                    completed: d.stats.completed_sessions,
                    pending: d.stats.pending_debriefs,
                  });
                }
              }
            });
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [user]);

  // Filtered Sessions
  const filteredSessions = sessions.filter(
    (s) =>
      (s.name || s.session_code || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (s.date || s.created_at || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (s.status || "").toLowerCase().includes(searchQuery.toLowerCase())
  );

  const activeSession = sessions.find((s) => s.status === "Active");

  const handleLogout = async () => {
    await logout();
    navigate("/");
  };

  const handleStartSimulation = () => {
    navigate("/cases");
  };

  const handleOpenSession = (session) => {
    if (session.status === "Active") {
      sessionStorage.setItem("session_code", session.session_code);
      navigate(session.mode === "audio_only" ? "/audio-only" : "/instructor");
    } else {
      navigate(`/debrief/${session.session_code}`);
    }
  };

  return (
    <div className="medsim-dashboard-page">
      {/* Fixed Top Navbar */}
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

      {/* Main Body: Sidebar + Scrollable Content */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden", position: "relative" }}>
        {/* Left Sidebar */}
        <Sidebar
          sidebarExpanded={sidebarExpanded}
          setSidebarExpanded={setSidebarExpanded}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          handleStartSimulation={handleStartSimulation}
          onOpenModal={(modalType) => setActiveModal(modalType)}
        />

        {/* Scrollable Main Dashboard Content */}
        <main className="medsim-main-content">
          {/* Section 1: Welcome Card */}
          <WelcomeCard
            handleStartSimulation={handleStartSimulation}
            activeSessionCode={activeSession?.session_code}
            totalSessions={stats?.total}
          />
          <div className="rounded-xl border border-teal-200 bg-teal-50 p-4">
            <div className="font-semibold text-teal-950">Team conversation only?</div>
            <p className="mt-1 text-sm text-teal-900">Record and debrief speech without launching a simulator scenario.</p>
            <button type="button" onClick={() => navigate("/audio-only")} className="mt-3 rounded-lg bg-teal-700 px-4 py-2 text-sm font-semibold text-white">Start audio-only debrief</button>
          </div>

          {/* Section 2: Quick Actions */}
          <QuickActions
            handleStartSimulation={handleStartSimulation}
            onOpenModal={(modalType) => setActiveModal(modalType)}
          />

          {/* Section 3: Statistics */}
          <Statistics stats={stats} />

          {/* Section 4: Recent Sessions */}
          <RecentSessions
            sessions={filteredSessions.slice(0, 5)}
            searchQuery={searchQuery}
            loading={loading}
            handleStartSimulation={handleStartSimulation}
            onOpenSession={handleOpenSession}
            onOpenModal={(modalType) => setActiveModal(modalType)}
          />
        </main>
      </div>

      {/* Interactive Modals */}
      <DashboardModals
        activeModal={activeModal}
        onClose={() => setActiveModal(null)}
        handleStartSimulation={handleStartSimulation}
        initialSessions={sessions}
        onOpenSession={handleOpenSession}
      />
    </div>
  );
}
