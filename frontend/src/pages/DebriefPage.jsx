import React, { useState, useEffect } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import socket from "../socket";
import PatientAssessment from '../components/monitor/PatientAssessment';
import Navbar from "../components/dashboard/Navbar";
import Sidebar from "../components/dashboard/Sidebar";
import DashboardModals from "../components/dashboard/DashboardModals";
import {
  AlertTriangle,
  Award,
  Activity,
  Download,
  Share2,
  Loader2,
  RefreshCw,
  MessageSquare,
  Sparkles,
  ShieldCheck,
  ChevronRight,
  HelpCircle,
  TrendingUp,
  Upload,
} from "lucide-react";
import "../components/dashboard/dashboard.css";

const API_BASE = (import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
const fetch = (url, options = {}) => window.fetch(url, { ...options, signal: AbortSignal.timeout(30000) });

export default function DebriefPage() {
  const navigate = useNavigate();
  const params = useParams();
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);

  // Extract sessionCode from URL params, query string, location state, or sessionStorage
  const sessionCode =
    params.sessionCode ||
    searchParams.get("sessionCode") ||
    location.state?.sessionCode ||
    sessionStorage.getItem("session_code") ||
    sessionStorage.getItem("currentSessionCode") ||
    sessionStorage.getItem("activeSessionCode") ||
    "";

  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [activeModal, setActiveModal] = useState(null);

  // API State
  const [loadingStatus, setLoadingStatus] = useState("running"); // pending | running | completed | failed
  const [debriefData, setDebriefData] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [realAudio, setRealAudio] = useState(null);
  const [realAudioSource, setRealAudioSource] = useState("ceiling");
  const [realAudioLanguage, setRealAudioLanguage] = useState("");
  const [realAudioOffsetSeconds, setRealAudioOffsetSeconds] = useState(0);
  const [realAudioState, setRealAudioState] = useState("idle");
  const [realAudioMessage, setRealAudioMessage] = useState("");
  const [manualRunState, setManualRunState] = useState("idle");
  const [audioSyncMessage, setAudioSyncMessage] = useState("");
  const [diarizationMessage, setDiarizationMessage] = useState("");

  const token = sessionStorage.getItem("token") || localStorage.getItem("token") || "";

  // ── Fetch Status & Report ──────────────────────────────────────────
  const fetchReport = async () => {
    try {
      const authHeader = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await fetch(`${API_BASE}/api/debrief/${encodeURIComponent(sessionCode)}?v=${Date.now()}`, {
        headers: authHeader,
        cache: "no-store",
      });

      if (!res.ok) {
        throw new Error(`Failed to load debrief report (${res.status})`);
      }

      const data = await res.json();
      if (String(data.status).toLowerCase() !== 'completed') return false;
      setDebriefData(data);
      setLoadingStatus("completed");
      setManualRunState("idle");
      setErrorMsg(null);
      return true;
    } catch (err) {
      console.error("Error fetching debrief report:", err);
      setErrorMsg(err.message || "Failed to load debrief report.");
      setLoadingStatus("failed");
      return false;
    }
  };

  const triggerGeneration = async () => {
    if (!sessionCode) return;
    try {
      const authHeader = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await fetch(`${API_BASE}/api/debrief/generate/${encodeURIComponent(sessionCode)}`, {
        method: "POST",
        headers: authHeader,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Could not start debrief generation (${res.status}).`);
      }
    } catch (err) {
      console.warn("Could not trigger generate endpoint:", err);
      throw err;
    }
  };

  const checkStatusAndPoll = async () => {
    if (!sessionCode) {
      setLoadingStatus("failed");
      setErrorMsg("No session code provided for debrief report.");
      return true; // stop polling
    }
    try {
      const authHeader = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await fetch(`${API_BASE}/api/debrief/status/${encodeURIComponent(sessionCode)}?v=${Date.now()}`, {
        headers: authHeader,
        cache: "no-store",
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail = data.detail || data.error_message;
        const guidance = res.status === 401 || res.status === 403
          ? "Your sign-in session has expired. Sign out and sign in again, then reopen this report."
          : `The report status service is unavailable (${res.status}). Check that the backend is running, then refresh this page.`;
        setLoadingStatus("failed");
        setErrorMsg(detail ? `${guidance} ${detail}` : guidance);
        return true;
      }

      {
        const data = await res.json();
        const currentStatus = (data.status || "pending").toLowerCase();

        if (currentStatus === "pending") {
          setLoadingStatus("running");
          try {
            await triggerGeneration();
          } catch (err) {
            setLoadingStatus("failed");
            setErrorMsg(err.message || "Could not start debrief generation.");
            return true;
          }
        } else if (currentStatus === "running" || currentStatus === "queued") {
          setLoadingStatus("running");
        } else if (currentStatus === "completed") {
          const audio = await fetch(`${API_BASE}/api/session/${encodeURIComponent(sessionCode)}/upload-audio/status`, { headers: authHeader });
          if (audio.ok) {
            const state = await audio.json();
            setDiarizationMessage(state.diarization_status === 'fallback_unverified'
              ? 'Transcript available, but acoustic speaker separation failed. Speaker/role labels require instructor review.'
              : state.diarization_status === 'acoustic_completed'
                ? 'Acoustic speaker separation completed. Names and roles still require instructor confirmation.'
                : 'Acoustic speaker-separation outcome was not recorded for this session.');
            if (['queued', 'running'].includes(state.status)) {
              setAudioSyncMessage('Preliminary report: audio analysis is still running. Transcript and communication findings are incomplete; the report will update automatically.');
              await fetchReport();
              return false;
            }
          }
          // Do not stop the status loop until the report itself has been
          // retrieved.  Without awaiting this request, a completed upload
          // could leave the page displaying its previous "generating" state.
          return await fetchReport();
        } else if (currentStatus === "failed") {
          setLoadingStatus("failed");
          setErrorMsg(data.error_message || "Debrief report generation failed on the server.");
          return true; // stop polling
        }
      }
    } catch (err) {
      console.warn("Error checking debrief status:", err);
      setLoadingStatus('failed');
      setErrorMsg('Cannot reach the report service. Your saved recording is preserved. Check the backend connection and use Retry.');
      return true;
    }
    return false;
  };

  useEffect(() => {
    if (!sessionCode) {
      setLoadingStatus("failed");
      setErrorMsg("No active session selected. Please launch or select a session to view its debrief report.");
      return;
    }

    let timer = null;
    let isCancelled = false;

    const poll = async () => {
      const done = await checkStatusAndPoll();
      if (!done && !isCancelled) {
        timer = setTimeout(poll, 2500);
      }
    };

    poll();

    return () => {
      isCancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [sessionCode]);

  // A live recording is finalized after the session ends. The first completed
  // debrief can therefore predate its transcript; WebSocket delivery is only
  // an optimization, not the source of truth for the final report.
  useEffect(() => {
    if (!sessionCode) return;
    let cancelled = false;
    let timer;
    let attempts = 0;
    const sync = async () => {
      try {
        const headers = token ? { Authorization: `Bearer ${token}` } : {};
        const audioRes = await fetch(`${API_BASE}/api/session/${encodeURIComponent(sessionCode)}/live-audio/status`, { headers, cache: "no-store" });
        if (!audioRes.ok) return;
        const recorders = (await audioRes.json()).recorders || [];
        if (!recorders.length) return;
        const failed = recorders.find((item) => item.job_status === "failed" || item.recorder_status === "failed");
        if (failed) {
          if (!cancelled) setAudioSyncMessage(failed.job_error || failed.recorder_error || "Audio processing failed; the transcript is not available.");
          return;
        }
        // Do not render a pre-audio report while chunks are being finalized or
        // transcribed.  That earlier report has no transcript yet and made the
        // debrief page look empty immediately after the microphone was stopped.
        const processing = recorders.some((item) =>
          ["recording", "queued", "running", "finalizing"].includes(String(item.job_status || item.recorder_status || "").toLowerCase())
        );
        if (processing) {
          if (!cancelled) {
            setLoadingStatus(previous => previous === 'completed' ? previous : 'running');
            setAudioSyncMessage("Preliminary report: audio is saved and speaker/transcript analysis is still running. Audio-dependent findings are incomplete and will update automatically.");
          }
          if (!cancelled && ++attempts < 360) timer = window.setTimeout(sync, 5000);
          else if (!cancelled) { setLoadingStatus('failed'); setErrorMsg('Processing has exceeded 30 minutes. Recording is saved; check status before retrying.'); }
          return;
        }
        const expected = recorders.reduce((total, item) => total + Number(item.segment_count || 0), 0);
        const reportRes = await fetch(`${API_BASE}/api/debrief/${encodeURIComponent(sessionCode)}`, { headers, cache: "no-store" });
        if (reportRes.ok) {
          const latest = await reportRes.json();
          const latestReport = latest.debrief || latest;
          const actual = latestReport.timeline?.transcript_segments?.length || 0;
          if (!cancelled) {
            if (actual < expected) {
              setLoadingStatus(previous => previous === 'completed' ? previous : 'running');
              setAudioSyncMessage(`Transcript ready (${expected} segments). Building the synchronized debrief report…`);
            } else {
              setDebriefData(latest);
              setLoadingStatus("completed");
              setAudioSyncMessage("");
            }
          }
          if (recorders.every((item) => item.job_status === "completed") && actual >= expected) return;
        } else if (!cancelled) {
          setAudioSyncMessage("Audio is processing. Waiting for the transcript-bearing report…");
        }
      } catch (err) {
        console.warn("Audio/report synchronization check failed:", err);
      }
      if (!cancelled && ++attempts < 360) timer = window.setTimeout(sync, 5000);
      else if (!cancelled) { setLoadingStatus('failed'); setErrorMsg('Report synchronisation timed out. Refresh to check the saved job.'); }
    };
    sync();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [sessionCode]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Download PDF Handler ───────────────────────────────────────────
  const handleDownloadPdf = async () => {
    setDownloadingPdf(true);
    try {
      const authHeader = token ? { Authorization: `Bearer ${token}` } : {};
      // A report may have been regenerated after an audio upload.  Include a
      // version token and opt out of the browser cache so Download PDF always
      // returns the latest transcript-bearing artifact for this session.
      const reportUrl = `${API_BASE}/api/reports/${encodeURIComponent(sessionCode)}?v=${Date.now()}`;
      const res = await fetch(reportUrl, {
        headers: authHeader,
        cache: "no-store",
      });

      if (!res.ok) {
        throw new Error("PDF report is not available yet.");
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${sessionCode}_debrief.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert(err.message || "Failed to download PDF report.");
    } finally {
      setDownloadingPdf(false);
    }
  };

  const handleManualRun = async () => {
    if (!sessionCode) return;
    setManualRunState("queueing");
    setLoadingStatus("running");
    setErrorMsg(null);
    try {
      await triggerGeneration();
      setManualRunState("queued");
      const pollRegeneration = async () => {
        const done = await checkStatusAndPoll();
        if (!done) window.setTimeout(pollRegeneration, 2500);
      };
      window.setTimeout(pollRegeneration, 400);
    } catch (err) {
      setManualRunState("failed");
      setLoadingStatus("failed");
      setErrorMsg(err.message || "Could not queue the manual debrief run.");
    }
  };

  const pollRealAudioStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/session/${encodeURIComponent(sessionCode)}/upload-audio/status`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not read audio processing status.");
      const status = String(data.status || "queued").toLowerCase();
      setRealAudioState(status);
      if (status === "completed") {
        setRealAudioMessage(`${data.segment_count || 0} conversation segments synchronized. Updating report…`);
        setLoadingStatus("running");
        const waitForReport = async () => {
          if (!(await checkStatusAndPoll())) window.setTimeout(waitForReport, 2500);
        };
        await waitForReport();
        return;
      }
      if (status === "failed") {
        setRealAudioMessage(data.error || "Audio processing failed.");
        return;
      }
      setRealAudioMessage(status === "running" ? "Transcribing and identifying speakers…" : "Audio queued for transcription…");
      window.setTimeout(pollRealAudioStatus, 2500);
    } catch (err) {
      setRealAudioState("failed");
      setRealAudioMessage(err.message || "Could not read audio processing status.");
    }
  };

  const handleRealAudioUpload = async () => {
    if (!sessionCode || !realAudio) return;
    setRealAudioState("uploading");
    setRealAudioMessage("Uploading recording…");
    try {
      const form = new FormData();
      form.append("audio", realAudio);
      form.append("source", realAudioSource);
      if (realAudioLanguage) form.append("language_mode", realAudioLanguage);
      form.append("audio_offset_ms", String(Math.max(0, Number(realAudioOffsetSeconds) || 0) * 1000));
      const res = await fetch(`${API_BASE}/api/session/${encodeURIComponent(sessionCode)}/upload-audio`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Audio upload failed.");
      setRealAudioState(data.status || "queued");
      setRealAudioMessage("Audio queued for transcription…");
      window.setTimeout(pollRealAudioStatus, 1000);
    } catch (err) {
      setRealAudioState("failed");
      setRealAudioMessage(err.message || "Audio upload failed.");
    }
  };

  const handleStartSimulation = () => navigate("/initializing");
  const handleLogout = () => {
    sessionStorage.clear();
    localStorage.clear();
    navigate("/");
  };

  // ── WebSocket: stop polling the moment the worker emits debrief_completed ──
  useEffect(() => {
    if (!sessionCode) return;
    const handler = (data) => {
      if (data?.session_code !== sessionCode) return;
      fetchReport();
    };
    socket.connect();
    socket.on("debrief_completed", handler);
    return () => {
      socket.off("debrief_completed", handler);
    };
  }, [sessionCode]); // eslint-disable-line react-hooks/exhaustive-deps

  // Extract debrief fields
  const debrief = debriefData?.debrief || debriefData || {};
  const overallScore = debriefData?.overall_score ?? debrief.overall_score ?? null;
  const grade = debriefData?.grade || debrief.grade || (overallScore !== null ? (overallScore >= 90 ? "A" : overallScore >= 80 ? "B" : "C") : "N/A");
  const scoreStatus = debrief.score_status || (overallScore === null ? "not_assessed" : "provisional");
  const classification = debrief.classification || null;
  const findings = debrief.findings || [];
  const timelineEvents = debrief.timeline?.events || [];
  const synchronizedItems = debrief.timeline?.synchronized_items || timelineEvents.map((event) => ({ kind: "clinical_event", ...event }));
  const conversationItems = synchronizedItems.filter((item) => item.kind === "conversation");
  const evidenceText = (evidence) => {
    if (Array.isArray(evidence)) return evidence.map((item) => item?.text || item?.ref || "").filter(Boolean).join(" · ");
    return typeof evidence === "string" ? evidence : "";
  };
  const isAudioDerived = (item) => {
    const sources = item.source_systems || [];
    return sources.length > 0 && sources.every((source) => ["lapel_audio", "ceiling_audio"].includes(source));
  };
  // A spoken statement that resembles an ACLS action is discussion evidence,
  // not a verified clinical action. Keep it out of this panel unless an
  // independent simulator/manual source confirms it.
  const clinicalItems = synchronizedItems.filter((item) => (
    item.kind === "clinical_event"
    && item.event_type !== "scenario_marker"
    && item.data_completeness !== "uncertain"
    && !isAudioDerived(item)
  ));
  const lowConfidenceTranscript = conversationItems.filter((item) => Number(item.confidence ?? 0) < 0.6);
  const roleLabel = (role) => String(role || "").includes("+")
    ? `Ambiguous role: ${String(role).split("+").map((part) => part.replace(/_/g, " ")).join(" or ")}`
    : ({
    team_leader: "Team Leader",
    compressor: "Compressor",
    airway: "Airway Manager",
    airway_manager: "Airway Manager",
    iv_member: "Medication Nurse",
    medication_nurse: "Medication Nurse",
    defib_coach: "Defibrillation Coach",
    defibrillator: "Defibrillation Coach",
    recorder: "Recorder",
    unknown: "Unassigned role",
  }[role] || String(role || "unknown").replace(/_/g, " "));
  const domainScores = debrief.domain_scores || [];
  // narrative_report.to_dict() nests sections under a "sections" key;
  // fall back to the top-level keys for backward compatibility.
  const narrativeRaw = debrief.narrative_report || {};
  const narrative = narrativeRaw.sections || narrativeRaw;
  const speechTopics = Array.isArray(narrativeRaw.generation_metadata?.speech_topics)
    ? narrativeRaw.generation_metadata.speech_topics : [];
  const scenarioName =
    narrativeRaw.scenario_name ||
    debrief.scenario_name ||
    debriefData?.scenario_name ||
    "Clinical Simulation Session";
  const audioOnlyReport = /audio.only/i.test(scenarioName);
  const reportReady = loadingStatus === "completed" && Boolean(debriefData);
  // reflective_prompts can be a string (JSON array) or direct array
  let reflectivePrompts = [];
  try {
    const rawPrompts = narrative.reflective_prompts;
    if (Array.isArray(rawPrompts)) reflectivePrompts = rawPrompts;
    else if (typeof rawPrompts === "string" && rawPrompts.trim()) {
      const parsed = JSON.parse(rawPrompts);
      if (Array.isArray(parsed)) reflectivePrompts = parsed;
      else reflectivePrompts = rawPrompts.split(/\n+/).filter(Boolean);
    }
  } catch {
    // keep empty array
  }

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
          activeTab="reports"
          setActiveTab={(tab) => {
            if (tab === "dashboard") navigate("/dashboard");
          }}
          handleStartSimulation={handleStartSimulation}
          onOpenModal={(modalType) => setActiveModal(modalType)}
        />

        <main className="medsim-main-content space-y-6 overflow-y-auto pb-12">
          {diarizationMessage && <p role="status" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">{diarizationMessage}</p>}
          {/* Header */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                  {audioOnlyReport ? "Audio-only team debrief" : "AI Automated Debrief Report"}
                </h1>
                <span className="font-mono text-xs font-bold bg-teal-50 text-teal-800 border border-teal-200 px-3 py-1 rounded-full">
                  {sessionCode}
                </span>
              </div>
              <p className="text-sm text-slate-500 mt-1">
                {audioOnlyReport ? "Recorded conversation and transcript evidence; no simulator events or clinical score" : "ACLS evidence, event timeline and performance analytics"}
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handleManualRun}
                disabled={!sessionCode || manualRunState === "queueing" || loadingStatus === "running"}
                title="Queue a fresh report from the saved simulator events and synchronized transcript"
                className="px-4 py-2 bg-white border border-teal-200 hover:bg-teal-50 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl text-xs font-semibold text-teal-800 cursor-pointer flex items-center gap-2"
              >
                {manualRunState === "queueing" || loadingStatus === "running"
                  ? <Loader2 className="w-4 h-4 animate-spin" />
                  : <RefreshCw className="w-4 h-4" />}
                {manualRunState === "queued" || loadingStatus === "running" ? "Debrief queued" : "Run / regenerate debrief"}
              </button>
              <button
                onClick={() => {
                  if (navigator.share) {
                    navigator.share({ title: `CPR Debrief ${sessionCode}`, url: window.location.href });
                  } else {
                    navigator.clipboard.writeText(window.location.href);
                    alert("Report link copied to clipboard!");
                  }
                }}
                className="px-4 py-2 bg-white border border-slate-200 hover:bg-slate-50 rounded-xl text-xs font-semibold text-slate-700 cursor-pointer flex items-center gap-2"
              >
                <Share2 className="w-4 h-4 text-slate-500" />
                Share Report
              </button>

              <button
                onClick={handleDownloadPdf}
                disabled={!reportReady || downloadingPdf}
                className="px-4 py-2 bg-teal-700 hover:bg-teal-800 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl text-xs font-semibold text-white cursor-pointer flex items-center gap-2 shadow-xs transition-colors"
              >
                {downloadingPdf ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                Download PDF
              </button>
            </div>
          </div>

          {sessionCode && (
            <p className="-mt-3 text-xs text-slate-500">
              Manual run uses the saved simulator events and synchronized transcript. It does not alter the original session data.
            </p>
          )}

          {/* Real observed audio. Its transcript timestamps are shifted onto
              the simulator clock using the supplied recording start offset. */}
          {sessionCode && <details style={{background:'#0f172a',padding:20,borderRadius:12,color:'#e2e8f0'}}>
            <summary>Faculty assessment observations and PDF addendum (confidential)</summary>
            <PatientAssessment sessionCode={sessionCode} instructor />
          </details>}
          {sessionCode && (
            <details className="rounded-2xl border border-teal-200 bg-teal-50/60 p-5">
              <summary className="cursor-pointer text-sm font-bold text-teal-950">Add supplementary audio recording <span className="ml-2 text-xs font-normal text-teal-700">Optional fallback for a recording not captured live</span></summary>
              <div className="flex items-start gap-3">
                <div className="rounded-xl bg-teal-100 p-2.5 text-teal-700"><MessageSquare className="h-5 w-5" /></div>
                <div>
                  <h2 className="text-sm font-bold text-teal-950">Observed team audio + simulator synchronization</h2>
                  <p className="mt-1 max-w-3xl text-xs text-teal-800">
                    Upload the actual session recording after the simulation ends. If recording began with the simulation, keep the offset at 0.
                    Otherwise enter how many seconds after simulation start the recording began.
                  </p>
                </div>
              </div>
              <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-[minmax(220px,1fr)_150px_150px_160px_auto] lg:items-end">
                <label className="text-xs font-semibold text-slate-700">
                  Recording
                  <input
                    aria-label="Observed session audio file"
                    type="file"
                    accept="audio/wav,audio/mpeg,audio/mp4,audio/webm,audio/ogg,audio/flac,.wav,.mp3,.m4a,.mp4,.webm,.ogg,.flac"
                    onChange={(event) => { setRealAudio(event.target.files?.[0] || null); setRealAudioState("idle"); setRealAudioMessage(""); }}
                    className="mt-1 block w-full text-xs text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-white file:px-3 file:py-2 file:text-xs file:font-semibold file:text-teal-700 hover:file:bg-teal-100"
                  />
                </label>
                <label className="text-xs font-semibold text-slate-700">
                  Microphone
                  <select value={realAudioSource} onChange={(event) => setRealAudioSource(event.target.value)} className="mt-1 w-full rounded-lg border border-teal-200 bg-white px-3 py-2 text-xs">
                    <option value="ceiling">Room / ceiling</option>
                    <option value="lapel">Leader lapel</option>
                  </select>
                </label>
                <label className="text-xs font-semibold text-slate-700">
                  Language
                  <select value={realAudioLanguage} onChange={(event) => setRealAudioLanguage(event.target.value)} className="mt-1 w-full rounded-lg border border-teal-200 bg-white px-3 py-2 text-xs">
                    <option value="">Auto detect</option>
                    <option value="english">English</option>
                    <option value="tamil">Tamil</option>
                    <option value="tanglish">Tanglish</option>
                  </select>
                </label>
                <label className="text-xs font-semibold text-slate-700">
                  Start offset (seconds)
                  <input type="number" min="0" step="1" value={realAudioOffsetSeconds} onChange={(event) => setRealAudioOffsetSeconds(event.target.value)} className="mt-1 w-full rounded-lg border border-teal-200 bg-white px-3 py-2 text-xs" />
                </label>
                <button type="button" disabled={!realAudio || ["uploading", "queued", "running"].includes(realAudioState)} onClick={handleRealAudioUpload} className="inline-flex items-center justify-center gap-2 rounded-xl bg-teal-700 px-4 py-2 text-xs font-semibold text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-50">
                  {["uploading", "queued", "running"].includes(realAudioState) ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                  Process observed audio
                </button>
              </div>
              {realAudioMessage && <p className={`mt-3 text-xs font-medium ${realAudioState === "failed" ? "text-red-700" : "text-teal-800"}`}>{realAudioMessage}</p>}
            </details>
          )}

          {/* ── LOADING ANIMATED STATE ────────────────────────────────────── */}
          {!reportReady && loadingStatus !== "failed" && (
            <div className="bg-white rounded-2xl p-12 border border-slate-200 shadow-xs flex flex-col items-center justify-center text-center space-y-4">
              <div className="relative">
                <div className="w-16 h-16 rounded-full border-4 border-teal-100 border-t-teal-600 animate-spin flex items-center justify-center" />
                <Sparkles className="w-6 h-6 text-teal-600 absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-900">Preparing your debrief report</h3>
                <p className="text-sm text-slate-500 mt-1 max-w-md">
                  {audioSyncMessage || "Loading saved session evidence and preparing the debrief report…"}
                </p>
              </div>
              <div className="grid w-full max-w-lg grid-cols-3 gap-2 text-left text-[11px] text-slate-600">
                <div className="rounded-lg border border-teal-100 bg-teal-50 px-3 py-2"><b className="block text-teal-800">1. Capture</b>Audio safely saved</div>
                <div className="rounded-lg border border-teal-100 bg-teal-50 px-3 py-2"><b className="block text-teal-800">2. Process</b>Transcript &amp; speakers</div>
                <div className="rounded-lg border border-teal-100 bg-teal-50 px-3 py-2"><b className="block text-teal-800">3. Debrief</b>Report &amp; PDF</div>
              </div>
              <div className="flex items-center gap-2 text-xs text-teal-700 bg-teal-50 px-4 py-2 rounded-full border border-teal-200 font-medium">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Status: {loadingStatus.toUpperCase()} (Polling backend...)
              </div>
            </div>
          )}

          {/* ── ERROR STATE ──────────────────────────────────────────────── */}
          {loadingStatus === "failed" && (
            <div className="bg-red-50 rounded-2xl p-8 border border-red-200 text-center space-y-3">
              <AlertTriangle className="w-10 h-10 text-red-600 mx-auto" />
              <h3 className="text-base font-bold text-red-900">Debrief Generation Failed</h3>
              <p className="text-xs text-red-700 max-w-md mx-auto">{errorMsg}</p>
              <button
                onClick={async () => {
                  setLoadingStatus("running");
                  await triggerGeneration();
                  setTimeout(() => {
                    checkStatusAndPoll();
                  }, 500);
                }}
                className="mt-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-xl text-xs font-semibold inline-flex items-center gap-2 cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Retry Generation
              </button>
            </div>
          )}

          {/* ── COMPLETED DEBRIEF CONTENT ────────────────────────────────── */}
          {reportReady && (
            <>
              {audioSyncMessage && <div className="rounded-xl border border-amber-200 bg-amber-50 px-5 py-3 text-xs text-amber-900">{audioSyncMessage}</div>}
              {/* Not-Assessed Banner — shown whenever the engine withheld grading */}
              {scoreStatus === "not_assessed" && (
                <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-5 py-4">
                  <HelpCircle className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-sm font-semibold text-amber-900">Overall grade not assessed for this session</p>
                    <p className="text-xs text-amber-800 mt-0.5">
                      {audioOnlyReport
                        ? "This audio-only session has no simulator-event evidence, so clinical performance cannot be graded. "
                        : "Grading requires a cardiac-arrest session with confirmed simulator-event timestamps. "}
                      Transcript evidence is available below, but it is not treated as proof of clinical actions.
                      {classification && classification.algorithm !== "cardiac_arrest" && (
                        <> Detected scenario: <strong>{classification.algorithm.replace(/_/g, " ")}</strong>
                        {classification.sub_type ? ` (${classification.sub_type})` : ""}.</>
                      )}
                    </p>
                  </div>
                </div>
              )}

              {/* 1. Overview Score Cards */}
              <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs grid grid-cols-1 md:grid-cols-4 gap-6">
                <div className="space-y-1">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Scenario</span>
                  <div className="text-base font-bold text-slate-900">{scenarioName}</div>
                  <div className="text-xs text-slate-500">Session ID: {sessionCode}</div>
                </div>

                <div className="space-y-1">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Overall Score</span>
                  <div className={`text-3xl font-extrabold ${overallScore === null ? "text-slate-400" : "text-teal-700"}`}>
                    {overallScore === null ? "N/A" : Number(overallScore).toFixed(0)}
                    <span className="text-xs font-normal text-slate-400 ml-1">{overallScore === null ? "not graded" : "/ 100"}</span>
                  </div>
                  <div className="text-xs text-emerald-600 font-semibold flex items-center gap-1">
                    <ShieldCheck className="w-3.5 h-3.5" /> Grade {grade}
                    {scoreStatus && <span className="ml-1 text-slate-400 font-normal">· {scoreStatus.replace(/_/g, " ")}</span>}
                  </div>
                </div>

                <div className="space-y-1">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Verified findings</span>
                  <div className="text-3xl font-extrabold text-slate-900">{findings.length || "—"}</div>
                  <div className="text-xs text-slate-500 font-medium">Only evidence-supported results</div>
                </div>

                <div className="space-y-1">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Evidence captured</span>
                  <div className="text-3xl font-extrabold text-slate-900">{clinicalItems.length} / {conversationItems.length}</div>
                  <div className="text-xs text-slate-500">Clinical events / transcript segments</div>
                </div>
              </div>

              {/* Classification Evidence Card */}
              {classification && (
                <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-teal-700" />
                      Scenario Classification
                    </h3>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${
                        classification.status === "classified"
                          ? "bg-emerald-100 text-emerald-800"
                          : classification.status === "ambiguous"
                          ? "bg-amber-100 text-amber-800"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {classification.status.replace(/_/g, " ")}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-2 text-sm mb-2">
                    <span className="font-semibold text-slate-800">
                      {classification.algorithm.replace(/_/g, " ")}
                    </span>
                    {classification.sub_type && (
                      <span className="bg-teal-50 text-teal-800 border border-teal-200 text-xs font-bold px-2 py-0.5 rounded-full">
                        {classification.sub_type}
                      </span>
                    )}
                  </div>
                  {classification.evidence_event_ids?.length > 0 && (
                    <p className="text-xs text-slate-500">
                      Evidence: {classification.evidence_event_ids.length} classified event{classification.evidence_event_ids.length !== 1 ? "s" : ""}
                    </p>
                  )}
                  {classification.warnings?.length > 0 && (
                    <ul className="mt-2 list-disc pl-5 text-xs text-amber-900 space-y-1">
                      {classification.warnings.map((w, i) => <li key={i}>{w}</li>)}
                    </ul>
                  )}
                </div>
              )}
              {/* Engine warnings (all non-classification) */}
              {debrief.warnings?.length > 0 && (
                <details className="bg-amber-50 border border-amber-200 rounded-xl px-5 py-3 text-xs">
                  <summary className="cursor-pointer font-semibold text-amber-900 select-none">
                    {debrief.warnings.length} engine warning{debrief.warnings.length !== 1 ? "s" : ""}
                  </summary>
                  <ul className="mt-2 list-disc pl-4 space-y-1 text-amber-800">
                    {debrief.warnings.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                </details>
              )}
              {/* Show scored domains only when the engine has enough verified evidence. */}
              {domainScores.length > 0 && (
              <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                    <Award className="w-5 h-5 text-teal-700" />
                    ACLS Domain Performance
                  </h3>
                  <span className="text-xs text-slate-500">{debrief.rule_set || "Legacy rule bundle"}</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  {domainScores.map((ds, idx) => {
                    const label = (ds.domain_key || ds.domain_label || `Domain ${idx + 1}`)
                      .replace(/_/g, " ")
                      .replace(/\b\w/g, (c) => c.toUpperCase());
                    const scoreVal = ds.score ?? ds.final_score ?? 0;
                    const confidence = String(ds.completeness_flag || ds.confidence_flag || "unknown").toUpperCase();
                    const maximum = ds.max_points || 100;

                    return (
                      <div key={idx} className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-2">
                        <div className="flex justify-between items-start">
                          <span className="text-xs font-bold text-slate-700">{label}</span>
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                              confidence === "FULL" || confidence === "COMPLETE"
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-amber-100 text-amber-800"
                            }`}
                          >
                            {confidence}
                          </span>
                        </div>

                        <div className="text-2xl font-extrabold text-slate-900">
                          {Number(scoreVal).toFixed(1)} <span className="text-xs font-normal text-slate-400">/ {maximum}</span>
                        </div>

                        <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="bg-teal-700 h-1.5 rounded-full"
                            style={{ width: `${Math.min(100, Math.max(0, scoreVal / maximum * 100))}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
              )}

              {/* 3. Clinical findings or an honest explanation of missing evidence */}
              <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs space-y-4">
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-amber-600" />
                  Clinical assessment evidence
                </h3>

                {findings.length === 0 ? (
                  <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-900">
                    {clinicalItems.length === 0
                      ? "No verified simulator actions were recorded for this session. The system cannot determine whether protocol deviations occurred."
                      : "No protocol deviations were produced from the available verified simulator evidence."}
                  </div>
                ) : (
                  <div className="space-y-3">
                    {findings.map((f, i) => {
                      const sev = (f.severity || "INFO").toUpperCase();
                      const sevBg =
                        sev === "CRITICAL"
                          ? "bg-red-50 text-red-800 border-red-200"
                          : sev === "HIGH"
                          ? "bg-amber-50 text-amber-800 border-amber-200"
                          : "bg-blue-50 text-blue-800 border-blue-200";

                      const tsS = Math.floor((f.timestamp_ms || 0) / 1000);
                      const timeStr = `${Math.floor(tsS / 60)}:${(tsS % 60).toString().padStart(2, "0")}`;

                      return (
                        <div key={i} className={`p-4 rounded-xl border ${sevBg} space-y-2`}>
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-xs px-2.5 py-0.5 rounded-md bg-white border border-current">
                                {sev}
                              </span>
                              <span className="font-bold text-xs">{f.title || f.rule_id || "Finding"}</span>
                            </div>
                            <span className="font-mono text-xs font-semibold">@{timeStr}</span>
                          </div>

                          <p className="text-xs font-medium leading-relaxed">{f.description}</p>

                          {f.guideline_citation && (
                            <div className="text-[11px] opacity-80 flex items-center gap-1 font-mono">
                              <span>Ref:</span> {f.guideline_citation}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Evidence streams are intentionally separate: audio never masquerades as a simulator action. */}
              <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                <section className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs space-y-4">
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="text-base font-bold text-slate-900 flex items-center gap-2"><Activity className="w-5 h-5 text-teal-700" /> Verified clinical evidence</h3>
                    <span className="rounded-full bg-teal-50 px-2 py-1 text-[10px] font-bold text-teal-800">{clinicalItems.length} events</span>
                  </div>
                  {clinicalItems.length === 0 ? (
                    <p className="rounded-xl bg-slate-50 p-4 text-xs leading-relaxed text-slate-600">No simulator actions were captured as clinical evidence. Conversation is shown separately and is not used as proof of CPR, shock, medication, or ROSC.</p>
                  ) : (
                    <div className="max-h-80 space-y-2 overflow-y-auto pr-1 text-xs">
                      {clinicalItems.map((event, index) => {
                        const seconds = Math.floor((event.timestamp_ms || 0) / 1000);
                        return <div key={event.event_id || index} className="flex gap-3 rounded-xl border border-emerald-100 bg-emerald-50/40 p-3"><span className="font-mono font-bold text-emerald-800">{`${Math.floor(seconds / 60).toString().padStart(2, "0")}:${(seconds % 60).toString().padStart(2, "0")}`}</span><span className="font-medium text-slate-800">{evidenceText(event.evidence) || event.event_type}</span></div>;
                      })}
                    </div>
                  )}
                </section>

                <section className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs space-y-4">
                  <div className="flex items-center justify-between gap-3"><h3 className="text-base font-bold text-slate-900 flex items-center gap-2"><MessageSquare className="w-5 h-5 text-blue-700" /> Team communication evidence</h3><span className="rounded-full bg-blue-50 px-2 py-1 text-[10px] font-bold text-blue-800">{conversationItems.length} segments</span></div>
                  <p className="text-xs text-slate-600">Speaker and role labels are shown as evidence quality, not as confirmed identity unless a roster introduction was captured.</p>
                  {conversationItems.length === 0 ? <p className="rounded-xl bg-slate-50 p-4 text-xs text-slate-600">No transcript was captured for this session.</p> : (
                    <div className="max-h-80 space-y-2 overflow-y-auto pr-1 text-xs">
                      {conversationItems.map((item, index) => {
                        const seconds = Math.floor((item.timestamp_ms || 0) / 1000);
                        const lowConfidence = Number(item.confidence ?? 0) < 0.6;
                        return <div key={item.segment_id || index} className={`rounded-xl border p-3 ${lowConfidence ? "border-amber-200 bg-amber-50/60" : "border-blue-100 bg-blue-50/40"}`}>
                          <div className="mb-1 flex flex-wrap items-center gap-2 text-[10px]"><span className="font-mono font-bold text-slate-600">{`${Math.floor(seconds / 60).toString().padStart(2, "0")}:${(seconds % 60).toString().padStart(2, "0")}`}</span><span className="font-semibold text-slate-700">{roleLabel(item.actor_role)}</span><span className={`rounded-full px-2 py-0.5 font-bold ${lowConfidence ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"}`}>{lowConfidence ? "Review transcript" : "Higher confidence"}</span></div>
                          <p className="leading-relaxed text-slate-800">{item.text}</p>
                        </div>;
                      })}
                    </div>
                  )}
                  {lowConfidenceTranscript.length > 0 && <p className="text-[11px] text-amber-800">{lowConfidenceTranscript.length} segment{lowConfidenceTranscript.length !== 1 ? "s" : ""} need instructor review before being used in feedback.</p>}
                </section>
              </div>

              {audioOnlyReport && speechTopics.length > 0 && (
                <section className="rounded-2xl border border-amber-200 bg-amber-50/40 p-6 space-y-4">
                  <div>
                    <h3 className="text-base font-bold text-amber-950">Speech-based clinical discussion - unverified</h3>
                    <p className="mt-1 text-xs leading-relaxed text-amber-900">These topics come from automatically transcribed words, not patient vitals or confirmed actions. Check each quotation against the recording before using it in a debrief. No clinical score is inferred.</p>
                  </div>
                  <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                    {speechTopics.map((topic, index) => {
                      const seconds = Math.floor(Number(topic.timestamp_ms || 0) / 1000);
                      return <div key={`${topic.topic}-${index}`} className="rounded-xl border border-amber-200 bg-white p-4 space-y-2 text-xs">
                        <div className="flex gap-2 font-semibold text-amber-950"><span className="font-mono">{`${Math.floor(seconds / 60).toString().padStart(2, "0")}:${(seconds % 60).toString().padStart(2, "0")}`}</span><span>{topic.topic}</span></div>
                        <p className="text-slate-700">Transcript excerpt (unverified): “{topic.excerpt}”</p>
                        <p className="text-slate-800">{topic.question}</p>
                      </div>;
                    })}
                  </div>
                </section>
              )}

              {narrative.communication_analysis && (
                <section className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs space-y-3"><h3 className="text-base font-bold text-slate-900 flex items-center gap-2"><MessageSquare className="w-5 h-5 text-teal-700" /> Communication analysis</h3><p className="text-xs leading-relaxed text-slate-700">{narrative.communication_analysis}</p></section>
              )}
              {(narrative.strengths || narrative.recommendations) && (
                <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  {narrative.strengths && <div className="rounded-2xl border border-emerald-200 bg-emerald-50/40 p-6"><h3 className="text-sm font-bold text-emerald-950">Observed strengths</h3><p className="mt-2 text-xs leading-relaxed text-slate-700">{narrative.strengths}</p></div>}
                  {narrative.recommendations && <div className="rounded-2xl border border-teal-200 bg-teal-50/40 p-6"><h3 className="text-sm font-bold text-teal-950">Recommendations</h3><p className="mt-2 text-xs leading-relaxed text-slate-700">{narrative.recommendations}</p></div>}
                </section>
              )}

              {/* Reflection questions must not imply actions absent from evidence. */}
              <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-xs space-y-3">
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <HelpCircle className="w-5 h-5 text-teal-700" />
                  Reflective Debrief Prompts
                </h3>
                {reflectivePrompts.length === 0 && <p className="text-xs text-slate-500">{audioOnlyReport ? "Audio-only evidence: confirm the transcript against the recording before drawing conclusions about clinical actions." : "No evidence-grounded prompts were produced for this session."}</p>}
                <div className="space-y-2">
                  {reflectivePrompts.map((q, idx) => (
                    <div key={idx} className="p-3 rounded-xl bg-teal-50/50 border border-teal-100 flex items-start gap-2.5 text-xs text-slate-700">
                      <ChevronRight className="w-4 h-4 text-teal-600 shrink-0 mt-0.5" />
                      <span>{typeof q === "string" ? q : q.question || q.prompt || JSON.stringify(q)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
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
