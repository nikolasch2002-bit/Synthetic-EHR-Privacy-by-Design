"""The config loads, and a mistake in it fails loudly instead of being ignored."""

import copy

import pytest
import yaml
from pydantic import ValidationError

from generator.config import DEFAULT_CONFIG, Config, load_config


@pytest.fixture(scope="module")
def raw() -> dict:
    with open(DEFAULT_CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_default_config_loads():
    config = load_config()
    assert config.population == 25_000
    assert config.locale == "nl_NL"
    assert str(config.history.start) == "2016-01-01"
    assert next(iter(config.conditions)) == "hypertension"


def set_value(path: tuple, value):
    """A change that sets the value at `path` (a list of keys and list positions)."""

    def change(config: dict) -> None:
        *parents, last = path
        for key in parents:
            config = config[key]
        config[last] = value

    return change


def rename_key(path: tuple, old: str, new: str):
    """A change that renames a key, as a typo would."""

    def change(config: dict) -> None:
        for key in path:
            config = config[key]
        config[new] = config.pop(old)

    return change


CKD = ("conditions", "ckd")

# Each case makes one mistake in a copy of the default config.
BROKEN = {
    "missing required key": rename_key((), "population", "populaton"),
    # A misspelt key that has a default is the dangerous typo: without the
    # unknown-key check it would be ignored and the default (1.0) used instead.
    "misspelt key with a default": rename_key(
        ("conditions", "type2_diabetes"), "prevalence_scale", "prevalence_scal"
    ),
    "age shares do not add up to 1": set_value(("age_mix", 0, "share"), 0.5),
    "age bands do not start at 18": set_value(("age_mix", 0, "age_from"), 16),
    "history ends before it starts": set_value(("history", "end"), "2015-12-31"),
    "prevalence above 1000": set_value((*CKD, "prevalence_per_1000", "male", 0), 1500),
    "lists of unequal length": set_value(
        (*CKD, "prevalence_per_1000", "female"), [5, 40]
    ),
    "raised by a later condition": set_value(
        ("conditions", "hypertension", "raised_by"), {"heart_failure": 2.0}
    ),
    "unknown department": set_value((*CKD, "department"), "urology"),
    "invalid ICD-10 code": set_value((*CKD, "icd10"), "N 18"),
    "chance of dying above 1": set_value(("mortality", "male", -1), 1.2),
    "hazard ratio for unknown condition": set_value(
        ("mortality", "hazard_ratios"), {"gout": 1.2}
    ),
}


@pytest.mark.parametrize("make_mistake", BROKEN.values(), ids=BROKEN.keys())
def test_broken_config_fails(raw, make_mistake):
    broken = copy.deepcopy(raw)
    make_mistake(broken)
    with pytest.raises(ValidationError):
        Config.model_validate(broken)
