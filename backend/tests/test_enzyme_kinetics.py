import pytest
from services.enzyme_kinetics import competitive_inhibition_rate, enzyme_activity_factor, michaelis_menten_rate

def test_mm_rate_zero_concentration():
    assert michaelis_menten_rate(0.0, vmax=100.0, km=10.0) == 0.0
    assert michaelis_menten_rate(-1.0, vmax=100.0, km=10.0) == 0.0

def test_mm_rate_at_km():
    vmax, km = (80.0, 40.0)
    rate = michaelis_menten_rate(km, vmax, km)
    assert rate == pytest.approx(vmax / 2.0)

def test_mm_rate_high_concentration():
    vmax, km = (50.0, 5.0)
    c = km * 1000.0
    rate = michaelis_menten_rate(c, vmax, km)
    assert rate == pytest.approx(vmax, rel=0.001)

def test_competitive_inhibition_no_inhibitors():
    c, vmax, km = (12.0, 30.0, 6.0)
    base = michaelis_menten_rate(c, vmax, km)
    inhib = competitive_inhibition_rate(c, vmax, km, [], [])
    assert inhib == pytest.approx(base)

def test_competitive_inhibition_halves_rate():
    vmax, km = (60.0, 10.0)
    c_sub = km
    uninhibited = michaelis_menten_rate(c_sub, vmax, km)
    inhibited = competitive_inhibition_rate(c_sub, vmax, km, inhibitor_concentrations=[km], ki_values=[km])
    assert uninhibited == pytest.approx(vmax / 2.0)
    assert inhibited == pytest.approx(vmax / 3.0)
    assert inhibited < uninhibited
    assert inhibited == pytest.approx(uninhibited * 2.0 / 3.0)

def test_enzyme_activity_no_inhibitors():
    assert enzyme_activity_factor([], []) == pytest.approx(1.0)

def test_enzyme_activity_with_inhibitor():
    f = enzyme_activity_factor([50.0], [100.0])
    assert f == pytest.approx(1.0 / (1.0 + 0.5))
    assert f < 1.0
