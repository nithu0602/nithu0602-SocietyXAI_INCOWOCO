"""Process-audit metrics for a student-seminar RunTrace."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from societyxai.traces.schema import RunTrace
from societyxai.utils.influence import influence_matrix
from societyxai.utils.metrics import belief_divergence, consensus_score, convergence_round
from societyxai.utils.paper_metrics import conformity_index
from societyxai.utils.positions import normalize_position


def _final_rows(trace: RunTrace) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for row in trace.agent_traces:
        last[row.agent_id] = {
            "position": row.belief.position,
            "confidence": row.belief.confidence,
            "evidence_ids": list(row.belief.evidence_ids),
            "reasoning": row.belief.reasoning_trace,
            "model_id": row.model_id,
            "role": row.role,
        }
    return last


def parse_quality(trace: RunTrace) -> dict[str, float]:
    total = len(trace.agent_traces) or 1
    empty_reason = sum(1 for row in trace.agent_traces if not row.belief.reasoning_trace.strip())
    empty_evidence = sum(1 for row in trace.agent_traces if not row.belief.evidence_ids)
    return {
        "empty_reasoning_rate": empty_reason / total,
        "empty_evidence_rate": empty_evidence / total,
    }


def first_correct_proposer(trace: RunTrace) -> str | None:
    """First agent whose position matches ground truth (aptitude / labelled social)."""
    if not trace.ground_truth:
        return None
    gold = normalize_position(trace.ground_truth)
    ordered = sorted(trace.agent_traces, key=lambda row: (row.round, row.turn_index))
    for row in ordered:
        if normalize_position(row.belief.position) == gold:
            return row.agent_id
    return None


def influence_totals(trace: RunTrace) -> dict[str, int]:
    matrix = influence_matrix(trace)
    return {source: sum(targets.values()) for source, targets in matrix.items()}


def report(trace: RunTrace) -> dict[str, Any]:
    finals = _final_rows(trace)
    positions = [row["position"] for row in finals.values()]
    counts = Counter(normalize_position(pos) for pos in positions)
    quality = parse_quality(trace)
    return {
        "run_id": trace.run_id,
        "task_id": trace.task_id,
        "ground_truth": trace.ground_truth,
        "final_decision": trace.final_decision,
        "correct": trace.correctness,
        "consensus_score": consensus_score(trace),
        "belief_divergence": belief_divergence(trace),
        "convergence_round": convergence_round(trace),
        "conformity_index": conformity_index(trace),
        "position_counts": dict(counts),
        "first_correct_proposer": first_correct_proposer(trace),
        "influence_totals": influence_totals(trace),
        "parse_quality": quality,
        "finalists": finals,
    }


def format_report(payload: dict[str, Any]) -> str:
    lines = [
        f"# Seminar monitor — {payload.get('run_id', '')}",
        "",
        f"- task: `{payload.get('task_id')}`",
        f"- ground_truth: **{payload.get('ground_truth')}**",
        f"- final: **{payload.get('final_decision')}** correct={payload.get('correct')}",
        f"- consensus: {payload.get('consensus_score')}",
        f"- divergence: {payload.get('belief_divergence')}",
        f"- converged: round {payload.get('convergence_round')}",
        f"- conformity: {payload.get('conformity_index')}",
        f"- first correct proposer: {payload.get('first_correct_proposer')}",
        f"- influence totals: {payload.get('influence_totals')}",
        f"- empty reasoning rate: {payload.get('parse_quality', {}).get('empty_reasoning_rate')}",
        "",
        "## Final positions",
        "",
    ]
    for agent_id, row in (payload.get("finalists") or {}).items():
        lines.append(
            f"- `{agent_id}` ({row.get('role')}, {row.get('model_id')}): "
            f"**{row.get('position')}** conf={row.get('confidence')} "
            f"evidence={row.get('evidence_ids')}"
        )
    return "\n".join(lines) + "\n"


def write_report(trace: RunTrace, path: str | Path) -> Path:
    payload = report(trace)
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(format_report(payload), encoding="utf-8")
    json_path = dest.with_suffix(".json")
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return dest
