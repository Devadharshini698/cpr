"""Compose reviewed teaching presets without implying automatic clinical transitions."""
from copy import deepcopy
from debriefing.scenarios.adult_tachycardia import configure_tachycardia_case
from debriefing.scenarios.adult_bradycardia import configure_bradycardia_case
from debriefing.scenarios.adult_arrest import configure_arrest_case

TOPIC = 'Adult megacode — configurable ward-based case'
STAGES = ('tachy_stable','tachy_unstable','brady_stable','brady_unstable','arrest','rosc','post_arrest')
DEFAULT_SEQUENCE = ['tachy_stable','tachy_unstable','brady_unstable','arrest','rosc','post_arrest']

def validate_sequence(sequence):
    if not isinstance(sequence,list) or not 2 <= len(sequence) <= 10:
        raise ValueError('Choose 2–10 megacode stages')
    arrested = False
    for index,key in enumerate(sequence):
        if not isinstance(key,str) or key not in STAGES:
            raise ValueError('Unknown megacode stage')
        if key == 'arrest':
            arrested = True
        elif key == 'rosc':
            if not arrested:
                raise ValueError('ROSC must follow an arrest stage')
            arrested = False
        elif arrested:
            raise ValueError('Add explicit ROSC before returning from arrest to a pulse-present stage')
        if key == 'post_arrest' and 'rosc' not in sequence[:index]:
            raise ValueError('Post-arrest care requires an earlier ROSC stage')
    return sequence

def configure_megacode(spec, sequence=None):
    sequence = validate_sequence(DEFAULT_SEQUENCE.copy() if sequence is None else sequence)
    tachy = configure_tachycardia_case(spec)
    brady = configure_bradycardia_case(spec)
    arrest = configure_arrest_case(spec)
    presets = {'tachy_stable':tachy['conditions'][0], 'tachy_unstable':tachy['conditions'][1],
               'brady_stable':brady['conditions'][0], 'brady_unstable':brady['conditions'][1],
               'arrest':arrest['conditions'][0], 'rosc':arrest['conditions'][2], 'post_arrest':arrest['conditions'][3]}
    first = tachy if sequence[0].startswith('tachy') else brady if sequence[0].startswith('brady') else arrest
    case = deepcopy(first)
    case['title'] = f"Adult megacode — {spec['location_label']}"
    case['conditions'] = []
    for index,key in enumerate(sequence):
        stage = deepcopy(presets[key])
        stage['id'] = f'megacode_{index}_{key}'
        stage['name'] = f'{index+1}. {stage["name"]}'
        stage['description'] += ' Faculty-selected teaching transition: establish the clinical explanation before applying; no treatment effect is inferred.'
        case['conditions'].append(stage)
    case['initial_state'] = deepcopy(case['conditions'][0]['state'])
    case['rhythm_type'] = case['initial_state']['rhythm']
    case['clinical_severity'] = sequence[0]
    # One patient's history persists; do not concatenate unrelated ward case histories.
    roles = ', '.join(spec['discipline_labels'])
    case['patient']['presentation'] = f'Adult patient in {spec["location_label"]}. Initial responding personnel: {roles}. ' + presets[sequence[0]]['description'].split(' Instructor')[0].split(' Faculty')[0]
    case['narration_intro'] = case['patient']['presentation']
    case['megacode_sequence'] = list(sequence)
    chosen = []
    if any(k.startswith('tachy') for k in sequence): chosen.append(tachy)
    if any(k.startswith('brady') for k in sequence): chosen.append(brady)
    if any(k in ('arrest','rosc','post_arrest') for k in sequence): chosen.append(arrest)
    seen = set()
    case['checklist'] = []
    for module in chosen:
        for item in module['checklist']:
            if item['action'] not in seen:
                seen.add(item['action']); case['checklist'].append(deepcopy(item))
    case['teaching_notes']['progression'] = 'Ordered instructor presets, not an automatic physiological model. Confirm the clinical explanation for transitions; rhythm and pulse remain manually adjustable. Repeated stages are permitted.'
    case['teaching_notes']['limitations'] = 'Faculty-review composite pilot; no validated megacode score, automatic drug responses or pacing/CPR-generated circulation model.'
    case['complications'] = []
    return case
