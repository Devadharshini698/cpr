import pytest
from debriefing.scenarios.adult_vf import configure_vf_pilot, TOPIC
from curriculum import validate_selection
from physiology import normalize_monitor_state

@pytest.mark.parametrize('level', ['beginner', 'intermediate', 'advanced'])
def test_vf_pilot_states_and_isolation(level):
    original = {'level': level, 'patient': {}, 'resources': {'defibrillator': True}}
    spec = configure_vf_pilot(original)
    assert 'conditions' not in original
    assert validate_selection('ACLS', TOPIC)
    assert spec['initial_state']['pulse_rate'] == 0
    assert spec['resources'] == original['resources']
    assert bool(spec['hints']) == (level == 'beginner')
    assert len(spec['conditions']) == (5 if level == 'advanced' else 4)
    for stage in spec['conditions']:
        state = stage['state']
        assert normalize_monitor_state(state) == state
        assert 'student_display' not in state
        if stage['id'] in ('vf_rosc', 'vf_stabilised'):
            assert state['pulse_rate'] > 0 and state['SpO2'] > 0 and state['CO'] > 0
            assert state['ABP_sys'] > state['ABP_dia'] > 0
        else:
            assert state['pulse_rate'] == state['SpO2'] == state['ABP_sys'] == 0
