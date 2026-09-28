import React, { useState, useEffect } from "react";

import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Navbar from "../components/dashboard/Navbar";
import Sidebar from "../components/dashboard/Sidebar";
import DashboardModals from "../components/dashboard/DashboardModals";
import BadgeGrid from "../components/gamification/BadgeGrid";
import { Trophy } from "lucide-react";
import "../components/dashboard/dashboard.css";

const API_BASE = (import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");


export default function ProfilePage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [activeTab, setActiveTab] = useState("profile");
  const [activeModal, setActiveModal] = useState(null);
  const [totalSimulations, setTotalSimulations] = useState(0);
  const [profile, setProfile] = useState(null); // saran: /auth/me data

  useEffect(() => {
    const token = sessionStorage.getItem("token");
    if (token) {
      // Fetch /auth/me for real account info (saran)
      fetch(`${API_BASE}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
        .then((r) => (r.ok ? r.json() : null))
        .then(setProfile)
        .catch(console.error);
    }
  }, []);

  const [profileData, setProfileData] = useState(null);
  const [loading, setLoading] = useState(true);

  const teamName = user?.username || sessionStorage.getItem("team_name") || sessionStorage.getItem("username") || "Resus Team";
  const token = sessionStorage.getItem("token") || localStorage.getItem("token") || "";

  const displayName = user?.username
    ? user.username.startsWith("Dr.") ? user.username : `Dr. ${user.username}`
    : "Instructor";
  const initials = user?.username
    ? user.username.replace(/^Dr\.\s*/, "").slice(0, 2).toUpperCase()
    : teamName.split(" ").map((w) => w[0]).join("").substring(0, 2).toUpperCase();

  useEffect(() => {
    const headers = token ? { Authorization: `Bearer ${token}` } : {};

    // Fetch gamification profile (local gamification feature)
    const fetchGamificationProfile = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/api/gamification/me`, { headers });
        if (res.ok) {
          const data = await res.json();
          setProfileData(data);
        }
      } catch (err) {
        console.error("Error fetching profile gamification data:", err);
      } finally {
        setLoading(false);
      }
    };

    // Fetch total simulations (reshma feature)
    fetch(`${API_BASE}/dashboard/user-data`, { headers, credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.stats) {
          setTotalSimulations(data.stats.total_simulations || 0);
        }
      })
      .catch((err) => console.error(err));

    fetchGamificationProfile();
  }, [token, user]);

  const handleStartSimulation = () => navigate("/cases");
  const handleLogout = async () => {
    await logout();
    navigate("/");
  };

  return (
    <div className="medsim-dashboard-page" style={{ backgroundColor: "#F8FAFC" }}>
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
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          handleStartSimulation={handleStartSimulation}
          onOpenModal={(modalType) => setActiveModal(modalType)}
        />

        <main className="medsim-main-content" style={{ flex: 1, padding: "32px 40px", overflowY: "auto" }}>
          <div style={{ maxWidth: 880, margin: "0 auto", display: "flex", flexDirection: "column", gap: 24 }}>
            <div>
              <h1 style={{ fontSize: 24, fontWeight: 800, color: "#0F172A", margin: 0, letterSpacing: "-0.02em" }}>
                Simulation Profile &amp; Achievements
              </h1>
              <p style={{ fontSize: 13, color: "#64748B", margin: "4px 0 0 0" }}>
                Team performance, level progression, and unlocked simulation badges
              </p>
            </div>

            {/* Profile Header Card */}
            <div style={{ backgroundColor: "#FFFFFF", borderRadius: 16, border: "1px solid #E2E8F0", padding: 24, boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 16, paddingBottom: 20, borderBottom: "1px solid #F1F5F9" }}>
                <div style={{ width: 64, height: 64, borderRadius: "50%", backgroundColor: "#0F766E", color: "#FFF", fontSize: 22, fontWeight: 800, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  {initials || "ST"}
                </div>
                <div>
                  <h2 style={{ fontSize: 20, fontWeight: 800, color: "#0F172A", margin: 0 }}>
                    {displayName}
                  </h2>
                  <div style={{ fontSize: 12, color: "#64748B", fontWeight: 500, marginTop: 2 }}>
                    {user?.role ? (user.role.charAt(0).toUpperCase() + user.role.slice(1)) + " Clinical Instructor" : "Clinical Resuscitation Simulation Team"}
                  </div>
                  <span style={{ display: "inline-block", marginTop: 6, padding: "3px 10px", borderRadius: 12, fontSize: 11, fontWeight: 700, backgroundColor: "#F0FDFA", color: "#0F766E", border: "1px solid #CCFBF1", textTransform: "uppercase" }}>
                    {profileData?.level || user?.role || "Instructor"} Level
                  </span>
                </div>
              </div>

              {/* Stats Grid */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, paddingTop: 20 }}>
                <div style={{ padding: "14px 16px", backgroundColor: "#F8FAFC", borderRadius: 12, border: "1px solid #E2E8F0" }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: "#64748B", textTransform: "uppercase", display: "block" }}>Total XP</span>
                  <span style={{ fontSize: 18, fontWeight: 800, color: "#D97706", display: "flex", alignItems: "center", gap: 4, marginTop: 4 }}>
                    ⚡ {profileData?.total_xp?.toLocaleString() || 0}
                  </span>
                </div>

                <div style={{ padding: "14px 16px", backgroundColor: "#F8FAFC", borderRadius: 12, border: "1px solid #E2E8F0" }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: "#64748B", textTransform: "uppercase", display: "block" }}>Sessions</span>
                  <span style={{ fontSize: 18, fontWeight: 800, color: "#0F172A", marginTop: 4, display: "block" }}>
                    {profileData?.session_count || profile?.total_sessions || totalSimulations || 0} Completed
                  </span>
                </div>

                <div style={{ padding: "14px 16px", backgroundColor: "#F8FAFC", borderRadius: 12, border: "1px solid #E2E8F0" }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: "#64748B", textTransform: "uppercase", display: "block" }}>Best Score</span>
                  <span style={{ fontSize: 18, fontWeight: 800, color: "#059669", marginTop: 4, display: "block" }}>
                    {profileData?.best_score || 0}%
                  </span>
                </div>

                <div style={{ padding: "14px 16px", backgroundColor: "#F8FAFC", borderRadius: 12, border: "1px solid #E2E8F0" }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: "#64748B", textTransform: "uppercase", display: "block" }}>Leaderboard Rank</span>
                  <span style={{ fontSize: 18, fontWeight: 800, color: "#2563EB", marginTop: 4, display: "block" }}>
                    #{profileData?.leaderboard_rank || "—"}
                  </span>
                </div>
              </div>
            </div>

            {/* Auth Info Card (Reshma + Saran) */}
            <div style={{ backgroundColor: "#FFFFFF", borderRadius: 16, border: "1px solid #E2E8F0", padding: 24, boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 16, fontSize: 12 }}>
                <div style={{ padding: "14px 16px", backgroundColor: "#F8FAFC", borderRadius: 12, border: "1px solid #E2E8F0" }}>
                  <span style={{ color: "#94A3B8", fontWeight: 600, display: "block", textTransform: "uppercase", fontSize: 10 }}>Username / Account</span>
                  <span style={{ fontWeight: 700, color: "#0F172A", fontSize: 14 }}>{user?.username || profile?.username || "instructor"}</span>
                </div>
                <div style={{ padding: "14px 16px", backgroundColor: "#F8FAFC", borderRadius: 12, border: "1px solid #E2E8F0" }}>
                  <span style={{ color: "#94A3B8", fontWeight: 600, display: "block", textTransform: "uppercase", fontSize: 10 }}>User ID</span>
                  <span style={{ fontWeight: 700, color: "#0F172A", fontSize: 14 }}>#{user?.id || "1"}</span>
                </div>
                <div style={{ padding: "14px 16px", backgroundColor: "#F8FAFC", borderRadius: 12, border: "1px solid #E2E8F0" }}>
                  <span style={{ color: "#94A3B8", fontWeight: 600, display: "block", textTransform: "uppercase", fontSize: 10 }}>Total Conducted Sessions</span>
                  <span style={{ fontWeight: 700, color: "#0F172A", fontSize: 14 }}>{profile?.total_sessions ?? totalSimulations} Sessions</span>
                </div>
                <div style={{ padding: "14px 16px", backgroundColor: "#F8FAFC", borderRadius: 12, border: "1px solid #E2E8F0" }}>
                  <span style={{ color: "#94A3B8", fontWeight: 600, display: "block", textTransform: "uppercase", fontSize: 10 }}>Account Created</span>
                  <span style={{ fontWeight: 700, color: "#059669", fontSize: 14 }}>
                    {profile?.created_at ? new Date(profile.created_at).toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" }) : "Authenticated"}
                  </span>
                </div>
              </div>
            </div>

            {/* Level Progression Progress Bar */}
            {profileData && (
              <div style={{ backgroundColor: "#FFFFFF", borderRadius: 16, border: "1px solid #E2E8F0", padding: 20, boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <Trophy size={18} color="#D97706" />
                    <span style={{ fontSize: 14, fontWeight: 700, color: "#0F172A" }}>
                      Simulation Level Progress
                    </span>
                  </div>
                  <span style={{ fontSize: 12, fontWeight: 700, color: "#0F766E" }}>
                    {profileData.level}
                  </span>
                </div>

                <div style={{ height: 10, backgroundColor: "#F1F5F9", borderRadius: 5, overflow: "hidden", border: "1px solid #E2E8F0" }}>
                  <div
                    style={{
                      height: "100%",
                      width: `${profileData.progress_percent || 100}%`,
                      background: "linear-gradient(90deg, #0F766E, #0D9488)",
                      borderRadius: 5,
                      transition: "width 0.5s ease-in-out"
                    }}
                  />
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 11, color: "#64748B" }}>
                  <span>{profileData.total_xp?.toLocaleString()} Total XP</span>
                  <span>
                    {profileData.progress_percent >= 100 && profileData.level === "Master Resuscitationist"
                      ? "MAX LEVEL REACHED"
                      : `${profileData.xp_into_level} / ${profileData.next_level_xp - profileData.current_level_xp} XP to next level`}
                  </span>
                </div>
              </div>
            )}

            {/* Badge Collection Section */}
            {profileData && (
              <BadgeGrid badges={profileData.badge_catalogue || []} />
            )}
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
