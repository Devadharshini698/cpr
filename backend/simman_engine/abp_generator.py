from __future__ import annotations
import numpy as np


def pressure_pulse(phase, peak=0.14, notch=0.40, notch_width=0.035, notch_depth=0.10):
    """Bounded periodic teaching trace, not a validated haemodynamic model.

    A rapid upstroke, systolic decline, valve-closure notch and diastolic
    runoff. Both ends meet at the diastolic baseline without the gamma
    pulse's abrupt truncation at the next beat. Output is a pulse fraction.
    """
    phase = float(phase) % 1.0
    knots = (0.0, peak, notch - notch_width, notch, notch + notch_width, 1.0)
    values = (0.0, 1.0, 0.52, 0.52 - notch_depth, 0.52 - notch_depth * 0.35, 0.0)
    for index in range(len(knots) - 1):
        if phase <= knots[index + 1]:
            fraction = (phase - knots[index]) / (knots[index + 1] - knots[index])
            eased = fraction * fraction * (3.0 - 2.0 * fraction)
            return values[index] + (values[index + 1] - values[index]) * eased
    return 0.0

def abp_equation(
    t: np.ndarray,
    systolic_pressure: float,
    diastolic_pressure: float,
    rise_time: float,
    notch_depth: float,
    notch_time: float,
    notch_sigma: float,
) -> np.ndarray:
    safe_rise_time = max(rise_time, 1e-6)
    safe_sigma = max(notch_sigma, 1e-6)

    # Standard clinical ABP pulse equation from formulas.py
    systolic_term = (t / safe_rise_time) * np.exp(1.0 - (t / safe_rise_time))
    notch_term = notch_depth * np.exp(-((t - notch_time) ** 2) / (2.0 * safe_sigma**2))
    return diastolic_pressure + (systolic_pressure - diastolic_pressure) * systolic_term - notch_term
