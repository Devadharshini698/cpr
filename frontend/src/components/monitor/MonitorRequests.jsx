import {useEffect,useRef,useState} from 'react';
import socket from '../../socket';
import useMonitorStore from '../../store/monitorStore';

const CHANNELS={ecg:'ECG / rhythm',spo2:'SpO₂ / pulse oximeter',nibp:'NIBP / blood pressure',abp:'Arterial line',pap:'Pulmonary artery pressure',co2:'Capnography / respiratory rate',temp:'Temperature',co:'Cardiac output'};
const API=(import.meta.env.VITE_BACKEND_URL || 'http://127.0.0.1:8001').replace(/\/+$/,'');
const control={width:'100%',padding:7,background:'#0f172a',color:'#e2e8f0',border:'1px solid #64748b',borderRadius:5};

export default function MonitorRequests({sessionCode,instructor=false}) {
  const requests=useMonitorStore(s=>s.student_requests) || [];
  const [channel,setChannel]=useState('');
  const [text,setText]=useState('');
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const [recording,setRecording]=useState(false);
  const [language,setLanguage]=useState('english');
  const [clip,setClip]=useState('');
  const [level,setLevel]=useState(0);
  const [devices,setDevices]=useState([]);
  const [device,setDevice]=useState('');
  const recorder=useRef(null),stream=useRef(null),timer=useRef(null),context=useRef(null),frame=useRef(null),alive=useRef(true);
  useEffect(()=>{
    alive.current=true;
    if(!instructor) navigator.mediaDevices?.enumerateDevices().then(items=>setDevices(items.filter(d=>d.kind==='audioinput'))).catch(()=>{});
    return ()=>{alive.current=false;clearTimeout(timer.current);if(recorder.current?.state==='recording') recorder.current.stop();stream.current?.getTracks().forEach(t=>t.stop());cancelAnimationFrame(frame.current);context.current?.close().catch(()=>{});};
  },[instructor]);
  useEffect(()=>()=>{if(clip)URL.revokeObjectURL(clip);},[clip]);
  const emit=(event,data)=>{
    setBusy(true);setError('');
    socket.timeout(10000).emit(event,data,(err,result)=>{
      if(!alive.current)return;
      setBusy(false);
      if(err || result?.status!=='success')setError(result?.message || 'Request was not confirmed. Please retry.');
      else if(event==='request_monitor'){setText('');setError('Sent. Waiting for the instructor to reveal the requested monitoring.');}
    });
  };
  const stop=()=>{clearTimeout(timer.current);if(recorder.current?.state==='recording')recorder.current.stop();};
  const record=async()=>{
    setError('');setClip('');setBusy(true);
    try{
      if(!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder)throw new Error('Microphone recording is unavailable. Use a typed request.');
      stream.current=await navigator.mediaDevices.getUserMedia({audio:{...(device?{deviceId:{exact:device}}:{}),echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
      if(!alive.current){stream.current.getTracks().forEach(t=>t.stop());return;}
      const mime=['audio/webm;codecs=opus','audio/webm','audio/mp4'].find(m=>MediaRecorder.isTypeSupported(m));
      if(!mime)throw new Error('No supported audio format. Use a typed request.');
      const AudioContext=window.AudioContext || window.webkitAudioContext;
      if(AudioContext){
        context.current=new AudioContext();await context.current.resume();
        const analyser=context.current.createAnalyser();analyser.fftSize=256;
        context.current.createMediaStreamSource(stream.current).connect(analyser);
        const values=new Float32Array(256);
        const meter=()=>{analyser.getFloatTimeDomainData(values);setLevel(Math.min(100,Math.round(Math.sqrt(values.reduce((sum,v)=>sum+v*v,0)/256)*700)));frame.current=requestAnimationFrame(meter);};meter();
      }
      const chunks=[];
      const capture=new MediaRecorder(stream.current,{mimeType:mime});recorder.current=capture;
      capture.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
      capture.onstop=async()=>{
        stream.current?.getTracks().forEach(t=>t.stop());cancelAnimationFrame(frame.current);context.current?.close().catch(()=>{});
        if(!alive.current)return;
        setRecording(false);setLevel(0);setBusy(true);
        const blob=new Blob(chunks,{type:mime});setClip(URL.createObjectURL(blob));
        setError('Recognising locally… This can take time on this laptop. No monitoring is revealed yet.');
        try{
          const form=new FormData();form.append('audio',blob,'request.webm');form.append('language',language);
          const token=sessionStorage.getItem('token') || localStorage.getItem('token');
          const response=await fetch(`${API}/api/session/${sessionCode}/request-voice`,{method:'POST',headers:{Authorization:`Bearer ${token}`},body:form,signal:AbortSignal.timeout(120000)});
          const data=await response.json();if(!response.ok)throw new Error(data.detail || 'Speech recognition failed');
          if(!alive.current)return;
          setText(data.text);setChannel(data.suggested_channel || '');
          setError('Review the recognised words and choose a channel, then send. The instructor must approve.');
        }catch(err){if(alive.current)setError(err.message || 'Recognition failed. Listen to your clip or type the request.');}
        finally{if(alive.current)setBusy(false);}
      };
      capture.start();setRecording(true);setBusy(false);timer.current=setTimeout(stop,12000);
    }catch(err){stream.current?.getTracks().forEach(t=>t.stop());cancelAnimationFrame(frame.current);context.current?.close().catch(()=>{});if(alive.current){setBusy(false);setError(err.message);}}
  };
  const visible=instructor?requests.filter(r=>r.status==='pending'):requests.slice(-8);
  return <section style={{fontSize:12,padding:10,background:'#0f172a',border:'1px solid #334155',borderRadius:6}}>
    <h3 style={{margin:'0 0 8px'}}>{instructor?`Student requests (${visible.length})`:'Ask for monitoring'}</h3>
    {!instructor && <div style={{display:'grid',gap:8}}>
      <p>Monitoring is concealed until your instructor reveals it. Ask verbally in the room or send a request here.</p>
      <select aria-label="Requested monitoring" style={control} value={channel} onChange={e=>setChannel(e.target.value)}><option value="">Choose monitoring</option>{Object.entries(CHANNELS).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select>
      <textarea aria-label="Request words" style={control} placeholder="Type your request or record it below" maxLength={500} value={text} onChange={e=>setText(e.target.value)}/>
      <button disabled={busy || recording || !channel} onClick={()=>emit('request_monitor',{channel,text})}>Send request to instructor</button>
      <p style={{margin:0}}>Voice request: up to 12 seconds, processed locally; not continuous command listening or speaker identification.</p>
      <select aria-label="Voice request language" style={control} value={language} disabled={busy || recording} onChange={e=>setLanguage(e.target.value)}><option value="english">English</option><option value="tamil">Tamil</option><option value="auto">Auto / Tanglish</option></select>
      <select aria-label="Voice request microphone" style={control} value={device} disabled={busy || recording} onChange={e=>setDevice(e.target.value)}><option value="">System microphone</option>{devices.map((d,i)=><option key={d.deviceId||i} value={d.deviceId}>{d.label || `Microphone ${i+1}`}</option>)}</select>
      <button disabled={busy} onClick={recording?stop:record}>{recording?'Stop and recognise':'Record voice request'}</button>
      {recording && <span role="status">Microphone level: {level}% · Speak now</span>}
      {clip && <audio aria-label="Recorded voice request playback" controls src={clip} style={{width:'100%'}}/>}
    </div>}
    {error && <p role="status" style={{color:'#fde68a',overflowWrap:'anywhere'}}>{error}</p>}
    <div style={{maxHeight:instructor?180:240,overflowY:'auto'}}>
      {visible.map(r=><div key={r.id} style={{padding:'8px 0',borderTop:'1px solid #334155'}}>
        <strong>{CHANNELS[r.channel]}</strong> · {r.status}<div style={{overflowWrap:'anywhere'}}>{r.text}</div>
        {instructor && <div style={{display:'flex',gap:8,marginTop:6}}>
          <button disabled={busy} onClick={()=>emit('resolve_monitor_request',{id:r.id,decision:'reveal'})}>Reveal</button>
          <button disabled={busy} onClick={()=>emit('resolve_monitor_request',{id:r.id,decision:'decline'})}>Decline</button>
        </div>}
      </div>)}
      {instructor && !visible.length && <span>No pending requests. You can also reveal readings after a verbal request using Student display.</span>}
    </div>
  </section>;
}
