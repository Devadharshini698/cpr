"""Original instructor-controlled shock pilots; no automatic treatment response."""
from copy import deepcopy
from physiology import normalize_monitor_state
from debriefing.scenarios.paediatric_respiratory import configure_respiratory_case, PROFILES, monitor_profile

CAUSES = {
 'hypovolaemic':('Recent fluid losses, poor intake and reduced urine output.', 'Dry mucosa, cool extremities, weak pulses and delayed refill.'),
 'septic':('Fever with progressive reduced activity; assess the infection source and recent treatment.', 'Abnormal peripheral perfusion, altered interaction and reduced urine output; assess warm or cold extremities rather than assuming one septic phenotype.'),
 'cardiogenic':('Reduced feeding or exercise tolerance with increasing breathlessness; review cardiac history.', 'Weak pulses and respiratory effort; request lung examination, liver size and cardiac assessment.'),
 'haemorrhagic':('Recent injury or procedure with possible blood loss.', 'Pallor, weak pulses and delayed refill; assess visible and concealed bleeding.'),
}

def configure_shock_case(spec, profile='child', severity='compensated', cause='hypovolaemic'):
    if profile not in PROFILES or severity not in ('compensated','hypotensive') or cause not in CAUSES:
        raise ValueError('Choose a supported profile, shock severity and cause')
    case=configure_respiratory_case(spec,profile); p=PROFILES[profile]; infant=profile=='infant'
    def stage(key, recovery=False, low=False):
        hr=(120 if infant else 105) if recovery else (180 if infant else 155)+(10 if low else 0)
        state=normalize_monitor_state({'rhythm':'NSR' if recovery else 'SINUS_TACHY','HR':hr,'pulse_rate':hr,
            'ABP_sys':(60 if infant else 70) if low else p['sys'],'ABP_dia':35 if low else p['dia'],
            'SpO2':92 if cause=='cardiogenic' and not recovery else 96,
            'avRR':(30 if infant else 24) if recovery else (48 if infant else 34),
            'etCO2':36 if recovery else 26 if low else 30,
            'Tblood':38.5 if cause=='septic' and not recovery else 37,'Tperi':37,
            'PAP_sys':0,'PAP_dia':0,'CO':0,'emd_pea':False})
        finding='Improved interaction and peripheral perfusion after faculty-confirmed support; continue reassessment.' if recovery else CAUSES[cause][1]
        if not recovery: finding+=' Blood pressure is low; urgent escalation.' if low else ' Maintained blood pressure does not exclude shock.'
        return {'id':key,'name':key.replace('_',' ').title(),'description':finding+' Instructor-controlled findings; not an automatic treatment effect.','state':state}
    compensated=stage('compensated_shock'); hypotensive=stage('hypotensive_shock',low=True)
    case['conditions']=([compensated,hypotensive] if severity=='compensated' else [hypotensive,compensated])+[stage('response_to_support',recovery=True)]
    case['initial_state']={**deepcopy(case['conditions'][0]['state']),**monitor_profile(profile)}
    case.update(title=f'Paediatric shock — {spec["location_label"]}',clinical_severity=severity,shock_cause=cause,monitor_schema='paediatric-shock-1')
    case['patient']['history']=f'Under assessment in {spec["location_label"]}. '+CAUSES[cause][0]
    case['patient']['presentation']=f'{p["age_months"]}-month-old, {p["weight_kg"]} kg patient with reduced activity and abnormal perfusion. Pulse present. Initial team: '+', '.join(spec['discipline_labels'])
    case['narration_intro']=case['patient']['presentation']
    actions=['Assess appearance, breathing, pulse quality, refill and peripheral temperature',
        'Assess consciousness, urine output and perfusion trends; do not wait for hypotension',
        'Confirm age and weight; obtain caregiver history and recent losses or treatment',
        'Differentiate the likely mechanism and seek paediatric expertise',
        'Select cause-appropriate support; do not apply one fluid strategy to every shock type',
        'Reassess perfusion and respiratory findings after each intervention and watch for overload',
        'Arrange escalation, cause-specific treatment and structured handover']
    if cause=='cardiogenic': actions.append('Recognise possible pump failure; seek expert-directed support and avoid indiscriminate fluid loading')
    if cause=='haemorrhagic': actions.append('Control bleeding and escalate for appropriate blood-product support')
    if cause=='septic': actions.append('Escalate suspected infection for timely source-specific treatment under the local protocol')
    case['checklist']=[{'action':a,'critical':i in (0,1,4),'window_sec':0} for i,a in enumerate(actions)]
    case['hints']=actions[:3] if spec['level']=='beginner' else []
    case['teaching_notes']['limitations']='Faculty-review pilot, illustrative physiology, generic ECG; no automatic fluid/drug responses or validated score. Other distributive and obstructive causes remain unimplemented.'
    case['teaching_notes']['reference']='https://publications.aap.org/pediatrics/article/doi/10.1542/peds.2025-074351/205236'
    return case
