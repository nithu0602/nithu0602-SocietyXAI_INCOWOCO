import societyxai
from societyxai import core, models, interventions, tasks, traces, config, utils


def test_package_imports() -> None:
    assert societyxai.__version__ == "0.1.0"
    assert core.__name__.endswith("core")
    assert models.__name__.endswith("models")
    assert interventions.__name__.endswith("interventions")
    assert tasks.__name__.endswith("tasks")
    assert traces.__name__.endswith("traces")
    assert config.__name__.endswith("config")
    assert utils.__name__.endswith("utils")
