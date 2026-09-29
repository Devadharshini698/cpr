"""Short push-to-talk requests. Offline only; never auto-reveal or infer identity."""
from pathlib import Path
import os
import threading
import gc
import re

SPEECH_MODEL_LOCK = threading.Lock()


def available_memory():
    """Windows RAM check using the standard library, without extra packages."""
    if os.name != 'nt':
        return None
    import ctypes
    class MemoryStatus(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in
            ('total_phys', 'avail_phys', 'total_page', 'avail_page', 'total_virtual', 'avail_virtual', 'extended')]
    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ValueError('Cannot check free memory safely. Use a typed request.')
    return status.avail_phys


def suggest_channel(text):
    groups = [('pap',r'\b(pap|pulmonary artery)\b'), ('abp',r'\b(abp|arterial pressure|arterial line)\b'),
        ('nibp',r'\b(nibp|nbp|bp|blood pressure)\b'), ('spo2',r'\b(spo2|sp o2|saturation|oxygen|pulse ox)\b'),
        ('co2',r'\b(etco2|co2|capnography|respiratory rate)\b'),('temp',r'\b(temperature|temp)\b'),
        ('co',r'\bcardiac output\b'),('ecg',r'\b(ecg|ekg|rhythm|electrocardiogram)\b')]
    matches=[key for key,pattern in groups if re.search(pattern,text,re.I)]
    return matches[0] if len(matches)==1 else None


def transcribe_request(path, language):
    import numpy as np
    from faster_whisper import WhisperModel
    from faster_whisper.audio import decode_audio
    cache=Path(os.getenv('DEBRIEF_WHISPER_CACHE_DIR',str(Path(__file__).parent/'uploads/model_cache/whisper')))
    model_path=cache/'Systran--faster-whisper-small'
    if not all((model_path/name).is_file() for name in ('config.json','model.bin','tokenizer.json')):
        raise ValueError('Local Whisper small is not installed. Use the typed request; no model was downloaded.')
    samples=decode_audio(str(path),sampling_rate=16000)
    if not 0.3 <= len(samples)/16000 <= 15:
        raise ValueError('Record a request between 1 and 12 seconds.')
    rms=float(np.sqrt(np.mean(samples*samples)))
    if rms < 0.0008:
        raise ValueError('The recording is almost silent. Select the correct microphone and move closer, or type the request.')
    free_memory = available_memory()
    if free_memory is not None and free_memory < 512*1024*1024:
        raise ValueError('Insufficient free memory for local speech recognition. Use a typed request.')
    model=None
    try:
        model=WhisperModel(str(model_path),device='cpu',compute_type='int8',cpu_threads=1,num_workers=1,local_files_only=True)
        segments,_=model.transcribe(samples,language={'english':'en','tamil':'ta'}.get(language),
            beam_size=3,vad_filter=True,condition_on_previous_text=False,temperature=0)
        text=' '.join(s.text.strip() for s in segments if s.no_speech_prob<0.7).strip()
        if not text: raise ValueError('No intelligible speech found. Listen to the clip and retry or type the request.')
        return {'text':text[:500],'suggested_channel':suggest_channel(text),'local_only':True}
    finally:
        del model
        gc.collect()
