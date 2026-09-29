import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const API = (import.meta.env.VITE_BACKEND_URL || 'http://127.0.0.1:8001').replace(/\/+$/, '');
const member = () => ({ id: crypto.randomUUID(), name: '', role: '', recording_id: '', url: '' });

export default function PrebriefPage() {
  const navigate = useNavigate();
  const [draft] = useState(() => { try { return JSON.parse(sessionStorage.getItem('prebrief_draft') || 'null'); } catch { return null; } });
  const [members, setMembers] = useState([member()]);
  const [consent, setConsent] = useState(false);
  const [recording, setRecording] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const recorder = useRef(null);
  const stream = useRef(null);
  const timeout = useRef(null);
  const urls = useRef([]);
  const alive = useRef(true);
  const headers = () => ({ Authorization: `Bearer ${sessionStorage.getItem('token') || localStorage.getItem('token') || ''}` });
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      clearTimeout(timeout.current);
      if (recorder.current?.state === 'recording') recorder.current.stop();
      stream.current?.getTracks().forEach(track => track.stop());
      urls.current.forEach(url => URL.revokeObjectURL(url));
    };
  }, []);
  const update = (id, changes) => setMembers(old => old.map(item => item.id === id ? { ...item, ...changes } : item));
  const stop = () => { clearTimeout(timeout.current); if (recorder.current?.state === 'recording') recorder.current.stop(); };
  const record = async (item) => {
    setBusy(true); setMessage('');
    try {
      if (!consent || !item.name.trim() || !item.role.trim()) throw new Error('Enter the member name and role, and confirm recording consent first.');
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error('Microphone recording is unavailable in this browser.');
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus'].find(type => MediaRecorder.isTypeSupported(type));
      if (!mime) throw new Error('No supported recording format. Try Chrome or Edge.');
      const capture = new MediaRecorder(stream.current, { mimeType: mime });
      const chunks = [];
      capture.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
      capture.onerror = () => { setMessage('Recording failed. Please record this member again.'); stop(); };
      capture.onstop = async () => {
        stream.current?.getTracks().forEach(track => track.stop());
        if (!alive.current) return;
        setRecording(''); setBusy(true);
        try {
          const blob = new Blob(chunks, { type: mime });
          const url = URL.createObjectURL(blob); urls.current.push(url);
          update(item.id, { url, recording_id: '' });
          const form = new FormData();
          form.append('audio', blob, 'introduction'); form.append('name', item.name);
          form.append('role', item.role); form.append('consent', 'true');
          const response = await fetch(`${API}/api/prebrief/recordings`, { method: 'POST', headers: headers(), body: form, signal: AbortSignal.timeout(30000) });
          if (!response.ok) throw new Error('Introduction could not be saved. Download the clip before leaving, then record again.');
          const data = await response.json();
          if (alive.current) { update(item.id, { recording_id: data.recording_id }); setMessage('Introduction saved locally. Listen back before launching.'); }
        } catch (error) { if (alive.current) setMessage(error.message); }
        finally { if (alive.current) setBusy(false); }
      };
      recorder.current = capture;
      capture.start(); setRecording(item.id); setBusy(false);
      timeout.current = setTimeout(stop, 45000);
    } catch (error) { stream.current?.getTracks().forEach(track => track.stop()); setMessage(error.message); setBusy(false); }
  };
  const launch = async () => {
    if (busy || recording || !consent || !members.every(item => item.recording_id)) return;
    setBusy(true); setMessage('Launching the scenario…');
    try {
      const response = await fetch(`${API}/api/scenario/launch`, {
        method: 'POST', headers: { ...headers(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...draft, prebrief: { consent_confirmed: consent, recording_ids: members.map(item => item.recording_id) } }),
      });
      if (!response.ok) { const data = await response.json(); throw new Error(data.detail || 'Launch failed'); }
      const data = await response.json();
      sessionStorage.setItem('session_code', data.session_code);
      sessionStorage.setItem('team_name', draft.team_name);
      sessionStorage.removeItem('prebrief_draft');
      navigate('/instructor');
    } catch (error) { setMessage(error.message); setBusy(false); }
  };
  if (!draft) return <main className="p-8"><h1>Select a scenario first</h1><button onClick={() => navigate('/cases')}>Open Scenario Studio</button></main>;
  return <main className="min-h-screen bg-slate-50 p-6 text-slate-900"><div className="mx-auto max-w-4xl space-y-5">
    <header><p className="text-teal-700 font-semibold">Before scenario launch · {draft.team_name}</p><h1 className="text-3xl font-bold">Team prebriefing</h1>
      <p className="mt-2">Introduce every member, agree roles and confirm the microphone. The clinical scenario timer has not started.</p></header>
    <section className="rounded-xl bg-white border p-5 space-y-3"><h2 className="font-bold">Briefing checklist</h2>
      <p>Explain learning objectives, equipment limitations, confidentiality and the right to pause. This is a simulation—not patient care or a competency certification.</p>
      <p>Each member should speak alone for 10–20 seconds: “My name is …, my role is …”. Add one recording per person; do not have one person read the entire roster.</p>
      <label className="flex gap-3"><input type="checkbox" checked={consent} disabled={busy || !!recording} onChange={e => setConsent(e.target.checked)} />All participants have agreed to local recording and instructor review.</label>
    </section>
    {members.map((item, index) => <section key={item.id} className="rounded-xl border bg-white p-5 space-y-3">
      <h2 className="font-semibold">Team member {index + 1} {item.recording_id ? '· Saved' : ''}</h2>
      {members.length > 1 && !item.recording_id && <button disabled={busy || !!recording} onClick={() => setMembers(old => old.filter(row => row.id !== item.id))}>Remove unrecorded member</button>}
      <div className="flex flex-wrap gap-3"><input aria-label={`Member ${index + 1} name`} maxLength={80} placeholder="Name or training alias" className="border rounded p-2" value={item.name} disabled={busy || !!recording || !!item.recording_id} onChange={e => update(item.id, { name: e.target.value })} />
        <input aria-label={`Member ${index + 1} role`} maxLength={80} placeholder="Role, e.g. team leader" className="border rounded p-2" value={item.role} disabled={busy || !!recording || !!item.recording_id} onChange={e => update(item.id, { role: e.target.value })} />
        <button className="rounded bg-teal-700 text-white px-4 py-2 disabled:opacity-40" disabled={busy || (!!recording && recording !== item.id) || !consent} onClick={() => recording === item.id ? stop() : record(item)}>{recording === item.id ? 'Stop introduction' : item.recording_id ? 'Record again' : 'Record introduction'}</button>
      </div>
      {item.url && <div className="flex flex-wrap items-center gap-3"><audio controls src={item.url} /><a className="underline" href={item.url} download={`member-${index + 1}-introduction`}>Download clip</a></div>}
    </section>)}
    <p className="text-sm text-slate-600">Introductions are stored separately from scenario audio and excluded from clinical scoring. Names and roles are instructor-entered; automatic voice matching is not yet validated.</p>
    {message && <p role="status" className="rounded border border-amber-300 bg-amber-50 p-3">{message}</p>}
    <div className="flex gap-3"><button className="rounded border px-4 py-2" disabled={busy || !!recording || members.length >= 12} onClick={() => setMembers(old => [...old, member()])}>Add team member</button>
      <button className="rounded bg-teal-700 text-white px-5 py-2 disabled:opacity-40" disabled={busy || !!recording || !consent || !members.every(item => item.recording_id)} onClick={launch}>Launch scenario</button></div>
  </div></main>;
}
