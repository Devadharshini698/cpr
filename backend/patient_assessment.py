"""Append-only instructor observations, separate from automated clinical scores."""
import aiomysql
from database import get_db_pool

async def init_assessment():
    pool=await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute('''CREATE TABLE IF NOT EXISTS patient_assessments (
                id BIGINT AUTO_INCREMENT PRIMARY KEY, session_id INT NOT NULL,
                phase VARCHAR(32) NOT NULL, item VARCHAR(32) NOT NULL,
                kind VARCHAR(32) NOT NULL, status VARCHAR(32) NOT NULL,
                finding TEXT NOT NULL, feedback TEXT NOT NULL, revealed BOOLEAN NOT NULL DEFAULT FALSE,
                observer_id INT NULL, created_at DATETIME(6) NOT NULL,
                INDEX assessment_session (session_id, id))''')

async def records(session_id):
    pool=await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute('SELECT * FROM patient_assessments WHERE session_id=%s ORDER BY id', (session_id,))
            return await cur.fetchall()

async def append(session_id, user, body, instructor):
    pool=await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute('''INSERT INTO patient_assessments
                (session_id,phase,item,kind,status,finding,feedback,revealed,observer_id,created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,UTC_TIMESTAMP(6))''',
                (session_id,body['phase'],body['item'],'observation' if instructor else 'request',
                 body['status'] if instructor else 'requested',body.get('finding','') if instructor else '',
                 body.get('feedback','') if instructor else '',body['revealed'] if instructor else False,user.get('id')))
        await conn.commit()
