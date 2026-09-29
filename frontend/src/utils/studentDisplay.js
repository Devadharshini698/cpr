// Presentation controls, not an access-control boundary for physiological data.
export const STUDENT_DISPLAY_FIELDS = [
  ['ecg_wave', 'ECG waveform'], ['hr', 'Heart rate'],
  ['pleth_wave', 'Pleth waveform'], ['spo2', 'SpO₂ value'],
  ['abp_wave', 'ABP waveform'], ['abp', 'ABP values'],
  ['pap_wave', 'PAP waveform'], ['pap', 'PAP values'],
  ['co2_wave', 'CO₂ waveform'], ['etco2', 'EtCO₂ value'], ['rr', 'Respiratory rate'],
  ['nibp', 'NIBP / MAP'], ['temp', 'Temperatures'], ['co', 'Cardiac output'],
  ['alarms', 'Alarm banner and sound'],
];
export const DEFAULT_STUDENT_DISPLAY = Object.fromEntries(STUDENT_DISPLAY_FIELDS.map(([key]) => [key, false]));
export const studentVisible = (state, isStudent, key) => !isStudent || state.student_display?.[key] === true;

export function displayedAlarms(state, isStudent) {
  if (isStudent && (state.initial_readings_hidden || !studentVisible(state,true,'alarms'))) return [];
  const keys = {HR:'hr', SpO2:'spo2', DESAT:'spo2', APNEA:'rr', avRR:'rr', etCO2:'etco2',
    ABP_sys:'abp', ABP_dia:'abp', MAP:'abp', PAP_sys:'pap', PAP_dia:'pap',
    NBP_sys:'nibp', NBP_dia:'nibp', NBP_mean:'nibp', Tblood:'temp', Tperi:'temp', CO:'co'};
  return (state.alarms || []).filter(alarm => studentVisible(state,isStudent,keys[alarm.split(' ')[0]]));
}
