from __future__ import annotations
from dataclasses import dataclass, field
FREQUENCY_INTERVAL_H: dict[str, float] = {'daily': 24.0, 'BID': 12.0, 'TID': 8.0, 'QHS': 24.0}

@dataclass
class DoseEvent:
    time_h: float
    dose_mg: float
    medication_index: int

@dataclass
class MedicationSchedule:
    medication_index: int
    generic_name: str
    bioavailability: float
    events: list[dict]

    def generate_dose_events(self, horizon_days: int=56) -> list[DoseEvent]:
        sorted_events = sorted(self.events, key=lambda e: e['day'])
        horizon_h = float(horizon_days) * 24.0
        dose_list: list[DoseEvent] = []
        active = False
        current_dose_mg = 0.0
        current_interval_h = 24.0
        segment_start_h = 0.0
        for i, evt in enumerate(sorted_events):
            evt_time_h = float(evt['day']) * 24.0
            if active and current_dose_mg > 0.0:
                t = segment_start_h
                while t < evt_time_h and t < horizon_h:
                    dose_list.append(DoseEvent(time_h=t, dose_mg=current_dose_mg, medication_index=self.medication_index))
                    t += current_interval_h
            evt_type = evt['event_type']
            if evt_type == 'start':
                active = True
                current_dose_mg = float(evt['dose_mg'])
                current_interval_h = FREQUENCY_INTERVAL_H.get(evt.get('frequency', 'daily'), 24.0)
                segment_start_h = evt_time_h
            elif evt_type == 'dose_change':
                current_dose_mg = float(evt['dose_mg'])
                current_interval_h = FREQUENCY_INTERVAL_H.get(evt.get('frequency', 'daily'), current_interval_h)
                segment_start_h = evt_time_h
            elif evt_type == 'stop':
                active = False
                segment_start_h = evt_time_h
        if active and current_dose_mg > 0.0:
            t = segment_start_h
            while t < horizon_h:
                dose_list.append(DoseEvent(time_h=t, dose_mg=current_dose_mg, medication_index=self.medication_index))
                t += current_interval_h
        return sorted(dose_list, key=lambda d: d.time_h)

def build_dose_timeline(schedules: list[MedicationSchedule], horizon_days: int=56) -> list[DoseEvent]:
    all_events: list[DoseEvent] = []
    for schedule in schedules:
        all_events.extend(schedule.generate_dose_events(horizon_days))
    return sorted(all_events, key=lambda d: (d.time_h, d.medication_index))

def get_active_dose_at_time(schedule: MedicationSchedule, time_h: float) -> float:
    sorted_events = sorted(schedule.events, key=lambda e: e['day'])
    current_dose = 0.0
    active = False
    for evt in sorted_events:
        evt_time_h = float(evt['day']) * 24.0
        if evt_time_h > time_h:
            break
        evt_type = evt['event_type']
        if evt_type == 'start':
            active = True
            current_dose = float(evt['dose_mg'])
        elif evt_type == 'dose_change':
            current_dose = float(evt['dose_mg'])
        elif evt_type == 'stop':
            active = False
            current_dose = 0.0
    return current_dose if active else 0.0
