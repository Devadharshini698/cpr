"""Consistency checks for simulated monitor values, not a clinical patient model."""
import math


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
