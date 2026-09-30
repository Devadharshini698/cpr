import asyncio
import itertools
from copy import deepcopy
from unittest.mock import AsyncMock
import pytest
import main
import socket_manager as sm
from curriculum import PROGRAMMES
from debriefing.scenarios.generator import ScenarioGenerator
from debriefing.scenarios.teaching_design import apply_teaching_design, ROLES

TOPICS=[(p,t) for p in ('ACLS','PALS','TLS','NALS','ALSO') for t in PROGRAMMES[p]['topics']]
TEAMS=[list(c) for n in range(1,5) for c in itertools.combinations(ROLES,n)]

@pytest.mark.parametrize('programme,topic',TOPICS)
@pytest.mark.parametrize('level',['beginner','intermediate','advanced'])
@pytest.mark.parametrize('roles',TEAMS)
def test_every_generated_topic_level_and_team(monkeypatch,programme,topic,level,roles):
    monkeypatch.setattr(main,'_scenario_gen',ScenarioGenerator())
    monkeypatch.setattr(main,'_outcome_pred',None)
    result=asyncio.run(main.api_scenario_generate(dict(programme=programme,subtopic=topic,level=level,
        location='ER',discipline=roles,speciality='ER'),user={'role':'instructor'}))
    case=result['spec']; plan=case['teaching_plan']
    assert plan['level']==level
    assert [t['role'] for t in plan['team_tasks']]==roles
    assert len(plan['faculty_challenges'])=={'beginner':0,'intermediate':1,'advanced':3}[level]
    assert bool(case['hints'])==(level=='beginner')
    assert case['team_size'] is None
    assert ('No physician role' in ' '.join(plan['escalation']))==('doctor' not in roles)
    assert ('No nurse role' in ' '.join(plan['escalation']))==('nurse' not in roles)
    assert len([i for i in case['checklist'] if i.get('source')=='teaching_design'])==3+len(roles)+len(plan['escalation'])
    assert apply_teaching_design(case)==case

def test_levels_roles_change_assessment_not_physiology():
    spec=dict(level='beginner',discipline=['nurse'],curriculum=dict(programme='TLS',subtopic='Head injury'),
        initial_state={'HR':95,'SpO2':97},conditions=[{'id':'baseline','state':{'HR':95}}],
        checklist=[dict(action='Assess airway',critical=True,window_sec=0)])
    original=deepcopy(spec)
    beginner=apply_teaching_design(spec)
    intermediate=apply_teaching_design({**spec,'level':'intermediate'})
    advanced=apply_teaching_design({**spec,'level':'advanced'})
    mixed=apply_teaching_design({**spec,'discipline':['doctor','nurse']})
    assert spec==original
    assert beginner['checklist']!=intermediate['checklist']!=advanced['checklist']
    assert mixed['checklist']!=beginner['checklist']
    for case in (beginner,intermediate,advanced,mixed):
        assert case['initial_state']==spec['initial_state']
        assert case['conditions']==spec['conditions']
        assert case['checklist'][0]==spec['checklist'][0]

@pytest.mark.parametrize('level,roles',[('bad',['doctor']),('beginner',[]),('beginner',['bad']),('beginner','nurse'),('beginner',[{}])])
def test_invalid(level,roles):
    with pytest.raises(ValueError): apply_teaching_design(dict(level=level,discipline=roles))

def test_faculty_plan_not_in_student_socket_event(monkeypatch):
    monkeypatch.setattr(sm.sio,'emit',AsyncMock())
    monkeypatch.setattr(sm.sio,'get_session',AsyncMock(side_effect=[{'role':'instructor'},{'role':'student'}]))
    monkeypatch.setattr(sm.sio.manager,'rooms',{'/':{'TEACH':{'teacher':None,'student':None}}})
    spec=apply_teaching_design(dict(level='advanced',discipline=['nurse']))
    asyncio.run(sm.emit_scenario_selected('TEACH',spec))
    calls=sm.sio.emit.call_args_list
    assert 'teaching_plan' in calls[0].args[1]
    assert 'teaching_plan' not in calls[1].args[1]
