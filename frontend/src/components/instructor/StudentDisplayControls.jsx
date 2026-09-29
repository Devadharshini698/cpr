import { useState } from 'react';
import socket from '../../socket';
import useMonitorStore from '../../store/monitorStore';
import { DEFAULT_STUDENT_DISPLAY, STUDENT_DISPLAY_FIELDS } from '../../utils/studentDisplay';

export default function StudentDisplayControls({ onClose, sessionCode }) {
  const [selection, setSelection] = useState(() => ({...DEFAULT_STUDENT_DISPLAY, ...useMonitorStore.getState().student_display}));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const apply = () => {
    setBusy(true); setError('');
    socket.timeout(10000).emit('set_student_display', selection, (err, result) => {
      setBusy(false);
      if (err || result?.status !== 'success') setError('Student display was not confirmed. Check the connection and retry.');
      else { useMonitorStore.getState().setFullState({student_display: selection}); onClose(); }
    });
  };
  return <div className="dialog-overlay" style={{zIndex:10000}}>
    <section className="dialog-box" role="dialog" aria-modal="true" aria-label="Student display" style={{width:520,maxWidth:'95vw',maxHeight:'90vh',overflowY:'auto'}}>
      <div className="dialog-header"><h2>Student display</h2><button onClick={onClose} disabled={busy}>Close</button></div>
      <div className="dialog-body" style={{padding:16}}>
        <p>Choose what students see live. Your instructor monitor stays complete. These settings control presentation, not access to session data.</p>
        <a href={`/student-preview/${encodeURIComponent(sessionCode)}`} style={{color:'#5eead4',textDecoration:'underline'}}>Preview saved student display</a>
        <div style={{display:'flex',gap:12,margin:'12px 0'}}>
          <button disabled={busy} onClick={() => setSelection(Object.fromEntries(STUDENT_DISPLAY_FIELDS.map(([key])=>[key,true])))}>Show all</button>
          <button disabled={busy} onClick={() => setSelection(Object.fromEntries(STUDENT_DISPLAY_FIELDS.map(([key])=>[key,false])))}>Hide all</button>
        </div>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
          {STUDENT_DISPLAY_FIELDS.map(([key,label])=><label key={key} style={{display:'flex',gap:8,alignItems:'center'}}>
            <input type="checkbox" checked={selection[key]} disabled={busy} onChange={event=>setSelection(old=>({...old,[key]:event.target.checked}))}/>{label}
          </label>)}
        </div>
        {error && <p role="alert">{error}</p>}
      </div>
      <div className="dialog-footer"><button disabled={busy} onClick={apply}>{busy ? 'Sending…' : 'Apply to students'}</button></div>
    </section>
  </div>;
}
