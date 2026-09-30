import React, {useEffect,useState,useRef,useLayoutEffect} from 'react';
import socket from '../../socket';
import useMonitorStore from '../../store/monitorStore';
import {useECGStore} from '../../store/ecgStore';
import ECGTrack from './ECGTrack';
import {studentVisible} from '../../utils/studentDisplay';
import './PacerPanel.css';

const DEFAULT={visible:false,student_enabled:false,pads_connected:false,enabled:false,rate:70,output:0,mode:'fixed',electrical_capture:false,mechanical_capture:false};
export default function PacerPanel({instructor=false}) {
  const saved=useMonitorStore(s=>s.pacer);
  const ended=useMonitorStore(s=>s.sessionEnded);
  const monitor=useMonitorStore();
  const connected=useECGStore(s=>s.connected);
  const screenRef=useRef(null);
  const [screenWidth,setScreenWidth]=useState(240);
  const canSeeEcg=instructor||(!monitor.initial_readings_hidden&&monitor.show_ecg!==false&&studentVisible(monitor,true,'ecg_wave'));
  useLayoutEffect(()=>{
    const element=screenRef.current;
    if(!element) return;
    const observer=new ResizeObserver(()=>setScreenWidth(Math.max(100,Math.floor(element.clientWidth))));
    observer.observe(element);
    return ()=>observer.disconnect();
  },[instructor,saved?.visible]);
  const p={...DEFAULT,...saved};
  const [rate,setRate]=useState(p.rate),[output,setOutput]=useState(p.output);
  const [busy,setBusy]=useState(false),[message,setMessage]=useState('');
  useEffect(()=>{setRate(p.rate);setOutput(p.output);},[p.rate,p.output]);
  const send=changes=>{
    setBusy(true);setMessage('');
    socket.timeout(8000).emit('pacer_update',changes,(error,result)=>{
      setBusy(false);
      setMessage(error?'Pacer update not confirmed; check connection.':result?.status==='success'?'Saved':result?.message||'Update failed');
    });
  };
  if (!instructor && !p.visible) return <p>The pacer has not been made available by the instructor.</p>;
  const disabled=busy||ended||(!instructor&&!p.student_enabled);
  const buttonStyle={padding:8,margin:4,border:'1px solid #64748b',borderRadius:6,background:'#0f172a',color:'#fff'};
  return <section style={{padding:12,border:'1px solid #64748b',borderRadius:8,color:'#e2e8f0',background:'#1e293b'}}>
    <h3>Transcutaneous pacer — simulation</h3>
    <p>Adult teaching simulator. Demand uses simplified intrinsic QRS sensing; fixed pacing is asynchronous. Sensing faults and competitive/fusion capture are not modelled. Rate/output ranges are simulator controls, not prescribed settings.</p>
    {instructor&&<div>
      <label><input type="checkbox" checked={p.visible} disabled={busy||ended} onChange={e=>send({visible:e.target.checked})}/> Make pacer available to students</label><br/>
      <label><input type="checkbox" checked={p.student_enabled} disabled={busy||ended||!p.visible} onChange={e=>send({student_enabled:e.target.checked})}/> Permit student operation</label>
    </div>}
    {!instructor&&!p.student_enabled&&<p>Observation only — instructor has not enabled operation.</p>}
    <label>Pacing mode
      <select aria-label="Pacing mode" value={p.mode} disabled={disabled} onChange={e=>send({mode:e.target.value})} style={{display:'block',width:'100%',padding:10,background:'#f8fafc',color:'#0f172a',margin:'6px 0'}}>
        <option value="demand">Demand — sense intrinsic QRS</option>
        <option value="fixed">Fixed — asynchronous</option>
      </select>
    </label>
    <p>{p.mode==='demand'?'Sensed intrinsic QRS resets the escape timer. A stimulus is delivered when that interval expires.':'Fixed mode delivers stimuli regardless of intrinsic QRS. It does not sense or inhibit output.'}</p>
    <div className="pacer-device" aria-label="Live simulated pacer monitor">
      <div className="pacer-device__status"><strong>{p.enabled?(p.output>0?'PACING ON':'ON — ZERO OUTPUT'):'PACING OFF'}</strong><span>Pads {p.pads_connected?'connected':'disconnected'}</span></div>
      <strong>{p.mode==='demand'?'DEMAND · sensing enabled':'FIXED · asynchronous'}</strong>
      <div className="pacer-device__readouts">
        <div>SET RATE<strong>{p.rate}<small> /min</small></strong></div>
        <div>OUTPUT<strong>{p.output}<small> mA</small></strong></div>
      </div>
      <div className="pacer-device__connection" role="status">{ended?'Session ended':connected?'Live ECG stream connected':'ECG stream disconnected — do not assess frozen trace'}</div>
      <div ref={screenRef} className="pacer-device__trace">
        {canSeeEcg&&connected&&!ended?<ECGTrack lead="II" width={screenWidth} height={160} gain={5}/>:<p>{!canSeeEcg?'ECG not revealed — request it from your instructor.':'Live ECG unavailable.'}</p>}
      </div>
      <p className="pacer-device__caption">Lead II from the main monitor’s live sample stream. Set rate is not a measured pulse rate.</p>
      {instructor&&<p>Electrical capture: {p.electrical_capture?'confirmed':'not confirmed'}<br/>Mechanical capture: {p.mechanical_capture?'confirmed':'not confirmed'}</p>}
    </div>
    <label><input type="checkbox" checked={p.pads_connected} disabled={disabled} onChange={e=>send({pads_connected:e.target.checked,...(!e.target.checked?{enabled:false}:{})})}/> Simulated pads connected</label>
    <div style={{display:'flex',gap:12,flexWrap:'wrap',marginTop:12}}>
      <label>Rate (/min)<input className="pacer-setting" aria-label="Pacer rate" type="number" min="30" max="180" value={rate} disabled={disabled} onChange={e=>setRate(e.target.value)}/></label>
      <label>Output (mA)<input className="pacer-setting" aria-label="Pacer output" type="number" min="0" max="200" value={output} disabled={disabled} onChange={e=>setOutput(e.target.value)}/></label>
      <button style={buttonStyle} disabled={disabled||rate===''||output===''} onClick={()=>send({rate:Number(rate),output:Number(output)})}>Apply settings</button>
    </div>
    <button style={buttonStyle} disabled={disabled||(!p.enabled&&!p.pads_connected)} onClick={()=>send({enabled:!p.enabled})}>{p.enabled?'Stop pacing':'Start pacing'}</button>
    {instructor&&<div>
      <h4>Faculty capture response</h4>
      <p>Capture must be assessed; increasing mA does not automatically establish it. Mechanical capture uses the underlying pressure/oxygenation values, not an automatic improvement.</p>
      <button style={buttonStyle} disabled={busy||ended} onClick={()=>send({electrical_capture:false,mechanical_capture:false})}>No electrical capture</button>
      <button style={buttonStyle} disabled={busy||ended||!p.enabled||p.output===0} onClick={()=>send({electrical_capture:true,mechanical_capture:false})}>Electrical only — no paced pulse</button>
      <button style={buttonStyle} disabled={busy||ended||!p.enabled||p.output===0} onClick={()=>send({electrical_capture:true,mechanical_capture:true})}>Electrical + mechanical capture</button>
      <p>Electrical: {p.electrical_capture?'confirmed':'not confirmed'} · Mechanical: {p.mechanical_capture?'confirmed':'not confirmed'}</p>
    </div>}
    <p>Assess ECG capture and actual pulse/perfusion separately. Request ECG and pulse/BP findings through the instructor. Also assess discomfort and support needs.</p>
    <button style={buttonStyle} disabled={busy||ended||!p.visible} onClick={()=>send({activity:'assess_capture'})}>Request capture / pulse assessment</button>
    <button style={buttonStyle} disabled={busy||ended||!p.visible} onClick={()=>send({activity:'assess_comfort'})}>Request comfort assessment</button>
    <p>Mode, rate or output changes clear capture confirmation. Instructor physiology or condition changes stop pacing so a stale response is not retained.</p>
    <p role="status">{message}</p>
  </section>;
}
