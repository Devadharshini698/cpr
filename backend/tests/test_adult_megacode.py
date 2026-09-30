import pytest
from debriefing.scenarios.adult_megacode import configure_megacode, validate_sequence
from debriefing.scenarios.adult_arrest import CONTEXTS

@pytest.mark.parametrize('ward',CONTEXTS)
def test_composite(ward):
    spec={'location':ward,'location_label':ward,'level':'beginner','patient':{},'discipline_labels':['Nurse'],'resources':{}}
    case=configure_megacode(spec)
    assert len(case['conditions'])==6
    assert len({s['id'] for s in case['conditions']})==6
    assert case['conditions'][3]['state']['pulse_rate']==0
    assert case['conditions'][4]['state']['pulse_rate']>0
    assert case['initial_state']==case['conditions'][0]['state']
    assert spec['patient']=={}
    assert all('student_display' not in s['state'] for s in case['conditions'])

@pytest.mark.parametrize('sequence',[[],['arrest'],['rosc','arrest'],['arrest','brady_stable'],['post_arrest','arrest'],['bad','arrest'],['arrest']*11])
def test_invalid_sequence(sequence):
    with pytest.raises(ValueError): validate_sequence(sequence)

def test_rearrest():
    assert validate_sequence(['arrest','rosc','arrest','rosc','post_arrest'])
