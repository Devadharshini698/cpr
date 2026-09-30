"""Independent maternal hypertension cases; faculty review required."""
from copy import deepcopy
from physiology import normalize_monitor_state

TOPIC='Hypertensive emergencies'
CONTEXTS={'antenatal':'34 weeks pregnant','postpartum':'24 hours after birth at 39 weeks'}
SETTINGS={'maternity':'Maternity assessment / delivery unit','emergency':'Emergency department','critical_care':'Obstetric critical care'}
ENTRIES=('severe_hypertension','warning_signs','eclampsia')

def configure_obstetric_hypertension(spec,context='antenatal',entry='warning_signs',setting='maternity'):
    if context not in CONTEXTS or entry not in ENTRIES or setting not in SETTINGS:
        raise ValueError('Select a supported maternal context, hypertension presentation and setting')
    case=deepcopy(spec)
    def stage(key,name,hr,sys,dia,rr,spo2,description):
        state=normalize_monitor_state(dict(rhythm='SINUS_TACHY' if hr>100 else 'NSR',HR=hr,pulse_rate=hr,
            ABP_sys=sys,ABP_dia=dia,avRR=rr,SpO2=spo2,etCO2=0,Tperi=36.8,Tblood=36.8,
            PAP_sys=0,PAP_dia=0,CO=0,emd_pea=False))
        state.update(patient_profile='adult',patient_weight_kg=75,
            alarm_thresholds={'HR':{'low':50,'high':110},'ABP_sys':{'low':90,'high':159},'ABP_dia':{'low':50,'high':109},'avRR':{'low':10,'high':24},'SpO2':{'low':94,'high':100}},
            alarm_profile_note='Illustrative maternal alarms; severe systolic OR diastolic readings require assessment. Not a diagnostic score or treatment target.')
        return dict(id='obht_'+key,name=name,state=state,description=description)
    initial={
        'severe_hypertension':stage('severe_hypertension','Severe hypertension — reassessment required',96,170,112,20,98,
            'Markedly elevated pressure on an appropriate measurement; confirm technique and persistence while arranging prompt obstetric assessment. Absence of symptoms does not establish safety.'),
        'warning_signs':stage('warning_signs','Hypertension with concerning symptoms',108,178,118,24,97,
            'Persistent headache, visual disturbance and upper abdominal pain are reported on assessment. Evaluate possible pre-eclampsia and organ involvement; do not diagnose HELLP from the monitor.'),
        'eclampsia':stage('eclampsia','Convulsion — suspected eclampsia',125,185,120,10,88,
            'Faculty describes a generalised convulsion with impaired airway protection. Prioritise maternal safety, airway and breathing, urgent obstetric/anaesthetic help and appropriate seizure treatment; consider alternative causes. ECG is not EEG and does not depict the seizure.'),
    }
    respiratory=stage('respiratory','Respiratory deterioration — evaluate pulmonary oedema',120,175,115,32,86,
        'New breathlessness, crackles and hypoxaemia require urgent respiratory and fluid-balance reassessment and specialist support. Pulmonary oedema is a suspected diagnosis requiring clinical assessment.')
    response=stage('response','Faculty-confirmed response and reassessment',92,145,95,18,97,
        'Faculty confirms seizure cessation where applicable, improved oxygenation and reduced pressure after care. These illustrative numbers are not a universal target or proof that maternal organ dysfunction has resolved.')
    handover=deepcopy(response);handover.update(id='obht_handover',name='Specialist handover and continuing care',
        description='Communicate pressure trends, neurological and respiratory findings, medication actually given, renal/fluid status and investigation results. '+('Arrange fetal assessment and an obstetric plan after maternal stabilisation; delivery timing requires specialist judgement.' if context=='antenatal' else 'Continue postpartum surveillance; delivery does not eliminate hypertensive complications. Coordinate separate newborn care.'))
    case['conditions']=[initial[entry]]+([initial['eclampsia']] if entry!='eclampsia' else [])+[respiratory,response,handover]
    case['initial_state']={**deepcopy(case['conditions'][0]['state']),'show_ibp':False,'show_resp':False,'show_etco2':False,
        'configured_channels':{'ecg':True,'pleth':True,'abp':False,'pap':False,'co2':False},
        'waveform_channels':{'ecg':True,'pleth':True,'abp':False,'pap':False,'co2':False},
        'NBP_sys':None,'NBP_dia':None,'NBP_mean':None,'nibp_state':'IDLE','nibp_last_measured':None}
    case.update(title=f'Maternal hypertensive emergency — {SETTINGS[setting]}',location_label=SETTINGS[setting],
        monitor_schema='obstetric-hypertension-1',clinical_severity=entry,obstetric_hypertension_context=context,
        obstetric_hypertension_setting=setting,rhythm_type=case['initial_state']['rhythm'],release_status='teaching_pilot_faculty_review')
    case['patient']=dict(age=30,weight_kg=75,sex='female',gestational_age_weeks=34 if context=='antenatal' else 39,
        postpartum_hours=None if context=='antenatal' else 24,
        history='Review previous blood pressure, obstetric history, medications, allergies, renal disease and recent symptoms. No assumed laboratory results.',
        presentation=f'Fictional 30-year-old, 75 kg patient, {CONTEXTS[context]}, with {entry.replace("_"," ")}. Setting: {SETTINGS[setting]}. Team: '+', '.join(spec['discipline_labels']))
    case['narration_intro']=case['patient']['presentation']
    actions=[
        'Recognise severe systolic or diastolic hypertension, check measurement technique and obtain timely repeat observations without delaying escalation',
        'Assess maternal airway, breathing, circulation and neurological state; urgently activate obstetric and anaesthetic support for deterioration',
        'For convulsions, protect the patient, support airway and breathing and review indicated magnesium sulfate under the approved protocol; also consider alternative causes',
        'Arrange indicated urgent antihypertensive treatment with qualified staff; verify contraindications, dose, route and response using the local protocol',
        'Assess headache, vision, abdominal pain, urine output and organ involvement; request appropriate renal, hepatic, platelet and urine investigations',
        'Review fluid balance, respiratory status and medication safety monitoring; normal SpO2 alone does not exclude deterioration',
        'Arrange fetal assessment after maternal stabilisation when still pregnant; obtain a specialist ongoing obstetric plan',
        'Reassess treatment response and communicate findings, actual therapies, unresolved concerns and the monitoring plan during handover',
    ]
    if context=='postpartum': actions[6]='Continue maternal surveillance after birth and coordinate separate newborn care; do not infer resolution from delivery'
    case['checklist']=[dict(action=a,critical=i in (0,1,2,3),window_sec=0) for i,a in enumerate(actions)]
    case['hints']=actions[:3] if spec['level']=='beginner' else [];case['complications']=[]
    case['teaching_notes']=dict(reference='https://www.nice.org.uk/guidance/ng133/chapter/recommendations',
        authorship='Independent fictional cases, not licensed ALSO content; faculty review required',
        limitations='No automatic drug response, dose calculator, seizure animation, EEG or fetal/CTG simulator. No validated clinical grade. Maternal pulse remains present.',
        progression='Convulsion and respiratory deterioration are optional faculty-selected branches, not inevitable progression. Improvement and delivery decisions require clinical judgement.',
        readings='Cuff pressures require NIBP measurement; invasive channels and capnography are unconfigured. Monitor numbers cannot diagnose pre-eclampsia, HELLP, eclampsia or pulmonary oedema by themselves.',
        findings='Enter and explicitly reveal neurological, laboratory and fetal findings through Patient assessment. Selected professions do not establish specialist competence.')
    return case
