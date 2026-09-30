"""Single-patient multisystem trauma teaching presets, not coupled physiology."""
from copy import deepcopy
from physiology import normalize_monitor_state
from debriefing.scenarios.trauma_haemorrhage import configure_trauma_haemorrhage, WARD_CONTEXT

FOCUSES = ('initial','respiratory','circulatory','neurological')

def configure_multisystem_trauma(spec, focus='initial'):
    if focus not in FOCUSES:
        raise ValueError('Select a supported multisystem trauma starting state')
    case=configure_trauma_haemorrhage(spec,'pelvic')
    def stage(key,name,values,findings):
        hr,sys,dia,rr,spo2,co2,temp=values
        return dict(id='multisystem_'+key,name=name,
            description=findings+' Pulse present. Head, right chest and pelvic injuries remain concerns in this same patient. Reassess the whole primary survey; findings require instructor disclosure. No intervention is inferred from selecting this preset.',
            state=normalize_monitor_state(dict(rhythm='SINUS_TACHY' if hr>100 else 'NSR',HR=hr,pulse_rate=hr,
                ABP_sys=sys,ABP_dia=dia,SpO2=spo2,avRR=rr,etCO2=co2,Tblood=temp,Tperi=temp,
                PAP_sys=0,PAP_dia=0,CO=0,emd_pea=False)))
    initial=stage('initial','Multiple injuries — initial assessment',(115,105,65,26,92,33,36),
        'High-energy road collision with head impact, right chest pain and pelvic pain. Airway patent but speech limited by breathlessness; reduced right air entry, cool extremities and delayed refill. Confused but obeys commands (E4 V4 M6, GCS 14), pupils equal/reactive. No visible major external bleeding; seek concealed haemorrhage.')
    respiratory=stage('respiratory','Chest compromise with shock',(135,80,45,34,84,26,35.8),
        'Markedly reduced right air entry and asymmetric chest movement, worsening distress and hypotension raise concern for tension physiology as well as concealed bleeding. Eyes open to voice, confused speech, obeys commands (E3 V4 M6, GCS 13). Urgently assess and arrange trained treatment; do not assume one cause explains all shock.')
    circulatory=stage('circulatory','Persistent shock after chest support',(140,75,40,28,95,25,35.5),
        'Faculty confirms improved right chest movement and air entry after appropriate chest support, but weak pulses, delayed refill and hypotension persist. Pelvic injury remains a possible bleeding source; seek other sources. E3 V4 M6, GCS 13; pupils equal/reactive. Improved oxygen saturation does not mean haemorrhage is controlled.')
    neurological=stage('neurological','Neurological deterioration after physiological support',(100,120,75,20,96,36,36.2),
        'Faculty confirms improved oxygenation and perfusion after support. Despite this, consciousness worsens to E2 V2 M5, GCS 9, with a newly enlarged sluggish right pupil. Reassess airway protection and examination confounders and urgently escalate suspected intracranial injury. Do not diagnose a lesion from monitor values.')
    reassessment=stage('reassessment','Ongoing stabilisation and definitive-care handover',(95,120,75,20,97,36,36.5),
        'Faculty confirms maintained oxygenation and perfusion after support. Neurological impairment persists (E2 V2 M5, GCS 9); repeat pupil and motor assessment. Continue haemorrhage surveillance, reassessment and transfer/definitive-care planning. This state is not clearance of injury or a favourable neurological prognosis.')
    stages=dict(initial=initial,respiratory=respiratory,circulatory=circulatory,neurological=neurological)
    # Starting later skips already-addressed phases rather than implying spontaneous improvement.
    keys=list(FOCUSES)
    case['conditions']=[stages[k] for k in keys[keys.index(focus):]]+[reassessment]
    case['initial_state']={**deepcopy(case['conditions'][0]['state']),'show_ibp':False,
        'NBP_sys':None,'NBP_dia':None,'NBP_mean':None,'nibp_state':'IDLE','nibp_last_measured':None}
    case.update(title=f'Adult multisystem trauma — {spec["location_label"]}',
        rhythm_type=case['initial_state']['rhythm'],clinical_severity=focus,multisystem_focus=focus,
        monitor_schema='trauma-multisystem-1')
    case.pop('trauma_mechanism',None)
    case['patient']['history']='High-energy road collision with head impact, right chest injury and suspected pelvic injury. '+WARD_CONTEXT[spec['location']]
    case['patient']['presentation']='35-year-old, 70 kg fictional adult with multiple injuries. '+case['conditions'][0]['description']+' Initial responding personnel: '+', '.join(spec['discipline_labels'])
    case['narration_intro']=case['patient']['presentation']
    actions=['Assess external life-threatening bleeding and complete the primary survey with appropriate spinal precautions',
        'Allocate parallel team tasks within competence and call for trauma, airway, surgical and other required expertise',
        'Assess airway protection and oxygenation/ventilation; recognise life-threatening chest compromise and arrange urgent trained management',
        'Reassess persistent shock after chest support; investigate concealed haemorrhage and use the local haemorrhage pathway',
        'Repeat GCS components, pupil and motor assessment; escalate neurological deterioration even after vital signs improve',
        'Prevent secondary physiological insults and heat loss; reassess after every intervention',
        'Choose investigations according to stability without delaying treatment or definitive-care transfer',
        'Complete secondary survey and AMPLE history when safe; look for missed injuries without losing primary-survey priorities',
        'Coordinate receiving-team handover with mechanism, suspected injuries, trends, interventions, response and unresolved threats']
    case['checklist']=[dict(action=a,critical=i in (0,2,3,4,5),window_sec=0) for i,a in enumerate(actions)]
    case['hints']=actions[:3] if spec['level']=='beginner' else []
    case['teaching_notes']['limitations']='Independent composite teaching pilot requiring faculty review; manual sequential states, not a coupled injury or treatment-response model. No automatic drug/procedure effects or validated trauma grade. Later starting states assume the support explicitly described by faculty. Neurological findings are not derived from vital signs; GCS examples assume assessable non-intubated responses. Reassess confounders after airway management.'
    return case
