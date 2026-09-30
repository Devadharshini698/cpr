import pytest
from debriefing.scenarios.paediatric_respiratory import configure_respiratory_case, WARD_HISTORY, PROFILES
from curriculum import validate_selection

@pytest.mark.parametrize('ward',WARD_HISTORY)
@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('severity',['distress','failure'])
def test_cases(ward,profile,severity):
    spec={'patient':{'age':60,'weight_kg':80},'location':ward,'location_label':ward,'level':'beginner','discipline_labels':['Nurse']}
    case=configure_respiratory_case(spec,profile,severity)
    assert case['patient']['age_months']==PROFILES[profile]['age_months']
    assert case['patient']['weight_kg']==PROFILES[profile]['weight_kg']
    assert all(case['initial_state'][k]==v for k,v in case['conditions'][0]['state'].items())
    assert case['release_status']=='teaching_pilot_faculty_review'
    assert spec['patient']['age']==60
    assert all(c['state']['pulse_rate']>0 for c in case['conditions'])

def test_generation_only():
    validate_selection('PALS','Respiratory distress/failure',allow_case_draft=True)
    validate_selection('PALS','Respiratory distress/failure')
    with pytest.raises(ValueError): configure_respiratory_case({},'newborn','distress')
