"""Independent ward-based arrest cases; illustrative physiology, faculty review required."""
from debriefing.scenarios.adult_vf import configure_vf_pilot
from debriefing.scenarios.rhythm_selection import rhythm_state
from physiology import normalize_monitor_state

TOPIC = 'Adult cardiac arrest — ward-based case'
SEVERITIES = ('arrest', 'arrest_with_post_rosc_instability')
# Original fictional histories, not diagnostic conclusions or treatment algorithms.
CONTEXTS = {
    'ER': ('Chest discomfort followed by collapse in the emergency department.', 'Chest discomfort and diaphoresis before collapse; medical history initially incomplete.', 'VF'),
    'ICU': ('A critically ill adult deteriorates during treatment for severe infection.', 'Pneumonia with circulatory instability; review ventilation, access and recent trends.', 'PEA'),
    'Theatre': ('An adult undergoing abdominal surgery develops circulatory collapse.', 'Under anaesthesia; review blood loss, ventilation, recent medications and the surgical field.', 'PEA'),
    'Ward_Medical': ('An adult admitted with pneumonia is found unresponsive during a ward review.', 'Increasing breathlessness and reduced oral intake overnight.', 'PEA'),
    'Ward_Surgical': ('A patient recovering from abdominal surgery collapses on the ward.', 'Recent operation with increasing weakness; assess wound, drains and fluid balance.', 'PEA'),
    'Ward_Ortho': ('An adult recovering from hip surgery collapses during mobilisation.', 'Recent surgery and limited mobility; preceding breathlessness requires assessment.', 'PEA'),
    'Ward_Neuro': ('An adult admitted after a stroke becomes unresponsive with abnormal breathing.', 'Swallowing difficulty and a recent change in respiratory status.', 'PEA'),
    'Ward_Cardio': ('An adult admitted with chest pain collapses in the cardiology ward.', 'Known coronary disease; new chest discomfort before collapse.', 'VF'),
}

def configure_arrest_case(spec, severity='arrest'):
    if severity not in SEVERITIES:
        raise ValueError('Select a supported clinical course')
    case = configure_vf_pilot(spec)
    presentation, history, rhythm = CONTEXTS[spec['location']]
    case['title'] = f"Adult cardiac arrest — {spec['location_label']}"
    case['patient'].update(history=history, presentation=presentation + ' The patient is unresponsive, has no normal breathing and no palpable pulse.')
    case['narration_intro'] = case['patient']['presentation']
    case['rhythm_type'] = rhythm
    case['clinical_severity'] = severity
    case['initial_state'] = rhythm_state(rhythm)
    for stage, identifier, name in zip(case['conditions'][:2], ('arrest_initial', 'arrest_persistent'), ('Cardiac arrest', 'Ongoing resuscitation')):
        stage.update(id=identifier, name=name, state=rhythm_state(rhythm), description='Pulseless cardiac arrest. Use ECG controls to select any evolving rhythm. Record observed actions separately; this preset does not prove CPR or shock delivery. Compression-generated waveforms are not modelled.')
    case['conditions'][2]['id'] = 'arrest_rosc'
    if severity == 'arrest_with_post_rosc_instability':
        case['conditions'][2]['state'].update(ABP_sys=80, ABP_dia=45, SpO2=90, CO=2.5)
        case['conditions'][2]['state'] = normalize_monitor_state(case['conditions'][2]['state'])
        case['conditions'][2]['description'] += ' Persistent circulatory and oxygenation instability requires reassessment and escalation.'
    if len(case['conditions']) > 4:
        case['conditions'][4].update(id='arrest_recurrence', name='Optional recurrent cardiac arrest', state=rhythm_state(rhythm))
    case['checklist'][3]['action'] = 'Assess rhythm and distinguish shockable from non-shockable arrest; defibrillate only when indicated'
    roles = ', '.join(spec['discipline_labels'])
    case['patient']['presentation'] += f' Initial responding personnel: {roles}. Allocate tasks within competence and call for additional help.'
    case['narration_intro'] = case['patient']['presentation']
    case['teaching_notes']['team'] = f'Available initial disciplines: {roles}. Do not assume an absent discipline is present or that professional title alone establishes procedural competence.'
    case['teaching_notes']['resources'] = 'Resource availability and response times are simulation assumptions, not facts about the institution. Instructor must confirm them.'
    case['teaching_notes']['severity'] = 'All cardiac arrest is critical; clinical course is separate from teaching difficulty.'
    return case
