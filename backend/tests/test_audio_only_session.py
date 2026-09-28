"""An old active simulator session must not block a microphone-only run."""
import asyncio
import json

import main


class FakeCursor:
    def __init__(self, active):
        self.active = active
        self.inserted = None

    async def __aenter__(self): return self
    async def __aexit__(self, *args): return False

    async def execute(self, sql, params):
        if sql.lstrip().startswith("INSERT"):
            self.inserted = params

    async def fetchall(self): return self.active


class FakeConnection:
    def __init__(self, active):
        self.cur = FakeCursor(active)
        self.committed = False

    async def __aenter__(self): return self
    async def __aexit__(self, *args): return False
    def cursor(self, *_): return self.cur
    async def commit(self): self.committed = True


class FakePool:
    def __init__(self, active): self.conn = FakeConnection(active)
    def acquire(self): return self.conn


def test_create_audio_only_ignores_active_simulation(monkeypatch):
    pool = FakePool([{"session_code": "OLDVF1", "current_scenario_json": json.dumps({"title": "VF"})}])
    async def get_pool(): return pool
    monkeypatch.setattr(main, "get_db_pool", get_pool)
    result = asyncio.run(main.create_audio_only_session(user={"id": 7}))
    assert result["mode"] == "audio_only"
    assert result["session_code"] != "OLDVF1"
    assert pool.conn.committed
    assert json.loads(pool.conn.cur.inserted[-1])["mode"] == "audio_only"


def test_create_audio_only_reuses_existing_audio_run(monkeypatch):
    pool = FakePool([{"session_code": "EXIST1", "current_scenario_json": json.dumps({"mode": "audio_only"})}])
    async def get_pool(): return pool
    monkeypatch.setattr(main, "get_db_pool", get_pool)
    result = asyncio.run(main.create_audio_only_session(user={"id": 7}))
    assert result == {"session_code": "EXIST1", "mode": "audio_only", "reused": True}
    assert pool.conn.cur.inserted is None
