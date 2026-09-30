import pytest
from debriefing.scenarios.adult_arrest import CONTEXTS, configure_arrest_case
from physiology import apply_perfusion_intent

@pytest.mark.parametrize('ward', CONTEXTS)
@pytest.mark.parametrize('level', ['beginner', 'intermediate', 'advanced'])
@pytest.mark.parametrize('severity', ['arrest','arrest_with_post_rosc_instability'])
def test_ward_cases(ward, level, severity):
    case = configure_arrest_case({'level':level,'patient':{},'location':ward,'location_label':ward,'discipline_labels':['Nurse'],'resources':{}},severity)
    assert 'Nurse' in case['patient']['presentation']
    assert case['patient']['history'] == CONTEXTS[ward][1]
    assert case['initial_state']['pulse_rate'] == 0
    assert 'VF' not in case['title']
    assert case['conditions'][2]['state']['pulse_rate'] > 0
    # Organised rhythm may still be pulseless: no implicit ROSC.
    state = dict(case['initial_state'], rhythm='NSR', HR=80)
    assert apply_perfusion_intent(state, {'rhythm':'NSR'})['pulse_rate'] == 0

def test_bad_course_rejected():
    with pytest.raises(ValueError): configure_arrest_case({}, 'mild arrest')
