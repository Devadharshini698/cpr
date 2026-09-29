import asyncio
import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock
from curriculum import catalogue,validate_selection,validate_assessment,public_assessment
from curriculum import assessment_items,curriculum_draft
import main

def test_agreed_programmes_and_draft_launch_gates():
    packs=catalogue()
    assert set(packs)=={'ACLS','PALS','NALS','TLS','ALSO'}
    for key,p in packs.items():
        for topic in p['topics']:
            if topic in p['launchable_topics']: assert validate_selection(key,topic)['programme']==key
            else:
                with pytest.raises(ValueError,match='draft'): validate_selection(key,topic)

def test_private_feedback_never_in_student_projection():
    row={'id':1,'phase':'primary','item':'airway','created_at':'now','kind':'observation','revealed':False,'finding':'hidden','feedback':'private','status':'omitted','observer_id':1}
    assert public_assessment(row)['finding'] is None
    assert 'feedback' not in public_assessment(row) and 'status' not in public_assessment(row)
    row['revealed']=True
    assert public_assessment(row)['finding']=='hidden'
    assert 'feedback' not in public_assessment(row)

def test_invalid_assessment_rejected():
    with pytest.raises(ValueError): validate_assessment({'phase':'primary','item':'unknown'},False)
    with pytest.raises(ValueError): validate_assessment({'phase':'primary','item':'airway','status':'performed','revealed':'yes'},True)

def test_student_cannot_submit_observed_performance(monkeypatch):
    import patient_assessment
    monkeypatch.setattr(main,'_debrief_session',AsyncMock(return_value={'id':1,'is_active':True}))
    append=AsyncMock();monkeypatch.setattr(patient_assessment,'append',append)
    asyncio.run(main.record_patient_assessment('TEST01',{'phase':'primary','item':'airway','status':'performed','finding':'fake','revealed':True},{'role':'student'}))
    assert append.call_args.args[-1] is False

def test_ended_session_read_only(monkeypatch):
    monkeypatch.setattr(main,'_debrief_session',AsyncMock(return_value={'id':1,'is_active':False}))
    with pytest.raises(HTTPException) as error:
        asyncio.run(main.record_patient_assessment('TEST01',{}, {'role':'instructor'}))
    assert error.value.status_code==409

def test_independent_labels_and_specific_assessment_domains():
    assert catalogue()['ALSO']['label']=='Obstetric Emergency Simulation'
    assert 'initial_birth_assessment' in assessment_items('NALS')
    assert 'primary' not in assessment_items('NALS')
    assert next(iter(assessment_items('TLS')['primary']))=='haemorrhage'
    assert 'age_weight' in assessment_items('PALS')['secondary']
    assert 'obstetric_context' in assessment_items('ALSO')['secondary']
    for key,pack in catalogue().items():
        for topic in pack['topics']:
            draft=curriculum_draft(key,topic)
            assert draft['assessment_domains'] and draft['pending']

def test_newborn_cannot_use_adult_assessment_items():
    with pytest.raises(ValueError):
        validate_assessment({'phase':'primary','item':'airway'},False,'NALS')
    validate_assessment({'phase':'initial_birth_assessment','item':'transition'},False,'NALS')

def test_pdf_escapes_findings_and_returns_pdf():
    from assessment_report import build_assessment_pdf
    content=build_assessment_pdf('QA', [{'phase':'primary','item':'airway','created_at':'now','kind':'observation','status':'not_observed','revealed':False,'finding':'<script> & signs','feedback':'Faculty-only','observer_id':1}],assessment_items(),{},True)
    assert content.startswith(b'%PDF-')

@pytest.mark.parametrize('programme',['PALS','NALS','TLS','ALSO'])
def test_nonadult_programmes_never_receive_adult_acls_findings(tmp_path,monkeypatch,programme):
    from debriefing.engine import DebriefEngine,ACLSEngine
    def forbidden(*args,**kwargs): raise AssertionError('Adult ACLS evaluator must not run')
    monkeypatch.setattr(ACLSEngine,'evaluate',forbidden)
    result=DebriefEngine(output_dir=tmp_path,enable_narrative=False).generate({
        'session_id':'CURRICULUMQA','scenario_configuration':{'curriculum':{'programme':programme}},
        'events':[{'event_id':'vf','event_type':'rhythm_change','timestamp_ms':0,'payload':{'rhythm':'VF'}}]})
    assert result['overall_score'] is None and result['grade']=='N/A' and result['findings']==[]
