import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";

import Login from "./pages/Login";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import RegistrationRequestPage from "./pages/RegistrationRequestPage";
import DashboardPage from "./pages/DashboardPage";
import ScenarioStudioPage from "./pages/ScenarioStudioPage";
import SimulationInitializingPage from "./pages/SimulationInitializingPage";
import PrebriefPage from './pages/PrebriefPage';
import SimulationCompletedPage from "./pages/SimulationCompletedPage";
import SessionsPage from "./pages/SessionsPage";
import DebriefPage from "./pages/DebriefPage";
import ReportsPage from "./pages/ReportsPage";
import SettingsPage from "./pages/SettingsPage";
import ProfilePage from "./pages/ProfilePage";
import StudentDashboardPage from "./pages/StudentDashboardPage";
import StudentMonitor from "./pages/StudentMonitor";
import InstructorDashboard from "./pages/InstructorDashboard";
import AudioOnlySessionPage from "./pages/AudioOnlySessionPage";
import SyntheticDebriefPage from "./pages/SyntheticDebriefPage";
import LeaderboardPage from "./pages/LeaderboardPage";

export default function App() {
  const instructorRoles = ["instructor", "operator", "admin"];
  const studentRoles = ["student", "admin"];

  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Authentication Flow */}
          <Route path="/" element={<Login />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/register" element={<RegistrationRequestPage />} />

          {/* Instructor Workflow */}
          <Route path="/dashboard" element={<ProtectedRoute allowedRoles={instructorRoles}><DashboardPage /></ProtectedRoute>} />
          <Route path="/cases" element={<ProtectedRoute allowedRoles={instructorRoles}><ScenarioStudioPage /></ProtectedRoute>} />
          <Route path="/library" element={<ProtectedRoute allowedRoles={instructorRoles}><ScenarioStudioPage /></ProtectedRoute>} />
          <Route path="/initializing" element={<ProtectedRoute allowedRoles={instructorRoles}><SimulationInitializingPage /></ProtectedRoute>} />
          <Route path="/prebrief" element={<ProtectedRoute allowedRoles={instructorRoles}><PrebriefPage /></ProtectedRoute>} />
          <Route path="/instructor" element={<ProtectedRoute allowedRoles={instructorRoles}><InstructorDashboard /></ProtectedRoute>} />
          <Route path="/audio-only" element={<ProtectedRoute allowedRoles={instructorRoles}><AudioOnlySessionPage /></ProtectedRoute>} />
          <Route path="/synthetic-test" element={<ProtectedRoute allowedRoles={instructorRoles}><SyntheticDebriefPage /></ProtectedRoute>} />
          <Route path="/leaderboard" element={<ProtectedRoute allowedRoles={instructorRoles}><LeaderboardPage /></ProtectedRoute>} />
          <Route path="/completed" element={<ProtectedRoute allowedRoles={instructorRoles}><SimulationCompletedPage /></ProtectedRoute>} />
          <Route path="/debrief" element={<ProtectedRoute allowedRoles={instructorRoles}><DebriefPage /></ProtectedRoute>} />
          <Route path="/debrief/:sessionCode" element={<ProtectedRoute allowedRoles={instructorRoles}><DebriefPage /></ProtectedRoute>} />
          <Route path="/sessions" element={<ProtectedRoute allowedRoles={instructorRoles}><SessionsPage /></ProtectedRoute>} />
          <Route path="/reports" element={<ProtectedRoute allowedRoles={instructorRoles}><ReportsPage /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute allowedRoles={instructorRoles}><SettingsPage /></ProtectedRoute>} />
          <Route path="/profile" element={<ProtectedRoute allowedRoles={instructorRoles}><ProfilePage /></ProtectedRoute>} />

          {/* Student Workflow */}
          <Route path="/student-dashboard" element={<ProtectedRoute allowedRoles={studentRoles}><StudentDashboardPage /></ProtectedRoute>} />
          <Route path="/monitor/:sessionCode" element={<ProtectedRoute allowedRoles={studentRoles}><StudentMonitor /></ProtectedRoute>} />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

