import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import socket from "../socket";
import {
  CheckCircle2,
  FileText,
  LayoutDashboard,
  Award,
  Clock,
  Zap,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Shield,
  Trophy
} from "lucide-react";
import "../styles/simulation.css";

export default function SimulationCompletedPage() {
  const navigate = useNavigate();
  const [score, setScore] = useState(null);
  const [grade, setGrade] = useState("A");
  const [durationStr, setDurationStr] = useState("Calculating...");
  const [scenarioName, setScenarioName] = useState("ACLS Scenario");
  const [loading, setLoading] = useState(true);
  const [gamification, setGamification] = useState(null);
  const [showBreakdown, setShowBreakdown] = useState(false);

  const sessionCode = sessionStorage.getItem("session_code") || "";
  const API_BASE = (import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
  const wsHandledRef = useRef(false);

  useEffect(() => {
    if (!sessionCode) {
      setLoading(false);
      return;
    }
    const token = sessionStorage.getItem("token") || "";

    const fetchGamification = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/gamification/session/${sessionCode}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) {
          const gamData = await res.json();
          setGamification(gamData);
        }
      } catch (err) {
        console.error("Error fetching session gamification:", err);
      }
    };

    const checkStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/debrief/status/${sessionCode}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) {
          const statusData = await res.json();

          // If still pending, trigger generation
          if (statusData.status === "pending") {
            await fetch(`${API_BASE}/api/debrief/generate/${sessionCode}`, {
              method: "POST",
              headers: token ? { Authorization: `Bearer ${token}` } : {},
            }).catch(() => {});
            return false;
          }

          if (statusData.status === "completed") {
            const reportRes = await fetch(`${API_BASE}/api/debrief/${sessionCode}`, {
              headers: token ? { Authorization: `Bearer ${token}` } : {},
            });
            if (reportRes.ok) {
              const report = await reportRes.json();
              setScore(report.overall_score);
              setGrade(report.grade || "A");

              const narrativeRaw = report.debrief?.narrative_report || {};
              const scenarioFromReport =
                narrativeRaw.scenario_name ||
                report.debrief?.scenario_name ||
                "ACLS Scenario";
              setScenarioName(scenarioFromReport);

              // Duration
              const sessionRes = await fetch(`${API_BASE}/session/${sessionCode}/info`, {
                headers: token ? { Authorization: `Bearer ${token}` } : {},
              }).catch(() => null);
              if (sessionRes?.ok) {
                const sessionData = await sessionRes.json();
                const startedAt = sessionData.started_at || sessionData.session?.started_at;
                const endedAt = sessionData.ended_at || sessionData.session?.ended_at;
                if (startedAt && endedAt) {
                  const durationMs = new Date(endedAt) - new Date(startedAt);
                  const totalSecs = Math.floor(durationMs / 1000);
                  const mins = Math.floor(totalSecs / 60);
                  const secs = totalSecs % 60;
                  setDurationStr(`${mins} Min${mins !== 1 ? "s" : ""} ${secs} Sec`);
                } else {
                  setDurationStr("Session completed");
                }
              } else {
                setDurationStr("Session completed");
              }

              // Fetch Gamification data
              await fetchGamification();
              setLoading(false);
              return true;
            }
          } else if (statusData.status === "failed") {
            setDurationStr("Generation failed");
            setLoading(false);
            return true;
          }
        }
      } catch (err) {
        console.error("Error fetching completed metrics:", err);
      }
      return false;
    };

    let timer;
    const poll = async () => {
      const done = await checkStatus();
      if (!done) {
        timer = setTimeout(poll, 2000);
      }
    };
    poll();

    // Also listen for the real-time push so we stop polling immediately
    // the moment the debrief worker emits debrief_completed via Socket.IO.
    const wsHandler = (data) => {
      if (data?.session_code !== sessionCode) return;
      if (wsHandledRef.current) return;
      wsHandledRef.current = true;
      clearTimeout(timer);
      checkStatus();
    };
    socket.connect();
    socket.on("debrief_completed", wsHandler);

    return () => {
      if (timer) clearTimeout(timer);
      socket.off("debrief_completed", wsHandler);
    };
  }, [sessionCode]); // eslint-disable-line react-hooks/exhaustive-deps

  const levelInfo = gamification?.level_info || {};
  const breakdown = gamification?.xp_breakdown || {};
  const newBadges = gamification?.badge_details || [];

  return (
    <div className="simulation-page" style={{ padding: "40px 16px" }}>
      <div className="sim-card" style={{ maxWidth: 640 }}>
        {/* Header */}
        <div style={{ textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: "12px" }}>
          <div style={{ width: 64, height: 64, borderRadius: "50%", backgroundColor: "#ECFDF5", border: "1px solid #A7F3D0", display: "flex", alignItems: "center", justifyContent: "center", color: "#059669" }}>
            <CheckCircle2 size={36} />
          </div>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 800, color: "#0F172A", letterSpacing: "-0.02em" }}>
              Simulation Completed
            </h1>
            <p style={{ fontSize: 12, color: "#64748B", marginTop: 4 }}>
              Session data saved and AI Debrief report generated successfully
            </p>
          </div>
        </div>

        {/* Level Up Banner */}
        {gamification?.levelled_up && (
          <div
            style={{
              backgroundColor: "#FFFBEB",
              border: "1px solid #FCD34D",
              borderRadius: 12,
              padding: "14px 18px",
              display: "flex",
              alignItems: "center",
              gap: 12,
              color: "#92400E"
            }}
          >
            <Sparkles size={24} color="#D97706" />
            <div>
              <h4 style={{ fontSize: 14, fontWeight: 800, margin: 0 }}>🎉 SIMULATION LEVEL UP!</h4>
              <p style={{ fontSize: 12, margin: "2px 0 0 0", color: "#B45309" }}>
                Your team achieved a new simulation competency level: <strong>{gamification.level}</strong>!
              </p>
            </div>
          </div>
        )}

        {/* Clinical Performance Card */}
        <div style={{ backgroundColor: "#F8FAFC", borderRadius: 12, border: "1px solid #E2E8F0", padding: "18px 20px", display: "flex", flexDirection: "column", gap: "12px", fontSize: 13 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: "12px", borderBottom: "1px solid #E2E8F0" }}>
            <span style={{ color: "#64748B", fontWeight: 500 }}>Scenario</span>
            <span style={{ fontWeight: 700, color: "#0F172A" }}>{scenarioName}</span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", paddingTop: "4px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <Clock size={18} color="#94A3B8" />
              <div>
                <span style={{ fontSize: "10px", color: "#94A3B8", display: "block", textTransform: "uppercase" }}>Duration</span>
                <span style={{ fontWeight: 700, color: "#1E293B" }}>{durationStr}</span>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <Award size={18} color="#0F766E" />
              <div>
                <span style={{ fontSize: "10px", color: "#94A3B8", display: "block", textTransform: "uppercase" }}>Performance Score</span>
                <span style={{ fontWeight: 800, color: "#0F766E", fontSize: "15px" }}>
                  {score !== null ? `${score} / 100 (Grade ${grade})` : "Calculating..."}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Gamification Result Card */}
        {gamification && (
          <div
            style={{
              background: "linear-gradient(135deg, #F0FDFA, #FFFFFF)",
              border: "1px solid #CCFBF1",
              borderRadius: 14,
              padding: "20px",
              display: "flex",
              flexDirection: "column",
              gap: 16
            }}
          >
            {/* XP Earned Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <span style={{ fontSize: 10, fontWeight: 700, color: "#0F766E", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                  Simulation XP Earned
                </span>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 2 }}>
                  <Zap size={22} color="#D97706" fill="#F59E0B" />
                  <span style={{ fontSize: 26, fontWeight: 800, color: "#0F172A", letterSpacing: "-0.02em" }}>
                    +{gamification.xp_earned} XP
                  </span>
                </div>
              </div>

              <div style={{ textAlign: "right" }}>
                <span style={{ fontSize: 10, fontWeight: 700, color: "#64748B", textTransform: "uppercase" }}>
                  Simulation Level
                </span>
                <div style={{ fontSize: 14, fontWeight: 800, color: "#0F766E", marginTop: 2 }}>
                  {gamification.level}
                </div>
              </div>
            </div>

            {/* Level Progress Bar */}
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#475569", fontWeight: 600 }}>
                <span>{gamification.total_xp.toLocaleString()} Total XP</span>
                <span>
                  {levelInfo.is_max_level
                    ? "MAX LEVEL"
                    : `${levelInfo.xp_into_level} / ${levelInfo.next_level_xp - levelInfo.current_level_xp} XP to ${levelInfo.level === "Novice" ? "Practitioner" : levelInfo.level === "Practitioner" ? "Expert" : "Master Resuscitationist"}`}
                </span>
              </div>
              <div style={{ height: 8, backgroundColor: "#E2E8F0", borderRadius: 4, overflow: "hidden" }}>
                <div
                  style={{
                    height: "100%",
                    width: `${levelInfo.progress_percent || 100}%`,
                    background: "linear-gradient(90deg, #0F766E, #0D9488)",
                    borderRadius: 4,
                    transition: "width 0.6s ease-out"
                  }}
                />
              </div>
            </div>

            {/* Transparent XP Breakdown Accordion */}
            <div style={{ border: "1px solid #E2E8F0", borderRadius: 10, backgroundColor: "#FFFFFF", overflow: "hidden" }}>
              <button
                onClick={() => setShowBreakdown(!showBreakdown)}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  backgroundColor: "#F8FAFC",
                  border: "none",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  fontSize: 12,
                  fontWeight: 600,
                  color: "#334155",
                  cursor: "pointer"
                }}
              >
                <span>View XP Calculation Breakdown</span>
                {showBreakdown ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </button>

              {showBreakdown && (
                <div style={{ padding: "12px 14px", fontSize: 12, display: "flex", flexDirection: "column", gap: 8, color: "#475569" }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Scenario Base XP ({breakdown.difficulty_multiplier}x Multiplier)</span>
                    <span style={{ fontWeight: 600 }}>+{breakdown.base_xp} XP</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Performance Bonus ({breakdown.performance_score}% Accuracy)</span>
                    <span style={{ fontWeight: 600, color: "#059669" }}>+{breakdown.performance_bonus} XP</span>
                  </div>
                  {breakdown.deviation_penalty > 0 && (
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span>Protocol Deviation Penalty ({gamification.deviation_count} Deviations)</span>
                      <span style={{ fontWeight: 600, color: "#DC2626" }}>-{breakdown.deviation_penalty} XP</span>
                    </div>
                  )}
                  <div style={{ borderTop: "1px solid #E2E8F0", paddingTop: 6, display: "flex", justifyContent: "space-between", fontWeight: 700, color: "#0F172A" }}>
                    <span>Total XP Earned</span>
                    <span>+{gamification.xp_earned} XP</span>
                  </div>
                </div>
              )}
            </div>

            {/* Newly Earned Badges Section */}
            {newBadges.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 10, paddingTop: 4 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: "#0F766E", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                  🎉 Newly Unlocked Achievements
                </span>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 10 }}>
                  {newBadges.map((badge) => (
                    <div
                      key={badge.id}
                      style={{
                        backgroundColor: "#FFFFFF",
                        border: "1px solid #A7F3D0",
                        borderRadius: 10,
                        padding: "12px",
                        display: "flex",
                        alignItems: "flex-start",
                        gap: 10,
                        boxShadow: "0 1px 3px rgba(0,0,0,0.05)"
                      }}
                    >
                      <span style={{ fontSize: 24, lineHeight: 1 }}>{badge.icon}</span>
                      <div>
                        <h5 style={{ fontSize: 13, fontWeight: 700, color: "#0F172A", margin: 0 }}>
                          {badge.label}
                        </h5>
                        <p style={{ fontSize: 11, color: "#64748B", margin: "2px 0 0 0", lineHeight: 1.35 }}>
                          {badge.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Action Buttons */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10, paddingTop: 8 }}>
          <button
            onClick={() => navigate(`/debrief?sessionCode=${sessionCode}`)}
            style={{ width: "100%", height: 44, backgroundColor: "#0F766E", color: "#FFFFFF", fontWeight: 600, fontSize: 14, borderRadius: 10, border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
          >
            <FileText size={18} />
            View AI Debrief Report
          </button>

          <button
            onClick={() => navigate("/leaderboard")}
            style={{ width: "100%", height: 44, backgroundColor: "#FFFBEB", color: "#B45309", border: "1px solid #FCD34D", fontWeight: 600, fontSize: 14, borderRadius: 10, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
          >
            <Award size={18} color="#D97706" />
            View Team Leaderboard
          </button>

          <button
            onClick={() => navigate("/dashboard")}
            style={{ width: "100%", height: 44, backgroundColor: "#FFFFFF", color: "#334155", border: "1px solid #CBD5E1", fontWeight: 600, fontSize: 14, borderRadius: 10, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
          >
            <LayoutDashboard size={18} color="#64748B" />
            Return to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
}
