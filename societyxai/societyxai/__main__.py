"""Minimal CLI for running SocietyXAI experiments from YAML.

Usage::

    python -m societyxai run --config configs/example.yaml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from societyxai.config.loader import ExperimentLoader, ExperimentLoaderError
from societyxai.utils.document_log import ExperimentDocument
from societyxai.utils.envfile import load_env_file


def _build_intervention(config):
    """Construct a BaseIntervention from ExperimentConfig, or None if type is 'none'."""
    intervention_type = config.intervention.type.lower()
    if intervention_type == "none":
        return None

    from societyxai.interventions import (
        AgentRemovalIntervention,
        ConfidenceVisibilityIntervention,
        MajorityVisibilityIntervention,
        MessageInjectionIntervention,
        MessageRemovalIntervention,
        SpeakerOrderingIntervention,
    )

    if intervention_type == "message_injection":
        injected = config.intervention.injected_content or ""
        target_round = config.intervention.round
        return MessageInjectionIntervention(
            target_id=config.intervention.target_id,
            injected_content=injected,
            round=target_round if target_round is not None else 1,
        )
    if intervention_type == "agent_removal":
        return AgentRemovalIntervention(target_id=config.intervention.target_id)
    if intervention_type == "message_removal":
        return MessageRemovalIntervention(target_id=config.intervention.target_id)
    if intervention_type == "speaker_ordering":
        if not config.intervention.target_order:
            raise ValueError("speaker_ordering interventions require target_order")
        return SpeakerOrderingIntervention(target_order=list(config.intervention.target_order))
    if intervention_type == "confidence_visibility":
        if config.intervention.visible is None:
            raise ValueError("confidence_visibility interventions require visible")
        return ConfidenceVisibilityIntervention(visible=config.intervention.visible)
    if intervention_type == "majority_visibility":
        if config.intervention.visible is None:
            raise ValueError("majority_visibility interventions require visible")
        return MajorityVisibilityIntervention(visible=config.intervention.visible)

    return None


def _format_summary(result, trace_path: Path | None) -> str:
    """Return a concise human-readable summary string."""
    lines: list[str] = []

    trace = result.trace
    if trace is None:
        lines.append(f"Run ID    : {result.task_id}")
        lines.append(f"Task ID   : {result.task_id}")
        lines.append(f"Agents    : {', '.join(result.agent_ids)}")
        lines.append(f"Rounds    : {result.rounds_executed}")
        lines.append("No trace produced.")
        return "\n".join(lines)

    lines.append(f"Run ID    : {trace.run_id}")
    lines.append(f"Task ID   : {trace.task_id}")
    lines.append(f"Agents    : {', '.join(result.agent_ids)} ({len(result.agent_ids)} total)")
    lines.append(f"Rounds    : {result.rounds_executed}")
    lines.append(f"Final     : {trace.final_decision or 'N/A'}")
    lines.append(f"Correct   : {trace.correctness if trace.correctness is not None else 'N/A'}")

    if trace_path is not None:
        lines.append(f"Trace     : {trace_path}")

    try:
        from societyxai.utils.metrics import consensus_score, convergence_round, belief_divergence
        lines.append(f"Consensus : {consensus_score(trace):.4f}")
        lines.append(f"Divergence: {belief_divergence(trace):.4f}")
        lines.append(f"Converged : round {convergence_round(trace)}")
    except Exception:
        pass

    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint.  Returns 0 on success, non-zero on failure."""
    parser = argparse.ArgumentParser(
        prog="societyxai",
        description="SocietyXAI: multi-agent belief-dynamics research framework.",
    )
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Run an experiment from a YAML config file.")
    run_parser.add_argument(
        "--config", required=True, help="Path to the YAML experiment configuration file.",
    )
    run_parser.add_argument(
        "--output-dir", default="runs", help="Directory to persist the RunTrace (default: runs/).",
    )
    run_parser.add_argument(
        "--log-doc",
        default="docs/EXPERIMENT_LOG.md",
        help="Markdown file that records every agent turn.",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "run":
        return _cmd_run(args)

    parser.print_help()
    return 0


def _cmd_run(args) -> int:
    """Execute the 'run' subcommand."""
    load_env_file(
        Path(".env"),
        Path(__file__).resolve().parents[1] / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    )
    config_path = Path(args.config)
    log_doc = ExperimentDocument(args.log_doc)

    # -- Load & validate --
    try:
        experiment = ExperimentLoader.load(config_path)
    except ExperimentLoaderError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected error loading config: {exc}", file=sys.stderr)
        return 1

    # -- Build intervention --
    intervention = _build_intervention(experiment.config)

    # -- Build orchestrator & execute --
    try:
        from societyxai.core.orchestrator import Orchestrator

        orchestrator = Orchestrator.from_experiment(experiment)
        orchestrator.log_sink = log_doc
        log_doc.heading(
            f"{experiment.config.run_id} · {experiment.config.architecture or 'deliberation'} · "
            f"topology={experiment.config.topology.kind} · provider={experiment.config.provider}"
        )
        log_doc.write(f"- task: {experiment.task.question}\n- ground_truth: {experiment.task.ground_truth}")
        if intervention is not None:
            orchestrator.interventions = [intervention]
        result = orchestrator.run()
    except Exception as exc:
        print(f"Error running experiment: {exc}", file=sys.stderr)
        return 1

    # -- Persist trace --
    trace_path: Path | None = None
    if result.trace is not None:
        try:
            trace_path = result.save_trace(directory=args.output_dir)
        except Exception as exc:
            print(f"Warning: could not persist trace: {exc}", file=sys.stderr)

    # -- Summary --
    print(_format_summary(result, trace_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
