"""Independent paediatric arrest pilot with explicit instructor-confirmed ROSC."""
from copy import deepcopy
from physiology import normalize_monitor_state
from debriefing.scenarios.rhythm_selection import rhythm_state
from debriefing.scenarios.paediatric_respiratory import configure_respiratory_case, PROFILES, monitor_profile

CONTEXTS={'respiratory':'Increasing breathing difficulty and reduced responsiveness before collapse.',
          'shock':'Progressive abnormal perfusion and reduced responsiveness before collapse.',
          'sudden':'Sudden witnessed collapse; review cardiac history, preceding symptoms and reversible causes.'}

def configure_paediatric_arrest(spec, profile='child', context='respiratory', initial_rhythm=None):
    if profile not in PROFILES or context not in CONTEXTS:
        raise ValueError('Select a supported patient profile and arrest context')
    rhythm=initial_rhythm or ('VF' if context=='sudden' else 'PEA')
    if rhythm not in ('PEA','ASYSTOLE','VF','PVT'):
        raise ValueError('Initial arrest rhythm must be pulseless')
    case=configure_respiratory_case(spec,profile); p=PROFILES[profile]
    def arrest_stage(key,name,selected):
        state=rhythm_state(selected)
        state.update(Tperi=37,Tblood=37)
        if selected=='PEA': state['HR']=60
        if selected=='PVT': state['HR']=220 if profile=='infant' else 190
        return {'id':key,'name':name,'description':'Unresponsive, no normal breathing and no palpable pulse. ECG appearance alone does not establish circulation. Zero SpO2 denotes no modelled perfusing signal, not measured saturation. Compression-generated circulation is not simulated.','state':normalize_monitor_state(state)}
    initial=arrest_stage('paediatric_arrest','Cardiac arrest',rhythm)
    ongoing=arrest_stage('ongoing_arrest','Ongoing arrest — reassess rhythm',rhythm)
    rosc_state=normalize_monitor_state({'rhythm':'NSR','HR':130 if profile=='infant' else 110,
        'pulse_rate':130 if profile=='infant' else 110,'ABP_sys':p['sys'],'ABP_dia':p['dia'],
        'SpO2':95,'avRR':30 if profile=='infant' else 24,'etCO2':38,'PAP_sys':0,'PAP_dia':0,
        'CO':0,'Tblood':37,'Tperi':37,'emd_pea':False})
    rosc={'id':'paediatric_rosc','name':'ROSC — confirmed palpable pulse',
        'description':'Faculty confirms circulation. Reassess airway, ventilation, perfusion and neurological status; these illustrative numbers are not treatment targets or proof of neurological recovery.', 'state':rosc_state}
    case['conditions']=[initial,ongoing,rosc]
    if spec['level']=='advanced': case['conditions'].append(arrest_stage('recurrent_arrest','Optional recurrent arrest','PEA'))
    case['initial_state']={**deepcopy(initial['state']),**monitor_profile(profile)}
    case.update(title=f'Paediatric cardiac arrest — {spec["location_label"]}',rhythm_type=rhythm,
        clinical_severity='cardiac_arrest',arrest_context=context,monitor_schema='paediatric-arrest-1')
    case['patient']['history']=f'Under assessment in {spec["location_label"]}. '+CONTEXTS[context]
    case['patient']['presentation']=f'{p["age_months"]}-month-old, {p["weight_kg"]} kg patient is unresponsive with no normal breathing or palpable pulse. Initial team: '+', '.join(spec['discipline_labels'])
    case['narration_intro']=case['patient']['presentation']
    actions=['Assess responsiveness, breathing and pulse; recognise cardiac arrest',
        'Call for paediatric help, allocate roles and request age-appropriate equipment',
        'Provide high-quality CPR with ventilation and minimise interruptions',
        'Distinguish shockable from non-shockable rhythms; defibrillate only when indicated',
        'Confirm weight and follow the current paediatric protocol for equipment, energy and medication decisions',
        'Investigate and address reversible causes without unnecessary CPR interruption',
        'Reassess rhythm and circulation; do not equate an organised ECG with ROSC',
        'After confirmed ROSC, reassess oxygenation, ventilation, haemodynamics and neurological status and arrange ongoing care']
    case['checklist']=[{'action':a,'critical':i in (0,2,3,6),'window_sec':0} for i,a in enumerate(actions)]
    case['hints']=actions[:3] if spec['level']=='beginner' else []
    case['teaching_notes']['limitations']='Manual teaching pilot; no automatic CPR-generated circulation, drug or shock response, or validated paediatric scoring. Generic ECG morphology. Instructor may change any rhythm; ROSC requires explicit pulse confirmation.'
    case['teaching_notes']['reference']='https://publications.aap.org/pediatrics/article/doi/10.1542/peds.2025-074351/205236'
    return case
