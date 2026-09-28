import React, { useEffect, useState } from "react";
import { Activity, Search, Bell, ChevronDown, LogOut, Settings, Play, FileCheck } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useNavigate } from "react-router-dom";
import "./dashboard.css";

const API = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
const LAST_SEEN_KEY = "notifications_last_seen_at";

function timeAgo(iso) {
  if (!iso) return "";
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min${mins === 1 ? "" : "s"} ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hour${hrs === 1 ? "" : "s"} ago`;
  const days = Math.floor(hrs / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

export default function Navbar({
  searchQuery,
  setSearchQuery,
  showNotifications,
  setShowNotifications,
  showProfileMenu,
  setShowProfileMenu,
  handleStartSimulation,
  handleLogout: customLogout,
  onOpenSettings,
}) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const displayName = user?.username
    ? user.username.startsWith("Dr.") ? user.username : `Dr. ${user.username}`
    : sessionStorage.getItem("username") || "Instructor";
  const userInitials = user?.username
    ? user.username.replace(/^Dr\.\s*/, "").slice(0, 2).toUpperCase()
    : (sessionStorage.getItem("username") || "IN").slice(0, 2).toUpperCase();
  const userRole = user?.role
    ? user.role.charAt(0).toUpperCase() + user.role.slice(1) + " Instructor"
    : "Clinical Instructor";

  const onLogoutClick = async () => {
    if (customLogout) {
      await customLogout();
    } else {
      await logout();
      navigate("/");
    }
  };

  // Real notifications: recently completed AI debrief reports (saran feature)
  const [notifications, setNotifications] = useState([]);
  const [lastSeenAt, setLastSeenAt] = useState(() => localStorage.getItem(LAST_SEEN_KEY) || "");

  useEffect(() => {
    const token = sessionStorage.getItem("token");
    fetch(`${API}/api/debrief/list?limit=5`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => setNotifications(data?.reports || []))
      .catch(console.error);
  }, []);

  const unreadCount = notifications.filter((n) => !lastSeenAt || n.updated_at > lastSeenAt).length;

  const handleMarkAllRead = () => {
    const now = new Date().toISOString();
    localStorage.setItem(LAST_SEEN_KEY, now);
    setLastSeenAt(now);
  };

  return (
    <header className="medsim-navbar">
      {/* Left: Logo & Title */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        <div className="medsim-logo-badge">
          <Activity size={22} strokeWidth={2.2} />
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span className="medsim-app-title">MedSim AI</span>
            <span className="medsim-app-subtitle">Simulation &amp; Debrief Platform</span>
          </div>
        </div>
      </div>

      {/* Center: Search Bar */}
      <div className="medsim-search-container">
        <Search className="medsim-search-icon" size={18} />
        <input
          type="text"
          placeholder="Search sessions..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="medsim-search-input"
        />
      </div>

      {/* Right: Notifications & Profile */}
      <div style={{ display: "flex", alignItems: "center", gap: "16px", position: "relative" }}>
        {/* Notifications Button */}
        <button
          onClick={() => {
            setShowNotifications(!showNotifications);
            setShowProfileMenu(false);
          }}
          className="medsim-icon-btn"
          title="Notifications"
        >
          <Bell size={20} color="#475569" />
          {unreadCount > 0 && <span className="medsim-unread-dot" />}
        </button>

        {/* Notifications Popup */}
        {showNotifications && (
          <div
            style={{
              position: "absolute",
              top: "52px",
              right: "60px",
              width: "320px",
              backgroundColor: "#FFFFFF",
              borderRadius: "16px",
              border: "1px solid #E2E8F0",
              boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.1)",
              zIndex: 50,
              padding: "16px",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                paddingBottom: "12px",
                borderBottom: "1px solid #F1F5F9",
              }}
            >
              <span style={{ fontWeight: "600", fontSize: "14px", color: "#0F172A" }}>
                Notifications
              </span>
              <button
                onClick={handleMarkAllRead}
                disabled={unreadCount === 0}
                style={{
                  fontSize: "11px",
                  color: unreadCount === 0 ? "#CBD5E1" : "#0F766E",
                  fontWeight: "600",
                  background: "none",
                  border: "none",
                  cursor: unreadCount === 0 ? "default" : "pointer",
                }}
              >
                Mark all as read
              </button>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginTop: "12px", maxHeight: "320px", overflowY: "auto" }}>
              {notifications.length === 0 && (
                <div style={{ fontSize: "12px", color: "#94A3B8", textAlign: "center", padding: "12px 0" }}>
                  No completed debriefs yet.
                </div>
              )}
              {notifications.map((n) => {
                const isUnread = !lastSeenAt || n.updated_at > lastSeenAt;
                return (
                  <div
                    key={n.session_code}
                    style={{
                      padding: "10px",
                      borderRadius: "10px",
                      backgroundColor: isUnread ? "#F0FDFA" : "#F8FAFC",
                      border: isUnread ? "1px solid #CCFBF1" : "1px solid #E2E8F0",
                      fontSize: "13px",
                      display: "flex",
                      gap: "8px",
                      alignItems: "flex-start",
                    }}
                  >
                    <FileCheck size={14} color={isUnread ? "#0F766E" : "#94A3B8"} style={{ marginTop: "2px", flexShrink: 0 }} />
                    <div>
                      <div style={{ fontWeight: "600", color: isUnread ? "#0F766E" : "#0F172A" }}>
                        Debrief ready — {n.session_code}
                      </div>
                      <div style={{ color: "#475569", marginTop: "2px" }}>
                        {n.overall_score != null ? `Score ${Math.round(n.overall_score)}/100` : "Score pending"}
                        {n.grade ? ` • Grade ${n.grade}` : ""}
                      </div>
                      <div style={{ fontSize: "11px", color: "#94A3B8", marginTop: "4px" }}>
                        {timeAgo(n.updated_at)}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Divider */}
        <div style={{ width: "1px", height: "24px", backgroundColor: "#E2E8F0", margin: "0 4px" }} />

        {/* Profile Trigger */}
        <div style={{ position: "relative" }}>
          <button
            onClick={() => {
              setShowProfileMenu(!showProfileMenu);
              setShowNotifications(false);
            }}
            className="medsim-profile-trigger"
          >
            <div className="medsim-avatar">{userInitials}</div>
            <div style={{ textAlign: "left", paddingRight: "4px" }}>
              <div style={{ fontSize: "13px", fontWeight: "600", color: "#0F172A", lineHeight: 1.2 }}>
                {displayName}
              </div>
              <div style={{ fontSize: "11px", color: "#64748B", lineHeight: 1.2 }}>
                {userRole}
              </div>
            </div>
            <ChevronDown size={14} color="#64748B" />
          </button>

          {/* Profile Dropdown */}
          {showProfileMenu && (
            <div
              style={{
                position: "absolute",
                top: "52px",
                right: "0",
                width: "220px",
                backgroundColor: "#FFFFFF",
                borderRadius: "16px",
                border: "1px solid #E2E8F0",
                boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.1)",
                zIndex: 50,
                padding: "8px 0",
                overflow: "hidden",
              }}
            >
              <div style={{ padding: "12px 16px", borderBottom: "1px solid #F1F5F9" }}>
                <div style={{ fontWeight: "600", fontSize: "14px", color: "#0F172A" }}>
                  {displayName}
                </div>
                <div style={{ fontSize: "12px", color: "#64748B" }}>
                  {user?.username ? `${user.username.toLowerCase()}@hospital.org` : userRole}
                </div>
              </div>

              <div style={{ padding: "4px 0" }}>
                <button
                  onClick={() => {
                    setShowProfileMenu(false);
                    handleStartSimulation();
                  }}
                  style={{
                    width: "100%",
                    padding: "10px 16px",
                    textAlign: "left",
                    backgroundColor: "transparent",
                    border: "none",
                    fontSize: "13px",
                    color: "#0F766E",
                    fontWeight: "600",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <Play size={16} color="#0F766E" />
                  Simulation Monitor
                </button>

                <button
                  onClick={() => {
                    setShowProfileMenu(false);
                    onOpenSettings();
                  }}
                  style={{
                    width: "100%",
                    padding: "10px 16px",
                    textAlign: "left",
                    backgroundColor: "transparent",
                    border: "none",
                    fontSize: "13px",
                    color: "#334155",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <Settings size={16} color="#64748B" />
                  Account Settings
                </button>
              </div>

              <div style={{ borderTop: "1px solid #F1F5F9", paddingTop: "4px" }}>
                <button
                  onClick={onLogoutClick}
                  style={{
                    width: "100%",
                    padding: "10px 16px",
                    textAlign: "left",
                    backgroundColor: "transparent",
                    border: "none",
                    fontSize: "13px",
                    color: "#EF4444",
                    fontWeight: "600",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <LogOut size={16} color="#EF4444" />
                  Log Out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
