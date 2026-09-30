"""Independent transfer/reassessment teaching cases; no transport clearance."""
from copy import deepcopy
from debriefing.scenarios.trauma_haemorrhage import configure_trauma_haemorrhage
from debriefing.scenarios.trauma_head_injury import configure_trauma_head_injury

PROFILES = ('bleeding','head_injury')
PHASES = ('preparation','deterioration')

def configure_trauma_transfer(spec, profile='bleeding', phase='preparation'):
    if profile not in PROFILES or phase not in PHASES:
        raise ValueError('Select a supported transfer case and starting phase')
    base=(configure_trauma_haemorrhage(spec,'pelvic') if profile=='bleeding' else configure_trauma_head_injury(spec))
    case=deepcopy(base)
    stable=deepcopy(base['conditions'][-1]['state'])
    if profile=='bleeding':
        concerns='Suspected pelvic bleeding after a road collision. Faculty confirms initial haemorrhage support; a definitive bleeding source/control plan remains unresolved. The patient is responsive but requires serial perfusion assessment.'
        worsening=base['conditions'][2]
    else:
        concerns='Head injury after a road collision; neurological impairment persists (E2 V2 M5, GCS 9). Faculty must explicitly assess airway protection, repeat pupils and document examination confounders. Normal vital signs do not establish transport readiness.'
        worsening=base['conditions'][2]
    def stage(key,name,state,description):
        return dict(id='trauma_transfer_'+key,name=name,state=deepcopy(state),description=description+
            ' Instructor-selected teaching state, not evidence that treatment, receiving-team acceptance or transfer has occurred.')
    preparation=stage('preparation','Transfer preparation and risk review',stable,
        concerns+' Repeat primary survey; identify destination capability, trained escort, monitoring, oxygen and backup equipment needs. Balance urgent definitive care against immediately addressable transport risks with senior support.')
    deterioration=stage('deterioration','Deterioration during transfer preparation',worsening['state'],
        worsening['description']+' Reassess immediate threats, initiate appropriate support and update the receiving/transport teams; reassess timing and escort requirements rather than continuing the original plan unchanged.')
    reassessment=stage('reassessment','Reassessment after additional support',stable,
        concerns+' Faculty confirms improved physiological values after further support, but unresolved injuries and recurrence risk remain. Repeat the primary survey and assess device function and ongoing support requirements.')
    handover=stage('handover','Receiving-team handover rehearsal',stable,
        concerns+' Communicate mechanism, suspected injuries, serial findings, interventions with times and response, allergies/medications, pending results, unresolved threats and contingency plans. Confirm shared understanding and responsibility; this preset is not permission to move a real patient.')
    case['conditions']=([preparation,deterioration] if phase=='preparation' else [deterioration])+[reassessment,handover]
    case['initial_state']={**deepcopy(case['conditions'][0]['state']),'show_ibp':False,
        'NBP_sys':None,'NBP_dia':None,'NBP_mean':None,'nibp_state':'IDLE','nibp_last_measured':None}
    case.update(title=f'Adult trauma transfer and reassessment — {spec["location_label"]}',
        rhythm_type=case['initial_state']['rhythm'],clinical_severity=phase,transfer_profile=profile,
        transfer_phase=phase,monitor_schema='trauma-transfer-1')
    case.pop('trauma_mechanism',None)
    case.pop('head_injury_course',None)
    case['patient']['presentation']='35-year-old, 70 kg fictional adult undergoing transfer assessment. '+case['conditions'][0]['description']+' Initial responding personnel: '+', '.join(spec['discipline_labels'])
    case['narration_intro']=case['patient']['presentation']
    actions=['Recognise need for definitive trauma care and initiate senior/receiving-team coordination early',
        'Repeat primary survey and reassess immediate threats before movement and after every deterioration',
        'Assess airway protection, oxygenation, ventilation, bleeding/perfusion and neurological trends together',
        'Confirm receiving capability and clinician-to-clinician communication, acceptance and destination using the local transfer process',
        'Plan appropriate escort, monitoring, oxygen, power, equipment and contingencies for the expected journey',
        'Check access and devices, ongoing treatment, thermal protection and relevant precautions before movement',
        'Balance urgent definitive care against correctable transport risks with senior support; avoid unnecessary investigation-related delays',
        'Send a structured handover with mechanism, findings and trends, treatments/times/response, pending results and unresolved risks',
        'Update receiving and transport teams after changes; confirm shared understanding and responsibility',
        'Communicate the plan with the patient or family as appropriate and document reassessment and handover']
    case['checklist']=[dict(action=a,critical=i in (1,2,3,4,7,8),window_sec=0) for i,a in enumerate(actions)]
    case['hints']=actions[:3] if spec['level']=='beginner' else []
    case['teaching_notes']['limitations']='Independent faculty-review communication/reassessment pilot; no automatic transport-readiness decision, dispatch, receiving acceptance, treatment effects or validated score. Transfer timing and escort depend on local expertise and resources. GCS examples assume assessable non-intubated responses; reassess after airway management. Improved values do not resolve neurological injury or bleeding risk.'
    case['teaching_notes']['resources']='Ward and personnel define the starting setting, not destination availability. Faculty supplies receiving facility, transport time, equipment and escort details; no real transfer or external communication is initiated.'
    case['teaching_notes']['reference']='https://www.facs.org/quality-programs/trauma/quality/verification-review-and-consultation-program/trauma-verification-qas/vrc-2022-standards-qas/'
    return case
