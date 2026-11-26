"""One random stream per patient and per part of their record.

A stream is keyed by (seed, patient number, part). So patient 42's values do
not depend on how many patients are generated: a 200-patient CI run is an
exact sample of the 25,000-patient run. And adding a new part (conditions,
visits) leaves the parts generated before it unchanged.
"""

from enum import IntEnum

import numpy as np


class Part(IntEnum):
    # Never renumber: a part's number is part of its stream's key, so changing
    # it would change every patient's values for that part.
    IDENTITY = 0
    DEMOGRAPHICS = 1


def patient_rng(seed: int, patient_id: int, part: Part) -> np.random.Generator:
    """The random generator for one part of one patient's record."""
    # spawn_key gives an independent stream for each (patient, part) pair,
    # derived from the one seed in the config.
    return np.random.default_rng(
        np.random.SeedSequence(seed, spawn_key=(patient_id, part))
    )
