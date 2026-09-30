"""Independent faculty-controlled neonatal ventilation teaching pilot."""
from copy import deepcopy
from debriefing.scenarios.neonatal_transition import configure_neonatal_transition

TOPIC='Ventilation support'
PROBLEMS={
    'mask_leak':'Poor mask seal with audible leak and little chest movement. Review mask fit and technique with a competent second provider.',
    'airway_position':'Poor airway position and little chest movement. Reassess position and patency; clear secretions only when obstruction is suspected.',
    'equipment':'Ventilation device connection or gas-supply problem. Check the circuit and function and obtain an appropriate working alternative promptly.',
}

def configure_neonatal_ventilation(spec,profile='term',course='apnoea',setting='delivery_room',problem='mask_leak'):
    if course not in ('apnoea','ineffective') or problem not in PROBLEMS:
        raise ValueError('Select apnoea or ineffective ventilation and a supported ventilation problem')
    case=configure_neonatal_transition(spec,profile,'poor_transition',setting)
    template=case['conditions'][0]
    def stage(key,name,minute,hr,rate,spo2,description,support):
        result=deepcopy(template)
        result.update(id=key,name=name,description=description)
        state=result['state']
        low,high={2:(65,70),3:(70,75),5:(80,85),10:(85,95)}[minute]
        state.update(HR=float(hr),pulse_rate=float(hr),avRR=float(rate),SpO2=float(spo2),
            neonatal_age_minutes=minute,neonatal_ventilation=support,Tperi=36.7,Tblood=36.7)
        state['alarm_thresholds']['SpO2']={'low':low,'high':high}
        state['alarm_profile_note']=f'Teaching limits only. Preductal SpO2 reference at faculty-selected age {minute} minutes: {low}–{high}%.'
        return result
    apnoea=stage('neo_vent_apnoea','Apnoea / ventilation required — 2 min',2,90,0,55,
        'No effective spontaneous breathing, reduced tone and a heart rate below 100/min after initial steps. Initiate timely ventilation and call neonatal help. Case entry at 2 minutes is a delayed-presentation teaching problem, not permission to wait.','No effective ventilation')
    ineffective=stage('neo_vent_ineffective','Ineffective attempted ventilation — 3 min',3,75,0,58,
        PROBLEMS[problem]+' Attempted inflations have not established effective lung inflation or a rising heart rate. The displayed effective ventilation rate is zero, not the operator’s bagging cadence.','Attempted support ineffective')
    effective=stage('neo_vent_effective','Response to effective assisted ventilation — 5 min',5,125,40,82,
        'Faculty has confirmed chest movement and improving heart rate after corrective action. Effective assisted inflations are represented at 40/min; the baby is not yet breathing independently. Reassess and adjust support, avoiding excessive inflation.','Effective assisted ventilation')
    persistent=stage('neo_vent_escalation','Persistent severe bradycardia — 5 min',5,50,40,62,
        'Faculty confirms effective ventilation after corrective steps, yet heart rate remains below 60/min. Activate the advanced neonatal pathway with expert support. A heart rate is still present; this is not an adult pulseless arrest. Advanced interventions are outside this module.','Effective ventilation; advanced escalation required')
    recovery=stage('neo_vent_spontaneous','Spontaneous breathing and reassessment — 10 min',10,145,42,92,
        'Faculty confirms spontaneous regular breathing and improved tone after reassessment. Continue thermal care and determine ongoing monitoring, glucose assessment and neonatal handover needs. Do not withdraw support solely because a number improved.','Spontaneous breathing')
    case['conditions']=([apnoea,ineffective] if course=='apnoea' else [ineffective])+[effective,persistent,recovery]
    flags={k:v for k,v in case['initial_state'].items() if k.startswith('show_') or k.startswith('NBP_') or k.startswith('nibp_')}
    case['initial_state']={**deepcopy(case['conditions'][0]['state']),**flags}
    case.update(title=f'Newborn ventilation support — {case["location_label"]}',monitor_schema='neonatal-ventilation-1',
        clinical_severity=course,neonatal_ventilation_problem=problem)
    case['patient']['presentation']=f'Fictional {case["patient"]["gestational_age_weeks"]}-week newborn, {case["patient"]["weight_kg"]} kg, requiring ventilation assessment at {case["initial_state"]["neonatal_age_minutes"]} minutes after birth. Initial problem: {course}. Team: '+', '.join(spec['discipline_labels'])
    case['narration_intro']=case['patient']['presentation']
    actions=[
        'Recognise apnoea, gasping or persistent low heart rate and initiate timely ventilation with competent neonatal assistance',
        'Assess chest movement and heart-rate response rather than equating attempted inflations with effective ventilation',
        'If response is inadequate, assess mask seal, airway position and patency, device function and adequacy of inflation',
        'Request an alternative airway and appropriate expertise when corrective measures do not establish effective ventilation',
        'Use reliable preductal oximetry and age since birth to guide oxygen review; maintain thermal protection',
        'Recognise persistent severe bradycardia after confirmed effective ventilation and escalate to advanced neonatal resuscitation',
        'Reassess spontaneous breathing and continuing support needs and communicate the response and handover plan',
    ]
    case['checklist']=[dict(action=a,critical=i in (0,1,2,5),window_sec=0) for i,a in enumerate(actions)]
    case['hints']=actions[:3] if spec['level']=='beginner' else []
    case['teaching_notes'].update(
        limitations='Independent faculty-review pilot. No automatic bag/device response, airway placement validation, pressure/volume model or clinical grade. Advanced interventions are not implemented here; the escalation stage is a recognition endpoint.',
        ventilation='avRR represents effective spontaneous breaths or assisted inflations, not attempted bag cadence. Capnography is unconfigured and hidden; no invented EtCO2 trace. Faculty observes ventilation technique and selects response.',
        progression='Alternative branches, not a mandatory sequence: effective support may lead to recovery OR persistent severe bradycardia. All changes require instructor selection.')
    return case
