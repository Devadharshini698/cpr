import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import SessionAudioRecorder from "../components/instructor/SessionAudioRecorder";

const API = (import.meta.env.VITE_BACKEND_URL || "http://localhost:8000").replace(/\/+$/, "");

export default function AudioOnlySessionPage() {
  const navigate = useNavigate();
  const recorder = useRef(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState("");
  const [ended, setEnded] = useState(false);
  const token = sessionStorage.getItem("token") || localStorage.getItem("token");
  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    fetch(`${API}/api/sessions/list`, { headers })
      .then((response) => response.ok ? response.json() : null)
      .then((data) => {
        const active = data?.sessions?.find((item) => item.status === "Active" && item.mode === "audio_only");
        if (active) setCode(active.session_code);
      })
      .catch(() => {});
  }, []);

  const begin = async () => {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API}/session/create-audio-only`, { method: "POST", headers });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not create audio-only session");
      setCode(data.session_code);
      sessionStorage.setItem("session_code", data.session_code);
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
    }
  };

  const finish = async () => {
    setBusy(true);
    setError("");
    try {
      const flushed = await recorder.current?.stopAndFlush();
      if (!flushed) throw new Error("No recording was saved. Check the microphone and saved chunk count before ending.");
      setProgress("Audio saved. Ending session…");
      const response = await fetch(`${API}/session/${encodeURIComponent(code)}/end`, { method: "POST", headers });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not end session");
      setEnded(true);
      const finalized = await recorder.current?.finalizeAfterSessionEnd();
      if (finalized?.error) throw finalized.error;
      setProgress("Transcribing speech and identifying speakers. This can take several minutes…");
      let completed = false;
      for (let attempt = 0; attempt < 480; attempt += 1) {
        const statusResponse = await fetch(`${API}/api/session/${encodeURIComponent(code)}/live-audio/status`, { headers });
        if (!statusResponse.ok) throw new Error("Could not check transcription status");
        const status = await statusResponse.json();
        const jobs = status.recorders || [];
        const failed = jobs.find((item) => item.job_status === "failed");
        if (failed) throw new Error(failed.job_error || "Audio transcription failed");
        if (jobs.length && jobs.every((item) => item.job_status === "completed")) {
          completed = true;
          break;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 2500));
      }
      if (!completed) throw new Error("Transcription is still processing. You can open the debrief later from Sessions.");
      navigate(`/debrief/${code}`);
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
    }
  };

  return <main className="min-h-screen bg-slate-100 px-6 py-12 text-slate-900">
    <div className="mx-auto max-w-2xl rounded-2xl bg-white p-8 shadow-sm">
      <h1 className="text-2xl font-bold">Audio-only team debrief</h1>
      <p className="mt-3 text-sm text-slate-600">Record team conversation without launching a patient simulation. The report will include the transcript and evidence review, but no vitals-based clinical score.</p>
      {!code ? <button onClick={begin} disabled={busy} className="mt-6 rounded-lg bg-teal-700 px-5 py-3 font-semibold text-white disabled:opacity-50">Create recording session</button> : <>
        <p className="mt-6 font-mono text-sm">Session code: {code}</p>
        <div className="mt-4"><SessionAudioRecorder ref={recorder} sessionCode={code} participantLabel="Start microphone" /></div>
        <p className="mt-3 text-xs text-slate-600">Check the input meter and saved chunks while speaking. Recording is uploaded in recoverable chunks. Wait for the final report to finish transcribing after you end.</p>
        {!ended && <button onClick={finish} disabled={busy} className="mt-6 rounded-lg bg-slate-900 px-5 py-3 font-semibold text-white disabled:opacity-50">End recording and generate report</button>}
        {ended && <button onClick={() => navigate(`/debrief/${code}`)} className="mt-6 rounded-lg border border-slate-300 px-5 py-3 font-semibold">Open debrief status</button>}
      </>}
      {progress && <p role="status" className="mt-4 text-sm text-teal-800">{progress}</p>}
      {error && <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    </div>
  </main>;
}
