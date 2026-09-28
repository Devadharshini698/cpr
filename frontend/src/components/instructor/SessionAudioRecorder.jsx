import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { Mic, Radio, AlertTriangle } from "lucide-react";

const API = (import.meta.env.VITE_BACKEND_URL || "http://localhost:8000").replace(/\/+$/, "");
const CHUNK_MS = 20_000;

/**
 * Non-blocking live session recorder. It never controls the simulator: recorder
 * failures are displayed locally and the manual debrief upload remains available.
 */
const SessionAudioRecorder = forwardRef(function SessionAudioRecorder({ sessionCode, participantLabel = "Record audio" }, ref) {
  const [state, setState] = useState("idle");
  const [message, setMessage] = useState("");
  const [chunkCount, setChunkCount] = useState(0);
  const [source, setSource] = useState("ceiling");
  const [languageMode, setLanguageMode] = useState("english");
  const [audioLevel, setAudioLevel] = useState(0);
  const [speechSeen, setSpeechSeen] = useState(false);
  const [audioDevices, setAudioDevices] = useState([]);
  const [deviceId, setDeviceId] = useState("");
  const [activeDeviceLabel, setActiveDeviceLabel] = useState("");
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const audioContextRef = useRef(null);
  const meterFrameRef = useRef(null);
  const sequenceRef = useRef(0);
  const pendingUploadsRef = useRef(new Set());
  const failedUploadsRef = useRef(0);
  const maxDurationTimerRef = useRef(null);
  const recorderIdRef = useRef(null);
  // Tracks a successful server-side start independently of React render timing.
  const captureStartedRef = useRef(false);

  const recorderId = () => {
    if (recorderIdRef.current) return recorderIdRef.current;
    const key = `live-audio-recorder:${sessionCode}`;
    const existing = sessionStorage.getItem(key);
    const generated = `participant-${globalThis.crypto?.randomUUID?.() || Math.random().toString(36).slice(2)}`;
    recorderIdRef.current = existing || generated;
    if (!existing) sessionStorage.setItem(key, generated);
    return recorderIdRef.current;
  };

  const refreshAudioDevices = async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    const devices = (await navigator.mediaDevices.enumerateDevices()).filter((item) => item.kind === "audioinput");
    setAudioDevices(devices);
  };

  useEffect(() => {
    refreshAudioDevices().catch(() => {});
    const mediaDevices = navigator.mediaDevices;
    mediaDevices?.addEventListener?.("devicechange", refreshAudioDevices);
    return () => mediaDevices?.removeEventListener?.("devicechange", refreshAudioDevices);
  }, []);

  const stopAudioMeter = () => {
    if (meterFrameRef.current) cancelAnimationFrame(meterFrameRef.current);
    meterFrameRef.current = null;
    audioContextRef.current?.close?.().catch(() => {});
    audioContextRef.current = null;
    setAudioLevel(0);
  };

  const startAudioMeter = (stream) => {
    stopAudioMeter();
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const context = new AudioContext();
    const analyser = context.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.75;
    context.createMediaStreamSource(stream).connect(analyser);
    const samples = new Float32Array(analyser.fftSize);
    let lastPaint = 0;
    const sample = (now) => {
      analyser.getFloatTimeDomainData(samples);
      let energy = 0;
      for (const value of samples) energy += value * value;
      const rms = Math.sqrt(energy / samples.length);
      if (now - lastPaint > 100) {
        const level = Math.min(100, Math.round(rms * 700));
        setAudioLevel(level);
        if (rms > 0.018) setSpeechSeen(true);
        lastPaint = now;
      }
      meterFrameRef.current = requestAnimationFrame(sample);
    };
    audioContextRef.current = context;
    meterFrameRef.current = requestAnimationFrame(sample);
  };

  useEffect(() => () => {
    if (maxDurationTimerRef.current) window.clearTimeout(maxDurationTimerRef.current);
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    if (meterFrameRef.current) cancelAnimationFrame(meterFrameRef.current);
    audioContextRef.current?.close?.().catch(() => {});
  }, []);

  const authHeaders = () => {
    const token = sessionStorage.getItem("token") || localStorage.getItem("token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  // A browser can capture audio even when the API, database, or Docker-backed
  // backend is down. Verify the service before requesting microphone access so
  // that "Recording" always means chunks can actually be persisted.
  const ensureAudioServiceAvailable = async () => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 5_000);
    try {
      const response = await fetch(`${API}/docs`, { method: "GET", signal: controller.signal });
      if (!response.ok) throw new Error(`Audio service returned ${response.status}`);
    } catch {
      throw new Error("Live audio service is offline. Start Docker/MySQL and the backend, then try recording again.");
    } finally {
      window.clearTimeout(timeout);
    }
  };

  const uploadChunk = async (blob, sequence) => {
    if (!blob?.size) return;
    const form = new FormData();
    form.append("sequence", String(sequence));
    form.append("recorder_id", recorderId());
    form.append("audio", blob, `chunk-${String(sequence).padStart(5, "0")}.webm`);
    const upload = fetch(`${API}/api/session/${encodeURIComponent(sessionCode)}/live-audio/chunk`, {
      method: "POST", headers: authHeaders(), body: form,
    }).then(async (res) => {
      if (!res.ok) throw new Error((await res.json()).detail || "Chunk upload failed");
      setChunkCount((count) => Math.max(count, sequence + 1));
    }).catch((error) => {
      failedUploadsRef.current += 1;
      setMessage(`Recording continues, but chunk ${sequence + 1} could not be saved. Use the manual audio upload after this session if needed.`);
      console.warn("[SessionAudioRecorder] chunk upload failed", error);
    }).finally(() => pendingUploadsRef.current.delete(upload));
    pendingUploadsRef.current.add(upload);
  };

  const start = async () => {
    if (!sessionCode || state === "recording" || state === "starting") return;
    setState("starting"); setMessage(""); setChunkCount(0); setSpeechSeen(false); setAudioLevel(0); sequenceRef.current = 0; failedUploadsRef.current = 0;
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error("This browser does not support microphone recording.");
      await ensureAudioServiceAvailable();
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          ...(deviceId ? { deviceId: { exact: deviceId } } : {}),
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
        },
      });
      const track = stream.getAudioTracks()[0];
      if (!track || track.readyState !== "live") throw new Error("The selected microphone did not become active.");
      setActiveDeviceLabel(track.label || "Default microphone");
      await refreshAudioDevices().catch(() => {});
      startAudioMeter(stream);
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "audio/webm";
      const startResponse = await fetch(`${API}/api/session/${encodeURIComponent(sessionCode)}/live-audio/start`, {
        method: "POST", headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ source, language_mode: languageMode || null, mime_type: mimeType, recorder_id: recorderId() }),
      });
      if (!startResponse.ok) throw new Error((await startResponse.json()).detail || "Could not start the recoverable audio session.");
      captureStartedRef.current = true;
      const recorder = new MediaRecorder(stream, { mimeType });
      recorder.ondataavailable = (event) => {
        const sequence = sequenceRef.current++;
        uploadChunk(event.data, sequence);
      };
      recorder.onerror = () => setMessage("Microphone recorder encountered an error. The vital-sign simulation is still running; use manual audio upload after the session.");
      recorder.onstop = () => stream.getTracks().forEach((track) => track.stop());
      streamRef.current = stream;
      recorderRef.current = recorder;
      recorder.start(CHUNK_MS);
      maxDurationTimerRef.current = window.setTimeout(async () => {
        await stopAndFlush();
        setMessage("The 20-minute recording cap was reached. Simulation controls continue normally; end the session when ready to queue the saved recording.");
      }, 20 * 60 * 1000);
      setState("recording");
      setMessage("Recording safely in 20-second recoverable chunks.");
    } catch (error) {
      stopAudioMeter();
      streamRef.current?.getTracks().forEach((track) => track.stop());
      setState("failed");
      setMessage(error.message || "Microphone unavailable. You can upload the recorded audio later from the debrief page.");
    }
  };

  const stopAndFlush = async () => {
    if (maxDurationTimerRef.current) {
      window.clearTimeout(maxDurationTimerRef.current);
      maxDurationTimerRef.current = null;
    }
    if (recorderRef.current?.state === "recording") {
      setState("stopping");
      await new Promise((resolve) => {
        recorderRef.current.addEventListener("stop", resolve, { once: true });
        recorderRef.current.stop();
      });
    }
    await Promise.allSettled([...pendingUploadsRef.current]);
    let serverStatusSaved = true;
    if (captureStartedRef.current) {
      try {
        const response = await fetch(`${API}/api/session/${encodeURIComponent(sessionCode)}/live-audio/stop`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({ recorder_id: recorderId() }),
        });
        if (!response.ok) {
          const detail = await response.json().catch(() => ({}));
          throw new Error(detail.detail || "Could not save recording stop status");
        }
        captureStartedRef.current = false;
      } catch (error) {
        // Do not discard successfully uploaded chunks if the status request is
        // temporarily unavailable; session-end finalization remains a fallback.
        serverStatusSaved = false;
        console.warn("[SessionAudioRecorder] stop status update failed", error);
      }
    }
    stopAudioMeter();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    const canFinalize = sequenceRef.current > 0 && failedUploadsRef.current === 0;
    setState(canFinalize ? "stopped" : "failed");
    if (!canFinalize && sequenceRef.current > 0) setMessage("Some recorder chunks were not saved. Use the separate manual upload as the audio-debrief fallback.");
    else if (!serverStatusSaved) setMessage("Audio chunks were saved, but the server could not yet confirm recording stopped. Ending the session will finalize them.");
    return canFinalize;
  };

  const finalizeAfterSessionEnd = async () => {
    if (sequenceRef.current === 0 || failedUploadsRef.current > 0) return { skipped: true };
    setState("finalizing");
    try {
      const res = await fetch(`${API}/api/session/${encodeURIComponent(sessionCode)}/live-audio/finalize?recorder_id=${encodeURIComponent(recorderId())}`, {
        method: "POST", headers: authHeaders(),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not finalize recording");
      setState("queued");
      setMessage("Recording saved. Transcription and synchronized debrief are queued.");
      return data;
    } catch (error) {
      setState("failed");
      setMessage(`${error.message || "Could not finalize recording"}. Use the separate manual upload as fallback.`);
      return { error };
    }
  };

  useImperativeHandle(ref, () => ({ stopAndFlush, finalizeAfterSessionEnd, isRecording: () => state === "recording" }));

  const active = ["starting", "recording", "stopping", "finalizing"].includes(state);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "5px 8px", borderRadius: 8, border: `1px solid ${state === "recording" ? "#EF4444" : "#475569"}`, background: state === "recording" ? "#EF44441A" : "#0F172A" }}>
      <button type="button" onClick={state === "recording" ? stopAndFlush : start} disabled={active && state !== "recording"} title="Record room audio in recoverable 20-second chunks" style={{ border: "none", background: "transparent", color: state === "recording" ? "#F87171" : "#CBD5E1", cursor: active && state !== "recording" ? "default" : "pointer", display: "flex", alignItems: "center", gap: 5, fontSize: 11, fontWeight: 700 }}>
        {state === "recording" ? <><Radio size={14} /> Stop audio</> : <><Mic size={14} /> {participantLabel}</>}
      </button>
      <select aria-label="Live recording microphone" value={source} disabled={active} onChange={(event) => setSource(event.target.value)} style={{ background: "#1E293B", border: "1px solid #475569", color: "#CBD5E1", borderRadius: 5, fontSize: 10, padding: "3px" }}>
        <option value="ceiling">Room mic</option><option value="lapel">Leader lapel</option>
      </select>
      <select aria-label="Spoken language" value={languageMode} disabled={active} onChange={(event) => setLanguageMode(event.target.value)} title="Choose the language being spoken for better transcription" style={{ background: "#1E293B", border: "1px solid #475569", color: "#CBD5E1", borderRadius: 5, fontSize: 10, padding: "3px" }}>
        <option value="english">English</option><option value="tamil">Tamil</option><option value="tanglish">Tanglish</option><option value="">Auto</option>
      </select>
      {audioDevices.length > 1 && state !== "recording" && (
        <select aria-label="Microphone device" value={deviceId} disabled={active} onChange={(event) => setDeviceId(event.target.value)} title="Physical microphone used by the browser" style={{ maxWidth: 150, background: "#1E293B", border: "1px solid #475569", color: "#CBD5E1", borderRadius: 5, fontSize: 10, padding: "3px" }}>
          <option value="">System default</option>
          {audioDevices.map((device, index) => <option key={device.deviceId || index} value={device.deviceId}>{device.label || `Microphone ${index + 1}`}</option>)}
        </select>
      )}
      {state === "recording" && <div title={`Active input: ${activeDeviceLabel}`} style={{ display: "flex", alignItems: "center", gap: 5 }}>
        <div aria-label={`Microphone input level ${audioLevel}%`} style={{ width: 54, height: 7, background: "#334155", borderRadius: 8, overflow: "hidden" }}>
          <div style={{ width: `${audioLevel}%`, height: "100%", background: speechSeen ? "#22C55E" : "#F59E0B", transition: "width 100ms linear" }} />
        </div>
        <span style={{ color: speechSeen ? "#86EFAC" : "#FCD34D", fontSize: 10 }}>{speechSeen ? "Speech detected" : "Speak to test mic"} · {chunkCount} saved</span>
      </div>}
      {message && (state !== "recording" || failedUploadsRef.current > 0) && <span title={message} style={{ color: state === "failed" || failedUploadsRef.current > 0 ? "#FCA5A5" : "#94A3B8", fontSize: 10, maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}><AlertTriangle size={11} style={{ verticalAlign: "-2px", marginRight: 3 }} />{message}</span>}
    </div>
  );
});

export default SessionAudioRecorder;
