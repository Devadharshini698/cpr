import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import './progress.css';

const API=(import.meta.env.VITE_BACKEND_URL||'http://127.0.0.1:8000').replace(/\/+$/,'');
async function request(path='',body) {
  const token=sessionStorage.getItem('token')||localStorage.getItem('token');
  const response=await fetch(`${API}/api/progress${path}`,{method:body?'POST':'GET',headers:{Authorization:`Bearer ${token}`,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
  const data=await response.json();
  if(!response.ok) throw new Error(typeof data.detail==='string'?data.detail:'Could not complete this request.');
  return data;
}
const when=value=>value?new Date(value.endsWith('Z')?value:value+'Z').toLocaleString():'—';
const delta=value=>value==null?'No comparable previous attempt':`${value>0?'+':''}${value.toFixed(2)} / 3`;

export default function ProgressPage() {
  const [data,setData]=useState(null),[error,setError]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false);
  const [subject,setSubject]=useState(''),[cohort,setCohort]=useState(''),[session,setSession]=useState('');
  const [kind,setKind]=useState('student'),[name,setName]=useState(''),[reference,setReference]=useState('');
  const [role,setRole]=useState(''),[ratings,setRatings]=useState({}),[evidence,setEvidence]=useState(''),[nextSteps,setNextSteps]=useState(''),[confirmed,setConfirmed]=useState(false);
  const load=async()=>{const value=await request();setData(value);return value;};
  useEffect(()=>{load().catch(e=>setError(e.message));},[]);
  const subjects=data?.subjects||[],attempts=data?.attempts||[],domains=data?.domains||{};
  const profile=subjects.find(row=>row.id===subject);
  const own=attempts.filter(row=>row.subject_id===subject);
  const cohorts=useMemo(()=>Array.from(new Map(own.map(row=>[row.cohort,row.context])).entries()),[data,subject]);
  const shown=own.filter(row=>!cohort||row.cohort===cohort);
  const peers=cohort?Array.from(new Map(attempts.filter(row=>row.cohort===cohort).map(row=>[row.subject_id,row])).values()):[];
  const latest=shown.at(-1);
  const create=async event=>{
    event.preventDefault();setBusy(true);setError('');setMessage('');
    try {const result=await request('/subjects',{kind,name,reference});await load();setSubject(result.id);setCohort('');setName('');setReference('');setMessage('Tracking profile created.');}
    catch(e){setError(e.message);} finally{setBusy(false);}
  };
  const save=async event=>{
    event.preventDefault();setBusy(true);setError('');setMessage('');
    try {
      const result=await request('/observations',{subject_id:subject,session_code:session,role_label:role,
        ratings:Object.fromEntries(Object.keys(domains).map(key=>[key,ratings[key]==null||ratings[key]===''?null:Number(ratings[key])])),
        evidence,next_steps:nextSteps,confirmed_attribution:confirmed});
      await load();setMessage(result.notice);setConfirmed(false);setRatings({});setEvidence('');setNextSteps('');
    } catch(e){setError(e.message);} finally{setBusy(false);}
  };
  return <main className="progress-page">
    <header><Link to="/dashboard">← Dashboard</Link><h1>Performance & Progress</h1><p>Instructor-only student and team tracking · Faculty observation rubric</p></header>
    {error&&<p role="alert" className="progress-error">{error}</p>}{message&&<p role="status">{message}</p>}
    {!data?<><p>Loading progress records…</p><button onClick={()=>load().catch(e=>setError(e.message))}>Retry</button></>:<>
      <p className="progress-notice">{data.notice}</p>
      <details><summary>Create a student or team tracking profile</summary>
        <form onSubmit={create} className="progress-form">
          <label>Profile type<select value={kind} onChange={e=>setKind(e.target.value)}><option value="student">Student</option><option value="team">Team</option></select></label>
          <label>Display name<input required maxLength={120} value={name} onChange={e=>setName(e.target.value)} /></label>
          <label>Stable tracking reference<input required maxLength={80} value={reference} onChange={e=>setReference(e.target.value)} placeholder="e.g. local learner ID or team code" /></label>
          <p>Use the same reference for repeat attempts. Team profiles represent a fixed roster; create a new profile if membership changes. No account or voice identity is inferred.</p>
          <button disabled={busy}>Create profile</button>
        </form>
      </details>
      <section>
        <label>Student or team<select value={subject} onChange={e=>{setSubject(e.target.value);setCohort('');setConfirmed(false);setRatings({});setEvidence('');setNextSteps('');setRole('');setSession('');}}>
          <option value="">Select a profile</option>{subjects.map(row=><option key={row.id} value={row.id}>{row.kind}: {row.name} ({row.reference})</option>)}
        </select></label>
        {profile&&<><h2>{profile.name} — {profile.kind} progress</h2>
          <p>{own.length} assessed attempts. Unassessed historical sessions are not counted as zero.</p>
          <label>Comparable case group<select value={cohort} onChange={e=>setCohort(e.target.value)}>
            <option value="">All history — no pooled trend</option>{cohorts.map(([key,c])=><option value={key} key={key}>{c.programme} · {c.topic} · {c.level} · {c.role} · {c.setting} · {c.domains.length}/6 domains · {key.slice(0,6)}</option>)}
          </select></label>
          {cohort&&shown.length>0&&<p>First → latest: {shown[0].mean.toFixed(2)} → {latest.mean.toFixed(2)} / 3 · {shown.length} comparable attempts. {shown.length<2?'More attempts are needed to describe progression.':'Descriptive change only—not proof of competence or a statistically established trend.'}</p>}
          <div className="progress-table"><table><caption>Session-by-session observations (ordered by session completion)</caption><thead><tr><th>Completed</th><th>Session</th><th>Case / difficulty</th><th>Observed domains</th><th>Mean / 3</th><th>Change vs comparable previous attempt</th></tr></thead><tbody>
            {shown.map(row=><tr key={row.id}><td>{when(row.ended_at)}</td><td><Link to={`/debrief/${row.session_code}`}>{row.session_code}</Link></td><td>{row.context.topic} · {row.context.level}</td><td>{row.coverage}/6</td><td>{row.mean?.toFixed(2)??'Not assessed'}</td><td>{delta(row.change)}</td></tr>)}
          </tbody></table></div>
          {!shown.length&&<p>No observations yet. Record an explicitly attributed assessment below.</p>}
          {latest&&<details><summary>Latest observation: evidence, domain ratings and next steps</summary><p>{latest.evidence}</p>
            <ul>{Object.entries(domains).map(([key,label])=><li key={key}>{label}: {latest.ratings[key]==null?'Not observed / not applicable':`${latest.ratings[key]} — ${data.scale[latest.ratings[key]]}`}</li>)}</ul>
            <p><strong>Practice plan:</strong> {latest.next_steps}</p><p>Assessed role: {latest.role_label}. Recorded {when(latest.created_at)}.</p>
          </details>}
          <h3>Side-by-side comparison</h3>
          {!cohort?<p>Select a comparable case group first. Students and teams are never mixed.</p>:<div className="progress-table"><table><caption>Latest observation per profile in this exact group—not a ranking</caption><thead><tr><th>Profile</th>{Object.entries(domains).map(([key,label])=><th key={key}>{label}</th>)}<th>Mean / 3</th></tr></thead><tbody>
            {peers.map(row=><tr key={row.subject_id}><th>{subjects.find(p=>p.id===row.subject_id)?.name}</th>{Object.keys(domains).map(key=><td key={key}>{row.ratings[key]??'Not observed'}</td>)}<td>{row.mean?.toFixed(2)}</td></tr>)}
          </tbody></table>{peers.length<2&&<p>No other profile has matching observations yet.</p>}</div>}
          <details><summary>Record / revise a completed-session observation</summary>
            <form onSubmit={save} className="progress-form">
              <label>Completed session<select required value={session} onChange={e=>{setSession(e.target.value);setConfirmed(false);setRatings({});setEvidence('');setNextSteps('');}}><option value="">Select session</option>{data.sessions.map(row=><option key={row.session_code} value={row.session_code}>{row.session_code} · {row.title} · {row.level} · {when(row.ended_at)}</option>)}</select></label>
              <label>{profile.kind==='student'?'Observed student role':'Team composition / roster version'}<input required maxLength={80} value={role} onChange={e=>setRole(e.target.value)} placeholder={profile.kind==='student'?'e.g. nurse / team leader':'e.g. two nurses + one doctor, roster v1'} /></label>
              <p>0 = observed omission; 1 = major prompting; 2 = some prompting; 3 = independent. Use “not observed” when evidence is missing or the domain was not applicable.</p>
              {Object.entries(domains).map(([key,label])=><label key={key}>{label}<select value={ratings[key]??''} onChange={e=>setRatings(old=>({...old,[key]:e.target.value}))}><option value="">Not observed / not applicable</option>{Object.entries(data.scale).map(([value,text])=><option key={value} value={value}>{value} — {text}</option>)}</select></label>)}
              <label>Observed evidence (include actions and timestamps where possible)<textarea required maxLength={2000} value={evidence} onChange={e=>setEvidence(e.target.value)} /></label>
              <label>Feedback and next practice goals<textarea required maxLength={1000} value={nextSteps} onChange={e=>setNextSteps(e.target.value)} /></label>
              <label className="progress-confirm"><input required type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} />I confirm this {profile.kind} participated and these ratings describe their observed performance—not another learner’s or a copied team score.</label>
              <p>Revising this profile/session replaces its contribution to the trend, not the stored audit history.</p>
              <button disabled={busy}>{busy?'Saving…':'Save faculty observation'}</button>
            </form>
          </details>
        </>}
      </section>
    </>}
  </main>;
}
