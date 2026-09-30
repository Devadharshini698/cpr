"""Original obstetric teaching cases; not a licensed course or treatment engine."""
from copy import deepcopy
from physiology import normalize_monitor_state

SETTINGS = {'maternity':'Maternity / delivery suite','emergency':'Emergency department','theatre':'Obstetric theatre','critical_care':'Critical care'}
COLLAPSE_CAUSES = {'haemorrhage':'Suspected haemorrhage','embolism':'Suspected embolic cause','anaesthetic':'Possible anaesthetic complication','undifferentiated':'Undifferentiated collapse'}
EMERGENCIES = {'sepsis':'Maternal sepsis','cord_prolapse':'Umbilical cord prolapse','shoulder_dystocia':'Shoulder dystocia'}
AHA = 'https://cpr.heart.org/-/media/CPR-Files/CPR-Guidelines-Files/2025-Algorithms/Algorithm-SC-ACLS-CA-in-Pregnancy-250620.pdf'
REFERENCES = {
    'sepsis':'https://www.nice.org.uk/guidance/ng255/chapter/managing-suspected-sepsis',
    'cord_prolapse':'https://www.rcog.org.uk/guidance/browse-all-guidance/green-top-guidelines/umbilical-cord-prolapse-green-top-guideline-no-50/',
    'shoulder_dystocia':'https://www.rcog.org.uk/guidance/browse-all-guidance/green-top-guidelines/shoulder-dystocia-green-top-guideline-no-42/',
}

def stage(key,name,hr,bp,rr,spo2,description,rhythm=None,pulse=True,temp=36.8):
    state=normalize_monitor_state(dict(HR=hr,pulse_rate=hr if pulse else 0,
        rhythm=rhythm or ('SINUS_TACHY' if hr>100 else 'NSR'),ABP_sys=bp[0],ABP_dia=bp[1],
        avRR=rr,SpO2=spo2,etCO2=0,PAP_sys=0,PAP_dia=0,CO=0,Tperi=temp,Tblood=temp,emd_pea=(rhythm=='PEA')))
    state.update(patient_profile='adult',patient_weight_kg=75,
        alarm_thresholds={'HR':{'low':50,'high':120},'SpO2':{'low':94,'high':100},'ABP_sys':{'low':90,'high':159},'ABP_dia':{'low':50,'high':109},'avRR':{'low':10,'high':30}})
    return dict(id=key,name=name,state=state,description=description)

def finish(spec,topic,setting,context,conditions,actions,reference,schema):
    case=deepcopy(spec)
    case.update(title=f'{topic} — {SETTINGS[setting]}',location_label=SETTINGS[setting],conditions=conditions,
        monitor_schema=schema,release_status='teaching_pilot_faculty_review',clinical_severity=conditions[0]['id'])
    case['initial_state']={**deepcopy(conditions[0]['state']), 'show_ibp':False,'show_resp':False,'show_etco2':False,
        'configured_channels':dict(ecg=True,pleth=True,abp=False,pap=False,co2=False),
        'waveform_channels':dict(ecg=True,pleth=True,abp=False,pap=False,co2=False),
        'NBP_sys':None,'NBP_dia':None,'NBP_mean':None,'nibp_state':'IDLE','nibp_last_measured':None}
    case['rhythm_type']=case['initial_state']['rhythm']
    case['patient']=dict(age=30,weight_kg=75,sex='female',gestational_age_weeks=39 if context=='intrapartum' else 34,
        postpartum_hours=24 if context=='postpartum' else None,
        history='Faculty provides relevant history, medication exposure, allergies and examination findings on request.',
        presentation=f'Fictional patient: {context}, {topic}, {SETTINGS[setting]}. Selected team: '+', '.join(spec['discipline_labels']))
    case['narration_intro']=case['patient']['presentation']
    case['checklist']=[dict(action=action,critical=index<3,window_sec=0) for index,action in enumerate(actions)]
    case['hints']=actions[:3] if spec['level']=='beginner' else []
    case['complications']=[]
    case['teaching_notes']=dict(reference=reference,authorship='Original independent teaching pilot; no ALSO affiliation or certification. Faculty sign-off required.',
        limitations='No drug/dose engine, automatic intervention response, fetal CTG, delivery mechanics or validated clinical score. Monitor values are illustrative teaching presets.',
        progression='Faculty selects each branch and confirms clinical response. A normal maternal monitor does not establish fetal safety or successful delivery. No stage is a recommendation to delay care.',
        findings='Enter and reveal maternal, fetal and procedural findings using Patient assessment. Do not display fetal heart rate as maternal ECG.',
        readings='NIBP requires a cuff cycle. Optional sensors require instructor setup. Presets may replace sensor values; reassess after each transition.')
    return case

def configure_maternal_collapse(spec,context='antenatal',entry='deteriorating',cause='undifferentiated',setting='maternity'):
    if context not in ('antenatal','postpartum') or entry not in ('deteriorating','arrest') or cause not in COLLAPSE_CAUSES or setting not in SETTINGS:
        raise ValueError('Select a supported maternal collapse context, entry, cause and setting')
    pre=stage('mc_deteriorating','Severe deterioration — pulse present',135,(75,40),30,88,
        'Reduced responsiveness and severe circulatory compromise. Assess pulse and breathing; summon the maternal emergency team. '+COLLAPSE_CAUSES[cause]+' is a faculty hypothesis, not a monitor diagnosis.')
    pea=stage('mc_pea','Cardiac arrest — PEA',60,(0,0),0,0,'Faculty confirms no pulse and no normal breathing. Organised ECG is not proof of circulation.',rhythm='PEA',pulse=False)
    vf=stage('mc_vf','Shockable arrest — ventricular fibrillation',0,(0,0),0,0,'Optional shockable branch; faculty confirms arrest. Defibrillation and resuscitation follow the approved protocol.',rhythm='VF',pulse=False)
    rosc=stage('mc_rosc','Faculty-confirmed ROSC — ongoing instability',115,(90,55),22,94,'Pulse has returned on reassessment; continue airway, perfusion and cause-directed care. Selecting a rhythm alone does not prove ROSC.')
    stable=stage('mc_handover','Post-arrest reassessment and handover',95,(110,70),18,97,'Illustrative response after faculty-confirmed care. Communicate unresolved cause, neurological status and further critical-care needs.')
    actions=['Recognise collapse, assess breathing and pulse and activate a coordinated maternal resuscitation response',
        'If arrest is confirmed, provide appropriate resuscitation and rhythm-directed defibrillation under the approved protocol',
        'Prioritise airway and oxygenation while addressing reversible causes with obstetric, anaesthetic and resuscitation expertise',
        'Assign roles and obtain relevant history; investigate haemorrhagic, thromboembolic, anaesthetic and other causes without assuming a diagnosis from ECG',
        'Reassess for ROSC using clinical circulation, not an organised rhythm alone; plan ongoing monitoring and critical care',
        'Document observed actions and timings and provide a structured multidisciplinary handover']
    if context=='antenatal':
        actions.insert(3,'For a uterus at or above the umbilicus, provide manual left uterine displacement during CPR and mobilise qualified staff for resuscitative delivery immediately; aim to complete by 5 minutes if ROSC has not occurred, following the approved pregnancy-arrest protocol')
    else:
        actions.insert(3,'Use the postpartum history to prioritise maternal causes; resuscitative delivery is not applicable after birth, and neonatal care is a separate task')
    case=finish(spec,'Maternal collapse',setting,context,([pre] if entry=='deteriorating' else [])+[pea,vf,rosc,stable],actions,AHA,'maternal-collapse-1')
    case.update(maternal_collapse_context=context,maternal_collapse_cause=cause,maternal_collapse_entry=entry,maternal_collapse_setting=setting)
    case['patient']['history'] += ' Faculty hypothesis: '+COLLAPSE_CAUSES[cause]+'. '+{
        'haemorrhage':'Seek visible or concealed bleeding, recent delivery or procedures and transfusion needs.',
        'embolism':'Seek sudden respiratory symptoms and thromboembolic or peripartum context; do not diagnose the embolus type from this monitor.',
        'anaesthetic':'Clarify recent anaesthetic agents, regional techniques, airway events and timing with the anaesthetic team.',
        'undifferentiated':'Obtain witness history and assess reversible causes without anchoring on a single diagnosis.',
    }[cause]
    return case

def configure_other_obstetric(spec,kind='sepsis',setting='maternity',context='antenatal'):
    if kind not in EMERGENCIES or setting not in SETTINGS or context not in ('antenatal','postpartum'):
        raise ValueError('Select a supported obstetric emergency, context and setting')
    if kind=='sepsis':
        stages=[stage('obs_sepsis','Suspected infection with organ dysfunction',125,(90,55),28,94,'Fever, reduced urine output and altered behaviour are reported by faculty; investigate infection and alternative diagnoses.',temp=39),
            stage('obs_sepsis_shock','Worsening circulatory compromise',140,(70,40),34,90,'Faculty reports worsening perfusion despite initial support; urgent senior reassessment and critical care are required.',temp=39),
            stage('obs_sepsis_response','Faculty-confirmed response',105,(105,65),22,96,'Partial clinical improvement; source control and ongoing organ assessment remain necessary.',temp=38)]
        actions=['Recognise possible maternal sepsis and organ dysfunction; urgently escalate to senior obstetric and acute-care staff',
            'Assess airway, breathing, circulation, mental status and urine output while considering alternative causes',
            'Obtain appropriate microbiology and investigations without delaying indicated antimicrobial treatment under the local protocol',
            'Reassess circulation and respiratory status during individually prescribed fluid support; seek critical care for persistent compromise',
            'Identify the infection source and arrange qualified source-control and obstetric assessment',
            'Communicate treatment, investigation results, response and unresolved concerns during transfer']
    else:
        context='intrapartum'
        if kind=='cord_prolapse':
            finding='After membrane rupture, faculty describes a palpable or visible cord and fetal concern. Maternal observations alone do not establish fetal status.'
            action='Recognise suspected cord prolapse, call the obstetric emergency team and arrange urgent assessment and a safe expedited birth plan'
            practice='Use trained staff and the local cord-prolapse protocol to relieve compression while definitive birth is arranged; fetal assessment is separate from maternal ECG'
        else:
            finding='After the fetal head is born, the shoulders do not deliver with usual assistance. Faculty states the finding; the monitor does not model delivery mechanics.'
            action='Recognise shoulder dystocia, clearly announce the emergency and summon experienced obstetric and neonatal help'
            practice='Coordinate trained staff using the locally approved manoeuvre sequence; practical manoeuvres require a suitable task trainer and qualified supervision'
        stages=[stage('obs_'+kind,EMERGENCIES[kind]+' — recognition',110,(120,75),22,98,finding),
            stage('obs_'+kind+'_unresolved','Unresolved delivery emergency',120,(115,70),24,98,'Faculty confirms the emergency remains unresolved. Preserved maternal SpO2 must not be interpreted as fetal reassurance.'),
            stage('obs_'+kind+'_response','Faculty-confirmed birth and maternal reassessment',100,(110,70),20,98,'Faculty confirms birth; assess maternal bleeding and injury and hand the newborn to the neonatal team. No neonatal outcome is inferred from these maternal values.')]
        actions=[action,'Allocate team roles, maintain communication with the patient and record observed timings',practice,
            'Reassess maternal and fetal or newborn needs separately; maternal monitor readings do not confirm fetal wellbeing',
            'After birth assess maternal bleeding and injury, arrange neonatal assessment and structured handover']
    handover=deepcopy(stages[-1]);handover.update(id='obs_'+kind+'_handover',name='Ongoing reassessment and handover')
    case=finish(spec,EMERGENCIES[kind],setting,context,stages+[handover],actions,REFERENCES[kind],'other-obstetric-1')
    case.update(obstetric_emergency_kind=kind,obstetric_emergency_context=context,obstetric_emergency_setting=setting)
    return case
