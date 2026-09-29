"""Monitor control regressions; no database or real sessions are touched."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import main
import socket_manager as sm
from ecg_state import ECGState, RhythmType
from fastapi import WebSocketDisconnect


def test_get_state_uses_session_engine(monkeypatch):
    engine = SimpleNamespace(state=ECGState(rhythm=RhythmType.VT, heart_rate=170),
                             start=AsyncMock(), add_client=lambda fn: None,
                             remove_client=lambda fn: None)
    monkeypatch.setattr(main, 'get_session_engine', lambda code: engine)
    ws = SimpleNamespace(accept=AsyncMock(), client='test', send_text=AsyncMock(),
                         send_bytes=AsyncMock(), receive_text=AsyncMock(side_effect=[
                             '{"type":"GET_STATE"}', WebSocketDisconnect()]))
    asyncio.run(main.ws_ecg(ws, 'TEST01'))
    snapshots = [json.loads(call.args[0])['payload'] for call in ws.send_text.call_args_list]
    assert len(snapshots) == 2
    assert all(s['rhythm'] == 'VT' and s['heart_rate'] == 170 for s in snapshots)


def test_cuff_rejects_invalid_target_before_database(monkeypatch):
    monkeypatch.setattr(sm.sio, 'get_session', AsyncMock(return_value={'role':'instructor','session_code':'TEST01'}))
    get_pool = AsyncMock()
    monkeypatch.setattr(sm, 'get_db_pool', get_pool)
    for values in ({'NBP_sys':0}, {'NBP_sys':80,'NBP_dia':90}, {'NBP_dia':float('nan')}):
        result = asyncio.run(sm.apply_all_settings('test', values))
        assert result['status'] == 'error'
    get_pool.assert_not_called()


def test_student_cannot_change_display_and_bad_flags_rejected(monkeypatch):
    get_pool=AsyncMock()
    monkeypatch.setattr(sm,'get_db_pool',get_pool)
    monkeypatch.setattr(sm.sio,'get_session',AsyncMock(return_value={'role':'student'}))
    flags=dict.fromkeys(sm.STUDENT_DISPLAY_KEYS,True)
    assert asyncio.run(sm.set_student_display('test',flags))['status']=='error'
    monkeypatch.setattr(sm.sio,'get_session',AsyncMock(return_value={'role':'instructor'}))
    for data in ({}, {**flags,'pap':'false'}, {**flags,'unknown':True}):
        assert asyncio.run(sm.set_student_display('test',data))['status']=='error'
    get_pool.assert_not_called()


def test_student_display_persists_only_presentation_and_broadcasts(monkeypatch):
    class Cursor:
        execute=AsyncMock()
        fetchone=AsyncMock(return_value={'id':1})
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
    cursor=Cursor()
    class Connection:
        def cursor(self,*args): return cursor
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
    pool=SimpleNamespace(acquire=lambda:Connection())
    monkeypatch.setattr(sm,'get_db_pool',AsyncMock(return_value=pool))
    monkeypatch.setattr(sm.sio,'get_session',AsyncMock(return_value={'role':'instructor','session_code':'TEST01'}))
    emit=AsyncMock()
    monkeypatch.setattr(sm.sio,'emit',emit)
    flags=dict.fromkeys(sm.STUDENT_DISPLAY_KEYS,False)
    assert asyncio.run(sm.set_student_display('test',flags))['status']=='success'
    sql,params=cursor.execute.call_args_list[0].args
    assert 'JSON_SET' in sql and '$.student_display' in sql
    assert json.loads(params[0])==flags and params[1]=='TEST01'
    emit.assert_awaited_once_with('state_update',{'student_display':flags,'initial_readings_hidden':False},room='TEST01')
