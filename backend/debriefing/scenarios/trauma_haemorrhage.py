"""Independent adult trauma haemorrhage teaching pilot, not a licensed course."""
from copy import deepcopy
from physiology import normalize_monitor_state

MECHANISMS = {
    'external': ('Deep limb wound following a machinery injury.', 'Ongoing visible limb bleeding; inspect the wound and assess distal circulation.'),
    'pelvic': ('High-energy road collision with pelvic pain.', 'Pelvic pain and suspected concealed bleeding; avoid repeated provocative manipulation.'),
    'abdominal': ('Blunt abdominal injury after a road collision.', 'Abdominal tenderness with possible concealed haemorrhage; absence of external bleeding does not exclude blood loss.'),
}
WARD_CONTEXT = {
    'ER':'Newly arrived after injury; obtain the prehospital handover.',
    'ICU':'Under critical-care observation after injury; review prior haemorrhage control and current trends.',
    'Theatre':'In the operating area for trauma care; coordinate haemorrhage control with surgery and anaesthesia.',
    'Ward_Medical':'Deterioration during observation after injury; urgently arrange trauma-capable care.',
    'Ward_Surgical':'Under surgical observation after injury; urgently reassess for ongoing bleeding.',
    'Ward_Ortho':'Under orthopaedic care after injury; reassess concealed bleeding and associated injuries.',
    'Ward_Neuro':'Under neurological observation after trauma; do not attribute circulatory deterioration solely to head injury.',
    'Ward_Cardio':'Deterioration after injury in a non-trauma ward; mobilise trauma expertise and review anticoagulants.',
}

def configure_trauma_haemorrhage(spec, mechanism='external', severity='compensated'):
    if mechanism not in MECHANISMS or severity not in ('compensated','hypotensive'):
        raise ValueError('Select a supported injury mechanism and haemorrhage severity')
    case=deepcopy(spec)
    history, finding=MECHANISMS[mechanism]
    def stage(key,name,hr,sys,dia,rr,co2,temp,description):
        state=normalize_monitor_state(dict(rhythm='SINUS_TACHY' if hr>100 else 'NSR',HR=hr,pulse_rate=hr,
            ABP_sys=sys,ABP_dia=dia,SpO2=96,avRR=rr,etCO2=co2,Tblood=temp,Tperi=temp,
            PAP_sys=0,PAP_dia=0,CO=0,emd_pea=False))
        return dict(id=key,name=name,state=state,description=description+' '+finding+
            ' Airway: assess patency with appropriate spinal precautions. Breathing: assess effort, chest symmetry and air entry. Exposure: seek associated injuries and prevent heat loss. Instructor findings are not proof of learner actions.')
    compensated=stage('trauma_compensated','Haemorrhage — maintained blood pressure',115,110,70,24,32,36.2,
        'Anxious but responsive, cool extremities, weak peripheral pulse and delayed refill. Maintained pressure and oxygen saturation do not exclude serious blood loss.')
    hypotensive=stage('trauma_hypotensive','Haemorrhage — hypotension',135,80,45,30,27,35.5,
        'Increasing drowsiness, weak palpable pulse, cold extremities and hypotension; reassess life threats and urgently escalate haemorrhage control.')
    persistent=stage('trauma_persistent','Persistent bleeding and deterioration',145,65,35,32,24,35.2,
        'Poor responsiveness and worsening perfusion with a palpable pulse. Reassess ongoing bleeding, support, missed injuries and access to definitive care.')
    response=stage('trauma_reassessment','Response after faculty-confirmed support',95,105,65,20,35,36.3,
        'Faculty confirms improved perfusion following haemorrhage control and support. Repeat primary survey before secondary survey, reassess bleeding and arrange definitive care; improvement is not proof that all injuries are treated.')
    case['conditions']=([compensated,hypotensive] if severity=='compensated' else [hypotensive,compensated])+[persistent,response]
    case['initial_state']={**deepcopy(case['conditions'][0]['state']), 'show_ibp':False,
        'NBP_sys':None,'NBP_dia':None,'NBP_mean':None,'nibp_state':'IDLE','nibp_last_measured':None}
    case.update(title=f'Adult trauma haemorrhage — {spec["location_label"]}',rhythm_type='SINUS_TACHY',
        clinical_severity=severity,trauma_mechanism=mechanism,monitor_schema='trauma-haemorrhage-1',release_status='teaching_pilot_faculty_review')
    case['patient']={**case.get('patient',{}),'age':35,'weight_kg':70,
        'history':history+' '+WARD_CONTEXT[spec['location']],
        'presentation':'35-year-old, 70 kg fictional adult with traumatic bleeding. '+case['conditions'][0]['description']+
        ' Initial responding personnel: '+', '.join(spec['discipline_labels'])}
    case['narration_intro']=case['patient']['presentation']
    actions=['Identify and control life-threatening external bleeding promptly when present',
        'Assess airway with appropriate spinal precautions and assess breathing for immediate threats',
        'Assess pulse, perfusion and blood-pressure trends; seek concealed bleeding even without external blood loss',
        'Activate trauma and major-haemorrhage support as indicated, allocate roles and arrange definitive haemorrhage control',
        'Obtain appropriate vascular access and investigations and use the local haemorrhage protocol for resuscitation',
        'Assess responsiveness and neurological findings; do not infer brain injury severity from blood pressure alone',
        'Expose sufficiently to identify injuries while preventing heat loss',
        'Repeat the primary survey after interventions; perform secondary survey and AMPLE history when immediate threats are addressed',
        'Communicate injury mechanism, findings, treatment and response during urgent transfer or definitive-care handover']
    case['checklist']=[dict(action=a,critical=i in (0,1,2,3),window_sec=0) for i,a in enumerate(actions)]
    case['hints']=actions[:3] if spec['level']=='beginner' else []
    case['complications']=[]
    case['teaching_notes']={'authorship':'Independent fictional adult pilot; faculty review required; no course endorsement',
        'limitations':'Manual illustrative presets, not a validated haemorrhage model, shock classification or automatic clinical grade. No automatic fluid, transfusion or procedural effects. Pulse remains present. Associated chest/head injuries require faculty assessment; not yet dedicated case modules.',
        'readings':'Illustrative values, not resuscitation targets. SpO2 does not measure circulating blood volume. EtCO2 assumes usable sampling and is not interchangeable with arterial CO2. Invasive channels are hidden; measure NIBP for a cuff reading.',
        'resources':'Selected ward and personnel determine the setting; faculty must confirm equipment, blood products, trauma expertise and transfer availability.',
        'reference':'https://www.facs.org/quality-programs/trauma/education/advanced-trauma-life-support/atls-11/'}
    return case
