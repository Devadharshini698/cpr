import { useLayoutEffect, useMemo, useRef, useState } from "react";
import useMonitorStore from "../../store/monitorStore";
import ECGTrack from "./ECGTrack";
import PlethTrack from "./PlethTrack";
import ABPTrack from "./ABPTrack";
import PAPTrack from "./PAPTrack";
import ETCO2Track from "./ETCO2Track";
import VitalsPanel from './VitalsPanel';
import { studentVisible } from '../../utils/studentDisplay';
import "./VitalsPanel.css";
const TRACK_GAP = 4;

export default function WaveformStack({ lead = "II", onVitalClick, alignedVitals = false, isStudent = false }) {
  const stackRef = useRef(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  const state = useMonitorStore();
  const visible = key => studentVisible(state,isStudent,key);
  const hiddenInitially = isStudent && state.initial_readings_hidden;
  const showEcg = !hiddenInitially && state.show_ecg !== false && visible('ecg_wave');
  const showPleth = !hiddenInitially && state.show_pleth !== false && visible('pleth_wave');
  const showResp = !hiddenInitially && state.show_resp !== false && visible('co2_wave');
  const showAbp = !hiddenInitially && state.show_ibp !== false && visible('abp_wave');
  const showPap = !hiddenInitially && state.show_ibp !== false && visible('pap_wave');
  const ecgRow = showEcg || (alignedVitals && state.show_hr !== false && visible('hr'));
  const plethRow = showPleth || (alignedVitals && state.show_spo2 !== false && visible('spo2'));
  const abpRow = showAbp || (alignedVitals && state.show_ibp !== false && visible('abp'));
  const papRow = showPap || (alignedVitals && state.show_ibp !== false && visible('pap'));
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
    const availableHeight = Math.max(100, (size.height || 400) - totalGaps - 4);
    const height = Math.max(40, Math.floor(availableHeight / trackCount));
    return { width, height };
  }, [size, trackCount, alignedVitals]);

  const plethGain = useMemo(
    () => Math.max(8, Math.min(42, (trackSize.height - 31) / 1.75)),
    [trackSize.height]
  );
  const row = (key, label, track) => alignedVitals ? (
    <div key={key} style={{display:'grid', gridTemplateColumns:'minmax(0, 1fr) 176px', gap:4, height:trackSize.height, minHeight:40}}>
      <div style={{minWidth:0, overflow:'hidden'}}>{track || <div style={{height:'100%',display:'grid',placeItems:'center',color:'#64748b',background:'#070b0f'}}>{label} waveform not displayed</div>}</div>
      <VitalsPanel groups={[label]} compact isStudent={isStudent} onVitalClick={onVitalClick} />
    </div>
  ) : track;

  return (
    <div ref={stackRef} className="waveform-stack" style={{ display: "flex", flexDirection: "column", gap: `${TRACK_GAP}px`, height: "100%", overflow: "hidden" }}>
      {ecgRow && row('ecg','ECG',showEcg && <ECGTrack lead={lead} width={trackSize.width} height={trackSize.height} />)}
      {plethRow && row('pleth','SpO₂',showPleth && <PlethTrack width={trackSize.width} height={trackSize.height} gain={plethGain} />)}
      {abpRow && row('abp','ABP',showAbp && <ABPTrack width={trackSize.width} height={trackSize.height} />)}
      {papRow && row('pap','PAP',showPap && <PAPTrack width={trackSize.width} height={trackSize.height} />)}
      {co2Row && row('etco2','CO₂',showResp && <ETCO2Track width={trackSize.width} height={trackSize.height} />)}
      {!activeTracks.length && <p style={{padding:24,color:'#94a3b8'}}>Monitoring has not been revealed. Ask your instructor or use the Requests panel.</p>}
    </div>
  );
}
