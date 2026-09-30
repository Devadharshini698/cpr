import asyncio
from unittest.mock import AsyncMock, MagicMock
import json
import pytest
import socket_manager as sm
from debriefing.scenarios.obstetric_hypertension import configure_obstetric_hypertension
from monitor_channels import initialise_channels, configure_channel

@pytest.mark.parametrize('role',['student',None])
def test_instructor_only(monkeypatch,role):
    monkeypatch.setattr(sm.sio,'get_session',AsyncMock(return_value={'role':role}))
    assert asyncio.run(sm.set_waveform_channels('sid',{}))['status']=='error'
    assert asyncio.run(sm.configure_waveform_channel('sid',{}))['status']=='error'

@pytest.mark.parametrize('data',[None,{}, {'ecg':True},dict.fromkeys(['ecg','pleth','abp','pap','co2'],1)])
def test_invalid_payload(monkeypatch,data):
    monkeypatch.setattr(sm.sio,'get_session',AsyncMock(return_value={'role':'instructor'}))
    assert asyncio.run(sm.set_waveform_channels('sid',data))['status']=='error'

def test_hypertension_availability_is_independent_of_pressure():
    case=configure_obstetric_hypertension({'level':'beginner','discipline_labels':['Doctor']})
    state=case['initial_state']
    assert state['ABP_sys']>160 and state['NBP_sys'] is None
    assert state['configured_channels']==dict(ecg=True,pleth=True,abp=False,pap=False,co2=False)
    for condition in case['conditions']:
        assert 'waveform_channels' not in condition['state']
        assert 'student_display' not in condition['state']

def patient():
    return dict(HR=90,pulse_rate=90,rhythm='NSR',SpO2=98,ABP_sys=170,ABP_dia=110,
                avRR=20,etCO2=0,show_ibp=False,show_resp=False,student_display={'abp_wave':False},NBP_sys=None)

def test_all_legacy_channel_flags_migrate_without_inventing_values():
    source=patient(); result=initialise_channels(source)
    assert result['configured_channels']==dict(ecg=True,pleth=True,abp=False,pap=False,co2=False)
    assert 'configured_channels' not in source and 'PAP_sys' not in result

@pytest.mark.parametrize('channel,values',[('ecg',{}),('pleth',{}),('abp',{}),('pap',{'PAP_sys':25,'PAP_dia':10}),('co2',{'etCO2':35,'avRR':20})])
def test_connect_disconnect_does_not_reveal_or_change_cuff(channel,values):
    source=patient()
    result=configure_channel(source,dict(channel=channel,configured=True,values=values))
    assert result['configured_channels'][channel] and result['waveform_channels'][channel]
    assert result['student_display']==source['student_display'] and result['NBP_sys'] is None
    assert result['ABP_sys']==170 and result['pulse_rate']==90
    disconnected=configure_channel(result,dict(channel=channel,configured=False,values={}))
    assert disconnected['configured_channels'][channel] is False
    for key,value in values.items(): assert disconnected[key]==value

@pytest.mark.parametrize('values',[{}, {'PAP_sys':5,'PAP_dia':10}, {'PAP_sys':float('nan'),'PAP_dia':10}, {'PAP_sys':True,'PAP_dia':10}, {'PAP_sys':121,'PAP_dia':10}])
def test_invalid_pap_values(values):
    with pytest.raises(ValueError): configure_channel(patient(),dict(channel='pap',configured=True,values=values))

def test_configuration_does_not_establish_rosc():
    source={**patient(),'rhythm':'VF','HR':0,'pulse_rate':0,'ABP_sys':0,'ABP_dia':0,'SpO2':0}
    result=configure_channel(source,dict(channel='abp',configured=True,values={}))
    assert result['pulse_rate']==0 and result['ABP_sys']==0
    with pytest.raises(ValueError,match='pulseless'):
        configure_channel(source,dict(channel='pap',configured=True,values={'PAP_sys':25,'PAP_dia':10}))

def test_existing_metadata_preserved():
    state={**patient(),'configured_channels':{'abp':True},'waveform_channels':{'pap':True}}
    assert initialise_channels(state)['configured_channels']['abp'] is True
    assert initialise_channels(state)['waveform_channels']['pap'] is True

@pytest.mark.parametrize('valid',[True,False])
def test_configuration_transaction_and_broadcast(monkeypatch,valid):
    monkeypatch.setattr(sm.sio,'get_session',AsyncMock(return_value={'role':'instructor','session_code':'QA'}))
    emit=AsyncMock(); sync=AsyncMock()
    monkeypatch.setattr(sm.sio,'emit',emit)
    monkeypatch.setattr(sm,'_sync_waveform_engine',sync)
    cursor=AsyncMock()
    cursor.fetchone.side_effect=[{'id':1,'event_log':'[]'},{'state_data':json.dumps(patient())}]
    conn=MagicMock();conn.begin=AsyncMock();conn.commit=AsyncMock();conn.rollback=AsyncMock()
    conn.cursor.return_value.__aenter__.return_value=cursor
    pool=MagicMock();pool.acquire.return_value.__aenter__.return_value=conn
    monkeypatch.setattr(sm,'get_db_pool',AsyncMock(return_value=pool))
    values={'PAP_sys':25,'PAP_dia':10} if valid else {'PAP_sys':5,'PAP_dia':10}
    result=asyncio.run(sm.configure_waveform_channel('sid',dict(channel='pap',configured=True,values=values)))
    if valid:
        assert result['status']=='success'
        conn.commit.assert_awaited_once(); conn.rollback.assert_not_awaited()
        saved=json.loads(cursor.execute.call_args_list[2].args[1][0])
        assert saved['configured_channels']['pap'] is True
        assert saved['student_display']==patient()['student_display']
        sync.assert_awaited_once()
        assert emit.call_args_list[0].args[0]=='state_update'
    else:
        assert result['status']=='error'
        conn.rollback.assert_awaited_once(); conn.commit.assert_not_awaited()
        emit.assert_not_awaited(); sync.assert_not_awaited()
