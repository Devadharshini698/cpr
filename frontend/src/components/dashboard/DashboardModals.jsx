import React, { useEffect, useState } from "react";
import { X, BookOpen, FileText, ClipboardList } from "lucide-react";

const API = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

export default function DashboardModals({
  activeModal,
  onClose,
  handleStartSimulation,
  initialSessions = [],
  onOpenSession,
}) {
  const [catalog, setCatalog] = useState([]);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [latestReport, setLatestReport] = useState(null);
  const [reportLoading, setReportLoading] = useState(false);

  useEffect(() => {
    if (activeModal !== "library" || catalog.length > 0) return;
    setCatalogLoading(true);
    const token = sessionStorage.getItem("token");
    fetch(`${API}/api/scenarios/catalog`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => setCatalog(data?.scenarios || []))
      .catch(console.error)
      .finally(() => setCatalogLoading(false));
  }, [activeModal, catalog.length]);

  useEffect(() => {
    if (activeModal !== "reports") return;
    setReportLoading(true);
    const token = sessionStorage.getItem("token");
    fetch(`${API}/api/debrief/list?limit=1`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => setLatestReport(data?.reports?.[0] || null))
      .catch(console.error)
      .finally(() => setReportLoading(false));
  }, [activeModal]);

  if (!activeModal) return null;

  return (
    <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center z-50 p-5">
      {/* SCENARIO LIBRARY MODAL */}
      {activeModal === "library" && (
        <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-y-auto shadow-2xl p-6 flex flex-col gap-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <BookOpen className="w-5 h-5 text-teal-700" />
                Clinical Scenario Library
              </h3>
              <p className="text-xs text-slate-500 mt-1">
                Real patient scenarios seeded in the database
              </p>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center text-slate-500 cursor-pointer transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex flex-col gap-3">
            {catalogLoading && (
              <div className="text-xs text-slate-500 text-center py-6">Loading scenarios…</div>
            )}
            {!catalogLoading && catalog.length === 0 && (
              <div className="text-xs text-slate-500 text-center py-6">No scenarios found.</div>
            )}
            {catalog.map((item) => (
              <div
                key={item.id}
                className="p-4 rounded-xl border border-slate-200 bg-slate-50 flex items-center justify-between"
              >
                <div>
                  <div className="font-bold text-sm text-slate-900">{item.name}</div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    {item.diagnosis} • {item.triage_level} • Est. {item.duration}
                  </div>
                </div>
                <button
                  onClick={handleStartSimulation}
                  className="bg-teal-700 hover:bg-teal-800 text-white rounded-lg px-4 py-2 text-xs font-semibold cursor-pointer transition-colors"
                >
                  Select & Start →
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* DEBRIEF REPORTS MODAL */}
      {activeModal === "reports" && (
        <div className="bg-white rounded-2xl w-full max-w-xl shadow-2xl p-6 flex flex-col gap-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <FileText className="w-5 h-5 text-teal-700" />
                Automated Debrief Reports
              </h3>
              <p className="text-xs text-slate-500 mt-1">
                AI-generated clinical performance analytics & transcripts
              </p>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center text-slate-500 cursor-pointer transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {reportLoading && (
            <div className="text-xs text-slate-500 text-center py-4">Loading latest report…</div>
          )}

          {!reportLoading && !latestReport && (
            <div className="text-xs text-slate-500 text-center py-4">
              No completed debrief reports yet. Run and end a simulation session to generate one.
            </div>
          )}

          {!reportLoading && latestReport && (
            <div className="bg-teal-50 border border-teal-200 p-4 rounded-xl text-xs text-teal-800">
              <strong className="font-bold">Latest Completed Debrief Summary:</strong>
              <div className="mt-2 text-slate-700 leading-relaxed">
                Session: {latestReport.session_code}
                {latestReport.updated_at && (
                  <> ({new Date(latestReport.updated_at).toLocaleDateString()})</>
                )}
                <br />
                Grade: <strong className="text-emerald-700">{latestReport.grade || "—"}</strong>
                <br />
                Overall Score:{" "}
                <strong className="text-teal-800 font-bold">
                  {latestReport.overall_score != null ? `${Math.round(latestReport.overall_score)} / 100` : "—"}
                </strong>
              </div>
            </div>
          )}

          <button
            onClick={onClose}
            className="w-full bg-teal-700 hover:bg-teal-800 text-white rounded-xl py-2.5 text-xs font-semibold cursor-pointer transition-colors"
          >
            Close Reports Preview
          </button>
        </div>
      )}

      {/* SESSIONS LIST MODAL */}
      {activeModal === "sessions" && (
        <div className="bg-white rounded-2xl w-full max-w-2xl shadow-2xl p-6 flex flex-col gap-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <ClipboardList className="w-5 h-5 text-teal-700" />
                All Simulation Sessions
              </h3>
              <p className="text-xs text-slate-500 mt-1">
                Complete history of active and completed simulation runs
              </p>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center text-slate-500 cursor-pointer transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex flex-col gap-2.5 max-h-96 overflow-y-auto pr-1">
            {initialSessions.length === 0 && (
              <div className="text-xs text-slate-500 text-center py-6">No sessions yet.</div>
            )}
            {initialSessions.map((session) => (
              <div
                key={session.id}
                className="p-3.5 rounded-xl border border-slate-200 bg-slate-50 flex items-center justify-between"
              >
                <div>
                  <div className="font-bold text-sm text-slate-900">{session.name}</div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    {session.date} • {session.duration} • Patient: {session.patient}
                  </div>
                </div>
                <button
                  onClick={() => {
                    onClose();
                    onOpenSession ? onOpenSession(session) : handleStartSimulation();
                  }}
                  className="bg-teal-700 hover:bg-teal-800 text-white rounded-lg px-3.5 py-1.5 text-xs font-semibold cursor-pointer transition-colors"
                >
                  Open Session →
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
