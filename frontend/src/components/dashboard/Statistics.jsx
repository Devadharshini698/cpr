import React from "react";
import { Activity, Calendar, CheckCircle2, AlertCircle } from "lucide-react";
import "./dashboard.css";

// Accepts either `stats` (saran: { total, today, completed, pending }) 
// or `statsData` (reshma: { total_simulations, todays_sessions, completed_sessions, pending_debriefs })
export default function Statistics({ stats: realStats, statsData }) {
  const loading = !realStats && !statsData;
  const val = (saranKey, reshamaKey) => {
    if (realStats) return String(realStats?.[saranKey] ?? 0);
    if (statsData) return String(statsData?.[reshamaKey] ?? 0);
    return "—";
  };

  const stats = [
    {
      id: "total",
      label: "Total Simulations",
      value: val("total", "total_simulations"),
      icon: Activity,
      color: "#0F172A",
    },
    {
      id: "today",
      label: "Today's Sessions",
      value: val("today", "todays_sessions"),
      icon: Calendar,
      color: "#0F766E",
    },
    {
      id: "completed",
      label: "Completed Sessions",
      value: val("completed", "completed_sessions"),
      icon: CheckCircle2,
      color: "#0F172A",
    },
    {
      id: "pending",
      label: "Pending Debriefs",
      value: val("pending", "pending_debriefs"),
      icon: AlertCircle,
      color: "#D97706",
    },
  ];

  return (
    <section>
      <h2
        style={{
          fontSize: "16px",
          fontWeight: "700",
          color: "#0F172A",
          marginBottom: "16px",
          letterSpacing: "-0.01em",
          margin: "0 0 16px 0",
        }}
      >
        Statistics
      </h2>

      <div className="medsim-stats-grid">
        {stats.map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.id} className="medsim-stat-card">
              <div>
                <div style={{ fontSize: "12px", fontWeight: "500", color: "#64748B" }}>
                  {item.label}
                </div>
                <div
                  style={{
                    fontSize: "28px",
                    fontWeight: "800",
                    color: item.color,
                    marginTop: "4px",
                    letterSpacing: "-0.02em",
                  }}
                >
                  {loading ? "—" : item.value}
                </div>
              </div>
              <div
                style={{
                  width: "36px",
                  height: "36px",
                  borderRadius: "10px",
                  backgroundColor: "#F8FAFC",
                  border: "1px solid #F1F5F9",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Icon size={18} color="#94A3B8" />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
