import { useState } from 'react';
import socket from '../../socket';
import useMonitorStore from '../../store/monitorStore';
import { CHANNELS, channelEnabled, channelConfigured } from '../../utils/monitorChannels';

export default function WaveformControls() {
  const state = useMonitorStore();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState(null);
  const [values, setValues] = useState({});
  const fields = {pap:[['PAP_sys','Systolic (mmHg)',120],['PAP_dia','Diastolic (mmHg)',100]],co2:[['etCO2','EtCO₂ (mmHg)',150],['avRR','Ventilation rate (/min)',80]]};
  const configure = (channel, configured) => {
    if (configured && Object.values(values).some(value=>value==='')) { setError('Enter each measurement before applying.'); return; }
    setBusy(true); setError('');
    socket.timeout(10000).emit('configure_waveform_channel', {channel,configured,values:configured?Object.fromEntries(Object.entries(values).map(([key,value])=>[key,Number(value)])):{}}, (err,result)=>{
      setBusy(false);
      if (err || result?.status !== 'success') setError(result?.message || 'Configuration not confirmed. Check the connection and retry.');
      else setEditing(null);
    });
  };
  const change = (key, value) => {
    const channels = Object.fromEntries(CHANNELS.map(([id]) => [id, id === key ? value : channelEnabled(state,id)]));
    setBusy(true); setError('');
    socket.timeout(10000).emit('set_waveform_channels', channels, (err, result) => {
      setBusy(false);
      if (err || result?.status !== 'success') setError('Waveform selection not saved. Check the connection and retry.');
    });
  };
  return <details style={{marginBottom:12,color:'#e2e8f0'}}>
    <summary>Optional waveform channels</summary>
    <p style={{fontSize:12}}>Select channels here; reveal them separately in Student display. Selection does not connect a sensor or invent a reading.</p>
    {CHANNELS.map(([key,label]) => <div key={key} style={{padding:'4px 0'}}><label>
      <input type="checkbox" disabled={busy} checked={channelEnabled(state,key)} onChange={e=>change(key,e.target.checked)} /> {label}
      {!channelConfigured(state,key) && <small> — Not configured</small>}
    </label> <button disabled={busy} onClick={()=>{
      setEditing(key);setError('');setValues(Object.fromEntries((fields[key]||[]).map(([field])=>[field,channelConfigured(state,key)?state[field]??'':''])));
    }} style={{color:'#5eead4',textDecoration:'underline'}}>Set up</button></div>)}
    {editing && <form onSubmit={event=>{event.preventDefault();configure(editing,true);}} style={{padding:8,border:'1px solid #64748b'}}>
      <strong>{CHANNELS.find(([key])=>key===editing)?.[1]} simulated sensor</strong>
      <p style={{fontSize:12}}>Faculty-defined simulation, not a real sensor. Patient condition changes may replace these values. Student disclosure stays separate.</p>
      {editing==='abp' && <p>Use current patient pressure: {state.ABP_sys}/{state.ABP_dia} mmHg. This does not measure or change the NIBP cuff.</p>}
      {editing==='ecg' && <p>Use the current patient rhythm and heart rate.</p>}
      {editing==='pleth' && <p>Use current SpO₂ and perfusion. Connecting a sensor does not restore a pulse.</p>}
      {(fields[editing]||[]).map(([field,label,max])=><label key={field} style={{display:'block'}}>{label}
        <input required type="number" min="0" max={max} step="any" value={values[field]??''} onChange={e=>setValues(old=>({...old,[field]:e.target.value}))} style={{display:'block',width:'100%',boxSizing:'border-box',background:'#fff',color:'#111',padding:5}} />
      </label>)}
      <button type="submit" disabled={busy}>Connect / apply</button>{' '}
      <button type="button" disabled={busy} onClick={()=>configure(editing,false)}>Disconnect</button>{' '}
      <button type="button" disabled={busy} onClick={()=>setEditing(null)}>Cancel</button>
    </form>}
    {error && <p role="alert">{error}</p>}
  </details>;
}
