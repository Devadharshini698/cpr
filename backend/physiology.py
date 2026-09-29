"""Consistency checks for simulated monitor values, not a clinical patient model."""
import math


def apply_perfusion_intent(state, updates):
    """ECG rhythm and palpable pulse are distinct instructor decisions."""
    result = dict(state)
    if 'pulse_present' in updates:
        if type(updates['pulse_present']) is not bool:
            raise ValueError('Pulse present must be a boolean')
        present = updates['pulse_present']
        rhythm = str(result.get('rhythm', '')).upper()
        if present and (rhythm in {'VF', 'VENTRICULAR FIBRILLATION', 'ASYSTOLE', 'PEA'} or float(result.get('HR', 0)) <= 0):
            raise ValueError('Select a perfusing rhythm and positive heart rate before confirming ROSC')
        result['pulse_rate'] = float(result.get('HR', 0)) if present else 0.0
        result['emd_pea'] = False if present else result.get('emd_pea', False)
    elif 'HR' in updates and result.get('pulse_rate', 0) > 0:
        result['pulse_rate'] = updates['HR']
    # Never acknowledge a positive value that normalization will silently erase.
    # Explicit arrest transitions may intentionally clear previous measurements.
    pulseless = (result.get('emd_pea', False) or
                 str(result.get('rhythm', '')).upper() in {'VF', 'VENTRICULAR FIBRILLATION', 'ASYSTOLE', 'PEA'} or
                 float(result.get('pulse_rate', result.get('HR', 0)) or 0) <= 0)
    dependent = ('SpO2', 'ABP_sys', 'ABP_dia', 'PAP_sys', 'PAP_dia', 'CO')
    if pulseless and updates.get('pulse_present') is not False:
        if any(key in updates and float(updates[key]) > 0 for key in dependent):
            raise ValueError('Patient is still set to pulseless. Open ECG / heart rate, confirm simulated ROSC and review the values, then apply. Changing rhythm alone does not restore pulse.')
    if 'etCO2' in updates and float(updates['etCO2']) > 0 and result.get('avRR') == 0:
        raise ValueError('Set a positive simulated respiratory / ventilation rate before applying a positive EtCO2 value.')
    result.pop('pulse_present', None)
    return normalize_monitor_state(result)


def normalize_monitor_state(values):
    state = dict(values)
    rhythm = str(state.get('rhythm', '')).upper()
    pulseless = (state.get('emd_pea', False) or rhythm in
                 {'VF', 'VENTRICULAR FIBRILLATION', 'ASYSTOLE', 'PEA'} or
                 float(state.get('pulse_rate', state.get('HR', 0)) or 0) <= 0)
    for key in ('HR', 'pulse_rate', 'SpO2', 'ABP_sys', 'ABP_dia', 'avRR', 'etCO2', 'PAP_sys', 'PAP_dia', 'CO'):
        if key in state:
            number = float(state[key])
            if not math.isfinite(number) or number < 0:
                raise ValueError(f'{key} must be a finite non-negative value')
            state[key] = number
    if pulseless:
        for key in ('pulse_rate', 'ABP_sys', 'ABP_dia', 'MAP', 'PAP_sys', 'PAP_dia', 'PAP_mean', 'CO', 'SpO2'):
            state[key] = 0.0
    if rhythm in {'VF', 'VENTRICULAR FIBRILLATION', 'ASYSTOLE'}:
        state['HR'] = 0.0
    if state.get('avRR') == 0:
        state['etCO2'] = 0.0
    for sys, dia, mean in [('ABP_sys', 'ABP_dia', 'MAP'), ('PAP_sys', 'PAP_dia', 'PAP_mean')]:
        if sys in state and dia in state:
            if state[sys] < state[dia]:
                raise ValueError(f'{sys} cannot be lower than {dia}')
            state[mean] = round((state[sys] + 2 * state[dia]) / 3, 1)
    return state
