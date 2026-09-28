import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, AlertTriangle, Download, FileJson, Loader2, MessageSquare, ShieldAlert } from "lucide-react";

const API = (import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

const clock = (milliseconds) => {
  const seconds = Math.floor(Number(milliseconds || 0) / 1000);
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
};

const evidenceText = (evidence) => {
  if (Array.isArray(evidence)) return evidence.map((item) => item?.text || item?.ref || "").filter(Boolean).join(" · ");
  return typeof evidence === "string" ? evidence : "No fixture evidence text.";
};

export default function SyntheticDebriefPage() {
  const navigate = useNavigate();
  const [fixture, setFixture] = useState(null);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const token = sessionStorage.getItem("token") || localStorage.getItem("token") || "";
  const headers = token ? { Authorization: `Bearer ${token}` } : {};

  useEffect(() => {
    fetch(`${API}/api/demo/synthetic-vf`, { headers, cache: "no-store" })
      .then(async (res) => {
        const body = await res.json();
        if (!res.ok) throw new Error(body.detail || "Could not load synthetic test fixture.");
        setFixture(body);
      })
      .catch((err) => setError(err.message));
  }, []); // fixture is immutable until intentionally regenerated

  const downloadPdf = async () => {
    setDownloading(true);
    try {
      const response = await fetch(`${API}/api/demo/synthetic-vf/pdf`, { headers, cache: "no-store" });
      if (!response.ok) throw new Error("Synthetic PDF is unavailable.");
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = "SYNTH_VF_TEST_01_debrief.pdf";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    } finally {
      setDownloading(false);
    }
  };

  if (error) return <main className="min-h-screen bg-slate-100 p-10"><button onClick={() => navigate("/reports")} className="text-sm text-teal-800">← Reports</button><div className="mt-6 rounded-2xl border border-red-200 bg-white p-6 text-red-700">{error}</div></main>;
  if (!fixture) return <main className="min-h-screen bg-slate-100 grid place-items-center text-slate-600"><Loader2 className="h-8 w-8 animate-spin text-teal-700" /></main>;

  const report = fixture.report;
  const timeline = report.timeline || {};
  const segments = timeline.transcript_segments || [];
  const events = timeline.events || [];
  const findings = report.findings || [];
  const domains = report.domain_scores || [];

  return <main className="min-h-screen bg-slate-100 p-5 md:p-10">
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div><button onClick={() => navigate("/reports")} className="mb-3 text-sm font-semibold text-teal-800">← Back to reports</button><h1 className="text-3xl font-bold text-slate-900">Synthetic CPR debrief test</h1><p className="mt-2 text-sm text-slate-600">JSON input path: transcript and clinical-event annotations are generated internally; microphone and diarization are bypassed.</p></div>
        <button onClick={downloadPdf} disabled={!fixture.pdf_available || downloading} className="inline-flex items-center gap-2 rounded-xl bg-teal-700 px-4 py-3 text-sm font-bold text-white disabled:opacity-50"><Download className="h-4 w-4" />{downloading ? "Downloading…" : "Download test PDF"}</button>
      </div>

      <section className="rounded-2xl border border-amber-300 bg-amber-50 p-5 text-amber-950"><div className="flex gap-3"><ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" /><div><b>Synthetic fixture - not learner evidence.</b><p className="mt-1 text-sm">This view demonstrates the report workflow only. Its transcript, roles, events, timing, score, and findings are test data rather than a recording or patient-monitor output.</p></div></div></section>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {[['Session', report.session_id], ['Classification', `${report.classification?.algorithm || '—'} / ${report.classification?.sub_type || '—'}`], ['Score', `${report.overall_score ?? 'N/A'} / 100`], ['Grade', report.grade || 'N/A'], ['Evidence', `${events.length} events · ${segments.length} speech lines`]].map(([label, value]) => <div key={label} className="rounded-xl border border-slate-200 bg-white p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p><p className="mt-2 break-words font-bold text-slate-900">{value}</p></div>)}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6"><h2 className="flex items-center gap-2 text-lg font-bold text-slate-900"><Activity className="h-5 w-5 text-teal-700" />Synthetic clinical timeline</h2><p className="mt-1 text-sm text-slate-500">These events are fixture annotations linked to the test transcript.</p><div className="mt-4 max-h-96 space-y-2 overflow-y-auto pr-1">{events.map((event) => <div key={event.event_id} className="flex gap-4 rounded-lg border border-teal-100 bg-teal-50/40 p-3 text-sm"><b className="font-mono text-teal-800">{clock(event.timestamp_ms)}</b><div><b>{String(event.event_type).replaceAll('_', ' ')}</b><p className="mt-1 text-slate-700">{evidenceText(event.evidence)}</p></div></div>)}</div></section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-white p-6"><h2 className="flex items-center gap-2 text-lg font-bold text-slate-900"><AlertTriangle className="h-5 w-5 text-amber-600" />Rule findings</h2><div className="mt-4 space-y-3">{findings.map((finding) => <div key={finding.finding_id} className="rounded-lg border border-slate-200 p-3"><span className="text-xs font-bold text-amber-700">{finding.severity}</span><p className="font-semibold text-slate-900">{finding.title}</p><p className="text-sm text-slate-600">{finding.description}</p></div>)}</div></section>
        <section className="rounded-2xl border border-slate-200 bg-white p-6"><h2 className="text-lg font-bold text-slate-900">Domain scores</h2><div className="mt-4 space-y-3">{domains.map((domain) => <div key={domain.domain_key} className="flex items-center justify-between rounded-lg bg-slate-50 p-3"><div><p className="font-semibold text-slate-900">{domain.domain_label || domain.domain_key}</p><p className="text-xs text-slate-500">{domain.completeness_flag}</p></div><b>{Math.round(domain.score ?? domain.final_score ?? 0)}/100</b></div>)}</div></section>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-6"><h2 className="flex items-center gap-2 text-lg font-bold text-slate-900"><MessageSquare className="h-5 w-5 text-blue-700" />Synthetic team transcript</h2><p className="mt-1 text-sm text-slate-500">Direct JSON transcript input; no speech-to-text or speaker diarization was used.</p><div className="mt-4 max-h-[38rem] space-y-2 overflow-y-auto pr-1">{segments.map((segment) => <div key={segment.segment_id} className="rounded-lg border border-blue-100 bg-blue-50/40 p-3"><div className="flex flex-wrap gap-x-3 text-xs"><b className="font-mono text-slate-600">{clock(segment.timestamp_ms)}</b><b className="text-blue-900">{String(segment.actor_role).replaceAll('_', ' ')}</b></div><p className="mt-1 text-sm text-slate-800">{segment.text}</p></div>)}</div></section>
      <div className="flex items-center gap-2 text-xs text-slate-500"><FileJson className="h-4 w-4" />Fixture source: generated JSON transcript and event annotations.</div>
    </div>
  </main>;
}
