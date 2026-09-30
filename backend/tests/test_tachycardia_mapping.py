import pytest
from main import map_rhythm_type_to_vitals
from debriefing.scenarios.generator import ScenarioGenerator
from simman_engine.rhythm_intelligence import get_wave_visibility
from ecg_state import RhythmType

@pytest.mark.parametrize('label',['Tachycardia','Sinus Tachycardia','SINUS_TACHY','TACHY','TACHYARRHYTHMIA_WITH_PULSE'])
def test_generic_tachy_is_sinus(label):
    assert map_rhythm_type_to_vitals(label)['rhythm']=='SINUS_TACHY'
    stages=ScenarioGenerator()._derive_conditions(label)
    assert stages[0]['state']['rhythm']=='SINUS_TACHY'
    assert all(stage['state']['rhythm']!='SVT' for stage in stages)

@pytest.mark.parametrize('label',['SVT','Supraventricular tachycardia'])
def test_explicit_svt_preserved(label):
    assert map_rhythm_type_to_vitals(label)['rhythm']=='SVT'
    assert any(s['state']['rhythm']=='SVT' for s in ScenarioGenerator()._derive_conditions(label))

def test_sinus_has_atrial_activity_at_high_rate():
    assert get_wave_visibility(RhythmType.SINUS_TACHY,180)[0]>0
    assert get_wave_visibility(RhythmType.SVT,180)[0]==0

@pytest.mark.parametrize('label',['VT','Ventricular tachycardia'])
def test_explicit_vt_preserved(label):
    assert map_rhythm_type_to_vitals(label)['rhythm']=='VT'
