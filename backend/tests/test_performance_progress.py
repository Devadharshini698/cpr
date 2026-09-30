import asyncio
import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import performance_progress as p
from auth import get_current_user

def spec():
    return dict(curriculum={'programme':'PALS','subtopic':'Shock'},level='beginner',monitor_schema='pals-shock-1',
                discipline=['doctor','nurse'],clinical_severity='compensated',initial_state={'HR':130},conditions=[])

def body():
    return dict(subject_id='subject',session_code='CASE01',role_label='Nurse',evidence='Observed assessment at 00:30',
                next_steps='Practise closed-loop communication',confirmed_attribution=True,ratings={key:2 for key in p.DOMAINS})

def row(identifier=1,session=1,subject='s',cohort='a',rating=2,date='2026-09-01'):
    return dict(id=identifier,session_id=session,subject_id=subject,session_code=str(session),ended_at=date,
                created_at=date,role_label='Nurse',cohort=cohort,evidence='Observed',next_steps='Practise',
                ratings_json=json.dumps({key:rating for key in p.DOMAINS}),context_json='{}')

@pytest.mark.parametrize('value',[True,-1,4,1.5,'3',float('nan')])
def test_bad_ratings(value):
    data=body();data['ratings']['assessment']=value
    with pytest.raises(ValueError):p.validate_observation(data)

def test_missing_evidence_and_attribution():
    for key in ('evidence','next_steps','role_label'):
        data=body();data[key]=' '
        with pytest.raises(ValueError):p.validate_observation(data)
    data=body();data['confirmed_attribution']=False
    with pytest.raises(ValueError):p.validate_observation(data)
    data=body();data['ratings']=dict.fromkeys(p.DOMAINS)
    with pytest.raises(ValueError):p.validate_observation(data)

def test_missing_is_not_zero_and_zero_is_observation():
    attempt=row();attempt['ratings_json']=json.dumps({**dict.fromkeys(p.DOMAINS),'assessment':0})
    result=p.summarise([attempt])[0]
    assert result['coverage']==1 and result['mean']==0 and result['change'] is None

def test_revision_counts_once_and_chronology_is_session_not_entry_date():
    rows=[row(1,1,rating=1),row(2,2,rating=3,date='2026-09-02'),row(3,1,rating=2)]
    result=p.summarise(rows)
    assert len(result)==2 and result[0]['id']==3 and result[1]['change']==1

def test_no_cross_subject_or_cross_cohort_delta():
    result=p.summarise([row(1),row(2,2,cohort='b'),row(3,3,subject='other')])
    assert all(attempt['change'] is None for attempt in result)

def test_context_splits_difficulty_role_kind_domain_and_patient():
    ratings=body()['ratings'];base=p.comparison_context(spec(),'student','Nurse',ratings)[0]
    assert p.comparison_context(spec(),'student','nurse',ratings)[0]==base
    variants=[({**spec(),'level':'advanced'},'student','Nurse',ratings),
              (spec(),'team','Nurse',ratings),(spec(),'student','Leader',ratings),
              (spec(),'student','Nurse',{**ratings,'assessment':None}),
              ({**spec(),'initial_state':{'HR':170}},'student','Nurse',ratings)]
    for args in variants:assert p.comparison_context(*args)[0]!=base
    with pytest.raises(ValueError):p.comparison_context({},'student','Nurse',ratings)

def pool_with(monkeypatch,results):
    cursor=AsyncMock();cursor.fetchone.side_effect=results
    conn=MagicMock();conn.commit=AsyncMock();conn.cursor.return_value.__aenter__.return_value=cursor
    pool=MagicMock();pool.acquire.return_value.__aenter__.return_value=conn
    monkeypatch.setattr(p,'get_db_pool',AsyncMock(return_value=pool))
    return cursor,conn

@pytest.mark.parametrize('results',[[None,None],[{'id':'subject','kind':'student'},None]])
def test_inaccessible_subject_or_session_cannot_be_written(monkeypatch,results):
    cursor,conn=pool_with(monkeypatch,results)
    with pytest.raises(HTTPException) as error:asyncio.run(p.save_observation(body(),{'id':7}))
    assert error.value.status_code==404
    assert all(7 in call.args[1] for call in cursor.execute.call_args_list)
    conn.commit.assert_not_awaited()

def test_active_session_rejected(monkeypatch):
    pool_with(monkeypatch,[{'id':'subject','kind':'student'},{'id':1,'is_active':1,'ended_at':None}])
    with pytest.raises(HTTPException) as error:asyncio.run(p.save_observation(body(),{'id':7}))
    assert error.value.status_code==409

def test_append_owned_observation(monkeypatch):
    cursor,conn=pool_with(monkeypatch,[{'id':'subject','kind':'student'},dict(id=1,is_active=0,ended_at='2026-09-01',current_scenario_json=json.dumps(spec()))])
    assert asyncio.run(p.save_observation(body(),{'id':7}))['status']=='saved'
    assert cursor.execute.call_args.args[0].startswith('INSERT INTO progress_observations')
    conn.commit.assert_awaited_once()

@pytest.mark.parametrize('method,path',[('get','/api/progress'),('post','/api/progress/subjects'),('post','/api/progress/observations')])
def test_student_cannot_access_progress(method,path):
    app=FastAPI();app.include_router(p.router)
    app.dependency_overrides[get_current_user]=lambda:{'id':9,'role':'student'}
    with TestClient(app) as client:
        response=getattr(client,method)(path,**({'json':{}} if method=='post' else {}))
        assert response.status_code==403

def test_read_scopes_every_table_to_owner(monkeypatch):
    cursor,_=pool_with(monkeypatch,[]);cursor.fetchall.side_effect=[[],[],[]]
    result=asyncio.run(p.progress_data({'id':7}))
    assert result['attempts']==[] and result['subjects']==[]
    assert cursor.execute.call_args_list[0].args[1]==(7,)
    assert cursor.execute.call_args_list[1].args[1]==(7,7,7)
    assert cursor.execute.call_args_list[2].args[1]==(7,)
