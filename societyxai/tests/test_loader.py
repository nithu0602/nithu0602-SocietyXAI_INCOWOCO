"""Tests for ExperimentLoader: YAML loading, validation, and object assembly."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from societyxai.config import (
    BuiltExperiment,
    ExperimentConfig,
    ExperimentLoader,
    ExperimentLoaderError,
)
from societyxai.core.society import Society
from societyxai.models.ollama import OllamaBackend
from societyxai.tasks.base import Task

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

CONFIGS_DIR = Path(__file__).parent.parent / "configs"


@pytest.fixture
def example_yaml_path() -> Path:
    return CONFIGS_DIR / "example.yaml"


@pytest.fixture
def minimal_experiment_dict() -> dict:
    """Minimal valid experiment section as a Python dict."""
    return {
        "run_id": "run-test-001",
        "task_id": "task-test-001",
        "seed": 7,
        "model_id": "llama3",
        "provider": "ollama",
        "temperature": 0.0,
        "max_tokens": 64,
        "system_prompt": "You are a test agent.",
        "number_of_agents": 2,
        "number_of_rounds": 1,
        "topology": {"kind": "complete"},
        "speaker_order": {"order": ["a0", "a1"], "deterministic": True},
        "visibility": {"previous_messages": True, "confidence": False, "majority_position": False},
        "intervention": {"type": "none", "target_id": "a0"},
        "parser_version": "1.0",
        "stopping_rule": "max_rounds",
    }


@pytest.fixture
def minimal_task_dict() -> dict:
    return {
        "task_id": "task-test-001",
        "question": "Is the proposal sound?",
        "ground_truth": "yes",
    }


# ---------------------------------------------------------------------------
# from_yaml: file loading and schema validation
# ---------------------------------------------------------------------------


def test_from_yaml_loads_example_file(example_yaml_path: Path) -> None:
    config, task_data = ExperimentLoader.from_yaml(example_yaml_path)
    assert isinstance(config, ExperimentConfig)
    assert config.run_id == "run-example-001"
    assert config.provider == "ollama"
    assert config.number_of_agents == 3
    assert config.number_of_rounds == 2


def test_from_yaml_returns_task_dict_with_required_fields(example_yaml_path: Path) -> None:
    _, task_data = ExperimentLoader.from_yaml(example_yaml_path)
    assert "question" in task_data
    assert "ground_truth" in task_data
    assert task_data["ground_truth"] == "approve"


def test_from_yaml_task_dict_contains_evidence_list(example_yaml_path: Path) -> None:
    _, task_data = ExperimentLoader.from_yaml(example_yaml_path)
    assert "evidence" in task_data
    assert len(task_data["evidence"]) == 2
    assert task_data["evidence"][0]["evidence_id"] == "e1"


def test_from_yaml_derives_system_prompt_hash(example_yaml_path: Path) -> None:
    config, _ = ExperimentLoader.from_yaml(example_yaml_path)
    assert config.system_prompt_hash is not None
    assert len(config.system_prompt_hash) == 64  # SHA-256 hex digest


def test_from_yaml_raises_for_missing_file() -> None:
    with pytest.raises(ExperimentLoaderError, match="not found"):
        ExperimentLoader.from_yaml("configs/does_not_exist.yaml")


def test_from_yaml_raises_for_missing_experiment_section(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("task:\n  task_id: t1\n  question: q\n  ground_truth: g\n")
    with pytest.raises(ExperimentLoaderError, match="experiment"):
        ExperimentLoader.from_yaml(bad)


def test_from_yaml_raises_for_missing_task_section(
    tmp_path: Path,
    minimal_experiment_dict: dict,
) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.dump({"experiment": minimal_experiment_dict}))
    with pytest.raises(ExperimentLoaderError, match="task"):
        ExperimentLoader.from_yaml(bad)


def test_from_yaml_raises_for_invalid_yaml(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("experiment: {unclosed: [")
    with pytest.raises(ExperimentLoaderError, match="YAML"):
        ExperimentLoader.from_yaml(bad)


def test_from_yaml_raises_for_non_mapping_top_level(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("- item1\n- item2\n")
    with pytest.raises(ExperimentLoaderError, match="mapping"):
        ExperimentLoader.from_yaml(bad)


def test_from_yaml_raises_for_invalid_experiment_values(
    tmp_path: Path,
    minimal_experiment_dict: dict,
    minimal_task_dict: dict,
) -> None:
    bad_experiment = dict(minimal_experiment_dict)
    bad_experiment["temperature"] = -1.0
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.dump({"experiment": bad_experiment, "task": minimal_task_dict}))
    with pytest.raises(ExperimentLoaderError, match="Invalid experiment"):
        ExperimentLoader.from_yaml(bad)


def test_from_yaml_raises_when_speaker_order_count_mismatches_agents(
    tmp_path: Path,
    minimal_experiment_dict: dict,
    minimal_task_dict: dict,
) -> None:
    bad_experiment = dict(minimal_experiment_dict)
    bad_experiment["speaker_order"] = {"order": ["a0"], "deterministic": True}
    # number_of_agents is 2 but order has 1 — should fail ExperimentConfig validation
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.dump({"experiment": bad_experiment, "task": minimal_task_dict}))
    with pytest.raises(ExperimentLoaderError, match="Invalid experiment"):
        ExperimentLoader.from_yaml(bad)


# ---------------------------------------------------------------------------
# build: runtime object assembly
# ---------------------------------------------------------------------------


def test_build_returns_built_experiment(
    minimal_experiment_dict: dict,
    minimal_task_dict: dict,
) -> None:
    config = ExperimentConfig(**minimal_experiment_dict)
    experiment = ExperimentLoader.build(config, minimal_task_dict)
    assert isinstance(experiment, BuiltExperiment)


def test_build_produces_society_with_correct_agent_count(
    minimal_experiment_dict: dict,
    minimal_task_dict: dict,
) -> None:
    config = ExperimentConfig(**minimal_experiment_dict)
    experiment = ExperimentLoader.build(config, minimal_task_dict)
    assert isinstance(experiment.society, Society)
    assert len(experiment.society.agents) == config.number_of_agents


def test_build_agents_inherit_model_id_and_system_prompt(
    minimal_experiment_dict: dict,
    minimal_task_dict: dict,
) -> None:
    config = ExperimentConfig(**minimal_experiment_dict)
    experiment = ExperimentLoader.build(config, minimal_task_dict)
    for agent in experiment.society.agents:
        assert agent.model_id == config.model_id
        assert agent.system_prompt == config.system_prompt


def test_build_agent_ids_match_speaker_order(
    minimal_experiment_dict: dict,
    minimal_task_dict: dict,
) -> None:
    config = ExperimentConfig(**minimal_experiment_dict)
    experiment = ExperimentLoader.build(config, minimal_task_dict)
    agent_ids = [a.agent_id for a in experiment.society.agents]
    assert agent_ids == config.speaker_order.order


def test_build_society_topology_matches_config(
    minimal_experiment_dict: dict,
    minimal_task_dict: dict,
) -> None:
    config = ExperimentConfig(**minimal_experiment_dict)
    experiment = ExperimentLoader.build(config, minimal_task_dict)
    assert experiment.society.topology.kind == config.topology.kind


def test_build_society_number_of_rounds_matches_config(
    minimal_experiment_dict: dict,
    minimal_task_dict: dict,
) -> None:
    config = ExperimentConfig(**minimal_experiment_dict)
    experiment = ExperimentLoader.build(config, minimal_task_dict)
    assert experiment.society.number_of_rounds == config.number_of_rounds


def test_build_society_visibility_matches_config(
    minimal_experiment_dict: dict,
    minimal_task_dict: dict,
) -> None:
    config = ExperimentConfig(**minimal_experiment_dict)
    experiment = ExperimentLoader.build(config, minimal_task_dict)
    assert experiment.society.visibility.previous_messages == config.visibility.previous_messages
    assert experiment.society.visibility.confidence == config.visibility.confidence
    assert experiment.society.visibility.majority_position == config.visibility.majority_position


def test_build_produces_task_with_correct_fields(
    minimal_experiment_dict: dict,
    minimal_task_dict: dict,
) -> None:
    config = ExperimentConfig(**minimal_experiment_dict)
    experiment = ExperimentLoader.build(config, minimal_task_dict)
    assert isinstance(experiment.task, Task)
    assert experiment.task.task_id == minimal_task_dict["task_id"]
    assert experiment.task.question == minimal_task_dict["question"]
    assert experiment.task.ground_truth == minimal_task_dict["ground_truth"]


def test_build_task_with_evidence_items(
    minimal_experiment_dict: dict,
    minimal_task_dict: dict,
) -> None:
    task_data = dict(minimal_task_dict)
    task_data["evidence"] = [
        {"evidence_id": "ev-1", "content": "Supporting fact A."},
        {"evidence_id": "ev-2", "content": "Supporting fact B.", "source": "report-1"},
    ]
    config = ExperimentConfig(**minimal_experiment_dict)
    experiment = ExperimentLoader.build(config, task_data)
    assert len(experiment.task.evidence) == 2
    assert experiment.task.evidence[0].evidence_id == "ev-1"
    assert experiment.task.evidence[1].source == "report-1"


def test_build_produces_ollama_backend_for_ollama_provider(
    minimal_experiment_dict: dict,
    minimal_task_dict: dict,
) -> None:
    config = ExperimentConfig(**minimal_experiment_dict)
    experiment = ExperimentLoader.build(config, minimal_task_dict)
    assert isinstance(experiment.backend, OllamaBackend)
    assert experiment.backend.model_id == config.model_id
    assert experiment.backend.provider == "ollama"


def test_build_backend_defaults_match_config(
    minimal_experiment_dict: dict,
    minimal_task_dict: dict,
) -> None:
    config = ExperimentConfig(**minimal_experiment_dict)
    experiment = ExperimentLoader.build(config, minimal_task_dict)
    backend: OllamaBackend = experiment.backend  # type: ignore[assignment]
    assert backend.default_temperature == config.temperature
    assert backend.default_max_tokens == config.max_tokens
    assert backend.default_seed == config.seed


def test_build_raises_for_unsupported_provider(
    minimal_experiment_dict: dict,
    minimal_task_dict: dict,
) -> None:
    bad = dict(minimal_experiment_dict)
    bad["provider"] = "not-a-real-provider"
    config = ExperimentConfig(**bad)
    with pytest.raises(ExperimentLoaderError, match="Unsupported provider"):
        ExperimentLoader.build(config, minimal_task_dict)


def test_build_raises_for_invalid_task_fields(
    minimal_experiment_dict: dict,
) -> None:
    config = ExperimentConfig(**minimal_experiment_dict)
    bad_task = {"task_id": "t1", "question": "q"}  # missing ground_truth
    with pytest.raises(ExperimentLoaderError, match="Invalid task"):
        ExperimentLoader.build(config, bad_task)


# ---------------------------------------------------------------------------
# load: convenience end-to-end path
# ---------------------------------------------------------------------------


def test_load_convenience_method_returns_built_experiment(example_yaml_path: Path) -> None:
    experiment = ExperimentLoader.load(example_yaml_path)
    assert isinstance(experiment, BuiltExperiment)
    assert experiment.config.run_id == "run-example-001"
    assert isinstance(experiment.society, Society)
    assert isinstance(experiment.task, Task)
    assert isinstance(experiment.backend, OllamaBackend)


def test_load_experiment_config_is_preserved_on_built_experiment(
    example_yaml_path: Path,
) -> None:
    experiment = ExperimentLoader.load(example_yaml_path)
    assert experiment.config.number_of_rounds == 2
    assert experiment.config.topology.kind == "ring"
    assert experiment.config.visibility.previous_messages is True
    assert experiment.config.intervention.type == "none"


def test_load_task_evidence_is_populated_from_yaml(example_yaml_path: Path) -> None:
    experiment = ExperimentLoader.load(example_yaml_path)
    assert len(experiment.task.evidence) == 2
    ids = [e.evidence_id for e in experiment.task.evidence]
    assert "e1" in ids
    assert "e2" in ids


def test_build_does_not_mutate_caller_task_dict(
    minimal_experiment_dict: dict,
    minimal_task_dict: dict,
) -> None:
    """build() must not modify the caller's task_data dict."""
    task_data = dict(minimal_task_dict)
    task_data["evidence"] = [{"evidence_id": "ev-1", "content": "Fact."}]
    original_evidence = list(task_data["evidence"])
    config = ExperimentConfig(**minimal_experiment_dict)
    ExperimentLoader.build(config, task_data)
    # The original dict must still have its evidence key intact.
    assert task_data["evidence"] == original_evidence
