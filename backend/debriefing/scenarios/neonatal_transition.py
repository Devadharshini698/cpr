"""Independent birth-transition teaching cases; not an NRP course or device."""
from copy import deepcopy
from physiology import normalize_monitor_state

TOPIC='Preparation and transition at birth'
PROFILES={'term':(39,3.2),'late_preterm':(35,2.3)}
SETTINGS={
    'delivery_room':('Delivery room','Vaginal birth; confirm maternal history, antenatal risk factors and the newborn-care team before delivery.'),
    'theatre':('Obstetric theatre','Caesarean birth; request maternal anaesthetic and fetal history and confirm a separate newborn-care provider and warming area.'),
    'emergency':('Emergency department birth','Unexpected birth in the emergency department; gestation is the fictional case estimate. Mobilise neonatal expertise and verify available warming, ventilation and transfer resources.'),
}
REFERENCE='https://cpr.heart.org/en/resuscitation-science/cpr-and-ecc-guidelines/neonatal-resuscitation'

def configure_neonatal_transition(spec,profile='term',course='vigorous',setting='delivery_room'):
    if profile not in PROFILES or course not in ('vigorous','poor_transition') or setting not in SETTINGS:
        raise ValueError('Select term/late-preterm, vigorous/poor transition and a supported birth setting')
    case=deepcopy(spec)
    weeks,weight=PROFILES[profile]
    label,history=SETTINGS[setting]
    def stage(key,name,minute,hr,rr,spo2,temp,description):
        low,high={2:(65,70),5:(80,85),10:(85,95)}[minute]
        state=normalize_monitor_state(dict(rhythm='NSR',HR=hr,pulse_rate=hr,
            ABP_sys=60 if profile=='term' else 55,ABP_dia=35 if profile=='term' else 30,
            SpO2=spo2,avRR=rr,etCO2=0,Tblood=temp,Tperi=temp,
            PAP_sys=0,PAP_dia=0,CO=0,emd_pea=False))
        state.update(patient_profile='neonate',patient_age_months=0,patient_weight_kg=weight,
            gestational_age_weeks=weeks,neonatal_age_minutes=minute,
            neonatal_age_note='Faculty-selected case time, not elapsed session time',
            alarm_thresholds={'HR':{'low':100,'high':180},'avRR':{'low':30,'high':60},
                'SpO2':{'low':low,'high':high},'Tperi':{'low':36.5,'high':37.5}},
            alarm_profile_note=f'Teaching limits only. Preductal SpO2 reference at {minute} minutes: {low}–{high}%. Stage time is manually selected, not a treatment target clock.')
        return dict(id=key,name=name,description=description,state=state)
    good=stage('neonatal_vigorous','Vigorous transition — 2 min',2,150,45,68,36.8,
        'Good flexor tone, regular breathing and a strong cry. Continue thermal care and assessment; do not diagnose hypoxaemia using adult saturation expectations. Monitoring values are available only when faculty reveals them.')
    poor=stage('neonatal_poor_transition','Poor transition — 2 min',2,90,0,55,36.2,
        'Reduced tone and no effective spontaneous breathing; heart rate is present but low for transition. Escalate promptly and provide appropriate ventilation without waiting for oximetry. This is not adult pulseless arrest.')
    response=stage('neonatal_response','Faculty-confirmed response — 5 min',5,140,40,83,36.6,
        'Spontaneous breathing and tone improve after faculty-confirmed effective support. Reassess chest movement, heart rate, temperature and preductal saturation; numbers alone do not prove ventilation was effective.')
    stable=stage('neonatal_stabilisation','Ongoing assessment — 10 min',10,145,42,92,36.8,
        'Regular spontaneous breathing and improved tone. Determine continuing observation, feeding, glucose assessment and neonatal-team handover needs from the preceding course; this state is not discharge clearance.')
    case.update(title=f'Newborn preparation and transition — {label}',location_label=label,
        neonatal_profile=profile,neonatal_setting=setting,clinical_severity=course,
        monitor_schema='neonatal-transition-1',rhythm_type='NSR',release_status='teaching_pilot_faculty_review')
    case['patient']=dict(age=0,age_months=0,weight_kg=weight,gestational_age_weeks=weeks,
        history=history,presentation=f'Fictional newborn at 2 minutes after birth: {weeks} weeks, {weight} kg, {course.replace("_"," ")}. Birth setting: {label}. Team: '+', '.join(spec['discipline_labels']))
    case['conditions']=([good,poor] if course=='vigorous' else [poor])+[response,stable]
    case['initial_state']=deepcopy(case['conditions'][0]['state'])
    case['initial_state'].update(show_ibp=False,show_etco2=False,show_resp=False,show_co=False,
        NBP_sys=None,NBP_dia=None,NBP_mean=None,nibp_state='IDLE',nibp_last_measured=None)
    actions=[
        'Before birth, review perinatal risks, identify a newborn-care provider and check warming, ventilation, monitoring and escalation resources',
        'Assess gestation, breathing or crying and tone; decide routine transition care versus immediate support',
        'Plan cord management according to infant condition and available expertise; do not delay necessary support',
        'Provide appropriate thermal care and reassess temperature',
        'Assess heart rate and breathing; recognise that apnoea or ineffective breathing requires timely ventilation and neonatal expertise',
        'If indicated, obtain a reliable preductal oximetry signal from the right hand/wrist and interpret it against age since birth',
        'Reassess heart-rate and breathing response; do not infer effective ventilation from monitor numbers alone',
        'Document time since birth, support, response and ongoing observation needs; communicate with family and receiving neonatal team',
    ]
    case['checklist']=[dict(action=a,critical=i in (0,1,3,4),window_sec=0) for i,a in enumerate(actions)]
    case['hints']=actions[:3] if spec['level']=='beginner' else []
    case['complications']=[]
    case['narration_intro']=case['patient']['presentation']
    case['teaching_notes']=dict(reference=REFERENCE,authorship='Independent fictional scenarios; no certification or endorsement',
        limitations='Faculty review required. Generic ECG morphology, not validated neonatal ECG. No automatic intervention response or clinical grade. Ventilation technique and advanced resuscitation are separate modules. No neonatal pacing.',
        timing='Each condition includes a faculty-selected age since birth. The session timer is NOT the age since birth. Conditions never advance automatically.',
        readings='SpO2 is an illustrative preductal reading after faculty confirms a usable signal. Blood pressure is an illustrative hidden model input, not a measured invasive pressure. EtCO2/PAP/CO are not configured.',
        context=history)
    return case
