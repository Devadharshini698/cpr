import { useEffect, useRef, useState } from "react";
import { Mic, Loader2, Play, Pause, Save, Trash2 } from "lucide-react";

const API = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

const SpeechRecognitionCtor =
  typeof window !== "undefined"
    ? window.SpeechRecognition || window.webkitSpeechRecognition
    : null;

/**
 * Press-and-hold mic recorder + editable text area, used for both per-checklist-item
 * notes and the overall session review. Records real audio via MediaRecorder and,
 * where the browser supports it, live-transcribes speech via the Web Speech API so
 * the instructor gets an editable transcript instead of only a voice memo.
 */
export default function VoiceNoteRecorder({
  initialText = "",
  initialAudioUrl = null,
  onSave,
  placeholder = "Type a comment, or hold the mic and speak…",
  compact = false,
}) {
  const [text, setText] = useState(initialText);
  const [recording, setRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState(null);
  const [audioUrl, setAudioUrl] = useState(initialAudioUrl);
  const [playing, setPlaying] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [micError, setMicError] = useState("");

  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);
  const recognitionRef = useRef(null);
  const finalTranscriptRef = useRef("");
  const audioElRef = useRef(null);

  useEffect(() => {
    setText(initialText || "");
  }, [initialText]);

  useEffect(() => {
    setAudioUrl(initialAudioUrl || null);
  }, [initialAudioUrl]);

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
      mediaRecorderRef.current?.state === "recording" && mediaRecorderRef.current.stop();
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const startRecording = async () => {
    if (recording) return;
    setMicError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];

      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setAudioBlob(blob);
        setAudioUrl(URL.createObjectURL(blob));
        setDirty(true);
        streamRef.current?.getTracks().forEach((t) => t.stop());
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setRecording(true);

      if (SpeechRecognitionCtor) {
        finalTranscriptRef.current = text ? text + " " : "";
        const recognition = new SpeechRecognitionCtor();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = "en-US";
        recognition.onresult = (event) => {
          let interim = "";
          for (let i = event.resultIndex; i < event.results.length; i++) {
            const chunk = event.results[i][0].transcript;
            if (event.results[i].isFinal) finalTranscriptRef.current += chunk + " ";
            else interim += chunk;
          }
          setText((finalTranscriptRef.current + interim).trim());
          setDirty(true);
        };
        recognition.onerror = (e) => console.warn("[VoiceNoteRecorder] speech recognition error:", e.error);
        recognition.start();
        recognitionRef.current = recognition;
      }
    } catch (err) {
      console.error("[VoiceNoteRecorder] Microphone access failed:", err);
      setMicError("Microphone access denied or unavailable.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current?.state === "recording") mediaRecorderRef.current.stop();
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    setRecording(false);
  };

  const togglePlayback = () => {
    if (!audioElRef.current) return;
    if (playing) {
      audioElRef.current.pause();
    } else {
      audioElRef.current.play();
    }
  };

  const handleDiscardAudio = () => {
    setAudioBlob(null);
    setAudioUrl(null);
    setDirty(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave({ text, audioBlob });
      setDirty(false);
      setAudioBlob(null);
    } catch (err) {
      console.error("[VoiceNoteRecorder] Save failed:", err);
    } finally {
      setSaving(false);
    }
  };

  const resolvedAudioUrl = audioUrl
    ? audioUrl.startsWith("blob:") || audioUrl.startsWith("http")
      ? audioUrl
      : `${API}${audioUrl}`
    : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <textarea
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setDirty(true);
        }}
        placeholder={placeholder}
        rows={compact ? 2 : 3}
        style={{
          width: "100%",
          resize: "vertical",
          backgroundColor: "#0F172A",
          border: "1px solid #334155",
          borderRadius: 6,
          padding: "8px 10px",
          fontSize: compact ? 11 : 12,
          color: "#F8FAFC",
          fontFamily: "inherit",
        }}
      />

      {resolvedAudioUrl && (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <audio
            ref={audioElRef}
            src={resolvedAudioUrl}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onEnded={() => setPlaying(false)}
          />
          <button
            type="button"
            onClick={togglePlayback}
            style={{ display: "flex", alignItems: "center", gap: 4, background: "#0F172A", border: "1px solid #334155", color: "#10B981", borderRadius: 6, padding: "4px 8px", fontSize: 10, cursor: "pointer" }}
          >
            {playing ? <Pause size={12} /> : <Play size={12} />}
            {playing ? "Pause" : "Play voice note"}
          </button>
          <button
            type="button"
            onClick={handleDiscardAudio}
            style={{ display: "flex", alignItems: "center", gap: 4, background: "transparent", border: "none", color: "#94A3B8", fontSize: 10, cursor: "pointer" }}
          >
            <Trash2 size={12} /> Remove
          </button>
        </div>
      )}

      {micError && <div style={{ fontSize: 10, color: "#EF4444" }}>{micError}</div>}

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <button
          type="button"
          onMouseDown={startRecording}
          onMouseUp={stopRecording}
          onMouseLeave={() => recording && stopRecording()}
          onTouchStart={(e) => { e.preventDefault(); startRecording(); }}
          onTouchEnd={(e) => { e.preventDefault(); stopRecording(); }}
          title="Hold to record a voice note"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "6px 12px",
            borderRadius: 20,
            border: recording ? "1px solid #EF4444" : "1px solid #334155",
            backgroundColor: recording ? "#EF444422" : "#0F172A",
            color: recording ? "#EF4444" : "#CBD5E1",
            fontSize: 11,
            fontWeight: 700,
            cursor: "pointer",
            userSelect: "none",
          }}
        >
          {recording ? (
            <>
              <span style={{ width: 8, height: 8, borderRadius: "50%", backgroundColor: "#EF4444", animation: "pulse 1s infinite" }} />
              Recording… release to stop
            </>
          ) : (
            <>
              <Mic size={13} /> Hold to speak
            </>
          )}
        </button>

        <button
          type="button"
          onClick={handleSave}
          disabled={!dirty || saving || recording}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "6px 12px",
            borderRadius: 6,
            border: "none",
            backgroundColor: !dirty || saving || recording ? "#334155" : "#10B981",
            color: "#FFF",
            fontSize: 11,
            fontWeight: 700,
            cursor: !dirty || saving || recording ? "default" : "pointer",
          }}
        >
          {saving ? <Loader2 size={13} className="spin" /> : <Save size={13} />}
          {saving ? "Saving…" : "Save"}
        </button>
      </div>
      {!SpeechRecognitionCtor && (
        <div style={{ fontSize: 9, color: "#64748B" }}>
          Live transcription isn't supported in this browser — voice notes still record fine, just type the summary manually.
        </div>
      )}
    </div>
  );
}
