import pytest
from debriefing.scenarios.generator import ScenarioGenerator
from debriefing.scenarios.rhythm_selection import LABELS

@pytest.mark.parametrize('rhythm', list(LABELS))
@pytest.mark.parametrize('level',['beginner','intermediate','advanced'])
def test_selected_rhythm_is_consistent(rhythm,level):
    generator=ScenarioGenerator()
    spec=generator.generate(level,'Ward_Medical',['nurse','doctor'],'Medicine',monitor_rhythm=rhythm)
    assert spec['requested_rhythm']==spec['rhythm_type']==rhythm
    assert spec['title']==LABELS[rhythm]
    assert spec['initial_state']==spec['conditions'][0]['state']
    assert spec['initial_state']['rhythm']==('VT' if rhythm=='PVT' else rhythm)
    assert spec['location']=='Ward_Medical' and spec['discipline']==['nurse','doctor']
    assert bool(spec['hints'])==(level=='beginner')
    assert spec['clinical_review_required']
    if rhythm in ('VF','PVT','TORSADES','ASYSTOLE','PEA'):
        assert spec['initial_state']['pulse_rate']==spec['initial_state']['ABP_sys']==0
    else:
        assert spec['initial_state']['pulse_rate']>0

def test_unknown_selection_rejected():
    with pytest.raises(ValueError):
        ScenarioGenerator().generate('beginner','ER',['doctor'],'ER',monitor_rhythm='unknown')
