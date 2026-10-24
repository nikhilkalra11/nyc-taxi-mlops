import numpy as np
import pandas as pd
import pytest

from scripts.drift_report import psi


def test_psi_same_population_near_zero():
    data = pd.Series(np.linspace(1, 100, 1000))
    assert psi(data, data) == pytest.approx(0.0, abs=1e-9)


def test_psi_shift_positive():
    a = pd.Series(np.linspace(1, 100, 1000))
    b = pd.Series(np.linspace(51, 150, 1000))
    assert psi(a, b) > 0.2
