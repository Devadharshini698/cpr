"""Local, consented introduction clips. Never used as clinical-action evidence."""
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from auth import require_instructor

router = APIRouter(prefix='/api/prebrief', tags=['Prebriefing'])
ROOT = Path(__file__).parent / 'uploads' / 'prebrief'
MAX_BYTES = 12 * 1024 * 1024


def read_record(record_id, user):
    if not isinstance(record_id, str) or not re.fullmatch(r'[a-f0-9]{32}', record_id):
        raise HTTPException(422, 'Invalid introduction reference')
    path = ROOT / f'{record_id}.json'
    if not path.is_file():
        raise HTTPException(404, 'Introduction recording not found')
    record = json.loads(path.read_text(encoding='utf-8'))
    if record['owner_id'] != user['id']:
        raise HTTPException(403, 'Introduction belongs to another instructor')
    return record


def validate_prebrief(data, user):
    if data is None:
        return None  # Existing API clients remain compatible.
    if not isinstance(data, dict):
        raise HTTPException(422, 'Invalid prebrief data')
    ids = data.get('recording_ids', [])
    if (data.get('consent_confirmed') is not True or not isinstance(ids, list)
            or not all(isinstance(item, str) for item in ids)
            or not 1 <= len(ids) <= 12 or len(set(ids)) != len(ids)):
        raise HTTPException(422, 'Consent and 1–12 distinct team introductions are required')
    return {'completed_at': datetime.now(timezone.utc).isoformat(), 'consent_confirmed': True,
            'identity_status': 'instructor_entered_not_biometrically_verified',
            'members': [{k: v for k, v in read_record(item, user).items() if k != 'owner_id'} for item in ids]}


@router.post('/recordings', status_code=201)
async def upload_introduction(audio: UploadFile = File(...), name: str = Form(...),
                              role: str = Form(...), consent: bool = Form(False),
                              user: dict = Depends(require_instructor)):
    if not consent or not 1 <= len(name.strip()) <= 80 or not 1 <= len(role.strip()) <= 80:
        raise HTTPException(422, 'Confirm consent and enter a name and role (maximum 80 characters)')
    mime = (audio.content_type or '').split(';')[0]
    extensions = {'audio/webm': '.webm', 'audio/ogg': '.ogg', 'audio/mp4': '.m4a', 'audio/wav': '.wav'}
    if mime not in extensions:
        raise HTTPException(415, 'Use a supported audio recording')
    content = await audio.read(MAX_BYTES + 1)
    if not content or len(content) > MAX_BYTES:
        raise HTTPException(413, 'Introduction must be non-empty and at most 12 MB')
    ROOT.mkdir(parents=True, exist_ok=True)
    identifier = uuid.uuid4().hex
    filename = identifier + extensions[mime]
    (ROOT / filename).write_bytes(content)
    record = {'recording_id': identifier, 'name': name.strip(), 'role': role.strip(),
              'owner_id': user['id'], 'filename': filename, 'mime_type': mime,
              'recorded_at': datetime.now(timezone.utc).isoformat()}
    (ROOT / f'{identifier}.json').write_text(json.dumps(record), encoding='utf-8')
    return {'recording_id': identifier, 'status': 'saved'}


@router.get('/recordings/{record_id}')
async def get_introduction(record_id: str, user: dict = Depends(require_instructor)):
    record = read_record(record_id, user)
    return FileResponse(ROOT / record['filename'], media_type=record['mime_type'])
