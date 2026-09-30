"""Original pulse-present tachycardia teaching cases; faculty review required."""
from copy import deepcopy
from physiology import normalize_monitor_state
from debriefing.scenarios.paediatric_respiratory import configure_respiratory_case, PROFILES, monitor_profile

PATTERNS = {'sinus':'SINUS_TACHY','narrow':'SVT','wide':'VT'}

def configure_paediatric_tachyarrhythmia(spec, profile='child', severity='maintained', pattern='sinus'):
    if profile not in PROFILES or severity not in ('maintained','compromise') or pattern not in PATTERNS:
        raise ValueError('Choose a supported patient profile, perfusion state and teaching pattern')
    case=configure_respiratory_case(spec,profile); p=PROFILES[profile]; infant=profile=='infant'
    hr={'sinus':180 if infant else 160,'narrow':240 if infant else 200,'wide':220 if infant else 190}[pattern]
    def stage(key, poor=False, recovery=False):
        rate=(120 if infant else 105) if recovery else hr
        state=normalize_monitor_state({'rhythm':'NSR' if recovery else PATTERNS[pattern],'HR':rate,'pulse_rate':rate,
            'ABP_sys':(60 if infant else 70) if poor else p['sys'],'ABP_dia':35 if poor else p['dia'],
            'SpO2':95 if poor else 97,'avRR':(46 if infant else 34) if poor else (30 if infant else 24),
            'etCO2':30 if poor else 36,'Tblood':38.5 if pattern=='sinus' and not recovery else 37,
            'Tperi':38.5 if pattern=='sinus' and not recovery else 37,'PAP_sys':0,'PAP_dia':0,'CO':0,'emd_pea':False})
        description=('Improved interaction and perfusion after faculty-confirmed support; reassess for recurrence.' if recovery else
            'Weak palpable pulse, hypotension and reduced interaction; assess whether the rhythm is causing compromise or reflecting another illness.' if poor else
            'Fast palpable pulse with maintained blood pressure; assess symptoms, perfusion, onset and underlying causes.')
        return {'id':key,'name':key.replace('_',' ').title(),'description':description+' Instructor-selected state; not an automatic treatment effect.','state':state}
    maintained=stage('tachycardia_maintained_perfusion'); compromise=stage('tachycardia_with_compromise',poor=True)
    case['conditions']=([maintained,compromise] if severity=='maintained' else [compromise,maintained])+[stage('recovery_and_reassessment',recovery=True)]
    case['initial_state']={**deepcopy(case['conditions'][0]['state']),**monitor_profile(profile)}
    case.update(title=f'Paediatric tachyarrhythmia — {spec["location_label"]}',rhythm_type=PATTERNS[pattern],clinical_severity=severity,teaching_pattern=pattern,monitor_schema='paediatric-tachyarrhythmia-1')
    histories={'sinus':'Gradual increase in pulse during a febrile illness with reduced intake; review pain, oxygenation and perfusion.',
        'narrow':'Abrupt onset of a fast pulse; caregiver reports a sudden change in feeding or activity. Review prior episodes and medications.',
        'wide':'New fast pulse during observation; review cardiac history, medications, electrolytes and prior ECG. A wide-complex pattern does not establish its mechanism.'}
    case['patient']['history']=f'Under care in {spec["location_label"]}. '+histories[pattern]
    case['patient']['presentation']=f'{p["age_months"]}-month-old, {p["weight_kg"]} kg patient with a fast palpable pulse. Assess breathing and perfusion. Initial team: '+', '.join(spec['discipline_labels'])
    case['narration_intro']=case['patient']['presentation']
    actions=['Assess airway, breathing, pulse and perfusion before choosing rhythm treatment',
        'Confirm age and weight; obtain onset, caregiver history, medications and prior episodes',
        'Request monitoring and a 12-lead ECG; assess rate, regularity, atrial activity and QRS features together',
        'Differentiate sinus tachycardia from a primary arrhythmia; rate alone is not diagnostic',
        'Identify compromise and escalate with age- and weight-appropriate expert support',
        'Reassess symptoms, perfusion and rhythm after every intervention',
        'Plan ongoing observation and structured handover']
    actions.append('Treat the underlying cause rather than cardioverting a compensatory sinus response' if pattern=='sinus' else
        'Choose rhythm-appropriate management under the local paediatric protocol; avoid assuming all fast rhythms receive the same therapy')
    case['checklist']=[{'action':a,'critical':i in (0,3,4,7),'window_sec':0} for i,a in enumerate(actions)]
    case['hints']=actions[:3] if spec['level']=='beginner' else []
    case['teaching_notes']['limitations']='Generic ECG morphology: not a validated paediatric QRS-duration teaching tool. Wide-complex preset uses VT morphology but does not exclude SVT with aberrancy clinically. No automatic drug/cardioversion response or validated score. All presets retain a pulse.'
    case['teaching_notes']['reference']='https://publications.aap.org/pediatrics/article/doi/10.1542/peds.2025-074351/205236'
    return case
