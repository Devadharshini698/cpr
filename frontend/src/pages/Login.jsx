import React, { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Activity, Lock, User, ShieldCheck, UserCheck } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import "../styles/auth.css";

export default function Login() {
  const [selectedRole, setSelectedRole] = useState("instructor");
  const [username, setUsername] = useState("instructor");
  const [password, setPassword] = useState("instructor123");
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  
  const navigate = useNavigate();
  const { login, user, isAuthenticated } = useAuth();

  useEffect(() => {
    if (isAuthenticated && user) {
      if (user.role === "student") {
        navigate("/student-dashboard", { replace: true });
      } else {
        navigate("/dashboard", { replace: true });
      }
    }
  }, [isAuthenticated, user, navigate]);

  const handleRoleChange = (role) => {
    setSelectedRole(role);
    setError("");
    if (role === "instructor") {
      setUsername("instructor");
      setPassword("instructor123");
    } else {
      setUsername("student");
      setPassword("student123");
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      const res = await login(username, password, selectedRole, rememberMe);
      const userRole = res.role || selectedRole;
      if (userRole === "student") {
        navigate("/student-dashboard");
      } else {
        navigate("/dashboard");

      }
    } catch (err) {
      console.error("Authentication failed:", err);
      setError(err.message || "Invalid username or password");
    } finally {
      setSubmitting(false);
    }


  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        {/* App Header */}
        <div className="auth-header">
          <div className="auth-logo">
            <Activity size={30} />
          </div>
          <div>
            <h1 className="auth-title">MedSim AI</h1>
            <span className="auth-badge">Simulation & Debrief Platform</span>
          </div>
        </div>

        {/* Role Selector Tabs */}
        <div style={{ display: "flex", gap: "8px", marginBottom: "16px", backgroundColor: "#F1F5F9", padding: "4px", borderRadius: "10px" }}>
          <button
            type="button"
            onClick={() => handleRoleChange("instructor")}
            style={{
              flex: 1,
              padding: "8px 12px",
              borderRadius: "8px",
              border: "none",
              backgroundColor: selectedRole === "instructor" ? "#FFFFFF" : "transparent",
              color: selectedRole === "instructor" ? "#0F766E" : "#64748B",
              fontWeight: selectedRole === "instructor" ? 600 : 500,
              fontSize: "12px",
              cursor: "pointer",
              boxShadow: selectedRole === "instructor" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px"
            }}
          >
            <UserCheck size={14} />
            Instructor
          </button>
          <button
            type="button"
            onClick={() => handleRoleChange("student")}
            style={{
              flex: 1,
              padding: "8px 12px",
              borderRadius: "8px",
              border: "none",
              backgroundColor: selectedRole === "student" ? "#FFFFFF" : "transparent",
              color: selectedRole === "student" ? "#0F766E" : "#64748B",
              fontWeight: selectedRole === "student" ? 600 : 500,
              fontSize: "12px",
              cursor: "pointer",
              boxShadow: selectedRole === "student" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px"
            }}
          >
            <ShieldCheck size={14} />
            Student
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleLogin} className="auth-form">
          <div className="auth-field">
            <label className="auth-label">
              {selectedRole === "instructor" ? "Instructor Username / Email" : "Student Username / Student ID"}
            </label>
            <div className="auth-input-container">
              <User className="auth-input-icon" />
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder={selectedRole === "instructor" ? "instructor" : "student"}
                className="auth-input"
              />
            </div>
          </div>

          <div className="auth-field">
            <label className="auth-label">Password</label>
            <div className="auth-input-container">
              <Lock className="auth-input-icon" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="auth-input"
              />
            </div>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "12px", paddingTop: "4px" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "6px", color: "#475569", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                style={{ accentColor: "#0F766E" }}
              />
              Remember Me
            </label>
            <Link to="/forgot-password" style={{ color: "#0F766E", fontWeight: 600 }}>
              Forgot Password?
            </Link>
          </div>

          {error && (
            <div style={{ padding: "10px", borderRadius: "10px", backgroundColor: "#FEF2F2", color: "#DC2626", fontSize: "12px", fontWeight: 600, textAlign: "center" }}>
              {error}
            </div>
          )}

          <button type="submit" disabled={submitting} className="auth-btn-primary">
            {submitting ? "Authenticating..." : `Sign In as ${selectedRole === "instructor" ? "Instructor" : "Student"} →`}
          </button>

          <div style={{ textAlign: "center", fontSize: "12px", color: "#64748B" }}>
            Need an account?{" "}
            <Link to="/register" style={{ color: "#0F766E", fontWeight: 600 }}>
              Request Access
            </Link>
          </div>
        </form>

        <div style={{ textAlign: "center", fontSize: "11px", color: "#94A3B8" }}>
          🔒 Secure Clinical Simulation Node • MedSim AI v2.4
        </div>
      </div>
    </div>
  );
}

