"""Faculty-attributed longitudinal observations; never inferred from team/audio scores."""
import hashlib
import json
import uuid
from collections import defaultdict
import aiomysql
from fastapi import APIRouter, Depends, HTTPException
from auth import require_instructor
from database import get_db_pool

router = APIRouter(prefix='/api/progress', tags=['Performance progress'])
RUBRIC = 'faculty-progress-1'
DOMAINS = {'assessment':'Patient assessment', 'priorities':'Recognition and prioritisation',
           'actions':'Appropriate actions within role', 'communication':'Communication and teamwork',
           'reassessment':'Reassessment and adaptation', 'handover':'Escalation and handover'}
SCALE = {'0':'Observed omission / not achieved', '1':'Major prompting required',
         '2':'Some prompting required', '3':'Performed independently'}

async def init_progress():
    pool=await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute('''CREATE TABLE IF NOT EXISTS progress_subjects (
                id CHAR(36) PRIMARY KEY, owner_id INT NOT NULL, kind VARCHAR(10) NOT NULL,
                reference VARCHAR(80) NOT NULL, name VARCHAR(120) NOT NULL,
                created_at DATETIME(6) NOT NULL,
                UNIQUE KEY progress_identity(owner_id,kind,reference))''')
            await cur.execute('''CREATE TABLE IF NOT EXISTS progress_observations (
                id BIGINT AUTO_INCREMENT PRIMARY KEY, owner_id INT NOT NULL,
                subject_id CHAR(36) NOT NULL, session_id INT NOT NULL,
                rubric VARCHAR(40) NOT NULL, role_label VARCHAR(80) NOT NULL,
                cohort CHAR(64) NOT NULL, context_json JSON NOT NULL, ratings_json JSON NOT NULL,
                evidence TEXT NOT NULL, next_steps TEXT NOT NULL, created_at DATETIME(6) NOT NULL,
                INDEX progress_history(owner_id,subject_id,session_id,id))''')

def text_field(body,key,limit):
    value=body.get(key)
    if not isinstance(value,str) or not value.strip() or len(value.strip())>limit:
        raise ValueError(f'{key} is required (maximum {limit} characters)')
    return value.strip()

def validate_observation(body):
    role=text_field(body,'role_label',80)
    evidence=text_field(body,'evidence',2000)
    next_steps=text_field(body,'next_steps',1000)
    ratings=body.get('ratings')
    if not isinstance(ratings,dict) or set(ratings)!=set(DOMAINS):
        raise ValueError('Provide each assessment domain, using null for not observed / not applicable')
    if any(value is not None and (type(value) is not int or not 0<=value<=3) for value in ratings.values()):
        raise ValueError('Ratings must be integers from 0 to 3, or null')
    if all(value is None for value in ratings.values()):
        raise ValueError('At least one domain needs an observed rating')
    if body.get('confirmed_attribution') is not True:
        raise ValueError('Confirm the selected student or team actually participated and was observed')
    return role,evidence,next_steps,ratings

def comparison_context(spec,kind,role,ratings):
    curriculum=spec.get('curriculum') or {}
    if not curriculum.get('programme') or not curriculum.get('subtopic') or not spec.get('level'):
        raise ValueError('This session lacks curriculum/difficulty metadata and cannot enter comparable progress tracking')
    # Match authored clinical content, not generated IDs, team labels or narrative prose.
    context=dict(programme=curriculum['programme'],topic=curriculum['subtopic'],level=spec['level'],
        schema=spec.get('monitor_schema','legacy'),kind=kind,role=role.casefold(),rubric=RUBRIC,
        setting=spec.get('location_label') or spec.get('location'),
        team_roles=sorted(spec.get('discipline') or []),
        patient={key:(spec.get('patient') or {}).get(key) for key in ('age','weight_kg','gestational_age_weeks','postpartum_hours','postpartum_minutes')},
        severity=spec.get('clinical_severity'),initial=spec.get('initial_state') or spec.get('vitals'),
        stages=[dict(id=c.get('id'),state=c.get('state')) for c in spec.get('conditions',[])],
        domains=sorted(key for key,value in ratings.items() if value is not None))
    encoded=json.dumps(context,sort_keys=True,separators=(',',':'))
    return hashlib.sha256(encoded.encode()).hexdigest(),context

def summarise(rows):
    # Corrections are append-only, but only the latest assessment counts for an attempt.
    latest={}
    for row in sorted(rows,key=lambda row:row['id']):
        latest[(row['subject_id'],row['session_id'])]=row
    groups=defaultdict(list)
    attempts=[]
    for row in sorted(latest.values(),key=lambda row:(str(row['ended_at']),row['session_id'])):
        ratings=json.loads(row['ratings_json']) if isinstance(row['ratings_json'],str) else row['ratings_json']
        context=json.loads(row['context_json']) if isinstance(row['context_json'],str) else row['context_json']
        observed=[value for value in ratings.values() if value is not None]
        mean=round(sum(observed)/len(observed),2) if observed else None
        attempt={key:row[key] for key in ('id','subject_id','session_code','ended_at','created_at','role_label','cohort','evidence','next_steps')}
        attempt.update(ratings=ratings,mean=mean,coverage=len(observed),context=context)
        group=groups[(row['subject_id'],row['cohort'])]
        previous=group[-1] if group else None
        attempt['change']=round(mean-previous['mean'],2) if previous and mean is not None and previous['mean'] is not None else None
        group.append(attempt);attempts.append(attempt)
    return attempts

@router.get('')
async def progress_data(user:dict=Depends(require_instructor)):
    pool=await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute('SELECT id,kind,reference,name FROM progress_subjects WHERE owner_id=%s ORDER BY name,id',(user['id'],))
            subjects=await cur.fetchall()
            await cur.execute('''SELECT o.*,s.session_code,s.ended_at FROM progress_observations o
                JOIN sessions s ON s.id=o.session_id JOIN progress_subjects p ON p.id=o.subject_id
                WHERE o.owner_id=%s AND s.created_by=%s AND p.owner_id=%s AND s.is_active=0
                ORDER BY o.id''',(user['id'],user['id'],user['id']))
            observations=await cur.fetchall()
            await cur.execute('''SELECT session_code,team_name,ended_at,current_scenario_json FROM sessions
                WHERE created_by=%s AND is_active=0 AND ended_at IS NOT NULL ORDER BY ended_at DESC,id DESC LIMIT 500''',(user['id'],))
            sessions=await cur.fetchall()
    selectable=[]
    for row in sessions:
        spec=json.loads(row.pop('current_scenario_json') or '{}')
        if not spec.get('curriculum',{}).get('subtopic'): continue
        row.update(title=spec.get('title','Session'),programme=spec['curriculum']['programme'],topic=spec['curriculum']['subtopic'],level=spec.get('level'))
        selectable.append(row)
    return dict(subjects=subjects,sessions=selectable,attempts=summarise(observations),domains=DOMAINS,scale=SCALE,rubric=RUBRIC,
        notice='Faculty observation rubric (0–3), not a validated clinical score or certification. Missing domains are excluded, never scored zero. Comparisons match authored case, setting, difficulty, role and assessed domains; actual instructor-delivered variations may still differ. Only your own records are shown. Session picker shows up to 500 recent completed sessions.')

@router.post('/subjects')
async def create_subject(body:dict,user:dict=Depends(require_instructor)):
    try:
        if body.get('kind') not in ('student','team'): raise ValueError('Choose student or team')
        name=text_field(body,'name',120);reference=text_field(body,'reference',80)
    except ValueError as exc: raise HTTPException(422,str(exc))
    pool=await get_db_pool();identifier=str(uuid.uuid4())
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute('INSERT INTO progress_subjects (id,owner_id,kind,reference,name,created_at) VALUES (%s,%s,%s,%s,%s,UTC_TIMESTAMP(6))',
                    (identifier,user['id'],body['kind'],reference,name))
            await conn.commit()
    except aiomysql.IntegrityError: raise HTTPException(409,'That tracking reference already exists. Select the existing profile.')
    return {'id':identifier}

@router.post('/observations')
async def save_observation(body:dict,user:dict=Depends(require_instructor)):
    try:
        role,evidence,next_steps,ratings=validate_observation(body)
        subject_id=text_field(body,'subject_id',36);code=text_field(body,'session_code',100)
    except ValueError as exc: raise HTTPException(422,str(exc))
    pool=await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute('SELECT id,kind FROM progress_subjects WHERE id=%s AND owner_id=%s',(subject_id,user['id']))
            subject=await cur.fetchone()
            await cur.execute('SELECT id,is_active,ended_at,current_scenario_json FROM sessions WHERE session_code=%s AND created_by=%s',(code,user['id']))
            session=await cur.fetchone()
            if not subject or not session: raise HTTPException(404,'Profile or session not available to this instructor')
            if session['is_active'] or not session['ended_at']: raise HTTPException(409,'End the session before recording longitudinal performance')
            try:
                cohort,context=comparison_context(json.loads(session['current_scenario_json'] or '{}'),subject['kind'],role,ratings)
            except ValueError as exc: raise HTTPException(422,str(exc))
            await cur.execute('''INSERT INTO progress_observations
                (owner_id,subject_id,session_id,rubric,role_label,cohort,context_json,ratings_json,evidence,next_steps,created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,UTC_TIMESTAMP(6))''',
                (user['id'],subject_id,session['id'],RUBRIC,role,cohort,json.dumps(context),json.dumps(ratings),evidence,next_steps))
        await conn.commit()
    return {'status':'saved','notice':'Latest observation is used for this attempt; earlier revisions remain stored.'}
