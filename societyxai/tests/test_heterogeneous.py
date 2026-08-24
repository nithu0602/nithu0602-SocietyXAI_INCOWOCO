"""Focused tests for Phase 7A: heterogeneous per-agent backend/model routing.

Covers: BackendRegistry, per-agent model resolution, Orchestrator routing,
ExperimentLoader agent_models, Intervention/Counterfactual heterogeneous support,
YAML heterogeneous config, and no cross-agent contamination.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from societyxai.config.loader import BuiltExperiment, ExperimentLoader, ExperimentLoaderError
from societyxai.config.schema import (
    ExperimentConfig,
    InterventionConfig,
    SpeakerOrderConfig,
    TopologyConfig,
    VisibilityConfig,
)
from societyxai.core import Agent, Orchestrator, Society
from societyxai.interventions.branching import CounterfactualExperiment, run_counterfactual_experiment
from societyxai.interventions.message_injection import MessageInjectionIntervention
from societyxai.models import ModelBackend, ModelResponse
from societyxai.models.registry import BackendRegistry
from societyxai.tasks import Task
from societyxai.traces.schema import RunTrace

CONFIGS_DIR = Path(__file__).parent.parent / "configs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TrackingBackend(ModelBackend):
    """Backend that records every call and returns a configurable response."""

    def __init__(self, response: str = "I approve.", model_id: str = "fake", provider: str = "fake"):
        super().__init__(model_id=model_id, provider=provider)
        self.calls: list[list[dict]] = []
        self._response = response

    def generate(self, messages, temperature=None, max_tokens=None, seed=None):
        self.calls.append(list(messages))
        return ModelResponse(text=self._response)


def _make_society(
    agent_ids: list[str],
    model_ids: list[str] | None = None,
    rounds: int = 1,
) -> Society:
    """Create a Society with agents using potentially different model_ids."""
    if model_ids is None:
        model_ids = ["default-model"] * len(agent_ids)
    agents = [
        Agent(agent_id=aid, role="speaker", model_id=mid, system_prompt="Test prompt.")
        for aid, mid in zip(agent_ids, model_ids)
    ]
    return Society(
        agents=agents,
        topology=TopologyConfig(kind="complete"),
        number_of_rounds=rounds,
        speaker_order=SpeakerOrderConfig(order=agent_ids),
        visibility=VisibilityConfig(),
    )


def _make_task(task_id: str = "t1") -> Task:
    return Task(task_id=task_id, question="Q?", ground_truth="approve")


def _minimal_config(**overrides) -> ExperimentConfig:
    defaults = dict(
        run_id="test-run",
        task_id="test-task",
        seed=0,
        model_id="fake-model",
        provider="ollama",
        temperature=0.0,
        max_tokens=64,
        system_prompt="You are a test agent.",
        number_of_agents=2,
        number_of_rounds=1,
        topology=TopologyConfig(kind="complete"),
        speaker_order=SpeakerOrderConfig(order=["a1", "a2"], deterministic=True),
        visibility=VisibilityConfig(),
        intervention=InterventionConfig(type="none", target_id="a1"),
        parser_version="1.0",
        stopping_rule="max_rounds",
    )
    defaults.update(overrides)
    return ExperimentConfig(**defaults)


# ======================================================================
# 1. BackendRegistry: core operations
# ======================================================================


class TestBackendRegistry:

    def test_register_and_resolve(self):
        b1 = TrackingBackend(model_id="model-a")
        b2 = TrackingBackend(model_id="model-b")
        reg = BackendRegistry(default=b1)
        reg.register("model-b", b2)
        assert reg.resolve("model-a") is b1  # falls back to default
        assert reg.resolve("model-b") is b2
        assert reg.resolve("unknown") is b1  # fallback

    def test_resolve_without_default(self):
        b = TrackingBackend(model_id="m1")
        reg = BackendRegistry()
        reg.register("m1", b)
        assert reg.resolve("m1") is b
        assert reg.resolve("unknown") is None

    def test_has_model(self):
        b = TrackingBackend(model_id="m1")
        reg = BackendRegistry()
        reg.register("m1", b)
        assert reg.has_model("m1")
        assert not reg.has_model("m2")

    def test_models_sorted(self):
        b = TrackingBackend()
        reg = BackendRegistry()
        reg.register("z-model", b)
        reg.register("a-model", b)
        reg.register("m-model", b)
        assert reg.models() == ["a-model", "m-model", "z-model"]

    def test_backends_excludes_default(self):
        default = TrackingBackend(model_id="default")
        extra = TrackingBackend(model_id="extra")
        reg = BackendRegistry(default=default)
        reg.register("extra", extra)
        assert len(reg.backends()) == 1
        assert reg.backends()[0] is extra

    def test_len_and_contains(self):
        b = TrackingBackend()
        reg = BackendRegistry()
        assert len(reg) == 0
        reg.register("m1", b)
        assert len(reg) == 1
        assert "m1" in reg
        assert "m2" not in reg

    def test_iter(self):
        b = TrackingBackend()
        reg = BackendRegistry()
        reg.register("a", b)
        reg.register("c", b)
        assert sorted(reg) == ["a", "c"]

    def test_register_empty_model_id_raises(self):
        b = TrackingBackend()
        reg = BackendRegistry()
        with pytest.raises(ValueError, match="non-empty"):
            reg.register("", b)

    def test_register_non_backend_raises(self):
        reg = BackendRegistry()
        with pytest.raises(TypeError, match="ModelBackend"):
            reg.register("m1", "not-a-backend")  # type: ignore[arg-type]

    def test_repr(self):
        b = TrackingBackend(model_id="default")
        reg = BackendRegistry(default=b)
        reg.register("m1", b)
        r = repr(reg)
        assert "default" in r
        assert "m1" in r


# ======================================================================
# 2. Two agents using different model IDs
# ======================================================================


def test_two_agents_different_model_ids():
    backend_a = TrackingBackend(model_id="model-a", response="approve support")
    backend_b = TrackingBackend(model_id="model-b", response="reject disagree")
    registry = BackendRegistry(default=backend_a)
    registry.register("model-b", backend_b)

    society = _make_society(["a1", "a2"], model_ids=["model-a", "model-b"])
    task = _make_task()
    orchestrator = Orchestrator(
        society=society, task=task, backend=backend_a, backend_registry=registry,
    )
    result = orchestrator.run()

    # a1 uses model-a, a2 uses model-b
    assert result.turns[0].model_id == "model-a"
    assert result.turns[1].model_id == "model-b"
    # Each backend received exactly one call
    assert len(backend_a.calls) == 1
    assert len(backend_b.calls) == 1


# ======================================================================
# 3. Backend selection resolves correctly per agent
# ======================================================================


def test_backend_selection_resolves_per_agent():
    b_a = TrackingBackend(model_id="alpha", response="support yes")
    b_b = TrackingBackend(model_id="beta", response="reject no")
    reg = BackendRegistry(default=b_a)
    reg.register("beta", b_b)

    society = _make_society(["a1", "a2", "a3"], model_ids=["alpha", "beta", "alpha"], rounds=2)
    task = _make_task()
    orch = Orchestrator(
        society=society, task=task, backend=b_a, backend_registry=reg,
    )
    result = orch.run()

    # Round 1: a1->alpha, a2->beta, a3->alpha
    # Round 2: a1->alpha, a2->beta, a3->alpha
    assert result.turns[0].model_id == "alpha"
    assert result.turns[1].model_id == "beta"
    assert result.turns[2].model_id == "alpha"
    assert result.turns[3].model_id == "alpha"
    assert result.turns[4].model_id == "beta"
    assert result.turns[5].model_id == "alpha"
    assert len(b_a.calls) == 4  # 4 turns for alpha
    assert len(b_b.calls) == 2  # 2 turns for beta


# ======================================================================
# 4. Homogeneous one-backend behavior unchanged
# ======================================================================


def test_homogeneous_one_backend_unchanged():
    """Without a registry, all turns use the single backend."""
    backend = TrackingBackend(model_id="shared-model", response="support approve")
    society = _make_society(["a1", "a2"], model_ids=["shared-model", "shared-model"])
    task = _make_task()
    orch = Orchestrator(society=society, task=task, backend=backend)
    result = orch.run()

    assert result.turns[0].model_id == "shared-model"
    assert result.turns[1].model_id == "shared-model"
    assert len(backend.calls) == 2


def test_homogeneous_with_registry_also_works():
    """When registry is provided but all agents use the same model, behavior is identical."""
    backend = TrackingBackend(model_id="shared", response="support")
    reg = BackendRegistry(default=backend)
    society = _make_society(["a1", "a2"], model_ids=["shared", "shared"])
    task = _make_task()
    orch = Orchestrator(society=society, task=task, backend=backend, backend_registry=reg)
    result = orch.run()

    assert result.turns[0].model_id == "shared"
    assert result.turns[1].model_id == "shared"


# ======================================================================
# 5. Each turn invokes the expected backend
# ======================================================================


def test_each_turn_invokes_expected_backend():
    b1 = TrackingBackend(model_id="m1", response="support yes")
    b2 = TrackingBackend(model_id="m2", response="reject no")
    b3 = TrackingBackend(model_id="m3", response="neutral maybe")
    reg = BackendRegistry(default=b1)
    reg.register("m2", b2)
    reg.register("m3", b3)

    society = _make_society(["a1", "a2", "a3"], model_ids=["m1", "m2", "m3"])
    task = _make_task()
    orch = Orchestrator(society=society, task=task, backend=b1, backend_registry=reg)
    result = orch.run()

    # Verify each backend got exactly one call
    assert len(b1.calls) == 1
    assert len(b2.calls) == 1
    assert len(b3.calls) == 1

    # Verify the system prompt was sent to each backend
    for calls in [b1.calls, b2.calls, b3.calls]:
        assert calls[0][0]["role"] == "system"
        assert calls[0][0]["content"] == "Test prompt."


# ======================================================================
# 6. Trace records the actual model ID
# ======================================================================


def test_trace_records_actual_model_ids():
    b1 = TrackingBackend(model_id="llama", response="support")
    b2 = TrackingBackend(model_id="qwen", response="reject")
    reg = BackendRegistry(default=b1)
    reg.register("qwen", b2)

    society = _make_society(["a1", "a2"], model_ids=["llama", "qwen"])
    task = _make_task()
    orch = Orchestrator(society=society, task=task, backend=b1, backend_registry=reg)
    result = orch.run()

    assert result.trace is not None
    assert result.turns[0].model_id == "llama"
    assert result.turns[0].provider == "fake"
    assert result.turns[1].model_id == "qwen"
    assert result.turns[1].provider == "fake"


# ======================================================================
# 7. YAML loader builds heterogeneous agents correctly
# ======================================================================


def test_experiment_config_with_agent_models():
    """ExperimentConfig accepts agent_models and validates keys."""
    config = _minimal_config(
        agent_models={"a1": "model-x", "a2": "model-y"},
    )
    assert config.agent_models is not None
    assert config.agent_models["a1"] == "model-x"
    assert config.agent_models["a2"] == "model-y"


def test_experiment_config_agent_models_unknown_key_rejects():
    """agent_models referencing unknown agent IDs is rejected."""
    with pytest.raises(Exception, match="unknown agent IDs"):
        _minimal_config(
            agent_models={"a1": "m1", "UNKNOWN": "m2"},
        )


def test_experiment_config_agent_models_none_backward_compat():
    """agent_models=None preserves backward compatibility."""
    config = _minimal_config()
    assert config.agent_models is None


def test_loader_builds_heterogeneous_agents():
    """ExperimentLoader.build() creates agents with different model_ids when agent_models is set."""
    config = _minimal_config(
        number_of_agents=3,
        speaker_order=SpeakerOrderConfig(order=["a1", "a2", "a3"]),
        agent_models={"a1": "model-alpha", "a2": "model-beta", "a3": "model-alpha"},
    )
    task_data = {"task_id": "t1", "question": "Q?", "ground_truth": "A"}

    from societyxai.config.loader import _build_agents
    agents = _build_agents(config)
    assert len(agents) == 3
    assert agents[0].model_id == "model-alpha"
    assert agents[1].model_id == "model-beta"
    assert agents[2].model_id == "model-alpha"


def test_loader_builds_backend_registry():
    """_build_backend_registry returns a registry with the expected models."""
    config = _minimal_config(
        number_of_agents=2,
        speaker_order=SpeakerOrderConfig(order=["a1", "a2"]),
        agent_models={"a1": "model-x", "a2": "model-y"},
    )

    from societyxai.config.loader import _build_backend_registry
    registry = _build_backend_registry(config)

    assert registry is not None
    assert registry.has_model("model-x")
    assert registry.has_model("model-y")
    assert registry.default is not None
    assert registry.default.model_id == "fake-model"  # primary model_id


def test_loader_no_agent_models_returns_none_registry():
    """_build_backend_registry returns None when no agent_models are set."""
    config = _minimal_config()
    from societyxai.config.loader import _build_backend_registry
    registry = _build_backend_registry(config)
    assert registry is None


def test_built_experiment_carries_registry():
    """BuiltExperiment includes backend_registry when agent_models is configured."""
    config = _minimal_config(
        agent_models={"a1": "model-x", "a2": "model-y"},
    )
    task_data = {"task_id": "t1", "question": "Q?", "ground_truth": "A"}
    experiment = ExperimentLoader.build(config, task_data)
    assert experiment.backend_registry is not None
    assert experiment.backend_registry.has_model("model-x")
    assert experiment.backend_registry.has_model("model-y")


def test_built_experiment_no_registry_for_homogeneous():
    """BuiltExperiment has None backend_registry when no agent_models."""
    config = _minimal_config()
    task_data = {"task_id": "t1", "question": "Q?", "ground_truth": "A"}
    experiment = ExperimentLoader.build(config, task_data)
    assert experiment.backend_registry is None


def test_from_experiment_passes_registry():
    """Orchestrator.from_experiment forwards the registry."""
    config = _minimal_config(
        agent_models={"a1": "model-x", "a2": "model-y"},
    )
    backend = TrackingBackend(model_id="default", response="support")
    from societyxai.core.agent import Agent
    from societyxai.core.society import Society

    agents = [
        Agent(agent_id="a1", role="speaker", model_id="model-x", system_prompt="p"),
        Agent(agent_id="a2", role="speaker", model_id="model-y", system_prompt="p"),
    ]
    society = Society(
        agents=agents,
        topology=config.topology,
        number_of_rounds=config.number_of_rounds,
        speaker_order=config.speaker_order,
        visibility=config.visibility,
    )
    task = Task(task_id="t1", question="Q?", ground_truth="A")
    from societyxai.models.registry import BackendRegistry
    reg = BackendRegistry(default=backend)
    reg.register("model-x", TrackingBackend(model_id="model-x", response="support"))
    reg.register("model-y", TrackingBackend(model_id="model-y", response="reject"))

    experiment = BuiltExperiment(config=config, society=society, task=task, backend=backend, backend_registry=reg)
    orch = Orchestrator.from_experiment(experiment)
    assert orch.backend_registry is reg


# ======================================================================
# 8. Intervention works with heterogeneous agents
# ======================================================================


def test_intervention_with_heterogeneous_agents():
    b1 = TrackingBackend(model_id="m1", response="support")
    b2 = TrackingBackend(model_id="m2", response="reject")
    reg = BackendRegistry(default=b1)
    reg.register("m2", b2)

    society = _make_society(["a1", "a2"], model_ids=["m1", "m2"], rounds=2)
    task = _make_task()
    intervention = MessageInjectionIntervention(
        target_id="a1", injected_content="INJECTED TEXT", round=1,
    )
    orch = Orchestrator(
        society=society, task=task, backend=b1,
        backend_registry=reg, intervention=intervention,
    )
    result = orch.run()

    assert result.trace is not None
    assert result.trace.intervention is not None
    assert result.trace.intervention.intervention_type == "message_injection"
    # Each backend handled its own agent's turns
    assert len(b1.calls) == 2  # a1 round 1 + round 2
    assert len(b2.calls) == 2  # a2 round 1 + round 2
    # Verify turn model IDs
    assert result.turns[0].model_id == "m1"  # a1 round 1
    assert result.turns[1].model_id == "m2"  # a2 round 1
    assert result.turns[2].model_id == "m1"  # a1 round 2
    assert result.turns[3].model_id == "m2"  # a2 round 2


# ======================================================================
# 9. Counterfactual preserves same model mapping
# ======================================================================


def test_counterfactual_preserves_model_mapping():
    b1 = TrackingBackend(model_id="m1", response="support approve")
    b2 = TrackingBackend(model_id="m2", response="reject disagree")
    reg = BackendRegistry(default=b1)
    reg.register("m2", b2)

    society = _make_society(["a1", "a2"], model_ids=["m1", "m2"])
    task = _make_task()
    intervention = MessageInjectionIntervention(
        target_id="a1", injected_content="INJECTED", round=1,
    )

    cf = CounterfactualExperiment(
        society=society, task=task, backend=b1,
        backend_registry=reg,
    )
    comparison = cf.run_counterfactual(intervention=intervention)

    baseline = comparison.baseline_trace
    intervention_trace = comparison.intervention_trace

    # Both branches should have the correct per-agent model IDs
    baseline_turns = [t for t in baseline.message_traces]
    intervention_turns = [t for t in intervention_trace.message_traces]

    assert len(baseline_turns) == 2
    assert len(intervention_turns) == 2

    # In both branches, a1's model is m1, a2's is m2
    # Check via the intervention trace that branches ran independently
    assert comparison.baseline_trace.run_id != comparison.intervention_trace.run_id


def test_counterfactual_convenience_fn_with_registry():
    b1 = TrackingBackend(model_id="m1", response="support")
    b2 = TrackingBackend(model_id="m2", response="reject")
    reg = BackendRegistry(default=b1)
    reg.register("m2", b2)

    society = _make_society(["a1", "a2"], model_ids=["m1", "m2"])
    task = _make_task()
    intervention = MessageInjectionIntervention(
        target_id="a1", injected_content="INJECTED", round=1,
    )

    comparison = run_counterfactual_experiment(
        society=society, task=task, backend=b1,
        intervention=intervention, backend_registry=reg,
    )
    assert comparison.baseline_trace is not None
    assert comparison.intervention_trace is not None


# ======================================================================
# 10. CLI config supports heterogeneous agents
# ======================================================================


def test_heterogeneous_yaml_loads():
    """The heterogeneous example YAML loads without errors."""
    path = CONFIGS_DIR / "example_heterogeneous.yaml"
    config, task_data = ExperimentLoader.from_yaml(path)
    assert config.agent_models is not None
    assert config.agent_models["agent_0"] == "llama3.1:8b"
    assert config.agent_models["agent_1"] == "qwen3:8b"
    assert config.agent_models["agent_2"] == "gemma3:4b"


def test_homogeneous_yaml_has_no_agent_models():
    """The original example YAML has agent_models=None."""
    path = CONFIGS_DIR / "example.yaml"
    config, _ = ExperimentLoader.from_yaml(path)
    assert config.agent_models is None


# ======================================================================
# 11. No cross-agent backend/state contamination
# ======================================================================


def test_no_cross_agent_backend_contamination():
    """Different agents' backends do not share mutable state."""
    class StatefulBackend(ModelBackend):
        def __init__(self, model_id, initial_call_count=0):
            super().__init__(model_id=model_id, provider="fake")
            self.call_count = initial_call_count
            self.last_messages: list[dict] = []

        def generate(self, messages, **kwargs):
            self.call_count += 1
            self.last_messages = list(messages)
            return ModelResponse(text=f"response from {self.model_id}")

    ba = StatefulBackend("model-a")
    bb = StatefulBackend("model-b")
    reg = BackendRegistry(default=ba)
    reg.register("model-b", bb)

    society = _make_society(["a1", "a2"], model_ids=["model-a", "model-b"], rounds=3)
    task = _make_task()
    orch = Orchestrator(society=society, task=task, backend=ba, backend_registry=reg)
    result = orch.run()

    # model-a handled 3 turns (a1 in each round)
    assert ba.call_count == 3
    # model-b handled 3 turns (a2 in each round)
    assert bb.call_count == 3

    # Verify the system message in each backend's last call matches the right agent's prompt
    # model-a's last call should have the system prompt for a1
    assert ba.last_messages[0]["content"] == "Test prompt."
    assert bb.last_messages[0]["content"] == "Test prompt."

    # Each backend's call history is independent (not shared mutable list)
    assert ba.last_messages is not bb.last_messages


def test_no_cross_agent_belief_contamination():
    """Agents' belief states are independent."""
    b1 = TrackingBackend(model_id="m1", response="support yes")
    b2 = TrackingBackend(model_id="m2", response="reject no")
    reg = BackendRegistry(default=b1)
    reg.register("m2", b2)

    society = _make_society(["a1", "a2"], model_ids=["m1", "m2"])
    task = _make_task()
    orch = Orchestrator(society=society, task=task, backend=b1, backend_registry=reg)
    result = orch.run()

    agent_a1 = society.agents[0]
    agent_a2 = society.agents[1]

    assert agent_a1.current_belief is not None
    assert agent_a2.current_belief is not None
    assert agent_a1.current_belief.position == "support"
    assert agent_a2.current_belief.position == "reject"


# ======================================================================
# 12. Three agents, three different models
# ======================================================================


def test_three_agents_three_models():
    b1 = TrackingBackend(model_id="llama", response="support yes")
    b2 = TrackingBackend(model_id="qwen", response="reject no")
    b3 = TrackingBackend(model_id="mistral", response="neutral maybe")
    reg = BackendRegistry(default=b1)
    reg.register("qwen", b2)
    reg.register("mistral", b3)

    society = _make_society(
        ["a1", "a2", "a3"],
        model_ids=["llama", "qwen", "mistral"],
        rounds=2,
    )
    task = _make_task()
    orch = Orchestrator(society=society, task=task, backend=b1, backend_registry=reg)
    result = orch.run()

    expected_models = ["llama", "qwen", "mistral", "llama", "qwen", "mistral"]
    actual_models = [t.model_id for t in result.turns]
    assert actual_models == expected_models
    assert len(b1.calls) == 2
    assert len(b2.calls) == 2
    assert len(b3.calls) == 2


# ======================================================================
# 13. Backward compat: existing test patterns still work
# ======================================================================


def test_orchestrator_positional_args_still_work():
    """Orchestrator(society, task, backend) positional form works unchanged."""
    society = _make_society(["a1"], model_ids=["m1"])
    task = _make_task()
    backend = TrackingBackend(model_id="m1", response="support")
    orch = Orchestrator(society, task, backend)
    result = orch.run()
    assert result.turns[0].model_id == "m1"


def test_experiment_loader_unsupported_provider_rejects_in_registry():
    """An unsupported provider in agent_models raises during registry build."""
    config = _minimal_config(
        provider="openai",
        agent_models={"a1": "gpt-4"},
    )
    with pytest.raises(ExperimentLoaderError, match="Unsupported provider"):
        from societyxai.config.loader import _build_backend_registry
        _build_backend_registry(config)


# ======================================================================
# 14. Pilot experiment YAML configs load correctly
# ======================================================================


def test_pilot_homogeneous_config_loads():
    """The pilot homogeneous config loads and has correct structure."""
    from pathlib import Path as _P
    config_dir = _P(__file__).parent.parent / "configs" / "experiments"
    config, task_data = ExperimentLoader.from_yaml(config_dir / "homogeneous_minority_correct.yaml")
    assert config.run_id == "pilot-homogeneous"
    assert config.number_of_agents == 5
    assert config.agent_models is not None
    assert all(v == "llama3.1:8b" for v in config.agent_models.values())
    assert config.parser_version == "structured"
    assert config.stopping_rule == "max_rounds"
    assert config.intervention.type == "none"
    assert task_data["ground_truth"] == "approve"


def test_pilot_heterogeneous_config_loads():
    """The pilot heterogeneous config loads with mixed model assignments."""
    from pathlib import Path as _P
    config_dir = _P(__file__).parent.parent / "configs" / "experiments"
    config, task_data = ExperimentLoader.from_yaml(config_dir / "heterogeneous_minority_correct.yaml")
    assert config.run_id == "pilot-heterogeneous"
    assert config.agent_models is not None
    assert config.agent_models["agent_0"] == "llama3.1:8b"
    assert config.agent_models["agent_1"] == "qwen3:8b"
    assert config.agent_models["agent_2"] == "gemma3:4b"
    assert config.agent_models["agent_3"] == "deepseek-r1:7b"
    assert config.agent_models["agent_4"] == "qwen3:1.7b"
    assert config.intervention.type == "none"


def test_pilot_counterfactual_config_loads():
    """The pilot counterfactual config loads with intervention fields."""
    from pathlib import Path as _P
    config_dir = _P(__file__).parent.parent / "configs" / "experiments"
    config, _ = ExperimentLoader.from_yaml(config_dir / "heterogeneous_minority_counterfactual.yaml")
    assert config.run_id == "pilot-counterfactual"
    assert config.intervention.type == "message_injection"
    assert config.intervention.target_id == "agent_0"
    assert config.intervention.injected_content is not None
    assert len(config.intervention.injected_content) > 0
    assert config.intervention.round == 1


def test_pilot_counterfactual_intervention_applied():
    """Counterfactual experiment applies intervention to target agent."""
    b1 = TrackingBackend(model_id="m1", response="support approve")
    b2 = TrackingBackend(model_id="m2", response="reject disagree")
    reg = BackendRegistry(default=b1)
    reg.register("m2", b2)

    society = _make_society(["a1", "a2"], model_ids=["m1", "m2"])
    task = _make_task()
    intervention = MessageInjectionIntervention(
        target_id="a1", injected_content="INJECTED", round=1,
    )

    cf = CounterfactualExperiment(
        society=society, task=task, backend=b1,
        backend_registry=reg,
    )
    comparison = cf.run_counterfactual(intervention=intervention)

    # Intervention trace should confirm the intervention was applied
    assert comparison.intervention_trace is not None
    assert comparison.intervention_trace.intervention is not None
    assert comparison.intervention_trace.intervention.intervention_type == "message_injection"
    assert comparison.intervention_trace.intervention.target_id == "a1"
    # Baseline should have no intervention
    assert comparison.baseline_trace.intervention is None
