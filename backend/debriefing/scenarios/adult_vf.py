"""Original faculty-controlled teaching pilot, not a certified course algorithm."""
from copy import deepcopy
from debriefing.scenarios.rhythm_selection import rhythm_state
from physiology import normalize_monitor_state

TOPIC = 'VF arrest to ROSC and post-arrest care'

def configure_vf_pilot(spec):
    spec = deepcopy(spec)
    level = spec['level']
    def condition(identifier, name, description, rhythm, **updates):
        state = rhythm_state(rhythm)
        state.update(updates)
        return {'id': identifier, 'name': name, 'description': description,
                'state': normalize_monitor_state(state)}
    spec['title'] = 'Adult VF arrest to post-arrest care — faculty-review pilot'
    spec['patient']['presentation'] = 'An adult suddenly becomes unresponsive and is not breathing normally. Assess the patient and request the equipment and findings you need.'
    spec['narration_intro'] = spec['patient']['presentation']
    spec['conditions'] = [
        condition('vf_initial', 'VF arrest', 'No palpable pulse or normal breathing. Instructor reveals monitoring only when requested.', 'VF'),
        condition('vf_persistent', 'Persistent VF / resuscitation', 'Patient remains pulseless. Record observed CPR, rhythm checks and defibrillation separately. Compression-generated waveforms are not modelled by this preset.', 'VF'),
        condition('vf_rosc', 'ROSC — reassess perfusion', 'Instructor confirms a palpable pulse. Reassess airway, breathing, circulation and neurological state; these are example patient readings, not treatment targets.', 'NSR', HR=100, pulse_rate=100, ABP_sys=90, ABP_dia=55, SpO2=94, avRR=12, etCO2=38, CO=3.5),
        condition('vf_stabilised', 'Post-arrest stabilisation', 'Example response after faculty-confirmed care. Reassess, investigate the cause and arrange ongoing care and structured handover. Do not infer neurological recovery from normal monitor values.', 'NSR', HR=88, pulse_rate=88, ABP_sys=110, ABP_dia=70, SpO2=96, avRR=14, etCO2=36, CO=5),
    ]
    if level == 'advanced':
        spec['conditions'].append(condition('vf_recurrence', 'Optional recurrent VF', 'Optional faculty-triggered deterioration: reassess the patient and resume the appropriate arrest response. This is not an automatic consequence of a missed checklist item.', 'VF'))
    spec['initial_state'] = deepcopy(spec['conditions'][0]['state'])
    actions = [
        'Assess responsiveness, breathing and pulse; recognise arrest',
        'Call for help, allocate roles and request resuscitation equipment',
        'Provide high-quality CPR and minimise interruptions',
        'Identify the shockable rhythm and deliver safe defibrillation when indicated',
        'Resume CPR and reassess according to the current local arrest protocol',
        'Assess reversible causes and appropriate airway, access and medication needs',
        'Confirm ROSC clinically and reassess airway, ventilation and perfusion',
        'Assess neurological status and investigate the arrest cause',
        'Plan ongoing post-arrest care and give a structured handover',
    ]
    spec['checklist'] = [{'action': action, 'critical': i < 5, 'window_sec': 0} for i, action in enumerate(actions)]
    spec['hints'] = actions[:3] if level == 'beginner' else []
    spec['complications'] = ['Faculty may trigger recurrent VF after ROSC'] if level == 'advanced' else []
    spec['teaching_notes'] = {
        'authorship': 'Independent original simulation; clinical faculty review required',
        'progression': 'Manual instructor selection; never automatic proof of student performance',
        'limitations': 'No compression-generated circulation model; absent SpO2 during arrest is not a measured oxygen saturation. No validated case-specific automated grade.',
        'difficulty': {'beginner': 'Focused objectives with prompts', 'intermediate': 'Independent assessment and repeated reassessment', 'advanced': 'Competing priorities, resource coordination and optional re-arrest'}[level],
        'references': ['https://pubmed.ncbi.nlm.nih.gov/41122884/', 'https://pubmed.ncbi.nlm.nih.gov/41122894/'],
    }
    return spec
