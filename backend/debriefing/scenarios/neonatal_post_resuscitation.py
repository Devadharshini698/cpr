"""Independent neonatal post-resuscitation stabilisation teaching pilot."""
from copy import deepcopy
from physiology import normalize_monitor_state
from debriefing.scenarios.neonatal_transition import configure_neonatal_transition

TOPIC='Post-resuscitation stabilisation'
FOCI={
    'assessment':('Initial post-resuscitation assessment','Heart rate has recovered after prolonged assisted ventilation. Continuing support and surveillance are required; normal-looking monitor numbers do not establish neurological or metabolic recovery.'),
    'respiratory':('Ongoing respiratory compromise','Shallow, ineffective spontaneous breathing with reduced air entry after initial recovery. Reassess airway, support, chest movement and oxygenation.'),
    'perfusion':('Persistent poor perfusion','Pallor, cool extremities and delayed capillary refill despite recovered heart rate. Review perfusion, blood loss, support and available measurements; rate alone does not establish adequate circulation.'),
    'temperature':('Low temperature','Measured temperature is low after resuscitation and exposure. Review the environment and thermal care, and reassess serially without assuming intentional therapeutic cooling.'),
    'neurometabolic':('Neurological / glucose assessment','Reduced activity and tone persist despite recovered cardiorespiratory values. Request glucose measurement, repeat neurological assessment and specialist review; no laboratory result or neurological diagnosis can be inferred from the ECG.'),
}

def configure_neonatal_post_resuscitation(spec,profile='term',setting='delivery_room',focus='assessment'):
    if focus not in FOCI:
        raise ValueError('Select a supported neonatal stabilisation focus')
    case=configure_neonatal_transition(spec,profile,'poor_transition',setting)
    label,history=FOCI[focus]
    template=case['conditions'][-1]
    def stage(key,name,minute,hr,rr,spo2,sys,dia,temp,description):
        item=deepcopy(template)
        item.update(id=key,name=name,description=description)
        state=item['state']
        state.update(HR=hr,pulse_rate=hr,avRR=rr,SpO2=spo2,ABP_sys=sys,ABP_dia=dia,
            Tperi=temp,Tblood=temp,neonatal_age_minutes=minute,
            neonatal_ventilation='Faculty-confirmed effective respiratory rate; support assessed separately')
        # Post-transition limits are illustrative local teaching choices, not
        # an extension of the published minute-by-minute birth target table.
        state['alarm_thresholds']['SpO2']={'low':90,'high':97}
        state['alarm_profile_note']='Illustrative post-resuscitation teaching limits, not prescribed oxygen targets. Faculty must individualise for gestation, support and the clinical condition.'
        item['state']=normalize_monitor_state(state)
        return item
    values={
        'assessment':(140,40,94,55,30,36.7),
        'respiratory':(125,15,85,52,28,36.7),
        'perfusion':(165,45,93,38,20,36.6),
        'temperature':(120,35,93,52,28,35.5),
        'neurometabolic':(140,40,94,55,30,36.7),
    }
    initial=stage('neo_post_'+focus,label+' — 10 min',10,*values[focus],history)
    deterioration=stage('neo_post_deterioration','Recurrent deterioration — 15 min',15,85,10,78,36,18,36.3,
        'Breathing becomes ineffective with falling heart rate and poor perfusion. Reassess immediately, restore appropriate support and reactivate neonatal resuscitation expertise; transfer preparation must not delay treatment.')
    response=stage('neo_post_response','Faculty-confirmed stabilisation — 20 min',20,140,40,94,55,30,36.8,
        'Faculty confirms improved ventilation, perfusion and temperature after care. Continue surveillance and repeat glucose and neurological assessment where indicated; this stage does not certify metabolic or neurological recovery.')
    handover=stage('neo_post_handover','Specialist handover and monitored transfer — 20 min',20,140,40,94,55,30,36.8,
        'The receiving neonatal team is contacted. Summarise gestation, birth course, resuscitation, respiratory support, trends, temperature, glucose results if actually obtained, neurological findings and unresolved concerns. Confirm transport capability and contingency plans; this is not discharge clearance.')
    case['conditions']=[initial,deterioration,response,handover]
    flags={k:v for k,v in case['initial_state'].items() if k.startswith('show_') or k.startswith('NBP_') or k.startswith('nibp_')}
    case['initial_state']={**deepcopy(initial['state']),**flags}
    case.update(title=f'Newborn post-resuscitation stabilisation — {label} — {case["location_label"]}',
        monitor_schema='neonatal-post-resuscitation-1',clinical_severity=focus,neonatal_post_focus=focus)
    case['patient']['history']+=' Resuscitation included prolonged assisted ventilation; heart rate has recovered. '+history
    case['patient']['presentation']=f'Fictional {case["patient"]["gestational_age_weeks"]}-week, {case["patient"]["weight_kg"]} kg newborn at 10 minutes after birth following resuscitation. Focus: {label}. Team: '+', '.join(spec['discipline_labels'])
    case['narration_intro']=case['patient']['presentation']
    actions=[
        'Reassess airway, breathing, support requirements, heart rate and perfusion after resuscitation; do not equate heart-rate recovery with complete recovery',
        'Review reliable oxygenation readings and respiratory support with neonatal expertise; avoid unassessed withdrawal or excessive support',
        'Measure and trend temperature and provide appropriate thermal care',
        'Obtain an early glucose measurement and reassess until stable according to the neonatal protocol; document actual results rather than assumed normality',
        'Assess activity, tone and possible seizures and seek specialist evaluation of neurological concerns; therapeutic hypothermia requires eligibility assessment and a defined specialist protocol, not automatic cooling',
        'Recognise recurrent deterioration, reassess reversible causes and reactivate neonatal resuscitation promptly',
        'Arrange monitored specialist care and transport capability with an explicit airway and deterioration contingency plan',
        'Give a structured handover and communicate the course, uncertainties and ongoing plan with the family',
    ]
    case['checklist']=[dict(action=a,critical=i in (0,2,3,5),window_sec=0) for i,a in enumerate(actions)]
    case['hints']=actions[:3] if spec['level']=='beginner' else []
    case['teaching_notes'].update(
        limitations='Faculty-review teaching pilot. No glucose assay, EEG, drug/fluid response, cooling controller or automated clinical grade. Normal vital signs cannot exclude neurological injury or hypoglycaemia.',
        findings='Use the instructor Patient assessment panel to enter and explicitly reveal glucose and neurological findings after a learner request. No invented laboratory results are displayed on the monitor.',
        progression='Deterioration, improvement and handover are faculty-selected branches, not mandatory chronological steps or automatic treatment responses. Birth ages are case anchors, not waiting intervals.',
        readings='Post-resuscitation SpO2 alarm limits are illustrative and faculty-adjustable, not the first-minutes transition table or universal treatment targets. BP is a hidden model value until measured; EtCO2/PAP/CO remain unconfigured.',
        context=history)
    return case
