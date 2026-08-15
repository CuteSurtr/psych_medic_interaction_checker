"""Evidence-grounded replacements for constants that were previously invented.

Each value here carries a verified citation and, where the source reports one,
an interval that Monte Carlo can sample instead of a bare point estimate.

Audit trail: validation/AUDIT.md findings F-1 and F-2.
"""
from __future__ import annotations

import numpy as np

from services.provenance import (
    REGISTRY,
    Citation,
    Confidence,
    EvidenceClass,
    EvidenceType,
    Parameter,
)

# --------------------------------------------------------------------------
# Citations. verified=True means the DOI resolved via the Crossref API and the
# returned title, authors, journal, year and pages matched (checked 2026-08-15).
# --------------------------------------------------------------------------

FABER_FUHR_2004 = Citation(
    doi='10.1016/j.clpt.2004.04.003',
    pmid='15289794',
    title='Time response of cytochrome P450 1A2 activity on cessation of heavy smoking',
    first_author='Faber MS',
    journal='Clin Pharmacol Ther',
    year=2004,
    verified=True,
)

YANG_2008 = Citation(
    doi='10.2174/138920008784746382',
    title='Cytochrome P450 turnover: regulation of synthesis and degradation',
    first_author='Yang J',
    journal='Curr Drug Metab',
    year=2008,
    verified=True,
)

MEYER_2001 = Citation(
    doi='10.1097/00004714-200112000-00005',
    pmid='11763003',
    title='Individual changes in clozapine levels after smoking cessation',
    first_author='Meyer JM',
    journal='J Clin Psychopharmacol',
    year=2001,
    verified=True,
)

FLANAGAN_2024 = Citation(
    doi='10.1097/jcp.0000000000001909',
    pmid='39173038',
    title='Plasma clozapine and norclozapine concentrations: effect of dose, sex, and cigarette smoking',
    first_author='Flanagan RJ',
    journal='J Clin Psychopharmacol',
    year=2024,
    verified=True,
)

VANDERWEIDE_2003 = Citation(
    doi='10.1097/00008571-200303000-00006',
    pmid='12618594',
    title='The effect of smoking and CYP1A2 genetic polymorphism on clozapine clearance and dose requirement',
    first_author='van der Weide J',
    journal='Pharmacogenetics',
    year=2003,
    verified=True,
)


# --------------------------------------------------------------------------
# F-1: CYP1A2 enzyme turnover
#
# The engine previously used Yang et al.'s in vitro-derived degradation
# constant (k_deg 0.0077/h, t-half 90 h) as the relaxation rate of the enzyme
# pool, which sets how fast activity returns to baseline after an inducer is
# withdrawn.
#
# Faber & Fuhr measured that relaxation directly, in vivo, in 12 heavy smokers
# undergoing sudden cessation, and fitted a monoexponential decay to a residual
# value. They report an apparent half-life of 38.6 h (95% CI 27.4-54.4).
#
# THE TWO SOURCES DISAGREE by a factor of ~2.3 and this is not reconcilable:
# a single enzyme pool has a single turnover rate. We use the Faber & Fuhr
# value because it is (a) in vivo, (b) in humans, (c) a direct measurement of
# the exact quantity the model uses it for. Yang remains the source for the
# other CYPs, where no comparable in vivo de-induction measurement was found.
#
# This disagreement is deliberately surfaced rather than averaged away.
# --------------------------------------------------------------------------

CYP1A2_TURNOVER_HALFLIFE_H = REGISTRY.register(
    'CYP1A2_TURNOVER_HALFLIFE_H',
    Parameter(
        name='CYP1A2 apparent turnover half-life',
        value=38.6,
        unit='hour',
        ci_low=27.4,
        ci_high=54.4,
        distribution='lognormal',
        evidence_class=EvidenceClass.DIRECTLY_MEASURED,
        evidence_type=EvidenceType.HUMAN_PK_STUDY,
        citations=(FABER_FUHR_2004,),
        population='12 heavy smokers (8 male, 4 female, all white, 20+ cigarettes/day)',
        confidence=Confidence.HIGH,
        notes=(
            'Measured as monoexponential decay of CYP1A2 activity to a residual '
            'value after sudden smoking cessation, phenotyped by paraxanthine/'
            'caffeine ratio 6 h after a 148 mg caffeine test dose. '
            'CONFLICTS with Yang et al. 2008 (t-half ~90 h, in vitro-derived); '
            'see module docstring for why this value is preferred.'
        ),
    ),
)

CYP1A2_KDEG_PER_H = float(np.log(2.0) / CYP1A2_TURNOVER_HALFLIFE_H.value)


# --------------------------------------------------------------------------
# F-2: magnitude of CYP1A2 induction by cigarette smoking
#
# Previously a hard-coded (1.0, 1.0, 1.0) tuple in pk_simulator, which
# evaluates to exactly 1.5x with no source and no exposure dependence.
#
# Faber & Fuhr report caffeine clearance falling by 36.1% (95% CI 30.9-42.2)
# on cessation, from 2.47 to 1.53 mL/min/kg. The induction ratio is the
# reciprocal of the retained fraction:
#
#     ratio = 1 / (1 - 0.361) = 1.565     CI: 1/(1-0.309) = 1.447
#                                             1/(1-0.422) = 1.730
#
# LITERATURE_DERIVED rather than DIRECTLY_MEASURED: the paper reports the
# decrease, we computed the ratio.
# --------------------------------------------------------------------------

def _ratio_from_decrease(pct: float) -> float:
    return 1.0 / (1.0 - pct / 100.0)


SMOKING_CYP1A2_INDUCTION_RATIO = REGISTRY.register(
    'SMOKING_CYP1A2_INDUCTION_RATIO',
    Parameter(
        name='CYP1A2 activity ratio, chronic heavy smoking vs non-smoking',
        value=round(_ratio_from_decrease(36.1), 4),
        unit='dimensionless',
        ci_low=round(_ratio_from_decrease(30.9), 4),
        ci_high=round(_ratio_from_decrease(42.2), 4),
        distribution='lognormal',
        evidence_class=EvidenceClass.LITERATURE_DERIVED,
        evidence_type=EvidenceType.HUMAN_PK_STUDY,
        citations=(FABER_FUHR_2004,),
        population='12 heavy smokers (20+ cigarettes/day), caffeine probe',
        confidence=Confidence.HIGH,
        notes=(
            'Derived as the reciprocal of the reported 36.1% (30.9-42.2) fall in '
            'caffeine clearance on cessation. Applies to heavy smoking; the '
            'literature indicates near-maximal induction by roughly 7-12 '
            'cigarettes/day, so this is treated as a saturated on/off exposure '
            'rather than a dose-response.'
        ),
    ),
)

# Emax such that the enzyme pool reaches the measured ratio at steady state.
# With k_synth = k_deg, E_ss = 1 + Emax when the inducer term is saturated.
SMOKING_CYP1A2_EMAX = SMOKING_CYP1A2_INDUCTION_RATIO.value - 1.0

# Smoking is represented as a saturated binary exposure: normalised inducer
# "concentration" 1.0 against a low EC50, so the Hill term sits near its
# maximum. This is a modelling convention, not a measured potency, because
# cigarettes/day is not tracked as a continuous exposure variable.
SMOKING_EXPOSURE_UNITS = REGISTRY.register(
    'SMOKING_EXPOSURE_UNITS',
    Parameter(
        name='Normalised smoking exposure for a heavy smoker',
        value=1.0,
        unit='dimensionless',
        evidence_class=EvidenceClass.MODELING_ASSUMPTION,
        rationale=(
            'Smoking is modelled as a saturated binary exposure because the '
            'engine does not track cigarettes/day. Literature indicates '
            'near-maximal CYP1A2 induction at roughly 7-12 cigarettes/day, so '
            'a saturated term is a reasonable representation for heavy smokers '
            'but will overestimate induction in light smokers.'
        ),
        confidence=Confidence.MODERATE,
    ),
)

SMOKING_CYP1A2_EC50 = REGISTRY.register(
    'SMOKING_CYP1A2_EC50',
    Parameter(
        name='EC50 for the normalised smoking exposure term',
        value=0.05,
        unit='dimensionless',
        evidence_class=EvidenceClass.MODELING_ASSUMPTION,
        rationale=(
            'Chosen well below the normalised exposure of 1.0 so the Hill term '
            'is ~95% saturated, reproducing the measured steady-state induction '
            'ratio. Not a measured potency; only the saturated value is '
            'evidence-based.'
        ),
        confidence=Confidence.LOW,
    ),
)


def smoking_induction_term() -> tuple[float, float, float]:
    """Return (exposure, Emax, EC50) for the CYP1A2 smoking inducer.

    Replaces the previous hard-coded (1.0, 1.0, 1.0).
    """
    return (
        SMOKING_EXPOSURE_UNITS.value,
        SMOKING_CYP1A2_EMAX / (
            SMOKING_EXPOSURE_UNITS.value
            / (SMOKING_CYP1A2_EC50.value + SMOKING_EXPOSURE_UNITS.value)
        ),
        SMOKING_CYP1A2_EC50.value,
    )


# --------------------------------------------------------------------------
# F-22: clozapine Michaelis constant
#
# Found by the validation suite, not by reading the code. The seed value of
# 0.16 mg/L (0.49 uM) is roughly 125x below the published Km, which put the
# simulation at C/Km of 3.7-7.8 (saturated) instead of ~0.03 (linear). That
# inflated the predicted smoking-cessation effect from 1.38x to 2.08x.
#
# Because vmax is back-calculated as CL * Km (audit F-10), Km has no effect on
# clearance in the linear regime but silently controls where saturation begins.
# An arbitrary Km is therefore not harmless.
# --------------------------------------------------------------------------

EIERMANN_1997 = Citation(
    doi='10.1046/j.1365-2125.1997.t01-1-00605.x',
    pmid='9384460',
    title='The involvement of CYP1A2 and CYP3A4 in the metabolism of clozapine',
    first_author='Eiermann B',
    journal='Br J Clin Pharmacol',
    year=1997,
    verified=True,
)

OLESEN_LINNET_2001 = Citation(
    doi='10.1177/00912700122010717',
    pmid='11504269',
    title=('Contributions of five human cytochrome P450 isoforms to the '
           'N-demethylation of clozapine in vitro at low and high concentrations'),
    first_author='Olesen OV',
    journal='J Clin Pharmacol',
    year=2001,
    verified=True,
)

CLOZAPINE_MW_G_PER_MOL = 326.8

CLOZAPINE_CYP1A2_KM_MG_L = REGISTRY.register(
    'CLOZAPINE_CYP1A2_KM_MG_L',
    Parameter(
        name='Clozapine Michaelis constant, N-demethylation',
        value=round(61.0 * CLOZAPINE_MW_G_PER_MOL / 1000.0, 3),
        unit='mg/L',
        ci_low=round(40.0 * CLOZAPINE_MW_G_PER_MOL / 1000.0, 3),
        ci_high=round(82.0 * CLOZAPINE_MW_G_PER_MOL / 1000.0, 3),
        distribution='lognormal',
        evidence_class=EvidenceClass.LITERATURE_DERIVED,
        evidence_type=EvidenceType.IN_VITRO,
        citations=(EIERMANN_1997,),
        population='human liver microsomes, n=4',
        confidence=Confidence.MODERATE,
        notes=(
            'Reported as 61 +/- 21 uM for clozapine demethylation; converted at '
            'MW 326.8. Range is the reported standard deviation, not a 95% CI. '
            'Other studies report Km from 13 to 120 uM for clozapine metabolism, '
            'so this parameter is genuinely uncertain, but every published value '
            'places therapeutic clozapine concentrations in the linear regime.'
        ),
    ),
)

# --------------------------------------------------------------------------
# F-3 / F-4 / F-24: fluoxetine and norfluoxetine inhibition of CYP2D6
#
# Sager et al. 2014 characterised all four circulating species (both
# enantiomers of parent and metabolite) against CYP2D6, CYP2C19 and CYP3A4,
# and correlated in vitro parameters with observed in vivo AUC ratios.
#
# THE HEADLINE FINDING FOR NEUROTRACE: the paper reports time-dependent
# inactivation for CYP2C19 and CYP3A4 ONLY. CYP2D6 inhibition by fluoxetine
# and norfluoxetine is purely REVERSIBLE. The engine currently fabricates
# CYP2D6 mechanism-based inactivation for any inhibitor tagged "strong", which
# models a mechanism this interaction does not have. See AUDIT.md F-24.
# --------------------------------------------------------------------------

SAGER_2014 = Citation(
    doi='10.1038/clpt.2014.50',
    pmid='24569517',
    title=('Fluoxetine- and norfluoxetine-mediated complex drug-drug interactions: '
           'in vitro to in vivo correlation of effects on CYP2D6, CYP2C19, and CYP3A4'),
    first_author='Sager JE',
    journal='Clin Pharmacol Ther',
    year=2014,
    verified=True,
)

FLUOXETINE_MW_G_PER_MOL = 309.3
NORFLUOXETINE_MW_G_PER_MOL = 295.3

# Enantiomer-specific reversible Ki against CYP2D6, in uM, as printed.
SAGER_CYP2D6_KI_UM: dict[str, float] = {
    'R-fluoxetine': 0.86,
    'S-fluoxetine': 0.068,
    'R-norfluoxetine': 0.5,
    'S-norfluoxetine': 0.035,
}


def _racemic_effective_ki_um(ki_s: float, ki_r: float, frac_s: float = 0.5) -> float:
    """Composite Ki for a racemate modelled as one species.

    Competitive inhibition sums as C/Ki, so the racemate's effective constant is
    the fraction-weighted harmonic mean, not the arithmetic mean.
    """
    return 1.0 / (frac_s / ki_s + (1.0 - frac_s) / ki_r)


_NORFLUOX_KI_UM = _racemic_effective_ki_um(
    SAGER_CYP2D6_KI_UM['S-norfluoxetine'], SAGER_CYP2D6_KI_UM['R-norfluoxetine'])

NORFLUOXETINE_CYP2D6_KI_MG_L = REGISTRY.register(
    'NORFLUOXETINE_CYP2D6_KI_MG_L',
    Parameter(
        name='Norfluoxetine reversible Ki against CYP2D6 (racemic-effective)',
        value=round(_NORFLUOX_KI_UM * NORFLUOXETINE_MW_G_PER_MOL / 1000.0, 6),
        unit='mg/L',
        ci_low=round(SAGER_CYP2D6_KI_UM['S-norfluoxetine'] * NORFLUOXETINE_MW_G_PER_MOL / 1000.0, 6),
        ci_high=round(SAGER_CYP2D6_KI_UM['R-norfluoxetine'] * NORFLUOXETINE_MW_G_PER_MOL / 1000.0, 6),
        distribution='lognormal',
        evidence_class=EvidenceClass.LITERATURE_DERIVED,
        evidence_type=EvidenceType.IN_VITRO,
        citations=(SAGER_2014,),
        population='human recombinant CYP / liver microsomes, enantiomer-resolved',
        confidence=Confidence.HIGH,
        notes=(
            'Sager reports S-norfluoxetine 0.035 uM and R-norfluoxetine 0.5 uM. '
            'Fluoxetine is dosed as a racemate and NeuroTrace models one species '
            'per drug, so these are combined by fraction-weighted harmonic mean '
            'to 0.0654 uM (65.4 nM). The bounds are the two enantiomer values, '
            'which is a modelling range rather than a statistical CI. '
            'Enantiomer-resolved modelling, which Sager shows is what actually '
            'reproduces the in vivo data, would require splitting each species '
            'into two compartments.'
        ),
    ),
)

FLUOXETINE_CYP2D6_KI_MG_L = REGISTRY.register(
    'FLUOXETINE_CYP2D6_KI_MG_L',
    Parameter(
        name='Fluoxetine reversible Ki against CYP2D6 (racemic-effective)',
        value=round(_racemic_effective_ki_um(
            SAGER_CYP2D6_KI_UM['S-fluoxetine'],
            SAGER_CYP2D6_KI_UM['R-fluoxetine']) * FLUOXETINE_MW_G_PER_MOL / 1000.0, 6),
        unit='mg/L',
        ci_low=round(SAGER_CYP2D6_KI_UM['S-fluoxetine'] * FLUOXETINE_MW_G_PER_MOL / 1000.0, 6),
        ci_high=round(SAGER_CYP2D6_KI_UM['R-fluoxetine'] * FLUOXETINE_MW_G_PER_MOL / 1000.0, 6),
        distribution='lognormal',
        evidence_class=EvidenceClass.LITERATURE_DERIVED,
        evidence_type=EvidenceType.IN_VITRO,
        citations=(SAGER_2014,),
        population='human recombinant CYP / liver microsomes, enantiomer-resolved',
        confidence=Confidence.HIGH,
        notes='S-fluoxetine 0.068 uM, R-fluoxetine 0.86 uM; combined to 0.126 uM.',
    ),
)

# Observed in vivo AUC ratios after 2-week fluoxetine dosing. These are
# validation targets, not model inputs. Note the CYP3A4 probes came in slightly
# BELOW 1.0: time-dependent inhibition is offset by CYP3A4 induction, so a
# model that only inhibits will get the direction wrong.
SAGER_OBSERVED_AUC_RATIOS: dict[str, dict[str, float | str]] = {
    'dextromethorphan': {'enzyme': 'CYP2D6', 'ratio': 27.0, 'low': 5.8, 'high': 160.0},
    'omeprazole': {'enzyme': 'CYP2C19', 'ratio': 7.1, 'low': 4.4, 'high': 20.0},
    'midazolam': {'enzyme': 'CYP3A4', 'ratio': 0.80},
    'lovastatin': {'enzyme': 'CYP3A4', 'ratio': 0.94},
}

# Time-dependent inactivation, in uM and per hour, as printed. CYP2D6 is
# absent from this table in the source; that absence is the finding.
SAGER_TDI_PARAMS: dict[str, dict[str, float]] = {
    'CYP2C19': {
        'R-fluoxetine_KI_uM': 1.8, 'R-fluoxetine_kinact_per_h': 1.02,
        'S-fluoxetine_KI_uM': 55.0, 'S-fluoxetine_kinact_per_h': 3.3,
        'R-norfluoxetine_KI_uM': 15.0, 'R-norfluoxetine_kinact_per_h': 3.0,
        'S-norfluoxetine_KI_uM': 7.0, 'S-norfluoxetine_kinact_per_h': 3.5,
    },
    'CYP3A4': {
        'R-norfluoxetine_KI_uM': 7.7, 'R-norfluoxetine_kinact_per_h': 0.66,
        'S-fluoxetine_KI_uM': 21.0, 'S-fluoxetine_kinact_per_h': 0.564,
    },
}

def _racemic_tdi(enantiomers: list[tuple[float, float]]) -> tuple[float, float]:
    """Combine enantiomer TDI parameters for a racemate modelled as one species.

    Each enantiomer is present at half the total concentration, so:

      saturation limit   kinact_eff = sum(kinact_e)
      low-C efficiency   (kinact/KI)_eff = sum(kinact_e / (2 * KI_e))
      hence              KI_eff = kinact_eff / (kinact/KI)_eff

    Reproduces both asymptotes of the summed Michaelis-Menten-like rate. It is
    an approximation in between, and is documented as such.

    Args: list of (KI_uM, kinact_per_h) for each reported enantiomer.
    """
    kinact_eff = sum(k for _, k in enantiomers)
    efficiency = sum(k / (2.0 * ki) for ki, k in enantiomers)
    return kinact_eff / efficiency, kinact_eff


def documented_tdi(drug: str, enzyme: str) -> tuple[float, float] | None:
    """Return (KI in mg/L, kinact per hour) only where TDI is actually reported.

    Returns None when no source documents time-dependent inactivation for this
    drug/enzyme pair. Callers must NOT invent parameters in that case: absence
    of evidence for TDI is evidence the interaction is reversible, which is a
    different mechanism with different behaviour on rechallenge.
    """
    key = drug.strip().lower()
    table = _TDI_BY_DRUG.get(key)
    if table is None:
        return None
    entry = table.get(enzyme)
    if entry is None:
        return None
    ki_um, kinact = _racemic_tdi(entry['enantiomers'])
    return ki_um * entry['mw'] / 1000.0, kinact


_TDI_BY_DRUG: dict[str, dict[str, dict]] = {
    # Sager et al. 2014. CYP2D6 is deliberately absent: the paper reports
    # reversible inhibition only for that enzyme.
    'fluoxetine': {
        'CYP2C19': {'mw': FLUOXETINE_MW_G_PER_MOL,
                    'enantiomers': [(1.8, 1.02), (55.0, 3.3)]},
        'CYP3A4': {'mw': FLUOXETINE_MW_G_PER_MOL,
                   'enantiomers': [(21.0, 0.564)]},
    },
    'norfluoxetine': {
        'CYP2C19': {'mw': NORFLUOXETINE_MW_G_PER_MOL,
                    'enantiomers': [(15.0, 3.0), (7.0, 3.5)]},
        'CYP3A4': {'mw': NORFLUOXETINE_MW_G_PER_MOL,
                   'enantiomers': [(7.7, 0.66)]},
    },
}

CYP2D6_HAS_TIME_DEPENDENT_INHIBITION = False
"""Sager 2014 reports no TDI of CYP2D6 by fluoxetine or norfluoxetine.

Persistent CYP2D6 inhibition after fluoxetine is stopped is explained by
norfluoxetine's long half-life sustaining REVERSIBLE inhibition, not by enzyme
inactivation requiring resynthesis. Both mechanisms produce a similar-looking
curve, which is why the engine's fabricated MBI was not obviously wrong.
"""


# fm_CYP1A2 for clozapine remains UNSOURCED and is flagged, not fixed.
#
# Olesen & Linnet 2001 measured CYP1A2 at 30% of N-demethylation at a
# therapeutically relevant 5 uM (CYP2C19 24%, CYP3A4 22%, CYP2C9 12%,
# CYP2D6 6%). The model uses 0.70. Substituting 0.30 predicts only a 1.17x
# rise on cessation, well below the 1.34-1.76 observed range, whereas 0.70
# predicts 1.38x and matches.
#
# In other words the in vitro fraction and the clinical effect size disagree,
# and the authors themselves note CYP1A2 appears more important clinically than
# in vitro. This is left as an open conflict rather than resolved by picking
# whichever number makes the model agree.
CLOZAPINE_FM_CYP1A2 = REGISTRY.register(
    'CLOZAPINE_FM_CYP1A2',
    Parameter(
        name='Fraction of clozapine clearance via CYP1A2',
        value=0.70,
        unit='fraction',
        ci_low=0.30,
        ci_high=0.80,
        evidence_class=EvidenceClass.MODELING_ASSUMPTION,
        rationale=(
            'Carried over from seed data with no citation. Conflicts with '
            'Olesen & Linnet 2001, which measured 30% of N-demethylation via '
            'CYP1A2 at therapeutic concentrations. Retained at 0.70 because the '
            'clinical smoking-cessation effect size requires it, but this is an '
            'unresolved in vitro versus in vivo discrepancy and the single '
            'largest source of uncertainty in this scenario.'
        ),
        confidence=Confidence.LOW,
        citations=(),
        notes='Dominant sensitivity driver; see validation report.',
    ),
)
