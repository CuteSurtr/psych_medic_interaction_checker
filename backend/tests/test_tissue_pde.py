from __future__ import annotations
import math
import numpy as np
import pytest
from services.tissue_pde import DEFAULT_D_BRAIN_CM2_PER_H, TissuePDEParams, solve_tissue_pde, solve_tissue_pde_for_regimen

def _constant_plasma_trace(value_mg_l: float, hours: float=500.0, n: int=501):
    t = np.linspace(0.0, hours, n)
    c = np.full_like(t, value_mg_l)
    return (t, c)

class TestSteadyState:

    def test_constant_plasma_saturates_to_f_u_times_plasma(self):
        params = TissuePDEParams(drug_name='test', p_eff_cm_per_h=0.5, f_unbound=0.4, k_e_tissue_per_h=0.0, slab_depth_cm=1.0, n_nodes=41)
        t, c = _constant_plasma_trace(100.0, hours=1000.0, n=501)
        result = solve_tissue_pde(params, t, c)
        expected = params.f_unbound * 100.0
        np.testing.assert_allclose(result.deep_concentration[-1], expected, rtol=0.005)
        np.testing.assert_allclose(result.surface_concentration[-1], expected, rtol=0.005)
        np.testing.assert_allclose(result.mean_concentration[-1], expected, rtol=0.005)

    def test_zero_permeability_gives_zero_tissue(self):
        params = TissuePDEParams(drug_name='inert', p_eff_cm_per_h=0.0, f_unbound=1.0, slab_depth_cm=1.0)
        t, c = _constant_plasma_trace(500.0, hours=200.0, n=201)
        result = solve_tissue_pde(params, t, c)
        assert np.max(result.concentration) < 1e-06

    def test_nonzero_ke_lowers_steady_state(self):
        base = TissuePDEParams(drug_name='x', p_eff_cm_per_h=0.3, f_unbound=0.5, k_e_tissue_per_h=0.0)
        eliminated = TissuePDEParams(drug_name='x', p_eff_cm_per_h=0.3, f_unbound=0.5, k_e_tissue_per_h=0.05)
        t, c = _constant_plasma_trace(10.0, hours=1000.0, n=501)
        r_base = solve_tissue_pde(base, t, c)
        r_elim = solve_tissue_pde(eliminated, t, c)
        assert r_elim.mean_concentration[-1] < r_base.mean_concentration[-1]

class TestEquilibrationKinetics:

    def test_lithium_slow_equilibration(self):
        params = TissuePDEParams.for_drug('lithium')
        t, c = _constant_plasma_trace(1.0, hours=24.0 * 21, n=505)
        result = solve_tissue_pde(params, t, c)
        assert result.time_to_80pct_h is None or result.time_to_80pct_h > 24.0

    def test_diazepam_fast_equilibration(self):
        base = TissuePDEParams.for_drug('diazepam')
        params = TissuePDEParams(drug_name=base.drug_name, p_eff_cm_per_h=base.p_eff_cm_per_h, f_unbound=base.f_unbound, d_tissue_cm2_per_h=base.d_tissue_cm2_per_h, k_e_tissue_per_h=base.k_e_tissue_per_h, slab_depth_cm=0.3, n_nodes=41)
        t, c = _constant_plasma_trace(1.0, hours=48.0, n=481)
        result = solve_tissue_pde(params, t, c)
        assert result.time_to_80pct_h is not None
        assert result.time_to_80pct_h < 24.0

    def test_lithium_slower_than_diazepam_fractional(self):
        li = TissuePDEParams.for_drug('lithium')
        dz = TissuePDEParams.for_drug('diazepam')
        t, c = _constant_plasma_trace(1.0, hours=24.0 * 14, n=673)
        r_li = solve_tissue_pde(li, t, c)
        r_dz = solve_tissue_pde(dz, t, c)
        early = int(len(t) * 0.25)
        dz_frac = r_dz.deep_concentration[early] / r_dz.plasma_unbound[early]
        li_frac = r_li.deep_concentration[early] / r_li.plasma_unbound[early]
        assert dz_frac > li_frac

class TestAnalyticalSanity:

    def test_analytical_steady_state_robin_bc(self):
        params = TissuePDEParams(drug_name='ss_check', p_eff_cm_per_h=0.2, f_unbound=1.0, k_e_tissue_per_h=0.0, slab_depth_cm=2.0, n_nodes=81)
        t, c = _constant_plasma_trace(5.0, hours=2000.0, n=501)
        result = solve_tissue_pde(params, t, c)
        final = result.concentration[:, -1]
        assert (final.max() - final.min()) / final.mean() < 0.01
        np.testing.assert_allclose(final.mean(), 5.0, rtol=0.005)

    def test_profile_monotone_decreasing_during_uptake(self):
        params = TissuePDEParams(drug_name='x', p_eff_cm_per_h=0.05, f_unbound=0.5, slab_depth_cm=1.0, n_nodes=41)
        t, c = _constant_plasma_trace(10.0, hours=4.0, n=41)
        result = solve_tissue_pde(params, t, c)
        mid = len(t) // 2
        assert result.concentration[0, mid] > result.concentration[-1, mid]

class TestMultiDrug:

    def test_regimen_runs_per_drug(self):
        t = np.linspace(0.0, 168.0, 169)
        concs = {'fluoxetine': 0.1 * (1.0 - np.exp(-t / 12.0)), 'aripiprazole': 0.05 * (1.0 - np.exp(-t / 24.0))}
        out = solve_tissue_pde_for_regimen(t, concs)
        assert set(out.per_drug.keys()) == {'fluoxetine', 'aripiprazole'}
        for res in out.per_drug.values():
            assert res.concentration.shape == (res.x_cm.size, t.size)

class TestValidation:

    def test_rejects_degenerate_grid(self):
        params = TissuePDEParams(drug_name='bad', p_eff_cm_per_h=0.1, f_unbound=0.5, n_nodes=2)
        t, c = _constant_plasma_trace(1.0, hours=10.0, n=11)
        with pytest.raises(ValueError):
            solve_tissue_pde(params, t, c)

    def test_rejects_mismatched_trace(self):
        params = TissuePDEParams.for_drug('fluoxetine')
        t = np.linspace(0, 10, 11)
        c = np.linspace(0, 1, 5)
        with pytest.raises(ValueError):
            solve_tissue_pde(params, t, c)

class TestDiffusionStencilOrder:

    @pytest.mark.parametrize('n_nodes', [21, 41, 81])
    def test_refinement_converges(self, n_nodes: int):
        params = TissuePDEParams(drug_name='ref', p_eff_cm_per_h=0.3, f_unbound=1.0, d_tissue_cm2_per_h=DEFAULT_D_BRAIN_CM2_PER_H, k_e_tissue_per_h=0.0, slab_depth_cm=1.0, n_nodes=n_nodes)
        t, c = _constant_plasma_trace(1.0, hours=2000.0, n=401)
        result = solve_tissue_pde(params, t, c)
        assert math.isclose(result.mean_concentration[-1], 1.0, rel_tol=0.01)
