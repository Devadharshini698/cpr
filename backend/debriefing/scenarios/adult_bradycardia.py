"""Original fictional bradycardia cases; manual faculty-controlled physiology."""
from copy import deepcopy
from physiology import normalize_monitor_state
from debriefing.scenarios.rhythm_selection import rhythm_state

SEVERITIES = ('stable', 'unstable')
CONTEXTS = {
    'ER': ('An adult presents after an episode of light-headedness.', 'Review medication use, onset, prior episodes and baseline heart rate.', 'SINUS_BRADY', 42),
    'ICU': ('The monitored pulse slows during critical care.', 'Review recent sedation, oxygenation, electrolytes and haemodynamic trends.', 'SINUS_BRADY', 44),
    'Theatre': ('The heart rate falls during an abdominal procedure.', 'Coordinate with the anaesthetic and surgical team; review recent stimuli, drugs and ventilation.', 'SINUS_BRADY', 40),
    'Ward_Medical': ('A slow pulse is detected during a medication round.', 'Review rate-slowing medication, renal function, electrolytes and previous observations.', 'JUNCTIONAL', 42),
    'Ward_Surgical': ('A postoperative patient develops a slow pulse.', 'Review analgesia, recent procedures, oxygenation and symptoms against baseline.', 'SINUS_BRADY', 44),
    'Ward_Ortho': ('A patient recovering from joint surgery reports feeling faint.', 'Review analgesia, medication history, fluid balance and timing relative to mobilisation.', 'SINUS_BRADY', 45),
    'Ward_Neuro': ('A slow pulse is detected during neurological observations.', 'Compare consciousness and neurological findings with baseline; review respiratory status and medication changes.', 'SINUS_BRADY', 42),
    'Ward_Cardio': ('A patient under cardiac observation develops a slow pulse.', 'Review recent ischaemic symptoms, prior conduction abnormalities and rate-slowing medication.', 'AVB3', 35),
}

def configure_bradycardia_case(spec, severity='stable'):
    if severity not in SEVERITIES:
        raise ValueError('Choose stable or unstable bradycardia')
    case = deepcopy(spec)
    presentation, history, rhythm, rate = CONTEXTS[spec['location']]
    def stage(identifier, name, unstable=False, recovery=False):
        state = rhythm_state('NSR' if recovery else rhythm)
        state.update(HR=75 if recovery else rate, pulse_rate=75 if recovery else rate,
                     ABP_sys=80 if unstable else 116, ABP_dia=45 if unstable else 72,
                     SpO2=96, avRR=22 if unstable else 16, etCO2=34 if unstable else 36,
                     CO=2.5 if unstable else 4.5)
        finding = ('Weak palpable pulse and low blood pressure; assess symptoms and other evidence of poor perfusion.' if unstable else
                   'A palpable pulse and maintained blood pressure are present; assess symptoms, baseline and ongoing risk.')
        return {'id':identifier,'name':name,'description':finding + ' Faculty must disclose examination findings separately; selecting a preset does not prove treatment delivery.',
                'state':normalize_monitor_state(state)}
    stable = stage('brady_stable','Bradycardia with maintained perfusion')
    unstable = stage('brady_unstable','Bradycardia with circulatory instability',True)
    case.update(title=f"Adult bradycardia — {spec['location_label']}", rhythm_type=rhythm, clinical_severity=severity)
    case['conditions'] = ([stable,unstable] if severity=='stable' else [unstable,stable]) + [stage('brady_recovery','Recovery and reassessment',recovery=True)]
    case['initial_state'] = deepcopy(case['conditions'][0]['state'])
    roles = ', '.join(spec['discipline_labels'])
    case['patient'].update(history=history, presentation=f'{presentation} A pulse is present. {case["conditions"][0]["description"].split(" Faculty")[0]} Initial responding personnel: {roles}.')
    case['narration_intro'] = case['patient']['presentation']
    actions = [
        'Assess airway, breathing, pulse and perfusion; compare symptoms with baseline',
        'Request monitoring, blood pressure, oximetry and a 12-lead ECG where available',
        'Determine whether bradycardia is contributing to haemodynamic compromise',
        'Investigate reversible causes including medication effects, oxygenation and metabolic disturbance',
        'Escalate persistent compromise and prepare rhythm-appropriate medication or pacing support under the current local protocol',
        'If pacing is used, assess electrical and mechanical capture rather than monitor rate alone',
        'Reassess perfusion after interventions and communicate ongoing care needs',
    ]
    case['checklist'] = [{'action':a,'critical':i in (0,2,4),'window_sec':0} for i,a in enumerate(actions)]
    case['hints'] = actions[:3] if spec['level']=='beginner' else []
    case['complications'] = []
    case['teaching_notes'] = {
        'authorship':'Independent pilot; faculty review required; no certification claim',
        'progression':'Manual instructor selection. Any rhythm can be selected using ECG controls. A rhythm change alone does not confirm a pulse or ROSC.',
        'team':f'Initial disciplines: {roles}. Allocate tasks within competence and call for missing expertise.',
        'resources':'Ward resource availability and arrival times are teaching assumptions requiring instructor confirmation.',
        'difficulty':{'beginner':'Focused assessment with prompts','intermediate':'Unprompted assessment and reassessment','advanced':'Conduction disease, competing causes and resource coordination'}[spec['level']],
        'limitations':'Illustrative states; no automatic medication response, pacing capture model or validated bradycardia-specific automatic grade. Recovery is a faculty-selected example, not guaranteed conversion of conduction disease.',
        'reference':'https://cpr.heart.org/en/resuscitation-science/cpr-and-ecc-guidelines/adult-advanced-life-support',
    }
    return case
