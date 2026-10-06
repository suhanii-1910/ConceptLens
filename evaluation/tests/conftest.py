import json
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/"evaluation"),str(ROOT/"backend")]

from conceptlens_eval.dataset import load_manifest
from conceptlens_eval.simulation import Config, load_bank

@pytest.fixture
def manifest(): return load_manifest(ROOT/"evaluation/datasets/grounding.json")

@pytest.fixture
def config():
    data=json.loads((ROOT/"evaluation/configuration/simulation.json").read_text())
    data.update(seeds=[7,19],learners_per_profile_seed=1,sessions=2,bootstrap_samples=100)
    return Config.model_validate(data)

@pytest.fixture
def bank(): return load_bank(ROOT/"evaluation/datasets/items.json",4)
