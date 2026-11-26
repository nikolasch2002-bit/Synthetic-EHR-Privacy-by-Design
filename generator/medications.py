"""Medicines: who starts which, when they stop, and the orders that record it.

The rules are in docs/clinical-rules.md, section 9. A therapy is one patient
taking one medicine from a start day to a stop day. It is recorded as orders,
each covering `prescription_days`, repeated until the therapy stops. So a
"new start", as the prediction model defines it (an order with no order of
the same class in the 180 days before), happens exactly when a therapy
begins, and never at a repeat order.
"""

import datetime as dt
import math
from dataclasses import dataclass

import numpy as np

from generator.conditions import ClinicalHistory, random_day, years_after
from generator.config import Config
from generator.patients import Patient
from generator.streams import Part, patient_rng

ORDERS_PER_PATIENT_MAX = 10_000
RAAS_CLASSES = ("ace_inhibitor", "arb", "mra")
NEW_USER_DAYS = 180


@dataclass(frozen=True)
class Therapy:
    drug: str
    start: dt.date  # the first order
    stop: dt.date  # the last day covered


@dataclass(frozen=True)
class MedicationOrder:
    order_id: int
    patient_id: int
    drug: str
    atc: str
    dose: float
    unit: str
    frequency: str
    start: dt.date
    stop: dt.date


@dataclass(frozen=True)
class DrugStart:
    """A new start of a class: an order with none of that class in the 180 days before."""

    drug: str
    drug_class: str
    day: dt.date


class TherapyPlan:
    """One patient's therapies, with lookups the lab rules need."""

    def __init__(self, config: Config, therapies: list[Therapy]):
        self.config = config
        self.therapies = sorted(therapies, key=lambda t: (t.start, t.drug))

    def classes_on(self, day: dt.date) -> set[str]:
        return {
            self.config.drugs[t.drug].drug_class
            for t in self.therapies
            if t.start <= day <= t.stop
        }

    def stop_early(self, therapy: Therapy, day: dt.date) -> None:
        """End `therapy` on `day`, if that is before its planned stop."""
        self.therapies[self.therapies.index(therapy)] = Therapy(
            therapy.drug, therapy.start, min(therapy.stop, day)
        )

    def started_on(self, drug: str, day: dt.date) -> dt.date | None:
        """When the therapy with `drug` that covers `day` began, if any."""
        for t in self.therapies:
            if t.drug == drug and t.start <= day <= t.stop:
                return t.start
        return None


def time_to_stop(rng: np.random.Generator, yearly_chance: float) -> float:
    """Years until a therapy stops, with a constant yearly chance of stopping."""
    if yearly_chance <= 0:
        return math.inf
    return rng.exponential(1 / -math.log(1 - yearly_chance))


def draw_therapies(
    config: Config, patient: Patient, history: ClinicalHistory
) -> TherapyPlan:
    rules = config.medication_rules
    rng = patient_rng(config.seed, patient.patient_id, Part.MEDICATIONS)
    start = config.history.start
    last = min(history.death_date or config.history.end, config.history.end)
    therapies: list[Therapy] = []

    def classes_on(day: dt.date) -> set[str]:
        return TherapyPlan(config, therapies).classes_on(day)

    def add(drug: str, day: dt.date) -> None:
        # Not after death, and not a second therapy of a medicine the patient
        # is taking or is already set to start (decisions are not in time order).
        if day > last or any(t.drug == drug and t.stop >= day for t in therapies):
            return
        years = time_to_stop(rng, rules.yearly_stop_chance)
        stop = (
            last
            if years == math.inf
            else min(day + dt.timedelta(days=int(years * 365.25)), last)
        )
        therapies.append(Therapy(drug, day, max(stop, day)))

    # 1. Treatment decided when each condition is diagnosed, in onset order.
    for record in history.conditions:
        for choice in config.treatment.get(record.condition, []):
            if record.onset < start:
                # Already present: treatment began before the history, so the
                # first order seen is a repeat order in the first 90 days.
                day = start + dt.timedelta(
                    days=int(rng.integers(0, rules.prescription_days))
                )
            else:
                lag = rules.start_after_diagnosis_days
                day = record.onset + dt.timedelta(
                    days=int(rng.integers(lag.min, lag.max + 1))
                )
            if choice.after_years is not None:
                later = years_after(
                    record.onset,
                    int(
                        rng.integers(choice.after_years.min, choice.after_years.max + 1)
                    ),
                )
                day = max(later, day)
            draw = rng.random()
            if choice.unless and classes_on(day) & set(choice.unless):
                continue
            cumulative = 0.0
            for drug, chance in choice.drugs.items():
                cumulative += chance
                if draw < cumulative:
                    add(drug, day)
                    break

    # 2. ACE inhibitor stopped for cough and replaced by an ARB.
    for t in list(therapies):
        if config.drugs[t.drug].drug_class != "ace_inhibitor":
            continue
        switch = rng.random() < rules.ace_inhibitor_to_arb_switch
        day = t.start + dt.timedelta(days=int(rng.integers(30, 731)))
        if switch and day <= t.stop:
            therapies.remove(t)
            therapies.append(Therapy(t.drug, t.start, day - dt.timedelta(days=1)))
            add("losartan", day)

    # 3. Spironolactone added in heart failure, on top of an ACE inhibitor or ARB.
    onsets = {r.condition: r.onset for r in history.conditions}
    if "heart_failure" in onsets:
        year_start = max(onsets["heart_failure"], start)
        while year_start <= last:
            year_end = min(years_after(year_start, 1) - dt.timedelta(days=1), last)
            day = random_day(rng, year_start, year_end)
            on = classes_on(day)
            if (
                rng.random() < rules.spironolactone_add_on_per_year
                and on & {"ace_inhibitor", "arb"}
                and "mra" not in on
            ):
                add("spironolactone", day)
            year_start = years_after(year_start, 1)

    return TherapyPlan(config, therapies)


def orders_for(
    config: Config, patient: Patient, plan: TherapyPlan
) -> list[MedicationOrder]:
    """One order per prescription period, from each therapy's start to its stop."""
    days = config.medication_rules.prescription_days
    orders = []
    for t in plan.therapies:
        drug = config.drugs[t.drug]
        day = t.start
        while day <= t.stop:
            cover_until = min(day + dt.timedelta(days=days - 1), t.stop)
            order_id = patient.patient_id * ORDERS_PER_PATIENT_MAX + len(orders) + 1
            orders.append(
                MedicationOrder(
                    order_id,
                    patient.patient_id,
                    t.drug,
                    drug.atc,
                    drug.dose,
                    drug.unit,
                    drug.frequency,
                    day,
                    cover_until,
                )
            )
            day += dt.timedelta(days=days)
    if len(orders) >= ORDERS_PER_PATIENT_MAX:
        raise RuntimeError(f"patient {patient.patient_id} has too many orders")
    return orders


def new_starts(
    config: Config, orders: list[MedicationOrder], classes=RAAS_CLASSES
) -> list[DrugStart]:
    """Orders of a class with no order of that class in the 180 days before.

    Only from 180 days after the history starts: earlier, the 180 days before
    are not in the data, so a start cannot be told from a repeat order.
    """
    first_day = config.history.start + dt.timedelta(days=NEW_USER_DAYS)
    starts = []
    by_class: dict[str, list[MedicationOrder]] = {}
    for o in sorted(orders, key=lambda o: (o.start, o.drug)):
        by_class.setdefault(config.drugs[o.drug].drug_class, []).append(o)
    for drug_class, class_orders in by_class.items():
        if drug_class not in classes:
            continue
        previous = None
        for o in class_orders:
            if (
                previous is None or (o.start - previous).days > NEW_USER_DAYS
            ) and o.start >= first_day:
                starts.append(DrugStart(o.drug, drug_class, o.start))
            previous = o.start
    return sorted(starts, key=lambda s: (s.day, s.drug_class))
