import { useEffect, useRef, useState } from "react";
import socket from "../../socket";

const API = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

const isTranscript = (entry) => Boolean(
  entry?.audio_job_id || ["ceiling_audio", "lapel_audio"].includes(String(entry?.source || "").toLowerCase())
);

const eventTime = (entry) => {
  if (entry?.timestamp) {
    const parsed = new Date(entry.timestamp);
    if (!Number.isNaN(parsed.getTime())) return parsed.toLocaleTimeString();
  }
  const seconds = Math.max(0, Math.floor(Number(entry?.timestamp_ms || 0) / 1000));
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
};

const statusColour = (status) => {
  if (status === "completed") return "#22C55E";
  if (status === "failed") return "#F87171";
  if (["running", "finalizing", "queued"].includes(status)) return "#FBBF24";
  return "#60A5FA";
};

export default function CommunicationPanel({ sessionCode }) {
  const [activeTab, setActiveTab] = useState("events");
  const [events, setEvents] = useState([]);
  const [recorders, setRecorders] = useState([]);
  const [audioStatusError, setAudioStatusError] = useState("");
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const eventEndRef = useRef(null);
  const chatEndRef = useRef(null);

  const authHeaders = () => {
    const token = sessionStorage.getItem("token") || localStorage.getItem("token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const applyLog = (eventLog) => {
    if (!Array.isArray(eventLog)) return;
    setEvents(eventLog);
    setChatMessages(eventLog
      .filter((entry) => String(entry?.event || "").startsWith("Instructor Comment: "))
      .map((entry) => ({
        comment: entry.event.replace("Instructor Comment: ", ""),
        timestamp: entry.timestamp,
        from: "Instructor",
      })));
  };

  const refreshEvidence = async () => {
    if (!sessionCode) return;
    const headers = authHeaders();
    try {
      const [logResponse, audioResponse] = await Promise.all([
        fetch(`${API}/session/${encodeURIComponent(sessionCode)}/log`, { headers }),
        fetch(`${API}/api/session/${encodeURIComponent(sessionCode)}/live-audio/status`, { headers }),
      ]);
      if (logResponse.ok) applyLog((await logResponse.json()).event_log);
      if (audioResponse.ok) {
        const audioData = await audioResponse.json();
        setRecorders(Array.isArray(audioData.recorders) ? audioData.recorders : []);
        setAudioStatusError("");
      } else {
        const detail = await audioResponse.json().catch(() => ({}));
        setAudioStatusError(detail.detail || "Audio evidence status is unavailable.");
      }
    } catch (error) {
      setAudioStatusError(error.message || "Audio evidence status is unavailable.");
    }
  };

  useEffect(() => {
    refreshEvidence();
    const interval = window.setInterval(refreshEvidence, 3000);
    return () => window.clearInterval(interval);
  }, [sessionCode]);

  useEffect(() => {
    const handleEvent = (entry) => {
      setEvents((previous) => {
        if (previous.some((item) => item.timestamp === entry.timestamp && item.event === entry.event && item.segment_id === entry.segment_id)) return previous;
        return [...previous, entry].slice(-200);
      });
      setTimeout(() => eventEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    };
    const handleHistoryLog = (data) => applyLog(data?.event_log);
    const handleFacultyComment = (message) => {
      setChatMessages((previous) => previous.some((item) => item.timestamp === message.timestamp && item.comment === message.comment)
        ? previous : [...previous, message]);
      setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    };
    const handleAudioStatus = () => refreshEvidence();

    socket.on("session_event", handleEvent);
    socket.on("session_history_log", handleHistoryLog);
    socket.on("faculty_comment", handleFacultyComment);
    socket.on("live_audio_status", handleAudioStatus);
    socket.on("audio_debrief_completed", handleAudioStatus);
    return () => {
      socket.off("session_event", handleEvent);
      socket.off("session_history_log", handleHistoryLog);
      socket.off("faculty_comment", handleFacultyComment);
      socket.off("live_audio_status", handleAudioStatus);
      socket.off("audio_debrief_completed", handleAudioStatus);
    };
  }, [sessionCode]);

  const handleSendChat = () => {
    if (!chatInput.trim()) return;
    const text = chatInput.trim();
    socket.emit("add_event_log", { session_code: sessionCode, event: `Instructor Comment: ${text}` });
    socket.emit("faculty_comment", { session_code: sessionCode, comment: text, from: "Instructor", timestamp: Date.now() });
    setChatInput("");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, minHeight: 0 }}>
      <section style={{ background: "#0F172A", border: "1px solid #334155", borderRadius: 8, padding: 10 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <strong style={{ fontSize: 12, color: "#F8FAFC" }}>Audio evidence</strong>
          <span style={{ fontSize: 9, color: "#94A3B8" }}>Updates every 3 seconds</span>
        </div>
        {audioStatusError && <div style={{ color: "#FCA5A5", fontSize: 10 }}>{audioStatusError}</div>}
        {!audioStatusError && recorders.length === 0 && (
          <div style={{ color: "#FBBF24", fontSize: 11, lineHeight: 1.45 }}>
            No microphone recording has started. Click <strong>Record audio</strong> in the top bar and confirm that “Speech detected” and the saved-chunk count appear.
          </div>
        )}
        {recorders.map((recorder) => {
          const status = String(recorder.job_status || recorder.recorder_status || "unknown").toLowerCase();
          const error = recorder.job_error || recorder.recorder_error;
          return (
            <div key={recorder.recorder_id} style={{ borderTop: "1px solid #1E293B", paddingTop: 8, marginTop: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <span style={{ color: "#CBD5E1", fontSize: 10, overflow: "hidden", textOverflow: "ellipsis" }}>
                  {recorder.participant_role || "participant"} · {recorder.audio_source || "room"}
                </span>
                <strong style={{ color: statusColour(status), fontSize: 10, textTransform: "uppercase" }}>{status}</strong>
              </div>
              <div style={{ color: "#94A3B8", fontSize: 10, marginTop: 3 }}>
                {recorder.chunk_count || 0} chunks · {((recorder.bytes_uploaded || 0) / 1024 / 1024).toFixed(2)} MB
                {recorder.segment_count != null ? ` · ${recorder.segment_count} transcript segments` : ""}
              </div>
              {status === "recording" && <div style={{ color: "#64748B", fontSize: 9, marginTop: 3 }}>Audio is being saved now. Transcription and diarization begin after End Session.</div>}
              {error && <div style={{ color: "#FCA5A5", fontSize: 9, marginTop: 3 }}>{error}</div>}
            </div>
          );
        })}
      </section>

      <div className="comm-footer-tabs">
        <button className={`comm-tab ${activeTab === "events" ? "active" : ""}`} onClick={() => setActiveTab("events")}>Timeline ({events.length})</button>
        <button className={`comm-tab ${activeTab === "chat" ? "active" : ""}`} onClick={() => setActiveTab("chat")}>Instructor Chat</button>
      </div>

      {activeTab === "events" && (
        <div className="comm-pane event-list compact-list" style={{ maxHeight: 430, overflowY: "auto" }}>
          {events.length === 0 && <div className="empty-state">No simulator changes or transcript segments recorded yet.</div>}
          {events.map((entry, index) => {
            const transcript = isTranscript(entry);
            const audioStatus = entry.event_type === "AUDIO_STATUS" || entry.source === "live_audio";
            const role = entry.speaker_name || entry.actor_role || entry.speaker_label;
            return (
              <div key={entry.segment_id || `${entry.timestamp || entry.timestamp_ms}-${index}`} className="event-entry compact" style={{ alignItems: "flex-start" }}>
                <span className="event-time">{eventTime(entry)}</span>
                <span className="event-text" style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <span>
                    <span style={{ color: transcript ? "#2DD4BF" : audioStatus ? "#FBBF24" : "#60A5FA", fontSize: 9, fontWeight: 800, marginRight: 5 }}>
                      {transcript ? "TRANSCRIPT" : audioStatus ? "AUDIO" : "EVENT"}
                    </span>
                    {role && transcript ? <strong style={{ color: "#E2E8F0", marginRight: 4 }}>{role}:</strong> : null}
                    {entry.event || entry.text || "Unnamed event"}
                  </span>
                  {transcript && <span style={{ color: "#64748B", fontSize: 9 }}>confidence {Math.round(Number(entry.confidence || 0) * 100)}% · {entry.role_evidence || "role inferred"}</span>}
                </span>
              </div>
            );
          })}
          <div ref={eventEndRef} />
        </div>
      )}

      {activeTab === "chat" && (
        <div className="comm-pane chat-pane compact-chat" style={{ display: "flex", flexDirection: "column", minHeight: 260, padding: 10 }}>
          <div className="chat-history" style={{ flex: 1, overflowY: "auto", marginBottom: 10, display: "flex", flexDirection: "column", gap: 6 }}>
            {chatMessages.length === 0 && <div className="empty-state">No messages sent yet.</div>}
            {chatMessages.map((message, index) => (
              <div key={index} style={{ backgroundColor: "#1E293B", padding: "8px 12px", borderRadius: 6, border: "1px solid #334155" }}>
                <div style={{ fontSize: 10, color: "#94A3B8", display: "flex", justifyContent: "space-between" }}><span>{message.from || "Instructor"}</span><span>{new Date(message.timestamp).toLocaleTimeString()}</span></div>
                <div style={{ fontSize: 12, color: "#F1F5F9" }}>{message.comment}</div>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <input value={chatInput} onChange={(event) => setChatInput(event.target.value)} onKeyDown={(event) => event.key === "Enter" && handleSendChat()} placeholder="Broadcast message to students..." style={{ flex: 1, padding: "8px 12px", borderRadius: 6, border: "1px solid #334155", backgroundColor: "#0F172A", color: "#F8FAFC" }} />
            <button onClick={handleSendChat} style={{ backgroundColor: "#0EA5E9", color: "#FFF", border: "none", borderRadius: 6, padding: "0 16px", cursor: "pointer", fontWeight: 600 }}>Send</button>
          </div>
        </div>
      )}
    </div>
  );
}
