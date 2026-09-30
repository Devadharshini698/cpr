"""Independent, instructor-controlled paediatric post-resuscitation teaching cases."""
from copy import deepcopy
from physiology import normalize_monitor_state
from debriefing.scenarios.paediatric_respiratory import configure_respiratory_case, PROFILES, monitor_profile

FOCUSES = ('assessment', 'oxygenation', 'ventilation', 'perfusion')

def configure_post_resuscitation(spec, profile='child', focus='assessment'):
    if profile not in PROFILES or focus not in FOCUSES:
        raise ValueError('Select a supported paediatric profile and post-resuscitation focus')
    case = configure_respiratory_case(spec, profile)
    p = PROFILES[profile]
    hr = 130 if profile == 'infant' else 110
    baseline = dict(rhythm='NSR', HR=hr, pulse_rate=hr, ABP_sys=p['sys'], ABP_dia=p['dia'],
                    SpO2=95, avRR=30 if profile == 'infant' else 24, etCO2=38,
                    Tblood=37, Tperi=37, PAP_sys=0, PAP_dia=0, CO=0, emd_pea=False)
    def stage(key, name, description, **changes):
        return dict(id=key, name=name, description=description,
                    state=normalize_monitor_state({**baseline, **changes}))
    stages = {
        'assessment': stage('post_resuscitation_assessment', 'Initial post-resuscitation assessment',
            'Circulation returned before this case began. Pulse is palpable. Responsiveness remains reduced; request airway, breathing, perfusion and neurological findings. Normal numbers do not prove recovery.'),
        'oxygenation': stage('post_resuscitation_hypoxaemia', 'Persistent hypoxaemia',
            'Pulse present with low oxygen saturation. Check signal quality, airway, air entry, oxygen delivery and respiratory support; confirm findings clinically.', SpO2=88),
        'ventilation': stage('post_resuscitation_hypoventilation', 'Inadequate ventilation',
            'Pulse present, shallow breathing and reduced responsiveness. Elevated sampled EtCO2 prompts assessment of ventilation and blood gas; EtCO2 is not arterial CO2.', avRR=10, etCO2=58, SpO2=92),
        'perfusion': stage('post_resuscitation_hypotension', 'Hypotension and poor perfusion',
            'Pulse present but weak, prolonged capillary refill and low blood pressure. Reassess circulation, cause and age-appropriate haemodynamic goals with paediatric expertise.',
            rhythm='SINUS_TACHY', HR=160 if profile=='infant' else 145, pulse_rate=160 if profile=='infant' else 145,
            ABP_sys=60 if profile=='infant' else 70, ABP_dia=35),
    }
    case['conditions'] = [stages[focus]] + [stages[k] for k in FOCUSES if k != focus]
    case['conditions'].append(stage('post_resuscitation_stabilisation', 'Reassessment after support',
        'Faculty confirms improved oxygenation, ventilation and perfusion. Reassess neurological status separately, continue monitoring and arrange ongoing specialist care. This is not a neurological prognosis.'))
    case['initial_state'] = {**deepcopy(stages[focus]['state']), **monitor_profile(profile)}
    case.update(title=f'Paediatric post-resuscitation care — {spec["location_label"]}',
                rhythm_type=stages[focus]['state']['rhythm'], clinical_severity=focus,
                post_resuscitation_focus=focus, monitor_schema='paediatric-post-resuscitation-1')
    case['patient']['history'] = (f'Following cardiac arrest in {spec["location_label"]}, circulation has returned. '
        'Obtain the arrest timeline, suspected cause, interventions, baseline function and caregiver history; these are not inferred from the ECG.')
    case['patient']['presentation'] = (f'{p["age_months"]}-month-old, {p["weight_kg"]} kg fictional patient after return of circulation. '
        'Pulse present; responsiveness reduced. Initial team: ' + ', '.join(spec['discipline_labels']))
    case['narration_intro'] = case['patient']['presentation']
    actions = ['Confirm circulation and reassess airway, breathing, perfusion and neurological status',
        'Assess oxygenation and ventilation separately; verify monitoring and obtain appropriate blood gas assessment',
        'Assess blood pressure and perfusion using age-appropriate goals, not adult thresholds',
        'Monitor core temperature, avoid fever and request glucose and relevant investigations',
        'Assess for seizures and request specialist neurological monitoring when indicated',
        'Review reversible causes, arrest history, sedation and other confounders; avoid premature neurological prognosis',
        'Reassess after each intervention and arrange paediatric critical-care handover and caregiver communication']
    case['checklist'] = [dict(action=a, critical=i in (0,1,2), window_sec=0) for i,a in enumerate(actions)]
    case['hints'] = actions[:3] if spec['level']=='beginner' else []
    case['teaching_notes']['limitations'] = ('Manual teaching presets, not an automatic treatment-response model or validated paediatric score. '
        'All stages have circulation. Findings and investigation results require instructor assessment; neurological recovery cannot be inferred from monitor values. '
        'Faculty must confirm ward-specific equipment and staffing. Generic ECG; invasive channels not configured.')
    case['teaching_notes']['reference'] = 'https://publications.aap.org/pediatrics/article/doi/10.1542/peds.2025-074351/205236'
    return case
