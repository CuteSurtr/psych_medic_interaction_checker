"""Parameter provenance.

Every pharmacologic constant used by the model carries where it came from. The
point is that a reviewer can trace any number in a simulation back to a primary
source, or see immediately that it has none.

Two things are deliberately kept apart:

  evidence_class  what kind of thing the number is (measurement, regulatory
                  statement, or an assumption we made up)
  evidence_type   the study design behind it, ordered by the project's
                  evidence hierarchy

A value with no source cannot be constructed by accident. `assumption()`
requires a written rationale, and `Parameter(...)` refuses to be built with a
literature evidence_class and no citation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator

import numpy as np


class EvidenceClass(str, Enum):
    """What kind of number this is."""

    DIRECTLY_MEASURED = 'directly_measured'
    LITERATURE_DERIVED = 'literature_derived'
    REGULATORY = 'regulatory'
    ESTIMATED = 'estimated'
    INFERRED = 'inferred'
    MODELING_ASSUMPTION = 'modeling_assumption'
    EXPERIMENTAL = 'experimental'


class EvidenceType(str, Enum):
    """Study design. Ordered by the project's preferred evidence hierarchy."""

    FDA_LABEL = 'fda_label'
    FDA_GUIDANCE = 'fda_guidance'
    ICH_GUIDELINE = 'ich_guideline'
    CPIC_GUIDELINE = 'cpic_guideline'
    HUMAN_PK_STUDY = 'human_pk_study'
    CONTROLLED_TRIAL = 'controlled_trial'
    POPULATION_PK = 'population_pk'
    PBPK = 'pbpk'
    SYSTEMATIC_REVIEW = 'systematic_review'
    OBSERVATIONAL = 'observational'
    CASE_SERIES = 'case_series'
    CASE_REPORT = 'case_report'
    IN_VITRO = 'in_vitro'
    MECHANISTIC_INFERENCE = 'mechanistic_inference'
    NONE = 'none'


_HIERARCHY: list[EvidenceType] = [
    EvidenceType.FDA_LABEL,
    EvidenceType.FDA_GUIDANCE,
    EvidenceType.ICH_GUIDELINE,
    EvidenceType.CPIC_GUIDELINE,
    EvidenceType.HUMAN_PK_STUDY,
    EvidenceType.CONTROLLED_TRIAL,
    EvidenceType.POPULATION_PK,
    EvidenceType.PBPK,
    EvidenceType.SYSTEMATIC_REVIEW,
    EvidenceType.OBSERVATIONAL,
    EvidenceType.CASE_SERIES,
    EvidenceType.CASE_REPORT,
    EvidenceType.IN_VITRO,
    EvidenceType.MECHANISTIC_INFERENCE,
    EvidenceType.NONE,
]


def evidence_rank(t: EvidenceType) -> int:
    """Lower is stronger. Used to pick between conflicting sources."""
    return _HIERARCHY.index(t)


class Confidence(str, Enum):
    HIGH = 'high'
    MODERATE = 'moderate'
    LOW = 'low'
    UNKNOWN = 'unknown'


@dataclass(frozen=True)
class Citation:
    """A reference. `verified` means the DOI resolved and metadata matched.

    Set verified=False for anything not machine-checked. It is better to carry
    an unverified citation flagged as such than to imply a check that never ran.
    """

    doi: str | None = None
    pmid: str | None = None
    title: str = ''
    first_author: str = ''
    journal: str = ''
    year: int | None = None
    verified: bool = False
    # Reference databases such as PubChem, DrugBank or CredibleMeds are
    # authoritative but have no DOI. They are identified by an accession.
    source_db: str | None = None
    accession: str | None = None
    source_url: str | None = None

    def __post_init__(self) -> None:
        if not self.doi and not self.pmid and not (self.source_db and self.accession):
            raise ValueError(
                'Citation needs a DOI, a PMID, or a source_db plus accession'
            )

    @property
    def url(self) -> str | None:
        if self.doi:
            return f'https://doi.org/{self.doi}'
        if self.pmid:
            return f'https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/'
        if self.source_url:
            return self.source_url
        if self.source_db == 'PubChem' and self.accession:
            return f'https://pubchem.ncbi.nlm.nih.gov/compound/{self.accession}'
        return None

    def short(self) -> str:
        mark = '' if self.verified else ' [UNVERIFIED]'
        if self.source_db:
            return f'{self.source_db} {self.accession}{mark}'
        who = self.first_author or 'Unknown'
        when = self.year or '?'
        return f'{who} et al. {self.journal} {when}{mark}'


@dataclass(frozen=True)
class Parameter:
    """A pharmacologic value plus its provenance.

    `value` is the point estimate. When the literature reports a range, keep it
    in ci_low/ci_high rather than silently collapsing to a midpoint, and let
    Monte Carlo sample from it via `sample()`.
    """

    value: float
    unit: str
    evidence_class: EvidenceClass
    name: str = ''
    evidence_type: EvidenceType = EvidenceType.NONE
    citations: tuple[Citation, ...] = ()
    population: str = ''
    confidence: Confidence = Confidence.UNKNOWN
    ci_low: float | None = None
    ci_high: float | None = None
    distribution: str | None = None
    rationale: str = ''
    notes: str = ''

    _SOURCED_CLASSES = (
        EvidenceClass.DIRECTLY_MEASURED,
        EvidenceClass.LITERATURE_DERIVED,
        EvidenceClass.REGULATORY,
    )

    def __post_init__(self) -> None:
        if self.evidence_class in self._SOURCED_CLASSES and not self.citations:
            raise ValueError(
                f'Parameter {self.name!r} claims evidence_class='
                f'{self.evidence_class.value} but carries no citation. Use '
                f'assumption() if this value is not literature-derived.'
            )
        if self.evidence_class is EvidenceClass.MODELING_ASSUMPTION and not self.rationale:
            raise ValueError(
                f'Parameter {self.name!r} is a modeling assumption and needs a rationale.'
            )
        if self.ci_low is not None and self.ci_high is not None:
            if self.ci_low > self.ci_high:
                raise ValueError(f'Parameter {self.name!r}: ci_low exceeds ci_high')

    @property
    def is_sourced(self) -> bool:
        return bool(self.citations) and self.evidence_class in self._SOURCED_CLASSES

    @property
    def is_assumption(self) -> bool:
        return self.evidence_class is EvidenceClass.MODELING_ASSUMPTION

    @property
    def has_range(self) -> bool:
        return self.ci_low is not None and self.ci_high is not None

    def __float__(self) -> float:
        return float(self.value)

    def sample(self, rng: np.random.Generator) -> float:
        """Draw one value for Monte Carlo.

        Falls back to the point estimate when no range is recorded, so an
        unquantified parameter contributes no fake variability.
        """
        if not self.has_range:
            return float(self.value)
        lo, hi = float(self.ci_low), float(self.ci_high)
        if self.distribution == 'lognormal' and lo > 0 and hi > 0:
            # Treat the interval as a 95% CI on the log scale.
            mu = np.log(self.value)
            sigma = (np.log(hi) - np.log(lo)) / (2 * 1.959963985)
            return float(rng.lognormal(mu, max(sigma, 1e-12)))
        if self.distribution == 'uniform':
            return float(rng.uniform(lo, hi))
        # Default: normal truncated at the reported bounds.
        sigma = (hi - lo) / (2 * 1.959963985)
        draw = rng.normal(self.value, max(sigma, 1e-12))
        return float(np.clip(draw, lo, hi))

    def describe(self) -> str:
        bits = [f'{self.name or "parameter"} = {self.value} {self.unit}']
        if self.has_range:
            bits.append(f'(range {self.ci_low} to {self.ci_high})')
        bits.append(f'[{self.evidence_class.value}]')
        if self.is_assumption:
            bits.append(f'ASSUMPTION: {self.rationale}')
        elif self.citations:
            bits.append('; '.join(c.short() for c in self.citations))
        return ' '.join(bits)


def assumption(
    value: float,
    unit: str,
    rationale: str,
    *,
    name: str = '',
    ci_low: float | None = None,
    ci_high: float | None = None,
    notes: str = '',
) -> Parameter:
    """Build an explicitly-unsourced value.

    Use this instead of a bare float whenever a number is chosen for modelling
    convenience. The rationale is mandatory so the assumption is visible in the
    audit rather than buried in a constant.
    """
    return Parameter(
        value=value,
        unit=unit,
        evidence_class=EvidenceClass.MODELING_ASSUMPTION,
        name=name,
        evidence_type=EvidenceType.NONE,
        confidence=Confidence.LOW,
        ci_low=ci_low,
        ci_high=ci_high,
        rationale=rationale,
        notes=notes,
    )


class ParameterRegistry:
    """Collects parameters so the whole model can be audited at once."""

    def __init__(self) -> None:
        self._params: dict[str, Parameter] = {}

    def register(self, key: str, param: Parameter) -> Parameter:
        if key in self._params:
            raise ValueError(f'Parameter key {key!r} already registered')
        self._params[key] = param
        return param

    def get(self, key: str) -> Parameter:
        return self._params[key]

    def __iter__(self) -> Iterator[tuple[str, Parameter]]:
        return iter(sorted(self._params.items()))

    def __len__(self) -> int:
        return len(self._params)

    def assumptions(self) -> list[tuple[str, Parameter]]:
        return [(k, p) for k, p in self if p.is_assumption]

    def unsourced(self) -> list[tuple[str, Parameter]]:
        return [(k, p) for k, p in self if not p.is_sourced]

    def unverified_citations(self) -> list[tuple[str, Citation]]:
        out: list[tuple[str, Citation]] = []
        for key, param in self:
            for cite in param.citations:
                if not cite.verified:
                    out.append((key, cite))
        return out

    def audit_report(self) -> str:
        total = len(self._params)
        sourced = sum(1 for _, p in self if p.is_sourced)
        lines = [
            'Parameter provenance audit',
            f'  registered:  {total}',
            f'  sourced:     {sourced}',
            f'  assumptions: {len(self.assumptions())}',
            f'  unverified citations: {len(self.unverified_citations())}',
        ]
        if self.assumptions():
            lines.append('')
            lines.append('ASSUMPTIONS (not literature-derived):')
            for key, param in self.assumptions():
                lines.append(f'  {key}: {param.value} {param.unit} - {param.rationale}')
        return '\n'.join(lines)


REGISTRY = ParameterRegistry()
