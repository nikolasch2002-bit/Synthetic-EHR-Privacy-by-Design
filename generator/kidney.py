"""Each patient's true kidney function (eGFR) over time, and the CKD-EPI equation.

Lab results are measurements of this true course: a creatinine is drawn
around the creatinine that matches the true eGFR, and the reported eGFR is
computed from that creatinine, as a lab does. So creatinine and eGFR always
agree, and CKD on the problem list agrees with eGFR below 60.
"""

import datetime as dt

from generator.conditions import ClinicalHistory, age_years
from generator.config import Config
from generator.patients import Patient
from generator.streams import Part, patient_rng

UMOL_PER_MG_DL = 88.4  # creatinine: µmol/L = mg/dL x 88.4
NO_CKD_FLOOR = 61.0  # without CKD on the problem list, eGFR stays at 60 or above
CKD_FLOOR = 5.0


def ckd_epi_2021(creatinine_umol: float, age: float, sex: str) -> float:
    """eGFR (mL/min/1.73 m²) from serum creatinine: the CKD-EPI 2021 equation, without race."""
    scr = creatinine_umol / UMOL_PER_MG_DL
    kappa, alpha = (0.7, -0.241) if sex == "F" else (0.9, -0.302)
    ratio = scr / kappa
    egfr = 142 * min(ratio, 1) ** alpha * max(ratio, 1) ** -1.200 * 0.9938**age
    return egfr * (1.012 if sex == "F" else 1.0)


def creatinine_for_egfr(egfr: float, age: float, sex: str) -> float:
    """The creatinine (µmol/L) at which CKD-EPI 2021 gives this eGFR: its inverse."""
    kappa, alpha = (0.7, -0.241) if sex == "F" else (0.9, -0.302)
    base = egfr / (142 * 0.9938**age * (1.012 if sex == "F" else 1.0))
    # Above kappa the equation uses the exponent -1.200, below it alpha.
    ratio = base ** (1 / -1.200)
    if ratio < 1:
        ratio = base ** (1 / alpha)
    return ratio * kappa * UMOL_PER_MG_DL


class KidneyCourse:
    """True eGFR on any day: straight lines, falling with age, faster with CKD."""

    def __init__(self, config: Config, patient: Patient, history: ClinicalHistory):
        model = config.lab_model
        rng = patient_rng(config.seed, patient.patient_id, Part.KIDNEY)
        self.start = config.history.start
        age = age_years(patient.birth_date, self.start)
        healthy = (
            model.egfr_at_age_30
            - model.egfr_drop_per_year_of_age * max(age - 30, 0)
            + rng.normal(0, model.egfr_sd)
        )
        self.healthy_at_start = max(healthy, NO_CKD_FLOOR + 1)
        self.healthy_slope = -model.egfr_drop_per_year_of_age
        self.ckd_slope = -rng.uniform(
            model.egfr_ckd_yearly_drop.min, model.egfr_ckd_yearly_drop.max
        )
        onsets = {r.condition: r.onset for r in history.conditions}
        self.ckd_onset = onsets.get("ckd")
        if self.ckd_onset is not None and self.ckd_onset < self.start:
            r = model.egfr_ckd_at_start
            self.ckd_at_anchor, self.anchor = rng.uniform(r.min, r.max), self.start
        elif self.ckd_onset is not None:
            r = model.egfr_ckd_at_onset
            self.ckd_at_anchor, self.anchor = rng.uniform(r.min, r.max), self.ckd_onset

    def egfr(self, day: dt.date) -> float:
        years = (day - self.start).days / 365.25
        if self.ckd_onset is None:
            return max(self.healthy_at_start + self.healthy_slope * years, NO_CKD_FLOOR)
        if day >= self.anchor:
            after = (day - self.anchor).days / 365.25
            return max(self.ckd_at_anchor + self.ckd_slope * after, CKD_FLOOR)
        # Before CKD is diagnosed: a straight line from the healthy value on the
        # start date down to the value at diagnosis. It crosses 60 shortly before
        # the diagnosis, as kidney function falls before anyone names it.
        share = (day - self.start).days / max((self.anchor - self.start).days, 1)
        return (
            self.healthy_at_start + (self.ckd_at_anchor - self.healthy_at_start) * share
        )

    def first_day_below(self, threshold: float, until: dt.date) -> dt.date | None:
        """The first day (checked weekly) the true eGFR is below `threshold`."""
        day = self.start
        while day <= until:
            if self.egfr(day) < threshold:
                return day
            day += dt.timedelta(days=7)
        return None
