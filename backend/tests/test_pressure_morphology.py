import numpy as np
import pytest
from ecg_state import ECGState, RhythmType
from simman_engine.abp_generator import pressure_pulse
from simman_engine.waveform_generator import WaveformGenerator


@pytest.mark.parametrize('peak,notch,width,depth', [(0.14,0.42,0.035,0.1),(0.18,0.46,0.06,0.07)])
def test_pressure_is_continuous_bounded_and_has_notch(peak,notch,width,depth):
    pulse=lambda phase: pressure_pulse(phase,peak,notch,width,depth)
    values=np.array([pulse(t) for t in np.linspace(0,1,1001)])
    assert values.min() >= 0 and values.max() <= 1
    assert pulse(peak) == 1
    assert pulse(0) == pulse(1) == 0
    assert abs(pulse(1-1e-5)-pulse(1e-5)) < 1e-6
    assert pulse(notch) < pulse(notch-width)
    assert pulse(notch) < pulse(notch+width)
    runoff=np.array([pulse(t) for t in np.linspace(notch+width,0.999,100)])
    assert np.all(np.diff(runoff) <= 0)


@pytest.mark.parametrize('hr',[40,80,160])
@pytest.mark.parametrize('method',['generate_abp','generate_pap'])
def test_pressure_stream_is_finite_and_pulseless_is_flat(hr,method):
    gen=WaveformGenerator()
    state=ECGState(heart_rate=hr,rhythm=RhythmType.NSR)
    gen.generate(state,500)
    values=getattr(gen,method)(state,500)
    assert np.all(np.isfinite(values)) and np.ptp(values)>3
    state.pulse_present=False
    gen.generate(state,500)
    assert np.all(getattr(gen,method)(state,500)==0)
