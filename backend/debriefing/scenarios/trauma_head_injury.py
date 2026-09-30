"""Independent adult head-injury simulation; not a neurological outcome model."""
from copy import deepcopy
from physiology import normalize_monitor_state
from debriefing.scenarios.trauma_haemorrhage import WARD_CONTEXT

COURSES = ('observation','neurological_deterioration','secondary_insult')

def configure_trauma_head_injury(spec, course='observation'):
    if course not in COURSES:
        raise ValueError('Select a supported head-injury starting state')
    case=deepcopy(spec)
    def stage(key,name,values,description):
        hr,sys,dia,rr,spo2,co2=values
        return dict(id=key,name=name,description=description+
            ' Pulse present. Neurological findings require instructor disclosure, not inference from ECG or vital signs. Review sedatives, intoxication and other examination confounders.',
            state=normalize_monitor_state(dict(rhythm='SINUS_TACHY' if hr>100 else 'NSR',HR=hr,pulse_rate=hr,
                ABP_sys=sys,ABP_dia=dia,SpO2=spo2,avRR=rr,etCO2=co2,Tblood=36.5,Tperi=36.5,
                PAP_sys=0,PAP_dia=0,CO=0,emd_pea=False)))
    observation=stage('head_observation','Head injury — initial assessment',(95,125,75,20,97,36),
        'After a road collision, opens eyes spontaneously, is confused in conversation and obeys commands (E4 V4 M6, GCS 14). Pupils equal and reactive; headache and amnesia reported. These findings do not exclude intracranial injury.')
    deterioration=stage('head_deterioration','Neurological deterioration',(100,135,80,22,96,38),
        'Now opens eyes to pressure, makes incomprehensible sounds and localises stimulation (E2 V2 M5, GCS 9). New right pupil enlargement with sluggish reaction. Urgently reassess and seek trauma/neurosurgical expertise; maintained vital signs do not exclude a serious intracranial lesion.')
    secondary=stage('head_secondary_insult','Hypoxaemia and hypotension with head injury',(125,85,50,10,85,52),
        'Reduced responsiveness: E2 V2 M4, GCS 8, with shallow ineffective breathing, hypoxaemia and hypotension. Assess airway protection and ventilation, and look for associated bleeding or other shock causes rather than attributing hypotension to isolated head injury. Pupils equal but sluggish.')
    reassessment=stage('head_reassessment','Physiological improvement — neurological reassessment required',(95,120,75,18,97,36),
        'Faculty confirms improved oxygenation, ventilation and circulation after support. Consciousness remains impaired (E2 V2 M5, GCS 9); repeat pupil and motor examination and arrange definitive assessment. Normalised monitor values do not establish neurological recovery or prognosis.')
    choices=dict(observation=observation,neurological_deterioration=deterioration,secondary_insult=secondary)
    case['conditions']=[choices[course]]+[v for k,v in choices.items() if k!=course]+[reassessment]
    case['initial_state']={**deepcopy(case['conditions'][0]['state']),'show_ibp':False,
        'NBP_sys':None,'NBP_dia':None,'NBP_mean':None,'nibp_state':'IDLE','nibp_last_measured':None}
    case.update(title=f'Adult traumatic head injury — {spec["location_label"]}',
        rhythm_type=case['initial_state']['rhythm'],clinical_severity=course,head_injury_course=course,
        monitor_schema='trauma-head-injury-1',release_status='teaching_pilot_faculty_review')
    case['patient']={**case.get('patient',{}),'age':35,'weight_kg':70,
        'history':'Head impact in a road collision; obtain timing, loss of consciousness, vomiting, seizure history, anticoagulants and baseline function. '+WARD_CONTEXT[spec['location']],
        'presentation':'35-year-old, 70 kg fictional adult after head trauma. '+case['conditions'][0]['description']+
            ' Initial responding personnel: '+', '.join(spec['discipline_labels'])}
    case['narration_intro']=case['patient']['presentation']
    actions=['Assess external haemorrhage and complete the primary survey with appropriate spinal precautions',
        'Assess airway protection, oxygenation and ventilation; prevent and address secondary physiological insults',
        'Assess perfusion and investigate associated bleeding or other causes of hypotension',
        'Record serial eye, verbal and motor responses separately, pupil size/reactivity and focal findings, with examination confounders',
        'Recognise neurological deterioration even when monitor values appear maintained; escalate for trauma/neurosurgical assessment',
        'Arrange appropriate imaging and definitive care according to stability and the local head-injury pathway',
        'Avoid treating EtCO2 as arterial CO2; seek appropriate ventilation assessment and specialist guidance',
        'Repeat the primary survey and neurological examination after interventions; obtain secondary survey and relevant history when safe',
        'Communicate neurological trends, physiological insults and treatments during transfer; avoid premature outcome predictions']
    case['checklist']=[dict(action=a,critical=i in (1,2,3,4),window_sec=0) for i,a in enumerate(actions)]
    case['hints']=actions[:3] if spec['level']=='beginner' else []
    case['complications']=[]
    case['teaching_notes']={
        'authorship':'Independent fictional adult pilot; faculty review required; not an endorsed course',
        'limitations':'Manual alternative teaching states, not an inevitable progression or validated neurological/ICP model. No automatic drug, airway or procedural response, CT diagnosis, ICP/CPP estimate or clinical grade. Reassessment numbers do not prove neurological recovery. GCS examples assume assessable, non-intubated responses; reassess components and confounders after airway management.',
        'readings':'Illustrative vital signs, not treatment targets. EtCO2 assumes usable sampling and is not PaCO2. Invasive channels hidden; measure NIBP for cuff pressure.',
        'resources':'Faculty must confirm trained staff, imaging/neurosurgical access, equipment and transfer arrangements for the selected ward.',
        'reference':'https://www.facs.org/media/vgfgjpfk/best-practices-guidelines-traumatic-brain-injury.pdf'}
    return case
