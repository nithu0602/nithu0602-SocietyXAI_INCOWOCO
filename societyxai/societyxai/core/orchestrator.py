from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from societyxai.core.society import Society
from societyxai.interventions.base import BaseIntervention
from societyxai.models.base import ModelBackend
from societyxai.models.registry import BackendRegistry
from societyxai.parsers.base import BeliefParser
from societyxai.parsers.heuristic import HeuristicBeliefParser
from societyxai.tasks.base import Task
from societyxai.traces.schema import AgentTrace, BeliefState, MessageTrace, RunTrace
from societyxai.utils.positions import normalize_position


class ExecutionTurn(BaseModel):
    """Simple deterministic turn record for orchestration output."""

    model_config = ConfigDict(extra="forbid")

    round: int
    turn_index: int
    agent_id: str
    model_id: str
    provider: str
    response: str


class ExecutionResult(BaseModel):
    """Small execution summary for a deterministic orchestration pass."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    rounds_executed: int
    agent_ids: list[str] = Field(default_factory=list)
    turns: list[ExecutionTurn] = Field(default_factory=list)
    trace: RunTrace | None = None

    def to_run_trace(self) -> RunTrace | None:
        """Return the attached RunTrace if present."""
        return self.trace

    def save_trace(self, directory: str | Path = "runs", filename: str | None = None) -> Path | None:
        """Save the attached RunTrace to a JSON file on disk."""
        if self.trace is not None:
            return self.trace.save(directory=directory, filename=filename)
        return None


class Orchestrator:
    """Coordinate a Society on a Task without implementing model-specific logic."""

    def __init__(
        self,
        society: Society,
        task: Task,
        backend: ModelBackend,
        run_id: str | None = None,
        seed: int | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        system_prompt_hash: str | None = None,
        intervention: BaseIntervention | list[BaseIntervention] | None = None,
        branch_id: str | None = None,
        stopping_rule: str | None = None,
        belief_parser: BeliefParser | None = None,
        backend_registry: BackendRegistry | None = None,
        adjudicator_ids: list[str] | None = None,
        log_sink: Any | None = None,
    ):
        if society is None:
            raise ValueError("society must be provided")
        if task is None:
            raise ValueError("task must be provided")
        if backend is None:
            raise ValueError("backend must be provided")

        self.society = society
        self.task = task
        self.backend = backend
        self.run_id = run_id
        self.seed = seed
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.system_prompt_hash = system_prompt_hash
        self.branch_id = branch_id
        self.stopping_rule = stopping_rule
        self.belief_parser: BeliefParser = belief_parser or HeuristicBeliefParser()
        self.backend_registry: BackendRegistry | None = backend_registry
        self.adjudicator_ids: set[str] = set(adjudicator_ids or [])
        self.log_sink = log_sink
        self.last_trace: RunTrace | None = None

        if intervention is None:
            self.interventions: list[BaseIntervention] = []
        elif isinstance(intervention, list):
            self.interventions = list(intervention)
        elif isinstance(intervention, BaseIntervention):
            self.interventions = [intervention]
        else:
            self.interventions = []

    def _resolve_backend(self, agent: Any) -> ModelBackend:
        """Return the backend for a given agent.

        When a backend_registry is present, resolve by the agent's model_id.
        Otherwise fall back to the single experiment-level backend.
        """
        if self.backend_registry is not None:
            resolved = self.backend_registry.resolve(agent.model_id)
            if resolved is not None:
                return resolved
        return self.backend

    @classmethod
    def from_experiment(cls, experiment: Any) -> Orchestrator:
        """Create an Orchestrator from a BuiltExperiment."""
        config = getattr(experiment, "config", None)
        parser = cls._resolve_parser_from_config(config)
        registry = getattr(experiment, "backend_registry", None)
        return cls(
            society=experiment.society,
            task=experiment.task,
            backend=experiment.backend,
            run_id=getattr(config, "run_id", None),
            seed=getattr(config, "seed", None),
            temperature=getattr(config, "temperature", None),
            max_tokens=getattr(config, "max_tokens", None),
            system_prompt_hash=getattr(config, "system_prompt_hash", None),
            stopping_rule=getattr(config, "stopping_rule", None),
            belief_parser=parser,
            backend_registry=registry,
            adjudicator_ids=getattr(config, "adjudicator_ids", None),
        )

    @staticmethod
    def _resolve_parser_from_config(config: Any) -> BeliefParser | None:
        """Map a ``parser_version`` value from config to a ``BeliefParser``.

        Returns ``None`` when no config or an unrecognised version is found,
        which lets the Orchestrator default to ``HeuristicBeliefParser``.
        """
        if config is None:
            return None
        version = getattr(config, "parser_version", None)
        if version == "structured":
            from societyxai.parsers.structured import StructuredBeliefParser
            return StructuredBeliefParser()
        return None

    # ------------------------------------------------------------------
    # Topology helpers
    # ------------------------------------------------------------------

    def _build_adjacency_lookup(self) -> dict[str, list[str]]:
        """Map each agent_id to the set of agent_ids whose messages it may see.

        For ``complete`` topologies every agent sees every other agent.
        For ``custom`` topologies the explicit adjacency matrix is used.
        For ``ring`` / ``line`` / ``star`` the adjacency matrix must be
        supplied; if absent the behaviour falls back to ``complete``.
        """
        agent_ids = [a.agent_id for a in self.society.agents]
        n = len(agent_ids)
        topology = self.society.topology
        order = self.society.speaker_order.order

        if topology.kind == "complete" and topology.adjacency is None:
            all_agents = list(agent_ids)
            return {aid: list(all_agents) for aid in agent_ids}

        if topology.adjacency is not None:
            matrix = topology.adjacency
            if len(matrix) != n:
                raise ValueError(
                    f"adjacency matrix has {len(matrix)} rows, "
                    f"expected {n} (one per agent)"
                )
            lookup: dict[str, list[str]] = {}
            for i, agent_id in enumerate(order):
                if i >= len(matrix):
                    raise ValueError(
                        f"adjacency matrix row {i} missing for agent {agent_id}"
                    )
                row = matrix[i]
                lookup[agent_id] = []
                for j in row:
                    if j < 0 or j >= n:
                        raise ValueError(
                            f"adjacency index {j} out of range for agent {agent_id}"
                        )
                    neighbor = order[j]
                    if neighbor not in lookup[agent_id]:
                        lookup[agent_id].append(neighbor)
            return lookup

        all_agents = list(agent_ids)
        return {aid: list(all_agents) for aid in agent_ids}

    # ------------------------------------------------------------------
    # Visibility helpers
    # ------------------------------------------------------------------

    def _independent_first_round(self, round_num: int) -> bool:
        return bool(round_num == 1 and self.society.visibility.independent_first_round)

    def _visible_messages(
        self,
        current_agent_id: str,
        all_messages: list[dict[str, Any]],
        adjacency_lookup: dict[str, list[str]],
        round_num: int = 1,
    ) -> list[dict[str, Any]]:
        """Return the subset of *all_messages* visible to *current_agent_id*."""
        if self._independent_first_round(round_num) or not self.society.visibility.previous_messages:
            return []

        recipients = adjacency_lookup.get(current_agent_id, [])
        return [msg for msg in all_messages if msg["agent_id"] in recipients]

    # ------------------------------------------------------------------
    # Confidence / majority-position helpers
    # ------------------------------------------------------------------

    def _collect_confidence_info(
        self,
        current_agent_id: str,
        adjacency_lookup: dict[str, list[str]],
        agent_by_id: dict[str, Any],
        round_num: int = 1,
    ) -> list[dict[str, Any]]:
        """Gather confidence data for agents visible to *current_agent_id*."""
        if self._independent_first_round(round_num) or not self.society.visibility.confidence:
            return []
        recipients = adjacency_lookup.get(current_agent_id, [])
        info: list[dict[str, Any]] = []
        for aid in recipients:
            if aid == current_agent_id:
                continue
            a = agent_by_id.get(aid)
            if a is not None and a.current_belief is not None:
                info.append({"agent_id": aid, "confidence": a.current_belief.confidence})
        return info

    def _compute_majority_position(
        self,
        current_agent_id: str,
        adjacency_lookup: dict[str, list[str]],
        agent_by_id: dict[str, Any],
        round_num: int = 1,
    ) -> str | None:
        """Return the majority position among visible agents, or *None*."""
        if self._independent_first_round(round_num) or not self.society.visibility.majority_position:
            return None
        recipients = adjacency_lookup.get(current_agent_id, [])
        positions: list[str] = []
        for aid in recipients:
            if aid == current_agent_id:
                continue
            a = agent_by_id.get(aid)
            if a is not None and a.current_belief is not None:
                positions.append(a.current_belief.position)
        if not positions:
            return None
        from collections import Counter
        counts = Counter(positions)
        return counts.most_common(1)[0][0]

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    @staticmethod
    def _format_evidence(evidence: list[Any]) -> str:
        """Render evidence items into a single text block."""
        lines = ["Evidence:"]
        for item in evidence:
            source = getattr(item, "source", None)
            if source:
                lines.append(f"- [{item.evidence_id}] {item.content} (source: {source})")
            else:
                lines.append(f"- [{item.evidence_id}] {item.content}")
        return "\n".join(lines)

    def _build_messages(
        self,
        agent: Any,
        visible_messages: list[dict[str, Any]],
        has_evidence: bool,
        confidence_info: list[dict[str, Any]] | None = None,
        majority_position: str | None = None,
        initial_belief_section: str | None = None,
    ) -> list[dict[str, str]]:
        """Assemble the full message list for a single model call.

        initial_belief_section, when provided, is a short user-facing block that
        communicates the agent's own pre-round initial belief. It should be
        inserted immediately after the task question so as to avoid changing the
        rest of the prompt ordering.
        """
        messages: list[dict[str, str]] = [
            {"role": "system", "content": agent.system_prompt},
            {"role": "user", "content": self.task.question},
        ]

        if initial_belief_section:
            messages.append({"role": "user", "content": initial_belief_section})

        if visible_messages:
            conversation_lines: list[str] = []
            for msg in visible_messages:
                conversation_lines.append(f"{msg['agent_id']}: {msg['content']}")
            messages.append(
                {
                    "role": "user",
                    "content": "Previous messages:\n" + "\n".join(conversation_lines),
                }
            )

        if has_evidence:
            messages.append(
                {
                    "role": "user",
                    "content": self._format_evidence(self.task.evidence),
                }
            )

        if confidence_info:
            lines = ["Confidence levels of visible agents:"]
            for info in confidence_info:
                lines.append(f"- {info['agent_id']}: confidence={info['confidence']:.2f}")
            messages.append({"role": "user", "content": "\n".join(lines)})

        if majority_position is not None:
            messages.append(
                {
                    "role": "user",
                    "content": f"Current majority position: {majority_position}",
                }
            )

        return messages

    # ------------------------------------------------------------------
    # Belief update
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_belief(response: str) -> BeliefState:
        """Derive a basic BeliefState from raw response text."""
        lower = response.lower()
        if any(w in lower for w in ("support", "agree", "approve", "yes")):
            position = "support"
        elif any(w in lower for w in ("reject", "disagree", "oppose", "no")):
            position = "reject"
        else:
            position = "neutral"
        return BeliefState(position=position, confidence=1.0, evidence_ids=[])

    @staticmethod
    def _majority_vote(final_positions: list[str]) -> str | None:
        """Return the majority position from *final_positions*.

        Ties are resolved deterministically by choosing the lexicographically
        smallest tied position. This keeps the result independent of speaker
        order while remaining stable across repeated runs.
        """
        if not final_positions:
            return None

        counts = Counter(final_positions)
        max_count = max(counts.values())
        tied_positions = sorted(position for position, count in counts.items() if count == max_count)
        return tied_positions[0]

    # ------------------------------------------------------------------
    # Stopping-rule evaluation
    # ------------------------------------------------------------------

    def _should_stop_after_round(self, agent_by_id: dict[str, Any]) -> bool:
        """Evaluate whether the stopping condition is met after a complete round.

        Only ``"consensus"`` triggers early termination: all agents must hold
        the same belief position.  Any other value (including ``"max_rounds"``,
        ``None``, or empty string) runs the full configured number of rounds.
        """
        if self.stopping_rule != "consensus":
            return False

        positions: set[str] = set()
        for agent in self.society.agents:
            belief = agent_by_id.get(agent.agent_id, agent).current_belief
            if belief is None:
                return False
            positions.add(belief.position)
        return len(positions) == 1

    # ------------------------------------------------------------------
    # Main execution loop
    # ------------------------------------------------------------------

    def run(self) -> ExecutionResult:
        """Execute deterministic rounds according to the task and society configuration."""
        if not self.society.agents:
            raise ValueError("society must contain at least one agent")
        if not self.task.task_id:
            raise ValueError("task must include a task_id")

        for intervention in self.interventions:
            self.society = intervention.prepare_society(self.society)

        speaker_order = self.society.speaker_order.order
        agent_by_id = {agent.agent_id: agent for agent in self.society.agents}
        missing = [aid for aid in speaker_order if aid not in agent_by_id]
        if missing:
            raise ValueError(f"speaker order references unknown agents: {missing}")

        adjacency_lookup = self._build_adjacency_lookup()
        has_evidence = bool(self.task.evidence)

        # Capture a pre-round snapshot of initial beliefs (if any) so that
        # RunTrace can persist them without creating fake round-0 traces.
        initial_beliefs_snapshot: dict[str, BeliefState] | None = None
        snapshot: dict[str, BeliefState] = {}
        for a in self.society.agents:
            if a.current_belief is not None:
                snapshot[a.agent_id] = a.current_belief
        if snapshot:
            initial_beliefs_snapshot = snapshot

        all_messages: list[dict[str, Any]] = []
        turns: list[ExecutionTurn] = []
        agent_traces: list[AgentTrace] = []
        message_traces: list[MessageTrace] = []
        rounds_executed = 0

        for round_num in range(1, self.society.number_of_rounds + 1):
            for turn_index, agent_id in enumerate(speaker_order, start=1):
                if (
                    agent_id in self.adjudicator_ids
                    and round_num < self.society.number_of_rounds
                ):
                    continue
                agent = agent_by_id[agent_id]

                # -- 2. Build prompt with conversation + evidence + visibility --
                visible = self._visible_messages(agent_id, all_messages, adjacency_lookup, round_num)
                for interv in self.interventions:
                    visible = interv.filter_visible_messages(
                        agent_id,
                        visible,
                        all_messages,
                        round_num,
                        turn_index,
                    )
                parent_message_ids = [msg["message_id"] for msg in visible]
                agent.received_message_ids.extend(parent_message_ids)
                confidence_info = self._collect_confidence_info(
                    agent_id, adjacency_lookup, agent_by_id, round_num
                )
                majority_pos = self._compute_majority_position(
                    agent_id, adjacency_lookup, agent_by_id, round_num
                )
                # Expose the agent's own initial belief only on its first deliberation turn
                initial_belief_section: str | None = None
                if round_num == 1 and agent.current_belief is not None:
                    # Minimal exposed block per spec
                    initial_belief_section = (
                        f"Your initial belief:\nposition: {agent.current_belief.position}\nconfidence: {agent.current_belief.confidence:.2f}"
                    )

                messages = self._build_messages(
                    agent,
                    visible,
                    has_evidence,
                    confidence_info,
                    majority_pos,
                    initial_belief_section,
                )

                # -- 2b. Apply active interventions for this agent and turn --
                applied_intervention_status = "none"
                for interv in self.interventions:
                    if interv.should_apply(agent_id, round_num, turn_index):
                        messages = interv.apply_to_messages(agent_id, messages, round_num, turn_index)
                        applied_intervention_status = interv.intervention_type

                # -- 3. Generate response using agent-specific backend --
                agent_backend = self._resolve_backend(agent)
                response = agent_backend.generate(
                    messages=messages,
                    temperature=self.temperature if self.temperature is not None else 0.0,
                    max_tokens=self.max_tokens if self.max_tokens is not None else 64,
                    seed=self.seed if self.seed is not None else 0,
                )
                response_text = response.text if hasattr(response, "text") else str(response)

                # -- 4. Record the turn --
                turns.append(
                    ExecutionTurn(
                        round=round_num,
                        turn_index=turn_index,
                        agent_id=agent.agent_id,
                        model_id=agent_backend.model_id,
                        provider=agent_backend.provider,
                        response=response_text,
                    )
                )

                # -- 5. Store message in shared conversation & message traces --
                message_id = f"r{round_num}_t{turn_index}_{agent_id}"
                all_messages.append(
                    {
                        "message_id": message_id,
                        "agent_id": agent_id,
                        "round": round_num,
                        "turn_index": turn_index,
                        "content": response_text,
                    }
                )
                content_hash = hashlib.sha256(response_text.encode()).hexdigest()
                message_traces.append(
                    MessageTrace(
                        message_id=message_id,
                        agent_id=agent_id,
                        model_id=agent_backend.model_id,
                        provider=agent_backend.provider,
                        round=round_num,
                        turn_index=turn_index,
                        content=response_text if response_text else " ",
                        parent_message_ids=parent_message_ids,
                        content_hash=content_hash,
                        intervention_status=applied_intervention_status,
                    )
                )

                # -- 6. Update agent belief state & record agent trace --
                belief = self.belief_parser.parse(response_text)
                agent.current_belief = belief
                agent.belief_history.append(belief)

                social_style_str = None
                if agent.social_style is not None:
                    social_style_str = (
                        f"assertiveness={agent.social_style.assertiveness},"
                        f"verbosity={agent.social_style.verbosity},"
                        f"confidence_style={agent.social_style.confidence_style}"
                    )

                cited_agents = [
                    aid for aid in speaker_order if aid != agent_id and aid in response_text
                ]

                agent_traces.append(
                    AgentTrace(
                        agent_id=agent.agent_id,
                        role=agent.role,
                        model_id=agent_backend.model_id,
                        provider=agent_backend.provider,
                        capability_score=agent.capability_score,
                        social_style=social_style_str,
                        round=round_num,
                        turn_index=turn_index,
                        belief=belief,
                        received_message_ids=list(agent.received_message_ids),
                        cited_agent_ids=cited_agents,
                        exposed_majority_position=majority_pos,
                    )
                )
                if self.log_sink is not None:
                    self.log_sink.turn(
                        round_num=round_num,
                        turn_index=turn_index,
                        agent_id=agent.agent_id,
                        role=agent.role,
                        model_id=agent_backend.model_id,
                        provider=agent_backend.provider,
                        position=belief.position,
                        confidence=belief.confidence,
                        evidence_ids=list(belief.evidence_ids),
                        reasoning=belief.reasoning_trace,
                        response=response_text,
                    )

            # -- 6b. Round bookkeeping and stopping-rule check --
            rounds_executed = round_num
            if self._should_stop_after_round(agent_by_id):
                break

        # -- 7. Assemble RunTrace --
        resolved_run_id = self.run_id or f"run_{self.task.task_id}"
        resolved_seed = self.seed if self.seed is not None else (getattr(self.backend, "default_seed", None) or 0)
        resolved_temp = self.temperature if self.temperature is not None else (getattr(self.backend, "default_temperature", None) or 0.0)
        resolved_hash = self.system_prompt_hash
        if resolved_hash is None and self.society.agents and self.society.agents[0].system_prompt:
            resolved_hash = hashlib.sha256(self.society.agents[0].system_prompt.encode()).hexdigest()

        final_positions = [
            agent.current_belief.position
            for agent in self.society.agents
            if agent.current_belief is not None
        ]
        final_decision = self._majority_vote(final_positions)
        correctness = None
        if final_decision is not None and self.task.ground_truth:
            correctness = (
                normalize_position(final_decision)
                == normalize_position(self.task.ground_truth)
            )

        intervention_trace = None
        if self.interventions:
            intervention_trace = self.interventions[0].to_trace(branch_id=self.branch_id)

        run_trace = RunTrace(
            run_id=resolved_run_id,
            task_id=self.task.task_id,
            seed=resolved_seed,
            timestamp=datetime.now(timezone.utc),
            model_id=self.backend.model_id,
            provider=self.backend.provider,
            temperature=resolved_temp,
            system_prompt_hash=resolved_hash,
            topology=self.society.topology,
            speaker_order=list(self.society.speaker_order.order),
            visibility=self.society.visibility,
            initial_beliefs=initial_beliefs_snapshot,
            ground_truth=self.task.ground_truth,
            agent_traces=agent_traces,
            message_traces=message_traces,
            intervention=intervention_trace,
            final_decision=final_decision,
            correctness=correctness,
        )
        self.last_trace = run_trace

        return ExecutionResult(
            task_id=self.task.task_id,
            rounds_executed=rounds_executed,
            agent_ids=[agent.agent_id for agent in self.society.agents],
            turns=turns,
            trace=run_trace,
        )
