"""Original composite teaching case; transitions require instructor judgement."""
from copy import deepcopy
from debriefing.scenarios.paediatric_respiratory import configure_respiratory_case, monitor_profile
from debriefing.scenarios.paediatric_shock import configure_shock_case
from debriefing.scenarios.paediatric_bradycardia import configure_paediatric_bradycardia
from debriefing.scenarios.paediatric_tachyarrhythmia import configure_paediatric_tachyarrhythmia
from debriefing.scenarios.paediatric_arrest import configure_paediatric_arrest
from debriefing.scenarios.paediatric_post_resuscitation import configure_post_resuscitation

TOPIC = 'Paediatric megacode — configurable combined case'
STAGES = ('respiratory_distress','respiratory_failure','shock_compensated','shock_hypotensive',
          'sinus_tachy','svt','vt_pulse','brady_compromise','brady_persistent',
          'arrest_pea','arrest_asystole','arrest_vf','arrest_pvt','rosc',
          'post_oxygenation','post_ventilation','post_perfusion','stabilisation')
DEFAULT_SEQUENCE = ['respiratory_distress','sinus_tachy','shock_compensated','respiratory_failure',
                    'shock_hypotensive','brady_compromise','brady_persistent','arrest_pea','rosc',
                    'post_oxygenation','post_ventilation','post_perfusion','stabilisation']

def validate_sequence(sequence):
    if not isinstance(sequence,list) or not 2 <= len(sequence) <= 16:
        raise ValueError('Choose 2–16 paediatric megacode stages')
    arrested = False
    had_rosc = False
    for key in sequence:
        if not isinstance(key,str) or key not in STAGES:
            raise ValueError('Unknown paediatric megacode stage')
        if key.startswith('arrest_'):
            arrested = True
        elif key == 'rosc':
            if not arrested:
                raise ValueError('Confirmed ROSC must follow cardiac arrest')
            arrested = False
            had_rosc = True
        elif arrested:
            raise ValueError('Add explicit ROSC before a pulse-present stage after arrest')
        if key.startswith('post_') and not had_rosc:
            raise ValueError('Post-resuscitation problems require an earlier ROSC stage')
    return sequence

def configure_paediatric_megacode(spec, profile='child', sequence=None, shock_cause='septic'):
    sequence = validate_sequence(DEFAULT_SEQUENCE.copy() if sequence is None else sequence)
    respiratory = configure_respiratory_case(spec,profile)
    shock = configure_shock_case(spec,profile,cause=shock_cause)
    brady = configure_paediatric_bradycardia(spec,profile)
    post = configure_post_resuscitation(spec,profile)
    modules = [respiratory,shock,brady,post]
    presets = dict(zip(('respiratory_distress','respiratory_failure'),respiratory['conditions'][:2]))
    presets.update(shock_compensated=shock['conditions'][0],shock_hypotensive=shock['conditions'][1],
                   brady_compromise=brady['conditions'][0],brady_persistent=brady['conditions'][2],
                   post_oxygenation=post['conditions'][1],post_ventilation=post['conditions'][2],
                   post_perfusion=post['conditions'][3],stabilisation=post['conditions'][4])
    for key,pattern in (('sinus_tachy','sinus'),('svt','narrow'),('vt_pulse','wide')):
        module = configure_paediatric_tachyarrhythmia(spec,profile,pattern=pattern)
        presets[key] = deepcopy(module['conditions'][0])
        presets[key]['name'] = {'sinus_tachy':'Sinus tachycardia','svt':'SVT teaching variant','vt_pulse':'VT with a pulse'}[key]
        if key in sequence: modules.append(module)
    for rhythm in ('PEA','ASYSTOLE','VF','PVT'):
        module = configure_paediatric_arrest(spec,profile,initial_rhythm=rhythm)
        presets['arrest_'+rhythm.lower()] = deepcopy(module['conditions'][0])
        presets['arrest_'+rhythm.lower()]['name'] = 'Cardiac arrest — '+rhythm
        presets['rosc'] = module['conditions'][2]
        if 'arrest_'+rhythm.lower() in sequence: modules.append(module)
    case = deepcopy(respiratory)
    case.update(title=f'Paediatric combined megacode — {spec["location_label"]}',
                monitor_schema='paediatric-megacode-1',megacode_sequence=list(sequence),
                clinical_severity=sequence[0],shock_cause=shock_cause)
    case['conditions'] = []
    for index,key in enumerate(sequence):
        stage = deepcopy(presets[key])
        stage.update(id=f'paediatric_megacode_{index}_{key}',name=f'{index+1}. {stage["name"]}')
        stage['description'] += ' Faculty-selected transition: explain the clinical change before applying; this does not prove learner treatment or an automatic physiological response.'
        case['conditions'].append(stage)
    case['initial_state'] = {**deepcopy(case['conditions'][0]['state']),**monitor_profile(profile)}
    case['rhythm_type'] = case['initial_state']['rhythm']
    case['patient']['history'] = (shock['patient']['history'] + ' This single-patient composite includes faculty-selected respiratory and circulatory changes. '
        'Confirm the mechanism linking stages and supply consistent caregiver history and examination findings; optional arrhythmias are not an inevitable illness progression.')
    case['patient']['presentation'] = (f'{case["patient"]["age_months"]}-month-old, {case["patient"]["weight_kg"]} kg patient in {spec["location_label"]}. '
        'Initial responding team: '+', '.join(spec['discipline_labels'])+'. '+presets[sequence[0]]['description'])
    case['narration_intro'] = case['patient']['presentation']
    selected_modules = []
    if any(k.startswith('respiratory_') for k in sequence): selected_modules.append(respiratory)
    if any(k.startswith('shock_') for k in sequence): selected_modules.append(shock)
    if any(k.startswith('brady_') for k in sequence): selected_modules.append(brady)
    if any(k.startswith('post_') or k in ('rosc','stabilisation') for k in sequence): selected_modules.append(post)
    selected_modules.extend(modules[4:])
    seen = set()
    case['checklist'] = []
    for module in selected_modules:
        for item in module['checklist']:
            if item['action'] not in seen:
                seen.add(item['action'])
                case['checklist'].append(deepcopy(item))
    case['hints'] = [i['action'] for i in case['checklist'][:3]] if spec['level']=='beginner' else []
    case['teaching_notes']['limitations'] = ('Composite faculty-review pilot, not a validated physiological trajectory or score. '
        'No automatic drug, shock, ventilation or CPR effects. Explicit pulse confirmation is required for ROSC. '
        'Generic ECG morphology; age-appropriate equipment and ward staffing need faculty confirmation.')
    case['teaching_notes']['reference'] = post['teaching_notes']['reference']
    return case
