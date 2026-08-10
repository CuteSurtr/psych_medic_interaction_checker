from __future__ import annotations
import math
import pytest
from services.hepatic_extraction import EnzymePathway, InhibitorTerm, classify_extraction, compute_hepatic_clearance, compute_regimen_hepatic_extraction

class TestWellStirredIdentity:

    def test_algebraic_identity(self):
        pathways = [EnzymePathway('CYP3A4', vmax_mg_per_h=100.0, km_mg_per_l=0.5)]
        fu = 0.3
        q_h = 80.0
        cl_int = 100.0 / 0.5
        result = compute_hepatic_clearance(pathways, fu, q_hepatic_l_per_h=q_h)
        expected_cl_h = q_h * fu * cl_int / (q_h + fu * cl_int)
        assert math.isclose(result.cl_hepatic_l_per_h, expected_cl_h, rel_tol=1e-09)
        assert math.isclose(result.extraction_ratio, expected_cl_h / q_h, rel_tol=1e-09)
        assert math.isclose(result.first_pass_fraction, 1.0 - expected_cl_h / q_h, rel_tol=1e-09)

    def test_sum_of_pathways(self):
        pathways = [EnzymePathway('CYP3A4', 60.0, 0.3), EnzymePathway('CYP2D6', 40.0, 0.5)]
        result = compute_hepatic_clearance(pathways, f_unbound=0.5)
        expected = 60.0 / 0.3 + 40.0 / 0.5
        assert math.isclose(result.cl_intrinsic_l_per_h, expected)

class TestClassification:

    def test_low_extraction(self):
        pathways = [EnzymePathway('CYP1A2', vmax_mg_per_h=1.0, km_mg_per_l=1.0)]
        result = compute_hepatic_clearance(pathways, f_unbound=0.05)
        assert result.classification == 'low'
        assert result.extraction_ratio < 0.3

    def test_high_extraction(self):
        pathways = [EnzymePathway('CYP3A4', vmax_mg_per_h=1000000.0, km_mg_per_l=0.1)]
        result = compute_hepatic_clearance(pathways, f_unbound=1.0)
        assert result.classification == 'high'
        assert result.extraction_ratio > 0.9

    def test_classify_helper(self):
        assert classify_extraction(0.1) == 'low'
        assert classify_extraction(0.5) == 'intermediate'
        assert classify_extraction(0.8) == 'high'

class TestInhibition:

    def test_inhibitor_lowers_cl(self):
        pathways = [EnzymePathway('CYP3A4', 50.0, 0.5)]
        fu = 0.5
        inh = [InhibitorTerm(enzyme='CYP3A4', unbound_concentration_mg_per_l=0.2, ki_mg_per_l=0.1)]
        result = compute_hepatic_clearance(pathways, fu, inhibitors=inh)
        assert result.cl_intrinsic_inhibited_l_per_h < result.cl_intrinsic_l_per_h
        assert result.cl_hepatic_inhibited_l_per_h < result.cl_hepatic_l_per_h
        expected = 50.0 / 0.5 / 3.0
        assert math.isclose(result.cl_intrinsic_inhibited_l_per_h, expected, rel_tol=1e-09)

    def test_inhibitor_on_different_enzyme_has_no_effect(self):
        pathways = [EnzymePathway('CYP3A4', 50.0, 0.5)]
        inh = [InhibitorTerm('CYP2D6', 10.0, 0.1)]
        result = compute_hepatic_clearance(pathways, 0.5, inhibitors=inh)
        assert math.isclose(result.cl_intrinsic_inhibited_l_per_h, result.cl_intrinsic_l_per_h)

class TestPathwayPercentages:

    def test_percentages_sum_to_100(self):
        pathways = [EnzymePathway('CYP3A4', 60.0, 0.3), EnzymePathway('CYP2D6', 40.0, 0.5)]
        result = compute_hepatic_clearance(pathways, f_unbound=0.5)
        total = sum(result.pathway_contributions.values())
        assert math.isclose(total, 100.0, rel_tol=1e-06)

    def test_dominant_pathway(self):
        pathways = [EnzymePathway('CYP3A4', 90.0, 0.1), EnzymePathway('CYP2D6', 10.0, 0.5)]
        result = compute_hepatic_clearance(pathways, f_unbound=0.5)
        assert result.pathway_contributions['CYP3A4'] > 90.0

class TestValidation:

    def test_empty_pathways_raises(self):
        with pytest.raises(ValueError):
            compute_hepatic_clearance([], f_unbound=0.5)

    def test_fu_out_of_range(self):
        pathways = [EnzymePathway('CYP3A4', 50.0, 0.5)]
        with pytest.raises(ValueError):
            compute_hepatic_clearance(pathways, f_unbound=0.0)
        with pytest.raises(ValueError):
            compute_hepatic_clearance(pathways, f_unbound=1.5)

    def test_zero_qh_raises(self):
        pathways = [EnzymePathway('CYP3A4', 50.0, 0.5)]
        with pytest.raises(ValueError):
            compute_hepatic_clearance(pathways, f_unbound=0.5, q_hepatic_l_per_h=0.0)

class TestRegimen:

    def test_inhibitor_drug_affects_substrate_drug(self):
        drug_pathways = {'A': [EnzymePathway('CYP2D6', 10.0, 0.1)], 'B': [EnzymePathway('CYP3A4', 30.0, 0.5)]}
        f_unbound = {'A': 0.5, 'B': 1.0}
        drug_inhibitor_targets = {'B': [('CYP2D6', 0.1)]}
        inhibitor_plasma = {'B': 0.2}
        regimen = compute_regimen_hepatic_extraction(drug_pathways, f_unbound, inhibitor_plasma_mg_per_l=inhibitor_plasma, drug_inhibitor_targets=drug_inhibitor_targets)
        a = regimen.per_drug['A']
        b = regimen.per_drug['B']
        assert a.cl_hepatic_inhibited_l_per_h < a.cl_hepatic_l_per_h
        assert math.isclose(b.cl_hepatic_l_per_h, b.cl_hepatic_inhibited_l_per_h, rel_tol=1e-09)

    def test_single_drug_no_ddi(self):
        drug_pathways = {'A': [EnzymePathway('CYP2D6', 10.0, 0.1)]}
        regimen = compute_regimen_hepatic_extraction(drug_pathways, f_unbound={'A': 0.5})
        a = regimen.per_drug['A']
        assert math.isclose(a.cl_hepatic_l_per_h, a.cl_hepatic_inhibited_l_per_h)
