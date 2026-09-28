import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/dashboard/Navbar";
import Sidebar from "../components/dashboard/Sidebar";
import DashboardModals from "../components/dashboard/DashboardModals";
import RecentSessions from "../components/dashboard/RecentSessions";
import SearchBar from "../components/cases/SearchBar";
import "../components/dashboard/dashboard.css";

const API = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

export default function SessionsPage() {
  const navigate = useNavigate();
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [activeModal, setActiveModal] = useState(null);

  const [initialSessions, setInitialSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    const token = sessionStorage.getItem("token") || localStorage.getItem("token");
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    fetch(`${API}/api/sessions/list`, { headers })
      .then(async (r) => {
        if (!r.ok) throw new Error(r.status === 401 ? "Your sign-in has expired. Please sign in again." : `Could not load session history (${r.status}).`);
        return r.json();
      })
      .then((data) => {
        setInitialSessions(Array.isArray(data?.sessions) ? data.sessions : []);
        setLoadError("");
      })
      .catch((error) => {
        console.error("Could not load sessions", error);
        setLoadError(error.message || "Could not load session history.");
      })
      .finally(() => setLoading(false));
  }, []);

  const filteredSessions = initialSessions.filter(
    (s) =>
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.date.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.status.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleStartSimulation = () => {
    navigate("/initializing");
  };

  const handleLogout = () => {
    sessionStorage.clear();
    navigate("/");
  };

  const handleOpenSession = (session) => {
    if (session.status === "Active") {
      sessionStorage.setItem("session_code", session.session_code);
      navigate("/instructor");
    } else {
      navigate(`/debrief/${session.session_code}`);
    }
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
          activeTab="sessions"
          setActiveTab={(tab) => {
            if (tab === "dashboard") navigate("/dashboard");
          }}
          handleStartSimulation={handleStartSimulation}
          onOpenModal={(modalType) => setActiveModal(modalType)}
        />

        <main className="medsim-main-content">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              Clinical Sessions History
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              View and audit all past and active simulation runs
            </p>
          </div>

          <SearchBar searchQuery={searchQuery} setSearchQuery={setSearchQuery} />

          {loadError && (
            <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {loadError}
            </p>
          )}

          <RecentSessions
            sessions={filteredSessions}
            searchQuery={searchQuery}
            loading={loading}
            handleStartSimulation={handleStartSimulation}
            onOpenSession={handleOpenSession}
            onOpenModal={(modalType) => setActiveModal(modalType)}
          />
        </main>
      </div>

      <DashboardModals
        activeModal={activeModal}
        onClose={() => setActiveModal(null)}
        handleStartSimulation={handleStartSimulation}
        initialSessions={initialSessions}
        onOpenSession={handleOpenSession}
      />
    </div>
  );
}
