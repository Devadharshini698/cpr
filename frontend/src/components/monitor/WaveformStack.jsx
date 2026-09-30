import { useLayoutEffect, useMemo, useRef, useState } from "react";
import useMonitorStore from "../../store/monitorStore";
import ECGTrack from "./ECGTrack";
import PlethTrack from "./PlethTrack";
import ABPTrack from "./ABPTrack";
import PAPTrack from "./PAPTrack";
import ETCO2Track from "./ETCO2Track";
import VitalsPanel from './VitalsPanel';
import { studentVisible } from '../../utils/studentDisplay';
import { channelEnabled, channelConfigured } from '../../utils/monitorChannels';
import "./VitalsPanel.css";
const TRACK_GAP = 4;

export default function WaveformStack({ lead = "II", onVitalClick, alignedVitals = false, isStudent = false }) {
  const stackRef = useRef(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  const state = useMonitorStore();
  const neonatal=state.patient_profile==='neonate';
  const visible = key => studentVisible(state,isStudent,key);
  const hiddenInitially = isStudent && state.initial_readings_hidden;
  const showEcg = !hiddenInitially && channelEnabled(state,'ecg') && visible('ecg_wave');
  const showPacer = state.pacer && (!isStudent || state.pacer.visible);
  const pacing = showPacer && state.pacer.enabled;
  const pacerHeaderHeight = showPacer ? 24 : 0;
  const showPleth = !hiddenInitially && channelEnabled(state,'pleth') && visible('pleth_wave');
  const showResp = !hiddenInitially && channelEnabled(state,'co2') && visible('co2_wave');
  const showAbp = !hiddenInitially && channelEnabled(state,'abp') && visible('abp_wave');
  const showPap = !hiddenInitially && channelEnabled(state,'pap') && visible('pap_wave');
  const ecgRow = showEcg || (alignedVitals && state.show_hr !== false && visible('hr'));
  const plethRow = showPleth || (alignedVitals && state.show_spo2 !== false && visible('spo2'));
  const abpRow = showAbp || (alignedVitals && channelEnabled(state,'abp') && visible('abp'));
  const papRow = showPap || (alignedVitals && channelEnabled(state,'pap') && visible('pap'));
  const co2Row = showResp || (alignedVitals && ((state.show_etco2 !== false && visible('etco2')) || (state.show_rr !== false && visible('rr'))));

  useLayoutEffect(() => {
    const element = stackRef.current;
    if (!element) return undefined;

    const readSize = () => {
      setSize({
        width: Math.floor(element.clientWidth),
        height: Math.floor(element.clientHeight),
      });
    };

    readSize();
    const observer = new ResizeObserver(readSize);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const activeTracks = useMemo(() => {
    const tracks = [];
    if (ecgRow) tracks.push("ecg");
    if (plethRow) tracks.push("pleth");
    if (abpRow) tracks.push("abp");
    if (papRow) tracks.push("pap");
    if (co2Row) tracks.push("etco2");
    return tracks;
  }, [ecgRow, plethRow, abpRow, papRow, co2Row]);

  const trackCount = activeTracks.length || 1;

  const trackSize = useMemo(() => {
    const width = Math.max(100, (size.width || 800) - (alignedVitals ? 180 : 0));
    const totalGaps = TRACK_GAP * (trackCount - 1);
    const availableHeight = Math.max(100, (size.height || 400) - totalGaps - 4 - (neonatal?40:0));
    const height = Math.max(40, Math.floor(availableHeight / trackCount));
    return { width, height };
  }, [size, trackCount, alignedVitals, neonatal]);

  const plethGain = useMemo(
    () => Math.max(8, Math.min(42, (trackSize.height - 31) / 1.75)),
    [trackSize.height]
  );
  const row = (key, label, track) => {
    const configured = channelConfigured(state,key === 'etco2' ? 'co2' : key);
    const content = track && !configured ? <div style={{height:trackSize.height,display:'grid',placeItems:'center',background:'#070b0f',color:'#94a3b8'}}>{label} — Not configured</div> : track;
    return alignedVitals ? (
    <div key={key} style={{display:'grid', gridTemplateColumns:'minmax(0, 1fr) 176px', gap:4, height:trackSize.height, minHeight:40}}>
      <div style={{minWidth:0, overflow:'hidden'}}>{content || <div style={{height:'100%',display:'grid',placeItems:'center',color:'#64748b',background:'#070b0f'}}>{label} waveform not displayed</div>}</div>
      <VitalsPanel groups={[label]} compact isStudent={isStudent} onVitalClick={onVitalClick} />
    </div>
  ) : <div key={key}>{content}</div>;
  };

  return (
    <div ref={stackRef} className="waveform-stack" style={{ display: "flex", flexDirection: "column", gap: `${TRACK_GAP}px`, height: "100%", overflow: "hidden" }}>
      {neonatal&&<div style={{height:36,flexShrink:0,fontSize:12,padding:'2px 8px',boxSizing:'border-box',color:'#e2e8f0',background:'#0f172a'}}>
        Newborn · {state.gestational_age_weeks} weeks · {state.patient_weight_kg} kg · Case age: {state.neonatal_age_minutes} min after birth<br/>
        Faculty-selected birth age — not the session timer
      </div>}
      {ecgRow && row('ecg','ECG',showEcg && <div>
        {showPacer && <div style={{height:24,boxSizing:'border-box',padding:'3px 8px',background:'#0f172a',color:'#fde047',fontSize:12,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}} title="Pacer settings, not measured pulse rate">
          PACER {pacing?'ON':'OFF'} · {(state.pacer.mode||'fixed').toUpperCase()} · Set {state.pacer.rate}/min · {state.pacer.output} mA · {state.pacer.pads_connected?'Pads connected':'Pads disconnected'}
        </div>}
        <ECGTrack lead={lead} width={trackSize.width} height={Math.max(16,trackSize.height-pacerHeaderHeight)} gain={pacing?Math.max(1,Math.min(10,(trackSize.height-pacerHeaderHeight-12)/20)):10} />
      </div>)}
      {plethRow && row('pleth','SpO₂',showPleth && <PlethTrack width={trackSize.width} height={trackSize.height} gain={plethGain} />)}
      {abpRow && row('abp','ABP',showAbp && <ABPTrack width={trackSize.width} height={trackSize.height} />)}
      {papRow && row('pap','PAP',showPap && <PAPTrack width={trackSize.width} height={trackSize.height} />)}
      {co2Row && row('etco2','CO₂',showResp && <ETCO2Track width={trackSize.width} height={trackSize.height} />)}
      {!activeTracks.length && <p style={{padding:24,color:'#94a3b8'}}>Monitoring has not been revealed. Ask your instructor or use the Requests panel.</p>}
    </div>
  );
}
