"""Independent adult trauma airway/chest pilot; manual clinical presets."""
from copy import deepcopy
from physiology import normalize_monitor_state
from debriefing.scenarios.trauma_haemorrhage import WARD_CONTEXT

INJURIES = {
    'airway': ('Threatened airway', 'Facial injury after a road collision.',
        'Blood and secretions in the mouth, noisy breathing and difficulty speaking; assess airway patency with appropriate spinal precautions.',
        (115,110,70,28,90,45), (135,90,55,10,80,58)),
    'tension': ('Suspected tension pneumothorax', 'Right-sided chest injury after a road collision.',
        'Markedly reduced right air entry, asymmetric chest movement and respiratory distress with circulatory compromise. Do not require every classic sign before recognising the threat.',
        (125,85,50,32,87,28), (145,65,35,36,78,23)),
    'haemothorax': ('Suspected major haemothorax', 'Blunt right chest injury after a fall from height.',
        'Reduced right air entry, dull percussion if assessed, chest pain, pallor and poor peripheral perfusion; consider intrathoracic blood loss and associated injuries.',
        (120,90,55,28,91,30), (140,70,40,34,84,25)),
}

def configure_trauma_airway_chest(spec, injury='airway', severity='initial'):
    if injury not in INJURIES or severity not in ('initial','deteriorating'):
        raise ValueError('Choose a supported airway/chest injury and starting state')
    label, history, findings, initial_values, worse_values = INJURIES[injury]
    case = deepcopy(spec)
    def stage(key,name,values,description):
        hr,sys,dia,rr,spo2,co2 = values
        state = normalize_monitor_state(dict(rhythm='SINUS_TACHY' if hr>100 else 'NSR',HR=hr,pulse_rate=hr,
            ABP_sys=sys,ABP_dia=dia,SpO2=spo2,avRR=rr,etCO2=co2,Tblood=36,Tperi=36,
            PAP_sys=0,PAP_dia=0,CO=0,emd_pea=False))
        return dict(id=key,name=name,state=state,description=description+
            ' Pulse present. Findings require instructor disclosure and clinical reassessment; stage selection does not prove treatment delivery.')
    initial = stage('trauma_airway_chest_initial',label+' — initial assessment',initial_values,findings)
    worsening = stage('trauma_airway_chest_deterioration','Worsening respiratory/circulatory compromise',worse_values,
        findings+' Reduced responsiveness and worsening perfusion. '+('Breathing becomes shallow and ineffective; a slower rate represents fatigue, not improvement.' if injury=='airway' else 'Reassess immediately for an unresolved life threat.'))
    response = stage('trauma_airway_chest_response','Response after faculty-confirmed support',(95,110,70,20,96,36),
        'Faculty confirms improved airway patency, ventilation and perfusion after appropriate support. Repeat primary survey, reassess the injured side and confirm ongoing care needs; improvement does not exclude residual injury or bleeding.')
    case['conditions'] = ([initial,worsening] if severity=='initial' else [worsening,initial])+[response]
    case['initial_state'] = {**deepcopy(case['conditions'][0]['state']),'show_ibp':False,
        'NBP_sys':None,'NBP_dia':None,'NBP_mean':None,'nibp_state':'IDLE','nibp_last_measured':None}
    case.update(title=f'Adult trauma {label.lower()} — {spec["location_label"]}',
        rhythm_type='SINUS_TACHY',clinical_severity=severity,trauma_injury=injury,
        monitor_schema='trauma-airway-chest-1',release_status='teaching_pilot_faculty_review')
    case['patient']={**case.get('patient',{}),'age':35,'weight_kg':70,
        'history':history+' '+WARD_CONTEXT[spec['location']],
        'presentation':'35-year-old, 70 kg fictional adult after trauma. '+case['conditions'][0]['description']+
            ' Initial responding personnel: '+', '.join(spec['discipline_labels'])}
    case['narration_intro']=case['patient']['presentation']
    actions=['Identify external life-threatening bleeding and continue a structured primary survey',
        'Assess airway patency and protection with appropriate spinal precautions; call for skilled airway support',
        'Assess respiratory effort, chest movement, air entry and oxygenation; distinguish oxygenation from ventilation',
        'Assess pulse and perfusion alongside chest findings; consider obstructive and haemorrhagic causes',
        {'airway':'Clear and support the threatened airway using appropriate trained personnel and local protocols; reassess ventilation and prepare escalation',
         'tension':'Recognise suspected tension physiology with severe compromise and arrange urgent trained treatment without delaying for imaging',
         'haemothorax':'Escalate suspected intrathoracic bleeding for trauma expertise, haemorrhage support and definitive management'}[injury],
        'Use investigations appropriate to stability without delaying treatment of immediate life threats',
        'Reassess after intervention, including airway position/function when applicable and recurrent chest compromise',
        'Assess disability and exposure, prevent heat loss, and complete secondary survey and AMPLE history when appropriate',
        'Communicate mechanism, findings, interventions and response during definitive-care handover or transfer']
    case['checklist']=[dict(action=a,critical=i in (1,2,3,4),window_sec=0) for i,a in enumerate(actions)]
    case['hints']=actions[:3] if spec['level']=='beginner' else []
    case['complications']=[]
    case['teaching_notes']={
        'authorship':'Independent fictional adult pilot; faculty review required; not an endorsed or certified course',
        'limitations':'Manual illustrative states, not a validated respiratory mechanics model or automatic trauma grade. No automatic procedural, ventilation, transfusion or drug response. All presets retain a pulse. Open pneumothorax, flail chest, tamponade and other thoracic injuries are not yet dedicated cases.',
        'readings':'Illustrative values, not treatment targets. EtCO2 assumes usable sampling and is not arterial CO2; airway obstruction may make sampling unreliable. Waveforms do not encode unilateral chest findings. Invasive channels hidden; measure NIBP for a cuff reading.',
        'resources':'Faculty must confirm ward equipment, trained staff and access to trauma treatment and transfer.',
        'reference':'https://www.facs.org/media/qdgliayt/2025_tr_bestpracticesguidelines_chest-wall.pdf'}
    return case
