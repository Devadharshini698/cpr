"""Adult TCP teaching model; capture is an explicit faculty decision."""
from copy import deepcopy
import math

DEFAULT_PACER=dict(visible=False,student_enabled=False,pads_connected=False,enabled=False,
    rate=70,output=0,mode='fixed',electrical_capture=False,mechanical_capture=False)
RESPONSE_FIELDS=('rhythm','HR','pulse_rate','emd_pea','ABP_sys','ABP_dia','MAP','SpO2','CO','PAP_sys','PAP_dia','PAP_mean','avRR','etCO2','nbp_target_sys','nbp_target_dia')

def stop_pacer(state):
    result=deepcopy(state)
    p={**DEFAULT_PACER,**result.get('pacer',{})}
    baseline=p.pop('baseline',None)
    if baseline:
        for key in RESPONSE_FIELDS:
            if key not in baseline:
                result.pop(key,None)
        result.update(baseline)
    p.update(enabled=False,electrical_capture=False,mechanical_capture=False)
    result['pacer']=p
    return result

def update_pacer(state,changes,role):
    if not isinstance(changes,dict) or not changes or set(changes)-set(DEFAULT_PACER):
        raise ValueError('Unknown pacer setting')
    if role not in ('instructor','student'):
        raise ValueError('A session role is required')
    old={**DEFAULT_PACER,**state.get('pacer',{})}
    if role=='student' and (not old['visible'] or not old['student_enabled'] or set(changes)-{'enabled','rate','output','pads_connected','mode'}):
        raise ValueError('Instructor permission is required; capture is instructor-controlled')
    for key,value in changes.items():
        if key=='mode':
            if value not in ('fixed','demand'):
                raise ValueError('Pacer mode must be fixed or demand')
        elif key in ('rate','output'):
            low,high=(30,180) if key=='rate' else (0,200)
            if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:
                raise ValueError(f'{key} must be within the simulator range {low}–{high}')
        elif type(value) is not bool:
            raise ValueError('Pacer switches must be true or false')
    result=deepcopy(state)
    if old.get('baseline'):
        for key in RESPONSE_FIELDS:
            if key not in old['baseline']:
                result.pop(key,None)
        result.update(old['baseline'])
    p={**old,**changes}
    p.pop('baseline',None)
    if any(key in changes and changes[key]!=old[key] for key in ('rate','output','enabled','pads_connected','mode')):
        p['electrical_capture']=changes.get('electrical_capture',False)
        p['mechanical_capture']=changes.get('mechanical_capture',False)
    if not p['visible']:
        # Disclosure controls student access, not faculty operation. Previously
        # an instructor's Start command silently succeeded but stayed OFF.
        p['student_enabled']=False
        if changes.get('visible') is False:
            p['enabled']=False
    if not p['enabled'] or not p['pads_connected'] or p['output']==0:
        p.update(electrical_capture=False,mechanical_capture=False)
    if p['enabled'] and not p['pads_connected']:
        raise ValueError('Connect simulated pads before starting')
    if p['mechanical_capture'] and not p['electrical_capture']:
        raise ValueError('Mechanical capture requires electrical capture')
    if p['enabled']:
        if result.get('patient_profile') in ('neonate','infant','child'):
            raise ValueError('This initial pacer prototype supports adult scenarios only')
        if float(result.get('pulse_rate',0) or 0)<=0 or str(result.get('rhythm','')).upper() in ('VF','PVT','PEA','ASYSTOLE','TORSADES','VT'):
            raise ValueError('Use this prototype for an adult with an intrinsic pulse, not cardiac arrest or ventricular tachyarrhythmia')
    if p['electrical_capture']:
        if p['rate']<=float(result.get('HR',0) or 0):
            raise ValueError('Captured teaching rate must exceed the intrinsic rate. Demand mode inhibits on sensed beats; competitive/fusion capture is not modelled in fixed mode.')
        p['baseline']={k:result[k] for k in RESPONSE_FIELDS if k in result}
        result.update(rhythm='NSR',HR=p['rate'],pulse_rate=p['rate'] if p['mechanical_capture'] else 0,emd_pea=False)
        if not p['mechanical_capture']:
            for key in ('ABP_sys','ABP_dia','MAP','SpO2','CO','PAP_sys','PAP_dia','PAP_mean','nbp_target_sys','nbp_target_dia'):
                result[key]=0
        # Respiratory support is independent of electrical/mechanical capture.
    result['pacer']=p
    return result
