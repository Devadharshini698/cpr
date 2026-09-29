import {useEffect,useState} from 'react';
const API=(import.meta.env.VITE_BACKEND_URL || 'http://127.0.0.1:8001').replace(/\/+$/,'');
export default function PatientAssessment({sessionCode,instructor=false}) {
  const [data,setData]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [phase,setPhase]=useState('primary'),[item,setItem]=useState('airway');
  const [status,setStatus]=useState('not_observed'),[finding,setFinding]=useState(''),[feedback,setFeedback]=useState(''),[revealed,setRevealed]=useState(false);
  const headers=()=>({'Content-Type':'application/json',Authorization:`Bearer ${sessionStorage.getItem('token') || localStorage.getItem('token')}`});
  const url=`${API}/api/session/${sessionCode}/assessment`;
  useEffect(()=>{
    if(data?.items && !data.items[phase]) {const first=Object.keys(data.items)[0];setPhase(first);setItem(Object.keys(data.items[first])[0]);}
  },[data,phase]);
  const download=async()=>{
    setBusy(true);setError('');
    try{
      const r=await fetch(`${url}/pdf`,{headers:headers(),cache:'no-store'});
      if(!r.ok)throw new Error('Faculty assessment PDF could not be downloaded');
      const blob=await r.blob(),link=URL.createObjectURL(blob),a=document.createElement('a');
      a.href=link;a.download=`${sessionCode}_faculty_assessment.pdf`;a.click();setTimeout(()=>URL.revokeObjectURL(link),1000);
    }catch(e){setError(e.message);}finally{setBusy(false);}
  };
  useEffect(()=>{
    let alive=true;
    const load=async()=>{try{const r=await fetch(url,{headers:headers()});if(!r.ok)throw new Error('Assessment could not be loaded');const value=await r.json();if(alive)setData(value);}catch(e){if(alive)setError(e.message);}};
    load();const timer=setInterval(load,5000);return()=>{alive=false;clearInterval(timer);};
  },[url]);
  const save=async()=>{
    setBusy(true);setError('');
    try{
      const r=await fetch(url,{method:'POST',headers:headers(),body:JSON.stringify({phase,item,...(instructor?{status,finding,feedback,revealed}:{kind:'request'})})});
      if(!r.ok){const result=await r.json();throw new Error(result.detail || 'Entry not saved');}
      const fresh=await fetch(url,{headers:headers()});if(!fresh.ok)throw new Error('Saved, but refresh failed');setData(await fresh.json());
      setFinding('');setFeedback('');setRevealed(false);setError(instructor?'Observation saved.':'Request sent; await instructor findings.');
    }catch(e){setError(e.message);}finally{setBusy(false);}
  };
  const style={width:'100%',padding:8,background:'#0f172a',color:'#e2e8f0',border:'1px solid #64748b',borderRadius:5};
  return <section style={{display:'grid',gap:10,color:'#e2e8f0',fontSize:12}}>
    <h3>Patient assessment</h3>
    <p>Programme-specific assessment and reassessment. Do not delay urgent simulated care to complete this form. Independently authored draft framework; not a validated course rubric.</p>
    {instructor && <button disabled={busy || !data} onClick={download}>Download faculty assessment PDF (confidential)</button>}
    <label>Assessment phase<select style={style} aria-label="Assessment phase" value={phase} onChange={e=>{setPhase(e.target.value);setItem(Object.keys(data.items[e.target.value])[0]);}}>
      {Object.keys(data?.items || {}).map(p=><option key={p} value={p}>{p.replaceAll('_',' ')}</option>)}
    </select></label>
    <label>Assessment item<select style={style} aria-label="Assessment item" value={item} onChange={e=>setItem(e.target.value)}>
      {Object.entries(data?.items?.[phase] || {}).map(([key,label])=><option key={key} value={key}>{label}</option>)}
    </select></label>
    {instructor && <>
      <label>Observed performance<select style={style} value={status} onChange={e=>setStatus(e.target.value)}>{data?.statuses.map(s=><option key={s} value={s}>{s.replaceAll('_',' ')}</option>)}</select></label>
      <label>Patient finding<textarea style={style} maxLength={2000} value={finding} onChange={e=>setFinding(e.target.value)}/></label>
      <label>Private faculty feedback<textarea style={style} maxLength={2000} value={feedback} onChange={e=>setFeedback(e.target.value)}/></label>
      <label><input type="checkbox" checked={revealed} onChange={e=>setRevealed(e.target.checked)}/> Reveal this finding to students</label>
    </>}
    <button disabled={busy || !data?.active} onClick={save}>{busy?'Saving…':instructor?'Save faculty observation':'Request assessment finding'}</button>
    {error && <p role="status">{error}</p>}
    <p>{data?.notice} Requests are not evidence of performance. Entries are retained; corrections can be added as new observations.</p>
    {data?.records.filter(r=>instructor || r.kind==='request' || r.revealed).slice().reverse().map(r=><article key={r.id} style={{borderTop:'1px solid #475569',paddingTop:8}}>
      <strong>{data.items[r.phase]?.[r.item]} · {r.phase}</strong><div>{r.kind} · {r.created_at}</div>
      {instructor && <div>{r.status?.replaceAll('_',' ')} · {r.revealed?'Finding revealed':'Private'}{r.feedback && <p>Faculty: {r.feedback}</p>}</div>}
      {r.finding && <p>{r.finding}</p>}
    </article>)}
  </section>;
}
