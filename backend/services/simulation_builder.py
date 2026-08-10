"""Build a SimulationConfig from plain dose events.

Both the simulation router and the advanced-analysis router need to turn a set
of dose events plus patient covariates into a `SimulationConfig`. They used to
carry near-identical copies of this logic; it lives here once instead.

Taking plain dicts rather than ORM rows is what lets the API run without a
writable database: the caller may have loaded the events from a persisted
`Simulation`, or may have received them inline in the request body. Only
medications and CYP450 profiles are read here, and those are static reference
data.
"""

from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy.orm import Session


def build_config_from_dose_events(
    db: Session,
    dose_events: Iterable[dict[str, Any]],
    *,
    horizon_days: int | None = 56,
    cyp2d6_phenotype: str | None = "normal",
    cyp2c19_phenotype: str | None = "normal",
    smoking: bool = False,
    patient_weight_kg: float | None = 70.0,
):
    """Assemble a SimulationConfig, or raise ValueError if the input is unusable.

    Each dose event needs `medication_id`, `event_type`, `event_day`,
    `dose_mg` and `frequency`. Callers translate ValueError into whatever HTTP
    status suits them.
    """
    from models import Medication
    from services.dose_scheduler import MedicationSchedule
    from services.pk_simulator import SimulationConfig, build_drug_configs_from_db

    events = list(dose_events)
    if not events:
        raise ValueError("no dose schedules provided")

    med_ids = list({int(e["medication_id"]) for e in events})
    meds = {m.id: m for m in db.query(Medication).filter(Medication.id.in_(med_ids)).all()}
    missing = sorted(set(med_ids) - set(meds))
    if missing:
        raise ValueError(f"unknown medication ids: {missing}")

    drug_configs = build_drug_configs_from_db(db, med_ids)

    events_by_med: dict[int, list[dict]] = {}
    for e in sorted(events, key=lambda x: int(x["event_day"])):
        events_by_med.setdefault(int(e["medication_id"]), []).append(
            {
                "event_type": e["event_type"],
                "day": int(e["event_day"]),
                "dose_mg": float(e["dose_mg"]),
                "frequency": e.get("frequency", "daily"),
            }
        )

    # Drug configs are keyed by generic name; map medication id onto the index
    # the simulator uses.
    mid_to_idx: dict[int, int] = {}
    for dc in drug_configs:
        for mid, m in meds.items():
            if m.generic_name == dc.generic_name:
                mid_to_idx[mid] = dc.index

    schedules: list[MedicationSchedule] = []
    for mid, evts in events_by_med.items():
        idx = mid_to_idx.get(mid)
        if idx is None:
            continue
        m = meds[mid]
        schedules.append(
            MedicationSchedule(
                medication_index=idx,
                generic_name=m.generic_name,
                bioavailability=float(m.bioavailability or 1.0),
                events=evts,
            )
        )
    schedules.sort(key=lambda s: s.medication_index)

    return SimulationConfig(
        drugs=drug_configs,
        schedules=schedules,
        horizon_days=horizon_days or 56,
        cyp2d6_phenotype=cyp2d6_phenotype or "normal",
        cyp2c19_phenotype=cyp2c19_phenotype or "normal",
        smoking=bool(smoking),
        patient_weight_kg=float(patient_weight_kg or 70),
    )


def serialize_result(result) -> dict[str, Any]:
    """JSON-ready view of a SimulationResult."""
    return {
        "time_hours": result.time_hours.tolist(),
        "concentrations": {k: v.tolist() for k, v in result.concentrations.items()},
        "metabolite_concentrations": {
            k: v.tolist() for k, v in result.metabolite_concentrations.items()
        },
        "dose_events": result.dose_events,
        "enzyme_activity": {k: v.tolist() for k, v in result.enzyme_activity.items()},
        "steady_state_info": result.steady_state_info,
    }
