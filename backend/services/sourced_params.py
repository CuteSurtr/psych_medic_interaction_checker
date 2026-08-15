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
