"""Original paediatric respiratory teaching pilots; not a validated clinical monitor."""
from copy import deepcopy
from physiology import normalize_monitor_state

TOPIC = 'Respiratory distress/failure'
PROFILES = {'infant': {'age':0.5,'age_months':6,'weight_kg':7.5,'HR':150,'rr':55,'sys':85,'dia':50},
            'child': {'age':5,'age_months':60,'weight_kg':18,'HR':135,'rr':38,'sys':100,'dia':60}}

def monitor_profile(profile):
    # Teaching limits, not prescribed clinical alarm settings. Infant values use
    # RCH 6-month ranges; 5-year limits are an explicit interpolation of 4/6 years.
    hr, rr, systolic = ((110,170),(20,55),(75,105)) if profile=='infant' else ((78,145),(16,30),(78,113))
    return {'patient_profile':profile,'patient_age_months':PROFILES[profile]['age_months'],
        'patient_weight_kg':PROFILES[profile]['weight_kg'],
        'alarm_thresholds':{'HR':dict(zip(('low','high'),hr)), 'avRR':dict(zip(('low','high'),rr)),
            'ABP_sys':dict(zip(('low','high'),systolic)), 'SpO2':{'low':92,'high':100},'etCO2':{'low':30,'high':50}},
        'alarm_profile_note':'Illustrative paediatric teaching limits; faculty-adjustable, not clinical alarm prescriptions. Five-year bounds are interpolated.',
        'show_ibp':False, 'NBP_sys':None,'NBP_dia':None,'NBP_mean':None,
        'nibp_state':'IDLE','nibp_last_measured':None}
WARD_HISTORY = {
    'ER':'Caregiver reports cough, worsening breathing and reduced intake before arrival.',
    'ICU':'Receiving paediatric intensive care for a respiratory illness; review recent support and trends.',
    'Theatre':'Respiratory deterioration during recovery from anaesthesia; review airway, ventilation and recent drugs.',
    'Ward_Medical':'Admitted with a respiratory infection; caregiver reports increasing work of breathing.',
    'Ward_Surgical':'Postoperative respiratory deterioration; review airway, analgesia and aspiration risk.',
    'Ward_Ortho':'Recovering after an orthopaedic procedure; reassess ventilation after analgesia.',
    'Ward_Neuro':'Under neurological observation; breathing and responsiveness have changed from baseline.',
    'Ward_Cardio':'Under paediatric cardiac observation; compare respiratory findings with cardiac and fluid-balance history.',
}

def configure_respiratory_case(spec, profile='child', severity='distress'):
    if profile not in PROFILES or severity not in ('distress','failure'):
        raise ValueError('Choose infant or child and respiratory distress or failure')
    case=deepcopy(spec); p=PROFILES[profile]
    def stage(key, hr, rr, spo2, co2, description):
        state=normalize_monitor_state({'rhythm':'SINUS_TACHY','HR':hr,'pulse_rate':hr,
            'ABP_sys':p['sys'],'ABP_dia':p['dia'],'SpO2':spo2,'avRR':rr,'etCO2':co2,
            'Tblood':37.5,'Tperi':37.5,'PAP_sys':0,'PAP_dia':0,'CO':0,'emd_pea':False})
        return {'id':key,'name':key.replace('_',' ').title(),'description':description,'state':state}
    distress=stage('respiratory_distress',p['HR'],p['rr'],91,34,
        'Increased respiratory effort, recession and reduced feeding or speech appropriate to age; pulse present. Request and assess appearance, air entry and perfusion.')
    failure=stage('respiratory_failure',p['HR']+10,12,82,58,
        'Drowsiness, shallow ineffective breathing and reduced air entry with persistent hypoxaemia; pulse present. Less visible effort represents fatigue, not improvement.')
    recovery=stage('response_to_support',120 if profile=='infant' else 105,30 if profile=='infant' else 24,96,40,
        'Faculty-confirmed improvement after support. Reassess work of breathing, alertness, air entry and perfusion; normal monitor numbers alone do not establish recovery.')
    case.update(title=f'Paediatric respiratory emergency — {spec["location_label"]}',rhythm_type='SINUS_TACHY',clinical_severity=severity)
    case['patient']={**case['patient'],**{k:p[k] for k in ('age','age_months','weight_kg')},
        'history':WARD_HISTORY[spec['location']],
        'presentation':f'{p["age_months"]}-month-old, {p["weight_kg"]} kg fictional patient with respiratory {severity}. Pulse present. Initial team: '+', '.join(spec['discipline_labels'])}
    case['conditions']=([distress,failure] if severity=='distress' else [failure,distress])+[recovery]
    case['initial_state']=deepcopy(case['conditions'][0]['state'])
    case['initial_state'].update(monitor_profile(profile))
    case['paediatric_profile']=profile
    case['monitor_schema']='paediatric-respiratory-1'
    case['narration_intro']=case['patient']['presentation']
    actions=['Assess appearance, work of breathing and circulation before focusing on the monitor',
        'Assess airway patency, respiratory effort, air entry and adequacy of ventilation',
        'Confirm age and weight; obtain caregiver history, baseline and recent treatment',
        'Recognise fatigue and respiratory failure; escalate and support oxygenation and ventilation appropriately',
        'Request age-appropriate equipment and paediatric expertise; allocate tasks within competence',
        'Reassess breathing, pulse, perfusion and response after each intervention',
        'Communicate ongoing support and transfer needs to the receiving team']
    case['checklist']=[{'action':a,'critical':i in (0,1,3),'window_sec':0} for i,a in enumerate(actions)]
    case['hints']=actions[:3] if spec['level']=='beginner' else []
    case['complications']=[]
    case['release_status']='teaching_pilot_faculty_review'
    case['teaching_notes']={'authorship':'Independent fictional case; faculty review pending',
        'limitations':'Numerical rates and waveforms are synchronised for teaching; ECG morphology is generic, not a validated age-specific diagnostic ECG. Arrest escalation remains separate future work. No automated clinical grade. Invasive channels are hidden and not configured.',
        'readings':'Illustrative patient values, not age-normal ranges or treatment targets. EtCO2 assumes a usable sampling interface; it is not interchangeable with arterial CO2.',
        'resources':'Adult ward labels are reused as locations only; paediatric equipment, staffing and actual resource availability require faculty confirmation.',
        'reference':'https://cpr.heart.org/en/resuscitation-science/cpr-and-ecc-guidelines/pediatric-basic-life-support'}
    return case
