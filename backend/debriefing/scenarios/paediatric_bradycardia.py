"""Independent paediatric bradycardia teaching pilot, not neonatal resuscitation."""
from copy import deepcopy
from physiology import normalize_monitor_state
from debriefing.scenarios.paediatric_respiratory import configure_respiratory_case, PROFILES, monitor_profile

def configure_paediatric_bradycardia(spec, profile='child', severity='compromise'):
    if profile not in PROFILES or severity not in ('maintained','compromise'):
        raise ValueError('Choose infant or child and a supported perfusion state')
    case=configure_respiratory_case(spec,profile)
    p=PROFILES[profile]; infant=profile=='infant'
    def stage(key, hr, poor=False, supported=False, recovery=False):
        state=normalize_monitor_state({'rhythm':'NSR' if recovery else 'SINUS_BRADY','HR':hr,'pulse_rate':hr,
            'ABP_sys':(60 if infant else 70) if poor else p['sys'], 'ABP_dia':35 if poor else p['dia'],
            'SpO2':96 if supported or not poor else 82,'avRR':(30 if infant else 24) if supported or not poor else 10,
            'etCO2':38 if supported or not poor else 58,'Tblood':37,'Tperi':37,
            'PAP_sys':0,'PAP_dia':0,'CO':0,'emd_pea':False})
        description=('Improved interaction and perfusion following faculty-confirmed support; reassess for recurrence.' if recovery else
            'Slow pulse with maintained perfusion; assess baseline, symptoms, oxygenation and reversible causes.' if not poor else
            'Weak palpable pulse, low blood pressure and reduced responsiveness. '+('Faculty confirms effective ventilation with oxygen, but severe bradycardia and poor perfusion persist.' if supported else 'Shallow ineffective breathing and hypoxaemia; urgently assess and support airway and ventilation.'))
        return {'id':key,'name':key.replace('_',' ').title(),'description':description+' Stage changes do not prove learner actions.','state':state}
    maintained=stage('bradycardia_maintained_perfusion',90 if infant else 65)
    compromise=stage('bradycardia_with_compromise',55,poor=True)
    persistent=stage('persistent_compromise_after_ventilation',50,poor=True,supported=True)
    recovery=stage('recovery_and_reassessment',120 if infant else 105,supported=True,recovery=True)
    case['conditions']=([maintained,compromise] if severity=='maintained' else [compromise,maintained])+[persistent,recovery]
    case['initial_state']={**deepcopy(case['conditions'][0]['state']),**monitor_profile(profile)}
    case.update(title=f'Paediatric bradycardia — {spec["location_label"]}',rhythm_type='SINUS_BRADY',clinical_severity=severity,monitor_schema='paediatric-bradycardia-1')
    case['patient']['presentation']=f'{p["age_months"]}-month-old, {p["weight_kg"]} kg patient with a slow palpable pulse. Assess breathing and perfusion. Initial team: '+', '.join(spec['discipline_labels'])
    case['narration_intro']=case['patient']['presentation']
    actions=['Assess pulse, breathing and perfusion together; compare with age and baseline',
        'Recognise respiratory compromise and establish effective oxygenation and ventilation',
        'Reassess pulse and perfusion after respiratory support; do not infer recovery from oxygen saturation alone',
        'Recognise the need for CPR when heart rate remains below 60/min with cardiopulmonary compromise despite effective ventilation with oxygen',
        'Seek paediatric support and evaluate medication effects, vagal triggers, conduction disease and metabolic causes',
        'Use age- and weight-appropriate escalation under the current local protocol',
        'Reassess after each intervention and communicate ongoing support needs']
    case['checklist']=[{'action':a,'critical':i in (0,1,2,3),'window_sec':0} for i,a in enumerate(actions)]
    case['hints']=actions[:3] if spec['level']=='beginner' else []
    case['teaching_notes']['limitations']='Respiratory-associated bradycardia pilot; not a complete set of conduction or toxicological cases. No automatic medication, pacing or compression-generated circulation model. Pulse remains present in all presets. No validated clinical grade.'
    case['teaching_notes']['reference']='https://publications.aap.org/pediatrics/article/doi/10.1542/peds.2025-074351/205236'
    return case
