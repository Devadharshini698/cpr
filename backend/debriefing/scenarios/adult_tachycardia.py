"""Original ward-based teaching cases, not an automated treatment algorithm."""
from copy import deepcopy
from physiology import normalize_monitor_state
from debriefing.scenarios.rhythm_selection import rhythm_state

SEVERITIES = ('stable', 'unstable')
CONTEXTS = {
    'ER': ('Sudden palpitations while waiting for review.', 'Previous brief episodes of palpitations; medication history needs clarification.', 'SVT', 180),
    'ICU': ('A patient being treated for pneumonia develops a persistently fast pulse.', 'Recent infection, fluid balance and vasoactive medication changes require review.', 'AFIB', 155),
    'Theatre': ('During abdominal surgery, the monitored heart rate rises.', 'Review surgical blood loss, anaesthetic depth, temperature and ventilation with the team.', 'SINUS_TACHY', 135),
    'Ward_Medical': ('An adult admitted with infection develops a fast pulse during routine observations.', 'Fever and poor intake; review oxygenation, hydration and medications.', 'SINUS_TACHY', 130),
    'Ward_Surgical': ('A postoperative patient develops persistent tachycardia.', 'Review pain, fluid balance, wound and drain losses; do not assume an arrhythmia is the cause.', 'SINUS_TACHY', 135),
    'Ward_Ortho': ('A patient recovering from hip surgery develops tachycardia during mobilisation.', 'Review symptoms, analgesia, fluid balance and cardiopulmonary causes before assigning a diagnosis.', 'SINUS_TACHY', 130),
    'Ward_Neuro': ('An adult recovering from stroke develops a fast irregular pulse.', 'Compare neurological findings with baseline and review medication history.', 'AFIB', 150),
    'Ward_Cardio': ('An adult under observation for coronary disease develops palpitations.', 'Review prior ECG, ventricular function, medications and new symptoms.', 'VT', 165),
}

def configure_tachycardia_case(spec, severity='stable'):
    if severity not in SEVERITIES:
        raise ValueError('Choose stable or unstable tachycardia')
    case = deepcopy(spec)
    presentation, history, rhythm, rate = CONTEXTS[spec['location']]
    sinus = rhythm == 'SINUS_TACHY'
    def stage(identifier, name, unstable=False, recovery=False):
        state = rhythm_state('NSR' if recovery else rhythm)
        state.update(HR=90 if recovery else rate, pulse_rate=90 if recovery else rate,
                     ABP_sys=85 if unstable else 118, ABP_dia=50 if unstable else 74,
                     SpO2=95 if unstable else 97, avRR=24 if unstable else 18,
                     etCO2=32 if unstable else 36, CO=3 if unstable else 5)
        findings = ('Low blood pressure and weak peripheral pulses; reassess consciousness against baseline and signs of poor perfusion.' if unstable else
                    'Palpable pulse, maintained blood pressure and no new observed signs of poor perfusion; continue assessment.')
        return {'id':identifier,'name':name,'description':findings + ' Instructor must disclose examination findings separately. Preset selection is not evidence of an intervention.', 'state':normalize_monitor_state(state)}
    stable = stage('tachy_stable','Tachycardia with maintained perfusion')
    unstable = stage('tachy_unstable','Tachycardia with circulatory instability',True)
    case.update(title=f"Adult tachycardia — {spec['location_label']}", clinical_severity=severity, rhythm_type=rhythm)
    case['conditions'] = ([stable,unstable] if severity == 'stable' else [unstable,stable]) + [stage('tachy_recovery','Recovery and reassessment',recovery=True)]
    case['initial_state'] = deepcopy(case['conditions'][0]['state'])
    roles = ', '.join(spec['discipline_labels'])
    case['patient'].update(history=history, presentation=f'{presentation} A pulse is present. {case["conditions"][0]["description"].split(" Instructor")[0]} Initial responding personnel: {roles}.')
    case['narration_intro'] = case['patient']['presentation']
    cause_action = ('Investigate and treat the cause of sinus tachycardia; do not cardiovert a compensatory sinus response' if sinus else
                    'Assess whether the arrhythmia is causing instability and select rhythm-appropriate management with expert support')
    actions = ['Assess airway, breathing, pulse and perfusion; establish clinical stability',
               'Request monitoring, blood pressure, oximetry and a 12-lead ECG where available',
               'Characterise the rhythm and review reversible causes and medications', cause_action,
               'Allocate tasks within competence and request missing personnel or equipment',
               'Reassess symptoms, perfusion and rhythm after each intervention',
               'Plan ongoing care and communicate a structured handover']
    case['checklist'] = [{'action':a,'critical':i in (0,3),'window_sec':0} for i,a in enumerate(actions)]
    case['hints'] = actions[:3] if spec['level']=='beginner' else []
    case['complications'] = []
    case['teaching_notes'] = {'authorship':'Independent pilot; faculty clinical review required',
        'progression':'Instructor-controlled. Use ECG and pulse controls for any rhythm change or deterioration; no automatic conversion or ROSC.',
        'clinical_focus':cause_action, 'resources':'Ward resources and arrival times are configurable teaching assumptions, not institutional facts.',
        'difficulty':{'beginner':'Focused assessment with prompts','intermediate':'Unprompted reassessment and differential diagnosis','advanced':'Competing causes, resource coordination and escalation'}[spec['level']],
        'reference':'https://cpr.heart.org/-/media/CPR-Files/CPR-Guidelines-Files/2025-Algorithms/Algorithm-ACLS-Tachycardia-250514.pdf',
        'limitations':'Illustrative vital states; no validated tachycardia-specific automatic grade or automatic medication response.'}
    return case
