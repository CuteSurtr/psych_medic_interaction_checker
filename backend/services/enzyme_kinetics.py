import numpy as np
from dataclasses import dataclass, field
CYP_KDEG: dict[str, float] = {'CYP1A2': 0.0077, 'CYP2C9': 0.0087, 'CYP2C19': 0.0077, 'CYP2D6': 0.0136, 'CYP3A4': 0.0193, 'CYP2B6': 0.012, 'UGT1A4': 0.0077}

@dataclass
class EnzymeParams:
    enzyme_name: str
    vmax: float
    km: float
    fraction_metabolized: float

@dataclass
class InhibitorParams:
    enzyme_name: str
    ki: float
    drug_index: int

@dataclass
class MBIParams:
    enzyme_name: str
    k_inact: float
    k_i_conc: float

@dataclass
class InductionParams:
    enzyme_name: str
    e_max: float
    ec50: float

def michaelis_menten_rate(concentration: float, vmax: float, km: float) -> float:
    if concentration <= 0.0:
        return 0.0
    return vmax * concentration / (km + concentration)

def competitive_inhibition_rate(substrate_conc: float, vmax: float, km: float, inhibitor_concentrations: list[float], ki_values: list[float]) -> float:
    if substrate_conc <= 0.0:
        return 0.0
    inhibition_sum = 0.0
    for ci, ki in zip(inhibitor_concentrations, ki_values):
        if ki > 0.0 and ci > 0.0:
            inhibition_sum += ci / ki
    apparent_km = km * (1.0 + inhibition_sum)
    return vmax * substrate_conc / (apparent_km + substrate_conc)

def enzyme_activity_factor(inhibitor_concentrations: list[float], ki_values: list[float], inducer_effects: list[float] | None=None) -> float:
    inhibition_sum = 0.0
    for ci, ki in zip(inhibitor_concentrations, ki_values):
        if ki > 0.0 and ci > 0.0:
            inhibition_sum += ci / ki
    factor = 1.0 / (1.0 + inhibition_sum)
    if inducer_effects:
        for effect in inducer_effects:
            factor *= effect
    return factor

def enzyme_pool_derivative(enzyme_level: float, k_deg: float, induction_terms: list[tuple[float, float, float]], mbi_terms: list[tuple[float, float, float]]) -> float:
    k_synth = k_deg
    induction_fold = 1.0
    for c_ind, e_max, ec50 in induction_terms:
        if c_ind > 0.0 and ec50 > 0.0:
            induction_fold += e_max * c_ind / (ec50 + c_ind)
    mbi_rate = 0.0
    for c_inh, k_inact, k_i in mbi_terms:
        if c_inh > 0.0 and k_i > 0.0:
            mbi_rate += k_inact * c_inh / (k_i + c_inh)
    return k_synth * induction_fold - k_deg * enzyme_level - mbi_rate * enzyme_level
