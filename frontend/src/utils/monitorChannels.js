export const CHANNELS = [['ecg','ECG'], ['pleth','Pleth'], ['abp','ABP'], ['pap','PAP'], ['co2','Capnography']];
const legacy = {ecg:'show_ecg', pleth:'show_pleth', abp:'show_ibp', pap:'show_ibp', co2:'show_resp'};
export const channelEnabled = (state, key) => state.waveform_channels?.[key] ?? (state[legacy[key]] !== false);
// Missing metadata preserves existing cases. Explicit false is never inferred from a zero reading.
export const channelConfigured = (state, key) => state.configured_channels?.[key] ?? (state[legacy[key]] !== false);
