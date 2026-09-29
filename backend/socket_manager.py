"""Socket.IO server and event handlers — matches frozen contract."""

import asyncio
import math
import json
import uuid
from datetime import datetime

import socketio
import aiomysql
from auth import decode_token
from database import get_db_pool
from models import DEFAULT_MONITOR_STATE
from physiology import normalize_monitor_state
from ecg_state import ECGStateUpdate, RhythmType, TransferFn
from simman_engine.state_machine import get_session_engine

# Create async Socket.IO server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)

# Track active transfer tasks: { (session_id, field): asyncio.Task }
_transfer_tasks: dict = {}

# Scenarios Cache
SCENARIOS_CACHE = []
_active_nibp_loops = {}


# The instructor's session monitor uses readable labels while the waveform
# engine uses RhythmType values. Keep both representations in one place.
_ENGINE_RHYTHMS = {
    **{r.value: r for r in RhythmType},
    "ATRIAL FIBRILLATION": RhythmType.AFIB,
    "ATRIAL FLUTTER": RhythmType.AFLUTTER,
    "TORSADE DE POINTES": RhythmType.TORSADES,
    "TORSADES DE POINTES": RhythmType.TORSADES,
    "1ST DEGREE AV BLOCK": RhythmType.AVB1,
    "2ND DEGREE AV BLOCK TYPE I": RhythmType.AVB2_I,
    "2ND DEGREE AV BLOCK TYPE II": RhythmType.AVB2_II,
    "SINUS RHYTHM": RhythmType.NSR,
    "NSR": RhythmType.NSR,
    "SINUS BRADYCARDIA": RhythmType.SINUS_BRADY,
    "SINUS BRADY": RhythmType.SINUS_BRADY,
    "SINUS TACHYCARDIA": RhythmType.SINUS_TACHY,
    "SINUS TACHY": RhythmType.SINUS_TACHY,
    "VENTRICULAR TACHYCARDIA": RhythmType.VT,
    "VT": RhythmType.VT,
    "VENTRICULAR FIBRILLATION": RhythmType.VF,
    "VF": RhythmType.VF,
    "ASYSTOLE": RhythmType.ASYSTOLE,
    "JUNCTIONAL RHYTHM": RhythmType.JUNCTIONAL,
    "JUNCTIONAL": RhythmType.JUNCTIONAL,
    "3RD DEGREE AV BLOCK": RhythmType.AVB3,
    "THIRD DEGREE AV BLOCK": RhythmType.AVB3,
}


def _engine_rhythm_for_state(state: dict) -> RhythmType | None:
    """Convert saved monitor state into the waveform engine's rhythm enum."""
    # The scenario model represents PEA as an organised ECG plus absent pulse.
    # The waveform engine needs the explicit PEA rhythm to suppress non-ECG traces.
    if state.get("emd_pea"):
        return RhythmType.PEA
    raw = str(state.get("rhythm", "")).strip().upper()
    return _ENGINE_RHYTHMS.get(raw)


async def _sync_waveform_engine(state: dict, session_code: str | None = None) -> None:
    """Apply a session condition/rhythm state to the live waveform engine.

    The engine is the source of binary waveform packets, while the persisted
    monitor state is the source of dashboard values. Synchronising here makes a
    selected scenario condition change both surfaces atomically from the user's
    perspective.
    """
    def number(key: str, current: float) -> float:
        value = state.get(key, current)
        try:
            return float(value)
        except (TypeError, ValueError):
            return current

    waveform_engine = get_session_engine(session_code)
    await waveform_engine.start()
    await waveform_engine.apply_command(ECGStateUpdate(
        rhythm=_engine_rhythm_for_state(state),
        heart_rate=number("HR", waveform_engine.state.heart_rate),
        pulse_present=bool(number("pulse_rate", number("HR", 0)) > 0 and not state.get("emd_pea")),
        spo2=number("SpO2", waveform_engine.state.spo2),
        sys_bp=number("ABP_sys", waveform_engine.state.sys_bp),
        dia_bp=number("ABP_dia", waveform_engine.state.dia_bp),
        pap_sys=number("PAP_sys", waveform_engine.state.pap_sys),
        pap_dia=number("PAP_dia", waveform_engine.state.pap_dia),
        etco2=number("etCO2", waveform_engine.state.etco2),
        resp_rate=number("avRR", waveform_engine.state.resp_rate),
        transfer_time=0.0,
        transfer_fn=TransferFn.IMMEDIATE,
    ))

async def _run_nibp_measurement(session_id, session_code):
    try:
        pool = await get_db_pool()
        stages = [
            ("INFLATING", 2.5),
            ("MEASURING", 3.0),
            ("PROCESSING", 2.0)
        ]
        
        for state_name, duration in stages:
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session_id,))
                    state_row = await cur.fetchone()
                    if not state_row:
                        return
                    state = json.loads(state_row["state_data"])
                    state["nibp_state"] = state_name
                    await cur.execute("UPDATE monitor_state SET state_data = %s WHERE session_id = %s", (json.dumps(state), session_id))
            
            await sio.emit("state_update", state, room=session_code)
            await asyncio.sleep(duration)
            
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session_id,))
                state_row = await cur.fetchone()
                if not state_row:
                    return
                state = json.loads(state_row["state_data"])
                
                target_sys = state.get("nbp_target_sys", state.get("NBP_sys", 120.0))
                target_dia = state.get("nbp_target_dia", state.get("NBP_dia", 80.0))
                
                perfusing = float(state.get('pulse_rate', state.get('HR', 0)) or 0) > 0 and not state.get('emd_pea')
                state["NBP_sys"] = target_sys if perfusing else None
                state["NBP_dia"] = target_dia if perfusing else None
                state["NBP_mean"] = round(target_dia + (target_sys - target_dia) / 3.0, 1) if perfusing else None
                state["nibp_state"] = "COMPLETE" if perfusing else "UNOBTAINABLE"
                state["nibp_last_measured"] = datetime.utcnow().isoformat()
                
                await cur.execute("UPDATE monitor_state SET state_data = %s WHERE session_id = %s", (json.dumps(state), session_id))
                
        await sio.emit("state_update", state, room=session_code)
    except Exception as e:
        print(f"[NIBP Measurement Error] {e}")

async def _nibp_interval_loop(session_id, session_code):
    while True:
        try:
            await asyncio.sleep(10)
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session_id,))
                    state_row = await cur.fetchone()
                    if not state_row:
                        break
                    state = json.loads(state_row["state_data"])
                    
            interval = int(state.get("nibp_interval", 0))
            nibp_state = state.get("nibp_state", "IDLE")
            
            if interval > 0 and nibp_state in ("IDLE", "COMPLETE", "UNOBTAINABLE"):
                last_measured_str = state.get("nibp_last_measured", "")
                should_measure = False
                if not last_measured_str:
                    should_measure = True
                else:
                    try:
                        last_measured = datetime.fromisoformat(last_measured_str)
                        elapsed_minutes = (datetime.utcnow() - last_measured).total_seconds() / 60.0
                        if elapsed_minutes >= interval:
                            should_measure = True
                    except Exception:
                        should_measure = True
                        
                if should_measure:
                    asyncio.create_task(_run_nibp_measurement(session_id, session_code))
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[NIBP Loop Error] {e}")
            await asyncio.sleep(5)


def safe_parse_json(val):
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return val
    return val

async def load_scenarios_to_cache():
    global SCENARIOS_CACHE
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, name, patient_details, symptoms, initial_readings FROM scenarios")
            rows = await cur.fetchall()
            SCENARIOS_CACHE = []
            for r in rows:
                SCENARIOS_CACHE.append({
                    "id": r["id"],
                    "name": r["name"],
                    "patient_details": safe_parse_json(r["patient_details"]),
                    "symptoms": safe_parse_json(r["symptoms"]),
                    "initial_readings": safe_parse_json(r["initial_readings"])
                })
            print(f"[CACHE] Loaded {len(SCENARIOS_CACHE)} scenarios into memory cache.")

def map_scenario_to_state(monitor_values):
    state_updates = {}
    if "heartRate" in monitor_values:
        state_updates["HR"] = float(monitor_values["heartRate"])
        state_updates["pulse_rate"] = float(monitor_values["heartRate"])
    if "spo2" in monitor_values:
        state_updates["SpO2"] = float(monitor_values["spo2"])
    if "bloodPressure" in monitor_values:
        bp = monitor_values["bloodPressure"]
        state_updates["ABP_sys"] = float(bp.get("systolic", 120.0))
        state_updates["ABP_dia"] = float(bp.get("diastolic", 80.0))
        state_updates["MAP"] = float(bp.get("map", 93.0))
        state_updates["NBP_sys"] = float(bp.get("systolic", 120.0))
        state_updates["NBP_dia"] = float(bp.get("diastolic", 80.0))
        state_updates["NBP_mean"] = float(bp.get("map", 93.0))
    if "respiratoryRate" in monitor_values:
        state_updates["avRR"] = float(monitor_values["respiratoryRate"])
    if "temperature" in monitor_values:
        temp = monitor_values["temperature"]
        state_updates["Tblood"] = float(temp.get("bloodTemperature", 37.0))
        state_updates["Tperi"] = float(temp.get("peripheralTemperature", 36.5))
    if "cardiacOutput" in monitor_values:
        state_updates["CO"] = float(monitor_values["cardiacOutput"])
    if "pulmonaryArteryPressure" in monitor_values:
        pap = monitor_values["pulmonaryArteryPressure"]
        state_updates["PAP_sys"] = float(pap.get("systolic", 20.0))
        state_updates["PAP_dia"] = float(pap.get("diastolic", 10.0))
        state_updates["PAP_mean"] = float(pap.get("mean", 13.0))
    if "pulmonaryCapillaryWedgePressure" in monitor_values:
        state_updates["PAP_wedge"] = float(monitor_values["pulmonaryCapillaryWedgePressure"])
    if "etco2" in monitor_values:
        state_updates["etCO2"] = float(monitor_values["etco2"])
    if "inco2" in monitor_values:
        state_updates["inCO2"] = float(monitor_values["inco2"])
    if "inspiredOxygen" in monitor_values:
        state_updates["inO2"] = float(monitor_values["inspiredOxygen"])
    if "endTidalOxygen" in monitor_values:
        state_updates["etO2"] = float(monitor_values["endTidalOxygen"])
    if "inspiredNitrousOxide" in monitor_values:
        state_updates["inN2O"] = float(monitor_values["inspiredNitrousOxide"])
    if "endTidalNitrousOxide" in monitor_values:
        state_updates["etN2O"] = float(monitor_values["endTidalNitrousOxide"])
    if "ecgRhythm" in monitor_values:
        state_updates["rhythm"] = str(monitor_values["ecgRhythm"])
    return state_updates

async def emit_scenario_selected(session_code, scenario):
    student_scenario = dict(scenario)
    student_scenario.pop("initial_readings", None)
    
    sids = []
    try:
        room_data = sio.manager.rooms.get("/", {}).get(session_code, {})
        sids = list(room_data.keys())
    except Exception:
        try:
            participants = sio.manager.get_participants("/", session_code)
            sids = [p[0] if isinstance(p, tuple) else p for p in participants]
        except Exception:
            pass
            
    if not sids:
        await sio.emit("scenario_selected", student_scenario, room=session_code)
        return

    for sid in sids:
        try:
            client_session = await sio.get_session(sid)
            if client_session and client_session.get("role") == "instructor":
                await sio.emit("scenario_selected", scenario, to=sid)
            else:
                await sio.emit("scenario_selected", student_scenario, to=sid)
        except Exception:
            pass


def compute_alarms(state: dict) -> list[str]:
    """Compute alarms by checking values against alarm_thresholds."""
    alarms = []
    thresholds = state.get("alarm_thresholds", {})

    for field, bounds in thresholds.items():
        val = state.get(field)
        if val is None:
            continue
        low = bounds.get("low")
        high = bounds.get("high")
        if low is not None and val < low:
            alarms.append(f"{field} LOW")
        if high is not None and val > high:
            alarms.append(f"{field} HIGH")

    # Special named alarms
    if state.get("avRR", 14) == 0:
        alarms.append("APNEA")
    if state.get("SpO2", 98) < 90:
        alarms.append("DESAT")

    return alarms


# ── Socket Events ─────────────────────────────────────────────────

@sio.event
async def connect(sid, environ):
    print(f"[SIO] Client connected: {sid}")


@sio.event
async def disconnect(sid):
    print(f"[SIO] Client disconnected: {sid}")


@sio.event
async def join_session(sid, data):
    """Client joins a session room."""
    session_code = data.get("session_code")
    token = data.get("token")
    if not session_code:
        await sio.emit("error", {"message": "Missing session_code"}, to=sid)
        return

    payload = {"sub": "Student", "role": "student"}
    if token:
        try:
            payload = decode_token(token)
        except Exception:
            payload = {"sub": "Student", "role": "student"}

    # A browser can move directly from one simulation to another without a
    # socket reconnect. Remember the old room so it can be left only after the
    # requested session is verified as joinable below.
    prior_client_session = await sio.get_session(sid) or {}
    prior_session_code = prior_client_session.get("session_code")
    state_to_hydrate = None

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, started_at, is_active FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            
            if not session:
                await sio.emit("error", {"message": "Session not found"}, to=sid)
                return
            if not session.get("is_active", True):
                await sio.emit("error", {"message": "Session has ended"}, to=sid)
                return

            if prior_session_code and prior_session_code != session_code:
                await sio.leave_room(sid, prior_session_code)
            await sio.enter_room(sid, session_code)
            await sio.save_session(sid, {
                "username": payload.get("sub"),
                "role": payload.get("role"),
                "session_code": session_code,
            })

            # Confirm join to the client (frontend listens for this)
            await sio.emit("join_confirmed", {
                "session_code": session_code,
                "role": payload.get("role"),
            }, to=sid)

            # Send current state with started_at
            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            
            if state_row:
                state = json.loads(state_row["state_data"])
                state["started_at"] = session["started_at"].isoformat() if session["started_at"] else datetime.utcnow().isoformat()
                state_to_hydrate = dict(state)
                await sio.emit("state_update", state, to=sid)
            # Send current event log history to the client
            await cur.execute("SELECT event_log FROM sessions WHERE id = %s", (session["id"],))
            sess_event_row = await cur.fetchone()
            if sess_event_row and sess_event_row.get("event_log"):
                event_history = json.loads(sess_event_row["event_log"])
                await sio.emit("session_history_log", {"event_log": event_history}, to=sid)

            # If session has current_scenario_id or current_scenario_json, fetch and send it
            await cur.execute("SELECT current_scenario_id, current_scenario_json, checklist_state FROM sessions WHERE id = %s", (session["id"],))
            session_row = await cur.fetchone()
            if session_row:
                scenario = None
                if session_row.get("current_scenario_json"):
                    try:
                        scenario = json.loads(session_row["current_scenario_json"])
                    except Exception:
                        pass
                elif session_row.get("current_scenario_id"):
                    scenario_id = session_row["current_scenario_id"]
                    scenario = next((s for s in SCENARIOS_CACHE if s["id"] == scenario_id), None)
                
                if scenario:
                    if payload.get("role") == "instructor":
                        await sio.emit("scenario_selected", scenario, to=sid)
                    else:
                        student_scenario = dict(scenario)
                        student_scenario.pop("initial_readings", None)
                        await sio.emit("scenario_selected", student_scenario, to=sid)

                if session_row.get("checklist_state"):
                    try:
                        chk_list = json.loads(session_row["checklist_state"])
                        await sio.emit("checklist_updated", {"checklist": chk_list}, to=sid)
                    except Exception:
                        pass

            if payload.get("role") == "instructor":
                session_id = session["id"]
                if session_id not in _active_nibp_loops:
                    _active_nibp_loops[session_id] = asyncio.create_task(_nibp_interval_loop(session_id, session_code))

    # A backend restart recreates in-memory waveform engines.  Hydrate the
    # session-specific engine from its persisted monitor state whenever a user
    # joins, so re-opening an active VF session cannot fall back to NSR.
    if state_to_hydrate is not None:
        await _sync_waveform_engine(state_to_hydrate, session_code)

    print(f"[SIO] {payload.get('sub')} joined session {session_code}")


@sio.event
async def update_parameter(sid, data):
    """Instructor updates a single parameter.
    Contract: {field, value, transfer_time_seconds, transfer_function}
    """
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return

    session_code = session_data.get("session_code")
    field = data.get("field")
    value = data.get("value")
    transfer_seconds = data.get("transfer_time_seconds", 0)
    transfer_fn = data.get("transfer_function", "immediate")

    if not field:
        await sio.emit("error", {"message": "Missing field"}, to=sid)
        return

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                return

    if transfer_seconds and transfer_seconds > 0 and transfer_fn in ("linear", "smooth"):
        print(f"[TRANSFER] Starting {transfer_fn} transfer: {field} -> {value} over {transfer_seconds}s")
        await _start_transfer(
            session, session_code, field, value,
            transfer_seconds, transfer_fn, session_data.get("username", "")
        )
    else:
        print(f"[UPDATE] Instant: {field} -> {value}")
        await _apply_update(session, session_code, field, value, session_data.get("username", ""))


@sio.event
async def update_rhythm(sid, data):
    """Instructor updates cardiac rhythm settings."""
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return

    session_code = session_data.get("session_code")
    
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, started_at, event_log FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                return

            update_fields = {}
            for key in ["rhythm", "extrasystole", "HR", "ecg_lead",
                        "artifact_electrical", "artifact_muscular", "emd_pea"]:
                if key in data:
                    update_fields[key] = data[key]

            # Keep pulse_rate in sync with HR
            if "HR" in update_fields:
                update_fields["pulse_rate"] = update_fields["HR"]

            update_fields["last_updated"] = datetime.utcnow().isoformat()
            update_fields["updated_by"] = session_data.get("username", "")

            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            state = json.loads(state_row["state_data"])
            
            for k, v in update_fields.items():
                state[k] = v
                
            state["initial_readings_hidden"] = False
            state["alarms"] = compute_alarms(state)
            
            await cur.execute("UPDATE monitor_state SET state_data = %s WHERE session_id = %s", (json.dumps(state), session["id"]))
            
            event_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "event": f"Rhythm -> {state.get('rhythm')}, HR -> {state.get('HR')}",
                "event_type": "rhythm_change",
                "source": "simman",
                "actor_role": "instructor",
                "payload": {"rhythm": state.get("rhythm"), "heart_rate": state.get("HR"),
                    **({"pulse_present": data["pulse_present"]} if isinstance(data.get("pulse_present"), bool) else {})},
            }
            event_log = json.loads(session["event_log"]) if session["event_log"] else []
            event_log.append(event_entry)
            await cur.execute("UPDATE sessions SET event_log = %s WHERE id = %s", (json.dumps(event_log), session["id"]))
            
            state["started_at"] = session["started_at"].isoformat() if session["started_at"] else datetime.utcnow().isoformat()
            
    await _sync_waveform_engine(state, session_code)
    await sio.emit("state_update", state, room=session_code)
    await sio.emit("rhythm_change", {
        k: state.get(k) for k in
        ["rhythm", "extrasystole", "HR", "ecg_lead",
         "artifact_electrical", "artifact_muscular", "emd_pea"]
    }, room=session_code)
    await sio.emit("session_event", event_entry, room=session_code)


@sio.event
async def update_eyes(sid, data):
    """Instructor updates eyes state."""
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return

    session_code = session_data.get("session_code")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, started_at FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                return

            update_fields = {}
            if "eyes_state" in data:
                update_fields["eyes_state"] = data["eyes_state"]
            if "eyes_look" in data:
                update_fields["eyes_look"] = data["eyes_look"]

            update_fields["last_updated"] = datetime.utcnow().isoformat()
            
            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            state = json.loads(state_row["state_data"])
            
            for k, v in update_fields.items():
                state[k] = v
    if event_entry:
        await sio.emit("session_event", event_entry, room=session_code)

    return state


@sio.event
async def perform_clinical_action(sid, data):
    """Instructor performs a clinical action (Shock, CPR, Medication, Pulse Check)."""
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return

    session_code = data.get("session_code") or session_data.get("session_code")
    action_type = data.get("action_type", "CLINICAL_ACTION")
    
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                return

    await _process_clinical_action(
        session["id"],
        session_code,
        action_type,
        data,
        session_data.get("username", "Instructor")
    )


async def _process_clinical_action(session_id, session_code, action_type, data, actor_name="Instructor"):
    """Persist a structured instructor action and publish it to the timeline.

    Checklist controls call this same path.  It must therefore exist even when
    no separate manual-action panel is visible; otherwise completed checklist
    actions looked successful in the UI but supplied no debrief evidence.
    """
    action = str(action_type or "").upper()
    event_type = {
        "CPR": "cpr_initiated",
        "SHOCK": "shock_delivered",
        "MEDICATION": "drug_administered",
        "PULSE_CHECK": "pulse_check",
        "RHYTHM_CHECK": "rhythm_check",
        "ROSC": "rosc_achieved",
    }.get(action, "scenario_marker")
    payload = dict(data or {})
    if event_type == "shock_delivered":
        payload["energy_joules"] = payload.get("energy_joules", payload.get("joules", 200))
    if event_type == "drug_administered":
        payload["drug_name"] = payload.get("drug_name", payload.get("drug", "Medication"))
        payload["dose"] = payload.get("dose", "not recorded")
    labels = {
        "CPR": "CPR initiated", "SHOCK": "Shock delivered", "MEDICATION": "Medication administered",
        "PULSE_CHECK": "Pulse check performed", "RHYTHM_CHECK": "Rhythm check performed", "ROSC": "ROSC documented",
    }
    now = datetime.utcnow().isoformat()
    entry = {
        "event_id": f"action_{uuid.uuid4().hex}", "timestamp": now,
        "event": labels.get(action, f"Clinical action: {action_type}"),
        "event_type": event_type, "source": "simman", "actor_role": "instructor",
        "payload": payload, "confidence": 1.0,
    }
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT event_log FROM sessions WHERE id=%s", (session_id,))
            row = await cur.fetchone()
            if not row:
                return
            event_log = json.loads(row["event_log"]) if row.get("event_log") else []
            event_log.append(entry)
            await cur.execute("UPDATE sessions SET event_log=%s WHERE id=%s", (json.dumps(event_log), session_id))
        await conn.commit()
    await sio.emit("session_event", entry, room=session_code)


@sio.event
async def add_event_log(sid, data):
    """Add an event to the session log."""
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return

    session_code = data.get("session_code") or session_data.get("session_code")
    event_text = data.get("event", "")
    
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, event_log FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                return

            event_log = json.loads(session["event_log"]) if session["event_log"] else []
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "event": event_text,
                "source": "manual",
                "actor_role": "instructor"
            }
            if data.get("event_type"):
                from debriefing.contracts import Event
                try:
                    validated = Event(event_id=data.get("event_id") or f"action_{uuid.uuid4().hex}",
                        event_type=data["event_type"], timestamp_ms=0, actor_role="instructor",
                        source="manual", payload=data.get("payload", {}), evidence=event_text)
                    entry.update({"event_id": validated.event_id, "event_type": validated.event_type,
                        "payload": validated.payload})
                except ValueError:
                    await sio.emit("error", {"message": "Invalid clinical event payload"}, to=sid)
                    return
            event_log.append(entry)
            
            await cur.execute("UPDATE sessions SET event_log = %s WHERE id = %s", (json.dumps(event_log), session["id"]))
            
    await sio.emit("session_event", entry, room=session_code)


@sio.event
async def faculty_comment(sid, data):
    """Broadcast instructor comment/message to the session room."""
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return

    session_code = session_data.get("session_code")
    comment_text = data.get("comment", "")
    
    entry = {
        "from": session_data.get("username", "Instructor"),
        "comment": comment_text,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    await sio.emit("faculty_comment", entry, room=session_code)


@sio.event
async def apply_condition(sid, data):
    """Instructor applies a predefined scenario condition state."""
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return

    session_code = session_data.get("session_code")
    condition_id = data.get("condition_id")
    condition_name = data.get("condition_name", condition_id)
    state_updates = data.get("state", {})

    if not condition_id or not state_updates:
        await sio.emit("error", {"message": "Invalid condition payload"}, to=sid)
        return

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, started_at, event_log, condition_history FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                return

            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            if not state_row:
                return
                
            state = json.loads(state_row["state_data"])
            for k, v in state_updates.items():
                state[k] = v
            try:
                state = normalize_monitor_state(state)
            except (ValueError, TypeError):
                await sio.emit('error', {'message': 'Condition has inconsistent physiological values'}, to=sid)
                return
            if 'ABP_sys' in state_updates or 'ABP_dia' in state_updates:
                state['nbp_target_sys'] = state['ABP_sys']
                state['nbp_target_dia'] = state['ABP_dia']
                
            state["last_updated"] = datetime.utcnow().isoformat()
            state["updated_by"] = session_data.get("username", "")
            state["alarms"] = compute_alarms(state)

            await cur.execute("UPDATE monitor_state SET state_data = %s WHERE session_id = %s", (json.dumps(state), session["id"]))

            # Record event in event_log
            now_iso = datetime.utcnow().isoformat()
            event_entry = {
                "timestamp": now_iso,
                "event": f"Condition Changed -> {condition_name}",
                "event_type": "rhythm_change",
                "source": "simman",
                "actor_role": "instructor",
                "payload": {
                    "rhythm": state.get("rhythm"), "heart_rate": state.get("HR"),
                    "pulse_present": bool(state.get("pulse_rate", 0) > 0),
                    "emd_pea": bool(state.get("emd_pea", False)), "condition_id": condition_id,
                },
                "condition_id": condition_id,
                "condition_name": condition_name
            }
            event_log = json.loads(session["event_log"]) if session.get("event_log") else []
            event_log.append(event_entry)
            if bool(state.get("pulse_rate", 0) > 0) and "rosc" in str(condition_name).lower():
                event_log.append({
                    "event_id": f"rosc_{uuid.uuid4().hex}", "timestamp": now_iso,
                    "event": "ROSC achieved by scripted physiology", "event_type": "rosc_achieved",
                    "source": "simman", "actor_role": "instructor", "payload": {"condition_id": condition_id},
                    "confidence": 1.0,
                })

            # Record condition history
            cond_hist = json.loads(session["condition_history"]) if session.get("condition_history") else []
            cond_hist.append({"condition_id": condition_id, "name": condition_name, "timestamp": now_iso})

            await cur.execute(
                "UPDATE sessions SET event_log = %s, condition_history = %s, current_condition_id = %s WHERE id = %s",
                (json.dumps(event_log), json.dumps(cond_hist), condition_id, session["id"])
            )

            state["started_at"] = session["started_at"].isoformat() if session.get("started_at") else now_iso

    await _sync_waveform_engine(state, session_code)
    # Broadcast updates
    await sio.emit("state_update", state, room=session_code)
    await sio.emit("condition_changed", {"condition_id": condition_id, "condition_name": condition_name, "timestamp": now_iso}, room=session_code)
    await sio.emit("rhythm_change", {
        k: state.get(k) for k in
        ["rhythm", "extrasystole", "HR", "ecg_lead", "artifact_electrical", "artifact_muscular", "emd_pea"]
    }, room=session_code)
    await sio.emit("session_event", event_entry, room=session_code)


@sio.event
async def mark_checklist_done(sid, data):
    """Instructor marks a checklist item completed."""
    session_data = await sio.get_session(sid)
    session_code = data.get("session_code") or (session_data.get("session_code") if session_data else None)
    item_id = data.get("item_id")
    if not session_code or not item_id:
        print(f"[mark_checklist_done] Missing parameters: session_code={session_code}, item_id={item_id}")
        return

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, started_at, event_log, checklist_state, current_scenario_json FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                return

            checklist = json.loads(session["checklist_state"]) if session.get("checklist_state") else []
            if not checklist and session.get("current_scenario_json"):
                try:
                    scen_spec = json.loads(session["current_scenario_json"])
                    checklist = scen_spec.get("checklist", [])
                except Exception:
                    checklist = []

            now_dt = datetime.utcnow()
            now_iso = now_dt.isoformat()
            
            start_dt = session.get("started_at") or now_dt
            if isinstance(start_dt, str):
                try:
                    start_dt = datetime.fromisoformat(start_dt.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    start_dt = now_dt
                    
            elapsed_sec = max(0, int((now_dt - start_dt).total_seconds()))

            action_name = item_id
            target_item = None
            for item in checklist:
                if (
                    str(item.get("id")) == str(item_id)
                    or item.get("action") == item_id
                    or str(item.get("item_id")) == str(item_id)
                ):
                    target_item = item
                    action_name = item.get("action", item_id)
                    window_sec = int(item.get("window_sec", 60))
                    
                    if elapsed_sec > window_sec:
                        item["status"] = "completed_late"
                        item["delay_seconds"] = elapsed_sec - window_sec
                    else:
                        item["status"] = "completed"
                        item["delay_seconds"] = 0
                    item["completed_at"] = now_iso
                    break

            if target_item:
                # Update database checklist table if table exists
                try:
                    await cur.execute(
                        """UPDATE session_checklist 
                           SET status = %s, completed_at = %s, delay_seconds = %s 
                           WHERE session_id = %s AND (item_id = %s OR action = %s)""",
                        (target_item["status"], now_dt, target_item["delay_seconds"], session["id"], str(target_item.get("id", item_id)), action_name)
                    )
                except Exception as ex:
                    print(f"[mark_checklist_done DB update warning] {ex}")

                # Add event to log
                event_entry = {
                    "timestamp": now_iso,
                    "event": f"Checklist Completed -> {action_name} ({target_item['status']})",
                    "event_type": "CHECKLIST_COMPLETED",
                    "item_id": target_item.get("id", item_id),
                    "status": target_item["status"]
                }
                event_log = json.loads(session["event_log"]) if session.get("event_log") else []
                event_log.append(event_entry)

                await cur.execute(
                    "UPDATE sessions SET checklist_state = %s, event_log = %s WHERE id = %s",
                    (json.dumps(checklist), json.dumps(event_log), session["id"])
                )

                await sio.emit("checklist_updated", {"checklist": checklist}, room=session_code)
                await sio.emit("session_event", event_entry, room=session_code)

                # Connect checklist interventions to live physiological state transition
                action_lower = str(action_name).lower()
                if "shock" in action_lower or "defib" in action_lower:
                    await _process_clinical_action(session["id"], session_code, "SHOCK", {"joules": 200})
                elif "cpr" in action_lower or "compress" in action_lower:
                    await _process_clinical_action(session["id"], session_code, "CPR", {})
                elif "epi" in action_lower or "epinephrine" in action_lower:
                    await _process_clinical_action(session["id"], session_code, "MEDICATION", {"drug": "Epinephrine", "dose": "1mg"})
                elif "atropine" in action_lower:
                    await _process_clinical_action(session["id"], session_code, "MEDICATION", {"drug": "Atropine", "dose": "1mg"})


@sio.event
async def update_alarm_thresholds(sid, data):
    """Instructor updates alarm thresholds."""
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return

    session_code = session_data.get("session_code")
    
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, started_at FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                return

            new_thresholds = data.get("thresholds", {})
            
            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            state = json.loads(state_row["state_data"])
            
            state["alarm_thresholds"] = new_thresholds
            state["initial_readings_hidden"] = False
            state["alarms"] = compute_alarms(state)
            
            await cur.execute("UPDATE monitor_state SET state_data = %s WHERE session_id = %s", (json.dumps(state), session["id"]))
            
            state["started_at"] = session["started_at"].isoformat() if session["started_at"] else datetime.utcnow().isoformat()

    await sio.emit("state_update", state, room=session_code)
    await sio.emit("alarm_update", {"alarms": state["alarms"]}, room=session_code)


@sio.event
async def list_scenarios(sid):
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return
    await sio.emit("scenarios_list", SCENARIOS_CACHE, to=sid)


@sio.event
async def select_scenario(sid, data):
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return
    
    session_code = session_data.get("session_code")
    scenario_id = data.get("scenario_id")
    if not scenario_id:
        await sio.emit("error", {"message": "Missing scenario_id"}, to=sid)
        return
    
    scenario = next((s for s in SCENARIOS_CACHE if s["id"] == scenario_id), None)
    if not scenario:
        await sio.emit("error", {"message": f"Scenario {scenario_id} not found"}, to=sid)
        return
    
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, started_at FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                return
            
            await cur.execute("UPDATE sessions SET current_scenario_id = %s WHERE id = %s", (scenario_id, session["id"]))
            
            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            state = json.loads(state_row["state_data"])
            
            updates = map_scenario_to_state(scenario["initial_readings"])
            for k, v in updates.items():
                state[k] = v
            
            state["initial_readings_hidden"] = True
            state["last_updated"] = datetime.utcnow().isoformat()
            state["updated_by"] = session_data.get("username", "")
            state["alarms"] = compute_alarms(state)
            
            await cur.execute("UPDATE monitor_state SET state_data = %s WHERE session_id = %s", (json.dumps(state), session["id"]))
            
            state["started_at"] = session["started_at"].isoformat() if session["started_at"] else datetime.utcnow().isoformat()

            event_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "event": f"Scenario loaded: {scenario['name']}",
            }
            await cur.execute("SELECT event_log FROM sessions WHERE id = %s", (session["id"],))
            sess_row = await cur.fetchone()
            event_log = json.loads(sess_row["event_log"]) if sess_row and sess_row["event_log"] else []
            event_log.append(event_entry)
            await cur.execute("UPDATE sessions SET event_log = %s WHERE id = %s", (json.dumps(event_log), session["id"]))

    await sio.emit("state_update", state, room=session_code)
    await sio.emit("alarm_update", {"alarms": state["alarms"]}, room=session_code)
    await sio.emit("session_event", event_entry, room=session_code)
    await emit_scenario_selected(session_code, scenario)


@sio.event
async def request_random_scenario(sid):
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return
    
    if not SCENARIOS_CACHE:
        await sio.emit("error", {"message": "No scenarios loaded in cache"}, to=sid)
        return
    
    import random
    scenario = random.choice(SCENARIOS_CACHE)
    await select_scenario(sid, {"scenario_id": scenario["id"]})


@sio.event
async def apply_all_settings(sid, data):
    """Instructor commits all current settings as a single transaction."""
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") != "instructor":
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return

    session_code = session_data.get("session_code")
    requested_updates = dict(data)
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, started_at, event_log FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                return

            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            state = json.loads(state_row["state_data"])

            # Extract NIBP updates to target variables
            if "NBP_sys" in data:
                state["nbp_target_sys"] = data.pop("NBP_sys")
            if "NBP_dia" in data:
                state["nbp_target_dia"] = data.pop("NBP_dia")

            # Apply other settings
            for k, v in data.items():
                state[k] = v

            # Keep derived fields in sync (except NIBP which is updated on cuff finish)
            if "HR" in data:
                state["pulse_rate"] = data["HR"]
            if "ABP_sys" in data or "ABP_dia" in data:
                sys_val = state.get("ABP_sys", 120.0)
                dia_val = state.get("ABP_dia", 80.0)
                state["MAP"] = round(dia_val + (sys_val - dia_val) / 3.0, 1)
            if "PAP_sys" in data or "PAP_dia" in data:
                sys_val = state.get("PAP_sys", 20.0)
                dia_val = state.get("PAP_dia", 10.0)
                state["PAP_mean"] = round(dia_val + (sys_val - dia_val) / 3.0, 1)

            state["initial_readings_hidden"] = False
            state["last_updated"] = datetime.utcnow().isoformat()
            state["updated_by"] = session_data.get("username", "")
            state["alarms"] = compute_alarms(state)

            await cur.execute("UPDATE monitor_state SET state_data = %s WHERE session_id = %s", (json.dumps(state), session["id"]))

            change_summary = ", ".join(f"{key}={value}" for key, value in requested_updates.items())
            event_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "event": f"Vitals updated: {change_summary}" if change_summary else "Vital settings confirmed",
                "event_type": "VITAL_CHANGE",
                "changes": requested_updates,
            }
            event_log = json.loads(session["event_log"]) if session["event_log"] else []
            event_log.append(event_entry)
            await cur.execute("UPDATE sessions SET event_log = %s WHERE id = %s", (json.dumps(event_log), session["id"]))

            state["started_at"] = session["started_at"].isoformat() if session["started_at"] else datetime.utcnow().isoformat()

    await sio.emit("state_update", state, room=session_code)
    await sio.emit("alarm_update", {"alarms": state["alarms"]}, room=session_code)
    await sio.emit("session_event", event_entry, room=session_code)

    # If rhythm/HR changed, broadcast rhythm_change
    if any(k in data for k in ["rhythm", "extrasystole", "HR", "ecg_lead", "artifact_electrical", "artifact_muscular", "emd_pea"]):
        await sio.emit("rhythm_change", {
            k: state.get(k) for k in
            ["rhythm", "extrasystole", "HR", "ecg_lead",
             "artifact_electrical", "artifact_muscular", "emd_pea"]
        }, room=session_code)

    return {"status": "success"}


@sio.event
async def measure_nibp(sid):
    session_data = await sio.get_session(sid)
    if not session_data or session_data.get("role") not in ("instructor", "operator", "admin"):
        await sio.emit("error", {"message": "Instructor role required"}, to=sid)
        return
    session_code = session_data.get("session_code")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id FROM sessions WHERE session_code = %s", (session_code,))
            session = await cur.fetchone()
            if not session:
                return

            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            if state_row:
                state = json.loads(state_row["state_data"])
                if state.get("nibp_state") in ("INFLATING", "MEASURING", "PROCESSING"):
                    return

    asyncio.create_task(_run_nibp_measurement(session["id"], session_code))


# ── Helpers ───────────────────────────────────────────────────────

async def _apply_update(session, session_code, field, value, username):
    """Apply a single field update, recompute alarms, broadcast."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            state = json.loads(state_row["state_data"])

            state[field] = value
            state["initial_readings_hidden"] = False
            state["last_updated"] = datetime.utcnow().isoformat()
            state["updated_by"] = username

            # Keep derived fields in sync
            if field == "HR":
                state["pulse_rate"] = value
            if field in ("ABP_sys", "ABP_dia"):
                sys_val = state.get("ABP_sys", 120)
                dia_val = state.get("ABP_dia", 80)
                state["MAP"] = round(dia_val + (sys_val - dia_val) / 3, 1)
            if field in ("NBP_sys", "NBP_dia"):
                sys_val = state.get("NBP_sys", 120)
                dia_val = state.get("NBP_dia", 80)
                state["NBP_mean"] = round(dia_val + (sys_val - dia_val) / 3, 1)
            if field in ("PAP_sys", "PAP_dia"):
                sys_val = state.get("PAP_sys", 20)
                dia_val = state.get("PAP_dia", 10)
                state["PAP_mean"] = round(dia_val + (sys_val - dia_val) / 3, 1)

            state["alarms"] = compute_alarms(state)
            await cur.execute("UPDATE monitor_state SET state_data = %s WHERE session_id = %s", (json.dumps(state), session["id"]))

            await cur.execute("SELECT started_at, event_log FROM sessions WHERE id = %s", (session["id"],))
            sess_row = await cur.fetchone()
            
            event_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "event": f"{field} -> {value}",
                "event_type": "VITAL_CHANGE",
                "changes": {field: value},
            }
            event_log = json.loads(sess_row["event_log"]) if sess_row["event_log"] else []
            event_log.append(event_entry)
            await cur.execute("UPDATE sessions SET event_log = %s WHERE id = %s", (json.dumps(event_log), session["id"]))
            
            state["started_at"] = sess_row["started_at"].isoformat() if sess_row["started_at"] else datetime.utcnow().isoformat()

    await sio.emit("state_update", state, room=session_code)
    await sio.emit("alarm_update", {"alarms": state["alarms"]}, room=session_code)
    await sio.emit("session_event", event_entry, room=session_code)


async def _start_transfer(session, session_code, field, target_value,
                           transfer_seconds, transfer_fn, username):
    """Background interpolation: linear or smooth (ease-in-out)."""
    task_key = (str(session["id"]), field)

    if task_key in _transfer_tasks:
        _transfer_tasks[task_key].cancel()

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT state_data FROM monitor_state WHERE session_id = %s", (session["id"],))
            state_row = await cur.fetchone()
            state = json.loads(state_row["state_data"])
            
    start_value = state.get(field, 0)
    steps = max(int(transfer_seconds), 1)

    async def _interpolate():
        try:
            for i in range(1, steps + 1):
                await asyncio.sleep(1)
                t = i / steps  # 0..1
                if transfer_fn == "smooth":
                    # Ease-in-out (smoothstep)
                    t = t * t * (3 - 2 * t)
                # linear is just t
                val = start_value + (target_value - start_value) * t
                val = round(val, 1)
                print(f"[TRANSFER] {field}: step {i}/{steps} = {val}")
                await _apply_update(session, session_code, field, val, username)
            # Final exact value
            await _apply_update(session, session_code, field, target_value, username)
            print(f"[TRANSFER] {field}: done -> {target_value}")
        except asyncio.CancelledError:
            print(f"[TRANSFER] {field}: cancelled")
        finally:
            _transfer_tasks.pop(task_key, None)

    task = asyncio.create_task(_interpolate())
    _transfer_tasks[task_key] = task


async def emit_session_ended(session_code: str):
    """Emit session_ended to all clients in the room."""
    await sio.emit("session_ended", {"session_code": session_code}, room=session_code)
