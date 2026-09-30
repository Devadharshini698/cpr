"""Independent postpartum haemorrhage teaching pilot, not an ALSO course."""
from copy import deepcopy
from physiology import normalize_monitor_state

TOPIC='Obstetric haemorrhage'
CAUSES={
    'tone':('Suspected uterine atony','On requested examination the uterus feels poorly contracted. Reassess the cause; other sources may coexist.'),
    'trauma':('Suspected genital tract trauma','Bleeding continues despite a firm uterus; request appropriate examination for genital tract injury by a skilled clinician.'),
    'tissue':('Suspected retained placental tissue','The placental examination raises concern about completeness. Seek obstetric assessment; do not infer a definitive diagnosis from the monitor.'),
    'thrombin':('Suspected coagulopathy','Diffuse oozing and bruising raise concern about a coagulation problem. Obtain appropriate investigations and obstetric/haematology support; laboratory results are not pre-assumed.'),
}
SETTINGS={
    'delivery_suite':('Delivery suite','Following vaginal birth; review labour, placental delivery and preventive treatments.'),
    'postnatal_ward':('Postnatal ward','Bleeding is recognised after transfer from the delivery area; obtain the birth handover and activate obstetric help.'),
    'theatre':('Obstetric theatre','Following caesarean birth; coordinate surgical, anaesthetic and obstetric assessment of visible and concealed bleeding.'),
    'emergency':('Emergency department','Transferred after birth elsewhere; verify the birth timeline, prior treatment and access to obstetric and transfusion support.'),
}
SEVERITIES=('maintained','hypotensive','critical')

def configure_obstetric_haemorrhage(spec,cause='tone',severity='maintained',setting='delivery_suite'):
    if cause not in CAUSES or severity not in SEVERITIES or setting not in SETTINGS:
        raise ValueError('Select a supported postpartum cause, severity and care setting')
    case=deepcopy(spec);label,finding=CAUSES[cause];ward,history=SETTINGS[setting]
    def stage(key,name,hr,sys,dia,rr,temp,blood_loss,description):
        state=normalize_monitor_state(dict(rhythm='SINUS_TACHY' if hr>100 else 'NSR',HR=hr,pulse_rate=hr,
            ABP_sys=sys,ABP_dia=dia,SpO2=97,avRR=rr,etCO2=0,Tperi=temp,Tblood=temp,
            PAP_sys=0,PAP_dia=0,CO=0,emd_pea=False))
        state.update(patient_profile='adult',patient_weight_kg=70,
            alarm_thresholds={'HR':{'low':50,'high':100},'ABP_sys':{'low':90,'high':160},
                'avRR':{'low':10,'high':24},'SpO2':{'low':94,'high':100},'Tperi':{'low':36,'high':38}},
            alarm_profile_note='Illustrative maternal teaching alarms, not a validated obstetric early-warning score.')
        return dict(id='pph_'+key,name=name,state=state,
            description=description+' '+finding+f' Faculty case finding: cumulative quantified blood loss {blood_loss} mL. Disclose on assessment; this is a preset, not a measurement device or treatment threshold.')
    stages={
        'maintained':stage('maintained','Bleeding with maintained blood pressure',112,110,70,22,36.5,400,
            'Ongoing bleeding, anxiety and pallor; pulse present. Maintained blood pressure and saturation do not exclude significant haemorrhage.'),
        'hypotensive':stage('hypotensive','Bleeding with hypotension',130,85,50,28,36.0,1000,
            'Dizziness, cool extremities and worsening perfusion with a palpable pulse. Escalate haemorrhage response without waiting for a further fall in blood pressure.'),
        'critical':stage('critical','Critical ongoing haemorrhage',145,65,35,32,35.5,1600,
            'Reduced responsiveness, weak palpable pulse and severe circulatory compromise. Urgent obstetric, anaesthetic and major-haemorrhage support is required.'),
    }
    response=stage('response','Faculty-confirmed bleeding control and reassessment',95,105,65,20,36.3,1800,
        'Faculty confirms bleeding control and improving perfusion after appropriate care. Repeat assessment and laboratory review; cumulative loss does not reset when bleeding stops.')
    handover=deepcopy(response);handover.update(id='pph_handover',name='Monitored handover and ongoing care')
    handover['description']='Maintain surveillance for recurrent bleeding and complications. Communicate cumulative loss, cause assessment, treatment actually given, response and unresolved concerns. Arrange maternal monitored care and separate newborn care; this is not discharge clearance.'
    order=SEVERITIES[SEVERITIES.index(severity):]
    case['conditions']=[stages[key] for key in order]+[response,handover]
    case['initial_state']={**deepcopy(case['conditions'][0]['state']),
        'show_ibp':False,'show_etco2':False,'show_resp':False,
        'NBP_sys':None,'NBP_dia':None,'NBP_mean':None,'nibp_state':'IDLE','nibp_last_measured':None}
    case.update(title=f'Postpartum haemorrhage — {ward}',location_label=ward,rhythm_type='SINUS_TACHY',
        clinical_severity=severity,obstetric_cause=cause,obstetric_setting=setting,
        monitor_schema='obstetric-haemorrhage-1',release_status='teaching_pilot_faculty_review')
    case['patient']=dict(age=28,weight_kg=70,sex='female',gestational_age_weeks=39,postpartum_minutes=30,
        history=history+' Fictional first birth at 39 weeks. Review allergies, comorbidity, medications and prior haemorrhage risk.',
        presentation=f'28-year-old, 70 kg patient, 30 minutes postpartum, with ongoing bleeding and {severity} perfusion state. Setting: {ward}. Initial team: '+', '.join(spec['discipline_labels']))
    case['narration_intro']=case['patient']['presentation']
    actions=[
        'Recognise postpartum bleeding promptly using quantified blood loss, haemodynamic signs and the clinical picture; do not wait for hypotension',
        'Assess maternal airway, breathing, circulation, consciousness and temperature while activating obstetric and major-haemorrhage support',
        'Allocate maternal resuscitation, obstetric examination, medication checking, blood-loss recording, escalation and separate newborn-care roles within competence',
        'Assess uterine tone, genital tract injury, placental completeness and coagulation concerns; causes may coexist',
        'Initiate the locally approved first-response PPH bundle promptly with qualified staff, including uterine measures, indicated uterotonic and tranexamic acid, IV support, examination and escalation; check contraindications, timing and dosing independently',
        'Arrange appropriate vascular access, laboratory and blood-bank support and definitive bleeding control according to the clinical response',
        'Reassess bleeding, perfusion, urine output, temperature and results after intervention; distinguish a recorded action from observed response',
        'Communicate maternal course, quantified loss, therapies, uncertainties and ongoing monitoring needs to the receiving team and family',
    ]
    case['checklist']=[dict(action=a,critical=i in (0,1,3,4,5),window_sec=0) for i,a in enumerate(actions)]
    case['hints']=actions[:3] if spec['level']=='beginner' else [];case['complications']=[]
    case['teaching_notes']=dict(reference='https://www.who.int/publications/i/item/9789240115637',
        authorship='Independent fictional maternal case, not licensed ALSO material; faculty review required',
        limitations='No automatic drug, fluid, transfusion or procedure response; no dose calculator, blood-loss sensor or validated clinical grade. Maternal pulse remains present; cardiac arrest and antenatal haemorrhage require separate cases.',
        readings='SpO2 is not a measure of circulating blood volume. BP is a hidden model input until NIBP is requested. Capnography and invasive channels are not configured. Loss values are faculty-authored case observations, not severity definitions.',
        findings='Use Patient assessment to enter and explicitly reveal uterine/examination findings, quantified bleeding and actual laboratory results. Stage descriptions are faculty guidance, not automatically completed learner assessments.',
        resources='The dedicated obstetric setting overrides the general ward label. Selected professions do not establish midwifery, obstetric, anaesthetic or transfusion competence; confirm available expertise.',
        progression='Faculty-selected deterioration, bleeding control and handover; numerical improvement does not prove definitive treatment. Cumulative loss never falls in the planned sequence.')
    return case
