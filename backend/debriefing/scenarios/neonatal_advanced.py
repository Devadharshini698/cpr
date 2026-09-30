"""Faculty-led advanced newborn resuscitation cases, not a drug/device model."""
from copy import deepcopy
from physiology import normalize_monitor_state
from debriefing.scenarios.neonatal_ventilation import configure_neonatal_ventilation

TOPIC='Advanced neonatal resuscitation'
CONTEXTS={
    'persistent_bradycardia':('Persistent severe bradycardia','Perinatal compromise with persistent severe bradycardia despite faculty-confirmed effective ventilation. Recheck ventilation and the quality of coordinated support.'),
    'blood_loss':('Suspected blood loss','Perinatal history includes visible bleeding and concern for disrupted placental circulation. The baby is markedly pale with poor perfusion. Obtain the obstetric account; volume loss is a hypothesis requiring assessment, not a monitor diagnosis.'),
    'air_leak':('Suspected air leak','Deterioration after respiratory support with asymmetric chest movement and reduced unilateral air entry on requested examination. Reassess airway position and consider an air leak; urgent expert assessment is needed.'),
}

def configure_neonatal_advanced(spec,profile='term',setting='delivery_room',context='persistent_bradycardia',entry='escalation'):
    if context not in CONTEXTS or entry not in ('escalation','ongoing_resuscitation'):
        raise ValueError('Select a supported advanced neonatal context and entry state')
    case=configure_neonatal_ventilation(spec,profile,'apnoea',setting)
    label,history=CONTEXTS[context]
    template=next(s for s in case['conditions'] if s['id']=='neo_vent_escalation')
    def stage(key,name,minute,hr,rr,spo2,sys,dia,description):
        result=deepcopy(template)
        result.update(id=key,name=name,description=description)
        state=result['state']
        state.update(HR=hr,pulse_rate=hr,avRR=rr,SpO2=spo2,ABP_sys=sys,ABP_dia=dia,
            neonatal_age_minutes=minute,neonatal_ventilation='Assisted ventilation; faculty-controlled response')
        low,high=(80,85) if minute==5 else (85,95)
        state['alarm_thresholds']['SpO2']={'low':low,'high':high}
        state['alarm_profile_note']=f'Illustrative limits; case age {minute} min. SpO2 reference {low}–{high}% applies only to a reliable preductal signal.'
        result['state']=normalize_monitor_state(state)
        return result
    escalation=stage('neo_adv_escalation','HR below 60 after effective ventilation — 5 min',5,50,40,58,38,20,
        'Heart rate remains below 60/min after effective ventilation and corrective measures, preferably including an alternative airway. Confirm these prerequisites, call the advanced neonatal team and coordinate compressions with ventilation. '+history)
    ongoing=stage('neo_adv_ongoing','Ongoing coordinated resuscitation — 5 min',5,45,30,56,35,18,
        'Faculty confirms coordinated support has been established, but heart rate remains below 60/min. Reassess ventilation and compression quality, prepare appropriate vascular access and medication review with qualified staff. The ECG rate is the intrinsic heart rate, NOT compression cadence.')
    refractory=stage('neo_adv_refractory','Persistent poor response — 10 min',10,40,30,55,32,16,
        'No sustained improvement despite faculty-confirmed effective ventilation, coordinated compressions and indicated therapy. Reassess delivery and consider reversible causes. '+history+' No automatic drug or procedure effect is simulated.')
    hr_response=stage('neo_adv_hr_response','Heart-rate recovery; ventilation still required — 10 min',10,90,40,86,45,25,
        'Faculty confirms sustained heart-rate recovery above 60/min with improving perfusion. Reassess the need for compressions and continue appropriate ventilation because spontaneous breathing remains inadequate. This is not complete recovery.')
    stabilisation=stage('neo_adv_stabilisation','Recovery and neonatal handover — 10 min',10,135,40,92,55,30,
        'Heart rate and perfusion have improved following faculty-confirmed care. Assisted ventilation is still represented; reassess breathing, thermal state, glucose and neurological status and arrange specialist monitoring and handover.')
    case['conditions']=([escalation,ongoing] if entry=='escalation' else [ongoing])+[refractory,hr_response,stabilisation]
    flags={k:v for k,v in case['initial_state'].items() if k.startswith('show_') or k.startswith('NBP_') or k.startswith('nibp_')}
    case['initial_state']={**deepcopy(case['conditions'][0]['state']),**flags}
    case.update(title=f'Advanced newborn resuscitation — {label} — {case["location_label"]}',
        monitor_schema='neonatal-advanced-1',clinical_severity='critical',neonatal_advanced_context=context,neonatal_advanced_entry=entry)
    case['patient']['history']+=' '+history
    case['patient']['presentation']=f'Fictional {case["patient"]["gestational_age_weeks"]}-week, {case["patient"]["weight_kg"]} kg newborn at 5 minutes after birth. Persistent severe bradycardia after effective ventilation. Team: '+', '.join(spec['discipline_labels'])
    case['narration_intro']=case['patient']['presentation']
    actions=[
        'Confirm effective ventilation and corrective steps before interpreting persistent severe bradycardia as requiring advanced escalation',
        'Activate neonatal expertise and allocate airway, compressions, vascular access, medication checking and timekeeping roles within demonstrated competence',
        'Coordinate neonatal compressions and ventilation at 3:1, assess technique and minimise interruptions',
        'Review oxygen delivery during compressions and retitrate following recovery using reliable preductal readings',
        'If severe bradycardia persists after optimised support, review indicated epinephrine and vascular access with qualified staff; verify weight, concentration, dose, route and timing against the current local protocol',
        'Assess evidence for blood loss or pneumothorax and request appropriately skilled treatment; do not diagnose either from heart rate alone',
        'Reassess heart rate, perfusion and breathing and distinguish heart-rate recovery from spontaneous breathing or complete stabilisation',
        'Plan post-resuscitation monitoring, temperature and glucose assessment, family communication and specialist handover',
    ]
    case['checklist']=[dict(action=a,critical=i in (0,1,2,4,6),window_sec=0) for i,a in enumerate(actions)]
    case['hints']=actions[:3] if spec['level']=='beginner' else []
    case['teaching_notes'].update(
        limitations='Teaching prototype requiring faculty review, not a certified course. No automated clinical grade, drug dosing calculator, procedure response, compression artefact or flow model. These cases retain intrinsic electrical activity and do not simulate absent-heart-rate arrest.',
        readings='HR is intrinsic cardiac activity, never compression rate. Low-perfusion SpO2 values are illustrative and only interpretable after faculty confirms signal reliability. Hidden BP is a model input, not an acquired invasive reading. EtCO2/PAP/CO remain unconfigured.',
        progression='Faculty selects ongoing support, poor response or recovery as alternative branches; no automatic response to medication, compression or procedure entries. Birth ages are case anchors, not waiting intervals.',
        context=history)
    return case
