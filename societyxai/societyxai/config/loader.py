from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import ValidationError

from societyxai.config.schema import ExperimentConfig
from societyxai.models.base import ModelBackend
from societyxai.models.ollama import OllamaBackend
from societyxai.models.groq import GroqBackend
from societyxai.models.registry import BackendRegistry
from societyxai.tasks.base import EvidenceItem, Task

if TYPE_CHECKING:
    from societyxai.core.agent import Agent
    from societyxai.core.society import Society


class ExperimentLoaderError(ValueError):
    """Raised when an experiment file cannot be loaded or assembled."""


@dataclass(frozen=True)
class BuiltExperiment:
    """Fully assembled runtime objects produced from an ExperimentConfig."""

    config: ExperimentConfig
    society: Society
    task: Task
    backend: ModelBackend
    backend_registry: BackendRegistry | None = None


ARCHITECTURE_FLAVORS = {
    "consultation": (
        "You are in a specialist consultation. Speak only from your specialty. "
        "Independent first opinions come before shared discussion."
    ),
    "committee": (
        "You are in a sequential committee / risk review. Critique the live proposal. "
        "Early speakers can anchor later ones."
    ),
    "adversarial": (
        "You are in an adversarial hearing. Argue your side from evidence. "
        "The adjudicator rules after hearing both sides."
    ),
    "negotiation": (
        "You are in a stakeholder negotiation. Your objective may conflict with others. "
        "Do not pretend consensus exists if it does not."
    ),
}


def _build_backend(config: ExperimentConfig) -> ModelBackend:
    """Instantiate a ModelBackend from the provider declared in *config*."""
    provider = config.provider.lower()
    if provider == "ollama":
        return OllamaBackend(
            model_id=config.model_id,
            default_temperature=config.temperature,
            default_max_tokens=config.max_tokens,
            default_seed=config.seed,
        )
    if provider == "groq":
        from societyxai.models.groq import GroqBackend

        return GroqBackend(
            model_id=config.model_id,
            default_temperature=config.temperature,
            default_max_tokens=config.max_tokens,
            default_seed=config.seed,
        )
    raise ExperimentLoaderError(
        f"Unsupported provider '{config.provider}'. "
        "Supported providers: ollama, groq."
    )


def _build_backend_for_model(
    model_id: str,
    config: ExperimentConfig,
) -> ModelBackend:
    """Instantiate a ModelBackend for a specific model_id using the experiment's provider."""
    provider = config.provider.lower()
    if provider == "ollama":
        return OllamaBackend(
            model_id=model_id,
            default_temperature=config.temperature,
            default_max_tokens=config.max_tokens,
            default_seed=config.seed,
        )
    if provider == "groq":
        from societyxai.models.groq import GroqBackend

        return GroqBackend(
            model_id=model_id,
            default_temperature=config.temperature,
            default_max_tokens=config.max_tokens,
            default_seed=config.seed,
        )
    raise ExperimentLoaderError(
        f"Unsupported provider '{config.provider}'. "
        "Supported providers: ollama, groq."
    )


def _build_agents(config: ExperimentConfig) -> list[Agent]:
    """Create one Agent per entry in speaker_order using shared or per-agent prompts."""
    from societyxai.core.agent import Agent

    agent_models = config.agent_models or {}
    agent_roles = config.agent_roles or {}
    agent_prompts = config.agent_prompts or {}
    flavor = ARCHITECTURE_FLAVORS.get((config.architecture or "").lower(), "")
    agents: list[Agent] = []
    for agent_id in config.speaker_order.order:
        role = agent_roles.get(agent_id, "speaker")
        prompt = agent_prompts.get(agent_id, config.system_prompt)
        if flavor:
            prompt = f"{flavor} Your role is {role}.\n{prompt}"
        agents.append(
            Agent(
                agent_id=agent_id,
                role=role,
                model_id=agent_models.get(agent_id, config.model_id),
                system_prompt=prompt,
            )
        )
    return agents


def _build_backend_registry(config: ExperimentConfig) -> BackendRegistry | None:
    """Build a BackendRegistry when per-agent models are configured.

    Returns ``None`` when no agent_models are specified, preserving
    the existing single-backend path.
    """
    agent_models = config.agent_models
    if not agent_models:
        return None

    primary = _build_backend(config)
    registry = BackendRegistry(default=primary)

    unique_model_ids = set(agent_models.values())
    for model_id in unique_model_ids:
        if model_id == config.model_id:
            registry.register(model_id, primary)
        else:
            backend = _build_backend_for_model(model_id, config)
            registry.register(model_id, backend)

    return registry


def _build_society(config: ExperimentConfig, agents: list[Agent]) -> Society:
    from societyxai.core.society import Society

    return Society(
        agents=agents,
        topology=config.topology,
        number_of_rounds=config.number_of_rounds,
        speaker_order=config.speaker_order,
        visibility=config.visibility,
    )


def _build_task(task_data: dict[str, Any]) -> Task:
    """Construct a Task from the raw task section of the YAML document."""
    evidence_raw: list[dict[str, Any]] = task_data.pop("evidence", [])
    evidence = [EvidenceItem(**item) for item in evidence_raw]
    return Task(evidence=evidence, **task_data)


class ExperimentLoader:
    """Load and assemble SocietyXAI experiments from YAML configuration files.

    Usage::

        config = ExperimentLoader.from_yaml("configs/my_experiment.yaml")
        experiment = ExperimentLoader.build(config)
        result = Orchestrator(
            society=experiment.society,
            task=experiment.task,
            backend=experiment.backend,
        ).run()
    """

    @staticmethod
    def from_yaml(path: str | Path) -> tuple[ExperimentConfig, dict[str, Any]]:
        """Parse and validate a YAML experiment file.

        The file must contain two top-level sections:

        - ``experiment``: fields that map to :class:`ExperimentConfig`
        - ``task``: fields that map to :class:`Task`

        Returns a ``(ExperimentConfig, task_dict)`` tuple so that callers can
        inspect or further enrich the task section before calling
        :meth:`build`.

        Raises :class:`ExperimentLoaderError` on missing sections, invalid
        YAML, or Pydantic validation failures.
        """
        resolved = Path(path)
        if not resolved.exists():
            raise ExperimentLoaderError(f"Experiment file not found: {resolved}")

        try:
            raw: Any = yaml.safe_load(resolved.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ExperimentLoaderError(f"YAML parse error in '{resolved}': {exc}") from exc

        if not isinstance(raw, dict):
            raise ExperimentLoaderError(
                f"Expected a YAML mapping at the top level of '{resolved}', got {type(raw).__name__}."
            )

        if "experiment" not in raw:
            raise ExperimentLoaderError(
                f"Missing required top-level key 'experiment' in '{resolved}'."
            )
        if "task" not in raw:
            raise ExperimentLoaderError(
                f"Missing required top-level key 'task' in '{resolved}'."
            )

        experiment_data: dict[str, Any] = raw["experiment"]
        task_data: dict[str, Any] = dict(raw["task"])  # shallow copy; _build_task mutates it

        # Derive system_prompt_hash automatically if not supplied.
        if "system_prompt" in experiment_data and experiment_data.get("system_prompt_hash") is None:
            prompt = experiment_data["system_prompt"]
            experiment_data["system_prompt_hash"] = hashlib.sha256(
                prompt.encode()
            ).hexdigest()

        try:
            config = ExperimentConfig(**experiment_data)
        except ValidationError as exc:
            raise ExperimentLoaderError(
                f"Invalid experiment configuration in '{resolved}':\n{exc}"
            ) from exc

        return config, task_data

    @staticmethod
    def build(
        config: ExperimentConfig,
        task_data: dict[str, Any],
    ) -> BuiltExperiment:
        """Assemble runtime objects from a validated *config* and *task_data*.

        Args:
            config: A validated :class:`ExperimentConfig` instance.
            task_data: A dict of fields for :class:`Task` (as returned by
                :meth:`from_yaml`).

        Returns:
            A :class:`BuiltExperiment` containing the assembled
            ``Society``, ``Task``, and ``ModelBackend``.

        Raises:
            :class:`ExperimentLoaderError` on unsupported providers or task
            validation failures.
        """
        try:
            task = _build_task(dict(task_data))
        except (ValidationError, TypeError) as exc:
            raise ExperimentLoaderError(f"Invalid task configuration: {exc}") from exc

        try:
            backend = _build_backend(config)
        except ExperimentLoaderError:
            raise
        except Exception as exc:
            raise ExperimentLoaderError(f"Failed to build backend: {exc}") from exc

        agents = _build_agents(config)
        society = _build_society(config, agents)

        # Apply initial beliefs from config (if any) to the Agent objects so that
        # they are present before the first deliberation round. Construct
        # BeliefState objects here to avoid importing traces.schema at module top
        # level and creating circular imports.
        if getattr(config, "initial_beliefs", None):
            from societyxai.traces.schema import BeliefState

            for aid, spec in config.initial_beliefs.items():
                # Find the matching agent and assign current_belief + seed history
                matching = [a for a in agents if a.agent_id == aid]
                if not matching:
                    # The config schema validator should prevent this, but guard anyway
                    raise ExperimentLoaderError(f"initial_beliefs references unknown agent id: {aid}")
                agent = matching[0]
                belief = BeliefState(
                    position=spec.position,
                    confidence=float(spec.confidence),
                    evidence_ids=list(spec.evidence_ids or []),
                    reasoning_trace=spec.reasoning_trace or "",
                )
                agent.current_belief = belief
                agent.belief_history.append(belief)

        try:
            backend_registry = _build_backend_registry(config)
        except ExperimentLoaderError:
            raise
        except Exception as exc:
            raise ExperimentLoaderError(f"Failed to build backend registry: {exc}") from exc

        return BuiltExperiment(
            config=config,
            society=society,
            task=task,
            backend=backend,
            backend_registry=backend_registry,
        )

    @classmethod
    def load(cls, path: str | Path) -> BuiltExperiment:
        """Convenience method: parse YAML and build in one call.

        Equivalent to::

            config, task_data = ExperimentLoader.from_yaml(path)
            return ExperimentLoader.build(config, task_data)
        """
        config, task_data = cls.from_yaml(path)
        return cls.build(config, task_data)
