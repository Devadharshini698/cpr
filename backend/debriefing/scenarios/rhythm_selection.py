"""Explicit rhythm teaching drafts; not a validated patient physiology model."""
from ecg_state import RhythmType
from simman_engine.rhythm_intelligence import get_rhythm_default_hr
from physiology import normalize_monitor_state

LABELS = {
    'NSR':'Normal sinus rhythm', 'SINUS_BRADY':'Sinus bradycardia',
    'SINUS_TACHY':'Sinus tachycardia', 'AFIB':'Atrial fibrillation',
    'AFLUTTER':'Atrial flutter', 'JUNCTIONAL':'Junctional rhythm',
    'AVB1':'First-degree AV block', 'AVB2_I':'Mobitz I AV block',
    'AVB2_II':'Mobitz II AV block', 'AVB3':'Complete heart block',
    'PAC':'Premature atrial contractions', 'PVC':'Premature ventricular contractions',
    'SVT':'Supraventricular tachycardia', 'VT':'Ventricular tachycardia with pulse',
    'PVT':'Pulseless ventricular tachycardia', 'VF':'Ventricular fibrillation',
    'TORSADES':'Torsades de pointes (pulseless training case)',
    'ASYSTOLE':'Asystole', 'PEA':'Pulseless electrical activity',
    'LBBB':'Left bundle branch block', 'RBBB':'Right bundle branch block',
    'ANT_STEMI':'Anterior ST elevation pattern', 'INF_STEMI':'Inferior ST elevation pattern',
    'LAT_STEMI':'Lateral ST elevation pattern',
}

def rhythm_template(key, level):
    if key not in LABELS: raise ValueError('Select a supported monitor rhythm')
    arrest = key in {'VF','PVT','PEA','ASYSTOLE','TORSADES'}
    actions = ['Assess responsiveness, breathing and pulse', 'Call for appropriate help and allocate roles']
    if arrest:
        actions += ['Recognise cardiac arrest and initiate high-quality CPR',
                    'Identify shockable versus non-shockable rhythm and follow the local arrest protocol']
    else:
        actions += ['Assess perfusion and adverse signs, not ECG appearance alone',
                    'Obtain and interpret a 12-lead ECG where available; escalate appropriately']
    if key == 'SINUS_TACHY': actions += ['Identify and address the underlying cause of sinus tachycardia']
    if level != 'beginner': actions += ['Reassess response and explain the differential diagnosis']
    if level == 'advanced': actions += ['Lead a structured handover and justify escalation under resource constraints']
    return {
        'template_id':'RHYTHM-'+key, 'title':LABELS[key], 'rhythm_type':key,
        'patient':{'presentation': 'Unresponsive with no palpable pulse and absent normal breathing.' if arrest
                   else 'Patient has a palpable pulse; assess symptoms, perfusion and the displayed ECG before deciding management.'},
        'checklist':[{'action':action,'critical':index < 4,'window_sec':0} for index,action in enumerate(actions)],
        'hints':actions[:3], 'complications':[],
        'estimated_duration_min':{'beginner':8,'intermediate':12,'advanced':15},
    }

def rhythm_state(key):
    rhythm = RhythmType.VT if key == 'PVT' else RhythmType(key)
    hr = get_rhythm_default_hr(rhythm)
    arrest=key in {'VF','PVT','PEA','ASYSTOLE','TORSADES'}
    if key == 'PEA': hr=60
    state={'rhythm':rhythm.value,'HR':hr,'pulse_rate':0 if arrest else hr,
           'ABP_sys':110,'ABP_dia':70,'SpO2':97,'avRR':16,'etCO2':35,
           'PAP_sys':20,'PAP_dia':10,'CO':5,'Tblood':37,'emd_pea':key=='PEA'}
    if key in {'AVB3','VT'}: state.update(ABP_sys=85,ABP_dia=55)
    if arrest: state.update(avRR=0,etCO2=0)
    return normalize_monitor_state(state)
