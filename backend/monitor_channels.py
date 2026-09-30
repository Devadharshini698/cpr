"""Simulated sensor setup, independent of student disclosure and patient pulse."""
from copy import deepcopy
from math import isfinite
from physiology import apply_perfusion_intent

LEGACY = dict(ecg='show_ecg', pleth='show_pleth', abp='show_ibp', pap='show_ibp', co2='show_resp')

def initialise_channels(state):
    result = deepcopy(state)
    defaults = {key: state.get(flag) is not False for key, flag in LEGACY.items()}
    result['configured_channels'] = {**defaults, **state.get('configured_channels', {})}
    result['waveform_channels'] = {**defaults, **state.get('waveform_channels', {})}
    return result

def configure_channel(state, data):
    if not isinstance(data, dict) or set(data) != {'channel', 'configured', 'values'}:
        raise ValueError('Provide channel, configured and values')
    channel = data['channel']
    if not isinstance(channel, str) or channel not in LEGACY or type(data['configured']) is not bool or not isinstance(data['values'], dict):
        raise ValueError('Invalid channel configuration')
    fields = {'pap': {'PAP_sys':120, 'PAP_dia':100}, 'co2': {'etCO2':150, 'avRR':80}}.get(channel, {}) if data['configured'] else {}
    if set(data['values']) != set(fields):
        raise ValueError('Review all measurements for this channel')
    for key, limit in fields.items():
        value = data['values'][key]
        if type(value) not in (int, float) or not isfinite(value) or not 0 <= value <= limit:
            raise ValueError(f'{key} must be between 0 and {limit}')
    result = initialise_channels(state)
    result.update(data['values'])
    if data['values']:
        result = apply_perfusion_intent(result, data['values'])
    result['configured_channels'][channel] = data['configured']
    if data['configured']:
        result['waveform_channels'][channel] = True
        if channel == 'co2': result['show_etco2'] = True
    return result
