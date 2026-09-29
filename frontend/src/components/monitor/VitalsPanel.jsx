import useMonitorStore from "../../store/monitorStore";
import socket from "../../socket";
import { studentVisible } from '../../utils/studentDisplay';

const VITAL_GROUPS = [
  {
    label: "ECG",
    color: "#00FF00",
    items: [
      { key: "HR", label: "HR", unit: "bpm", size: "xl" },
    ],
  },
  {
    label: "SpO₂",
    color: "#FFFF00",
    items: [
      { key: "SpO2", label: "SpO₂", unit: "%", size: "xl" },
    ],
  },
  {
    label: "NIBP",
    color: "#FF33AA",
    items: [
      { key: "NBP_sys", label: "NIBP", unit: "mmHg", size: "lg", paired: "NBP_dia", separator: "/" },
    ],
  },
  {
    label: "ABP",
    color: "#FF3333",
    items: [
      { key: "ABP_sys", label: "ABP", unit: "mmHg", size: "lg", paired: "ABP_dia", separator: "/" },
    ],
  },
  {
    label: "PAP",
    color: "#FFFF00",
    items: [
      { key: "PAP_sys", label: "PAP", unit: "mmHg", size: "md", paired: "PAP_dia", separator: "/" },
    ],
  },
  {
    label: "CO₂",
    color: "#EEEEEE",
    items: [
      { key: "etCO2", label: "etCO₂", unit: "mmHg", size: "lg", highlight: true },
      { key: "avRR", label: "awRR", unit: "/min", size: "md" },
    ],
  },
  {
    label: "Temp",
    color: "#CC99FF",
    items: [
      { key: "Tperi", label: "T peri", unit: "°C", size: "md" },
      { key: "Tblood", label: "T blood", unit: "°C", size: "md" },
    ],
  },
  {
    label: "CO",
    color: "#FF66CC",
    items: [
      { key: "CO", label: "CO", unit: "L/min", size: "md" },
    ],
  },
];

const SIZE_CLASSES = {
  xl: "text-5xl font-bold font-mono",
  lg: "text-3xl font-bold font-mono",
  md: "text-2xl font-bold font-mono",
};

const COMPACT_SIZE_CLASSES = {
  xl: "text-2xl font-bold font-mono",
  lg: "text-xl font-bold font-mono",
  md: "text-lg font-bold font-mono",
};

export default function VitalsPanel({ onVitalClick, compact, isStudent, renderPopover, groups }) {
  const state = useMonitorStore();
  const classes = compact ? COMPACT_SIZE_CLASSES : SIZE_CLASSES;
  const isHidden = isStudent && state.initial_readings_hidden;

  const isGroupVisible = (label) => {
    const key = {ECG:'hr', 'SpO₂':'spo2', NIBP:'nibp', ABP:'abp', PAP:'pap', Temp:'temp', CO:'co'}[label];
    if (key && !studentVisible(state, isStudent, key)) return false;
    if (label === 'CO₂' && !studentVisible(state,isStudent,'etco2') && !studentVisible(state,isStudent,'rr')) return false;
    if (label === "ECG") return state.show_hr !== false;
    if (label === "SpO₂") return state.show_spo2 !== false;
    if (label === "NIBP") return state.show_nibp !== false;
    if (label === "ABP") return state.show_ibp !== false;
    if (label === "PAP") return state.show_ibp !== false;
    if (label === "CO₂") return (state.show_etco2 !== false || state.show_rr !== false);
    if (label === "Temp") return state.show_temp !== false;
    if (label === "CO") return state.show_ibp !== false;
    return true;
  };

  const isItemVisible = (key) => {
    if (key === 'etCO2' && !studentVisible(state,isStudent,'etco2')) return false;
    if (key === 'avRR' && !studentVisible(state,isStudent,'rr')) return false;
    if (key === "etCO2") return state.show_etco2 !== false;
    if (key === "avRR") return state.show_rr !== false;
    return true;
  };

  return (
    <div className="vitals-panel" style={{ minWidth: 0, boxSizing: 'border-box', ...(compact ? { gap: "3px", padding: "2px", overflow: "hidden" } : {}), display: "flex", flexDirection: "column", height: "100%", justifyContent: "space-between" }}>
      {VITAL_GROUPS.filter(g => (!groups || groups.includes(g.label)) && isGroupVisible(g.label)).map((group) => (
        <div key={group.label} className="vital-brick" style={{ ...(compact ? { padding: "3px 6px", margin: 0, borderRadius: "4px" } : {}), display: "flex", flexDirection: "column", justifyContent: "center", flex: 1 }}>
          <div className="vital-brick-label" style={{ color: group.color, fontSize: compact ? "11px" : "12px", marginBottom: "1px" }}>
            {group.label}
          </div>
          {group.items.filter(i => isItemVisible(i.key)).map((item) => {
            const val = state[item.key];
            let displayVal = item.paired
              ? `${Math.round(val)}/${Math.round(state[item.paired])}`
              : typeof val === "number"
              ? val % 1 === 0
                ? val
                : val.toFixed(1)
              : val;

            if (isHidden) {
              displayVal = item.paired ? "--/--" : "--";
            }

            if (group.label === "NIBP" && !isHidden) {
              const ns = state.nibp_state || "IDLE";
              if (ns === "INFLATING") displayVal = "Inflating...";
              else if (ns === "MEASURING") displayVal = "Measuring...";
              else if (ns === "PROCESSING") displayVal = "Processing...";
              else if (ns === "IDLE") displayVal = "Cuff Idle";
              else if (ns === "UNOBTAINABLE") displayVal = "Unobtainable";
              else if (!(val > 0) || !(state[item.paired] > 0)) displayVal = "No valid reading";
            }

            const showSublabel = !["HR", "SpO₂", "ABP", "PAP", "CO", "NIBP"].includes(item.label);

            return (
              <div
                key={item.key}
                className={`vital-value-row ${item.highlight ? "vital-highlight" : ""}`}
                role={onVitalClick ? 'button' : undefined}
                tabIndex={onVitalClick ? 0 : undefined}
                aria-label={onVitalClick ? `Edit ${item.label}` : undefined}
                onKeyDown={event => { if (event.target === event.currentTarget && onVitalClick && ['Enter', ' '].includes(event.key)) { event.preventDefault(); onVitalClick(group.label === 'NIBP' ? 'nbp' : item.key); } }}
                onClick={() => onVitalClick && onVitalClick(group.label === "NIBP" ? "nbp" : item.key)}
                style={{ display: 'flex', alignItems: 'baseline', cursor: onVitalClick ? "pointer" : "default", flexWrap: "wrap", minWidth: 0, gap: compact ? "4px" : "8px" }}
              >
                {showSublabel && (
                  <span className="vital-sublabel" style={{ color: group.color, fontSize: compact ? "11px" : "12px" }}>
                    {item.label}
                  </span>
                )}
                <span
                  className={classes[item.size]}
                  style={{ color: group.color, ...(group.label === 'NIBP' && typeof displayVal === 'string' && !displayVal.includes('/') ? {fontSize: compact ? 14 : 18} : {}) }}
                >
                  {displayVal}
                </span>
                <span className="vital-unit" style={{ fontSize: compact ? "11px" : "12px" }}>{item.unit}</span>
                {group.label === "NIBP" && !isStudent && <button type="button"
                  disabled={["INFLATING", "MEASURING", "PROCESSING"].includes(state.nibp_state)}
                  onClick={(event) => { event.stopPropagation(); socket.emit("measure_nibp"); }}
                  style={{ fontSize: 11, padding: 5, border: '1px solid #FF33AA', borderRadius: 5, color: '#FF33AA' }}>
                  Measure NIBP
                </button>}
                {group.label === "NIBP" && state.nibp_last_measured && !isHidden &&
                  <small title="Last cuff cycle (not continuous blood pressure)">{new Date(state.nibp_last_measured + (state.nibp_last_measured.endsWith('Z') ? '' : 'Z')).toLocaleTimeString()}</small>}
                {group.label === "NIBP" && state.NBP_sys > 0 && state.NBP_dia > 0 && (state.nibp_state === "COMPLETE" || !state.nibp_state) && state.show_map !== false && !isHidden && (
                  <div className="vital-nibp-map" style={{ fontSize: compact ? "11px" : "13px", color: group.color, marginTop: "1px" }}>
                    MAP {Math.round(state.NBP_mean ?? 93)}
                  </div>
                )}
                {renderPopover && renderPopover(item.key)}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
