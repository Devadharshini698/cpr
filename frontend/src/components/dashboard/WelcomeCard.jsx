import React from "react";
import { Play, Clock } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import "./dashboard.css";

function timeOfDayGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good Morning";
  if (hour < 17) return "Good Afternoon";
  return "Good Evening";
}

export default function WelcomeCard({ handleStartSimulation, activeSessionCode, totalSessions }) {
  const { user } = useAuth();
  // Use auth context name when available, fall back to sessionStorage
  const username = user?.username
    ? (user.username.startsWith("Dr.") ? user.username : `Dr. ${user.username}`)
    : sessionStorage.getItem("username") || "Instructor";
  const hasActive = Boolean(activeSessionCode);

  return (
    <section className="medsim-welcome-card">
      <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <h1
            style={{
              fontSize: "20px",
              fontWeight: "700",
              color: "#0F172A",
              letterSpacing: "-0.01em",
              margin: 0,
            }}
          >
            {timeOfDayGreeting()}, {username}
          </h1>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "3px 10px",
              borderRadius: "16px",
              fontSize: "12px",
              fontWeight: "600",
              backgroundColor: hasActive ? "#F0FDFA" : "#F1F5F9",
              color: hasActive ? "#0F766E" : "#64748B",
              border: hasActive ? "1px solid #CCFBF1" : "1px solid #E2E8F0",
            }}
          >
            <span
              style={{
                width: "6px",
                height: "6px",
                borderRadius: "50%",
                backgroundColor: hasActive ? "#0F766E" : "#94A3B8",
              }}
            />
            {hasActive ? `Simulation ${activeSessionCode} in progress` : "No active simulation running"}
          </span>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "13px",
            color: "#64748B",
            fontWeight: "500",
          }}
        >
          <Clock size={14} color="#94A3B8" />
          <span>
            {typeof totalSessions === "number"
              ? `${totalSessions} simulation${totalSessions === 1 ? "" : "s"} run so far`
              : "Loading session history…"}
          </span>
        </div>
      </div>

      <div>
        <button onClick={handleStartSimulation} className="medsim-btn-primary">
          <Play size={16} fill="currentColor" color="#FFFFFF" />
          Start Simulation
        </button>
      </div>
    </section>
  );
}
