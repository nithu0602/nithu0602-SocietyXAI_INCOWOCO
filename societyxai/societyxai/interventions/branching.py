from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from societyxai.interventions.base import BaseIntervention
from societyxai.tasks.base import Task
from societyxai.traces.schema import BeliefState, InterventionTrace, RunTrace

if TYPE_CHECKING:
    from societyxai.config.loader import BuiltExperiment
    from societyxai.core.orchestrator import ExecutionResult, Orchestrator
    from societyxai.core.society import Society
    from societyxai.models.base import ModelBackend
    from societyxai.models.registry import BackendRegistry
    from societyxai.parsers.base import BeliefParser


class CounterfactualComparison(BaseModel):
    """Structured comparison between a baseline run and an intervention branch."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    baseline_trace: RunTrace
    intervention_trace: RunTrace
    intervention: InterventionTrace | None = None
    baseline_decision: str | None = None
    intervention_decision: str | None = None
    baseline_correctness: bool | None = None
    intervention_correctness: bool | None = None
    baseline_final_beliefs: dict[str, BeliefState] = Field(default_factory=dict)
    intervention_final_beliefs: dict[str, BeliefState] = Field(default_factory=dict)

    @property
    def decision_changed(self) -> bool:
        """Return True if the intervention changed the final decision compared to baseline."""
        return self.baseline_decision != self.intervention_decision

    @property
    def correctness_changed(self) -> bool:
        """Return True if the correctness status changed between branches."""
        return self.baseline_correctness != self.intervention_correctness

    def belief_changed(self, agent_id: str) -> bool:
        """Check whether a specific agent's final belief position changed."""
        base = self.baseline_final_beliefs.get(agent_id)
        interv = self.intervention_final_beliefs.get(agent_id)
        if base is None or interv is None:
            return base != interv
        return base.position != interv.position

    def save_traces(self, directory: str | Path = "runs") -> tuple[Path, Path]:
        """Persist both baseline and intervention RunTraces to disk.

        Returns:
            A tuple of (baseline_file_path, intervention_file_path).
        """
        base_path = self.baseline_trace.save(directory=directory)
        interv_path = self.intervention_trace.save(directory=directory)
        return base_path, interv_path


class CounterfactualExperiment:
    """Orchestrates baseline and intervention branch executions from shared initial state."""

    def __init__(
        self,
        society: Society,
        task: Task,
        backend: ModelBackend,
        base_run_id: str | None = None,
        seed: int | None = None,
        temperature: float | None = None,
        system_prompt_hash: str | None = None,
        stopping_rule: str | None = None,
        belief_parser: BeliefParser | None = None,
        backend_registry: BackendRegistry | None = None,
    ):
        self.society = society
        self.task = task
        self.backend = backend
        self.base_run_id = base_run_id or f"exp_{task.task_id}"
        self.seed = seed
        self.temperature = temperature
        self.system_prompt_hash = system_prompt_hash
        self.stopping_rule = stopping_rule
        self.belief_parser = belief_parser
        self.backend_registry = backend_registry

    @classmethod
    def from_built_experiment(
        cls,
        experiment: BuiltExperiment,
        base_run_id: str | None = None,
    ) -> CounterfactualExperiment:
        """Construct a CounterfactualExperiment from an assembled BuiltExperiment."""
        from societyxai.core.orchestrator import Orchestrator

        config = experiment.config
        parser = Orchestrator._resolve_parser_from_config(config)
        registry = getattr(experiment, "backend_registry", None)
        return cls(
            society=experiment.society,
            task=experiment.task,
            backend=experiment.backend,
            base_run_id=base_run_id or config.run_id,
            seed=config.seed,
            temperature=config.temperature,
            system_prompt_hash=config.system_prompt_hash,
            stopping_rule=getattr(config, "stopping_rule", None),
            belief_parser=parser,
            backend_registry=registry,
        )

    def run_baseline(self, branch_id: str = "baseline") -> ExecutionResult:
        """Execute the baseline branch without interventions using an isolated copy of state."""
        from societyxai.core.orchestrator import Orchestrator

        society_copy = self.society.model_copy(deep=True)
        task_copy = self.task.model_copy(deep=True)
        run_id = f"{self.base_run_id}_{branch_id}"

        orchestrator = Orchestrator(
            society=society_copy,
            task=task_copy,
            backend=self.backend,
            run_id=run_id,
            seed=self.seed,
            temperature=self.temperature,
            system_prompt_hash=self.system_prompt_hash,
            stopping_rule=self.stopping_rule,
            belief_parser=self.belief_parser,
            intervention=None,
            branch_id=branch_id,
            backend_registry=self.backend_registry,
        )
        return orchestrator.run()

    def run_branch(
        self,
        intervention: BaseIntervention,
        branch_id: str = "intervention",
    ) -> ExecutionResult:
        """Execute an intervention branch starting from a fresh copy of the initial state."""
        from societyxai.core.orchestrator import Orchestrator

        society_copy = self.society.model_copy(deep=True)
        task_copy = self.task.model_copy(deep=True)
        run_id = f"{self.base_run_id}_{branch_id}"

        orchestrator = Orchestrator(
            society=society_copy,
            task=task_copy,
            backend=self.backend,
            run_id=run_id,
            seed=self.seed,
            temperature=self.temperature,
            system_prompt_hash=self.system_prompt_hash,
            stopping_rule=self.stopping_rule,
            belief_parser=self.belief_parser,
            intervention=intervention,
            branch_id=branch_id,
            backend_registry=self.backend_registry,
        )
        return orchestrator.run()

    def run_counterfactual(
        self,
        intervention: BaseIntervention,
        baseline_branch_id: str = "baseline",
        intervention_branch_id: str = "intervention",
    ) -> CounterfactualComparison:
        """Run both baseline and intervention branches and produce a comparison."""
        baseline_result = self.run_baseline(branch_id=baseline_branch_id)
        intervention_result = self.run_branch(
            intervention=intervention,
            branch_id=intervention_branch_id,
        )

        if baseline_result.trace is None:
            raise RuntimeError("Baseline execution did not produce a RunTrace.")
        if intervention_result.trace is None:
            raise RuntimeError("Intervention execution did not produce a RunTrace.")

        baseline_trace = baseline_result.trace
        intervention_trace = intervention_result.trace

        # Extract final round beliefs for all agents
        baseline_beliefs: dict[str, BeliefState] = {}
        for at in baseline_trace.agent_traces:
            baseline_beliefs[at.agent_id] = at.belief

        intervention_beliefs: dict[str, BeliefState] = {}
        for at in intervention_trace.agent_traces:
            intervention_beliefs[at.agent_id] = at.belief

        return CounterfactualComparison(
            run_id=self.base_run_id,
            baseline_trace=baseline_trace,
            intervention_trace=intervention_trace,
            intervention=intervention_trace.intervention,
            baseline_decision=baseline_trace.final_decision,
            intervention_decision=intervention_trace.final_decision,
            baseline_correctness=baseline_trace.correctness,
            intervention_correctness=intervention_trace.correctness,
            baseline_final_beliefs=baseline_beliefs,
            intervention_final_beliefs=intervention_beliefs,
        )


def run_counterfactual_experiment(
    society: Society,
    task: Task,
    backend: ModelBackend,
    intervention: BaseIntervention,
    base_run_id: str | None = None,
    seed: int | None = None,
    temperature: float | None = None,
    system_prompt_hash: str | None = None,
    stopping_rule: str | None = None,
    belief_parser: BeliefParser | None = None,
    backend_registry: BackendRegistry | None = None,
    baseline_branch_id: str = "baseline",
    intervention_branch_id: str = "intervention",
) -> CounterfactualComparison:
    """Convenience helper to initialize and run a counterfactual experiment."""
    experiment = CounterfactualExperiment(
        society=society,
        task=task,
        backend=backend,
        base_run_id=base_run_id,
        seed=seed,
        temperature=temperature,
        system_prompt_hash=system_prompt_hash,
        stopping_rule=stopping_rule,
        belief_parser=belief_parser,
        backend_registry=backend_registry,
    )
    return experiment.run_counterfactual(
        intervention=intervention,
        baseline_branch_id=baseline_branch_id,
        intervention_branch_id=intervention_branch_id,
    )
