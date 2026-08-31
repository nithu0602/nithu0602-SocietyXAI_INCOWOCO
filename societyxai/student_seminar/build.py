"""Assemble a student-seminar experiment from roster + question inbox."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml

from societyxai.config.loader import ExperimentLoader
from societyxai.config.schema import ExperimentConfig
from societyxai.models.factory import provider_has_credentials

PACK_DIR = Path(__file__).resolve().parent
CASE = Literal["social", "aptitude"]
ORDER = Literal["default", "reverse", "weak_first"]


def load_roster(path: Path | None = None) -> dict[str, Any]:
    roster_path = path or (PACK_DIR / "roster.yaml")
    data = yaml.safe_load(roster_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "students" not in data:
        raise ValueError(f"Roster missing students: {roster_path}")
    return data


def load_question(path: str | Path) -> dict[str, Any]:
    question_path = Path(path)
    if not question_path.is_file():
        raise FileNotFoundError(f"Question file not found: {question_path}")
    data = yaml.safe_load(question_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "question" not in data:
        raise ValueError(f"Question file must contain a 'question' field: {question_path}")
    if "ground_truth" not in data:
        raise ValueError(f"Question file must contain 'ground_truth': {question_path}")
    return data


def default_question_path(case: str) -> Path:
    if case == "social":
        return PACK_DIR / "questions" / "INBOX_SOCIAL.yaml"
    if case == "aptitude":
        return PACK_DIR / "questions" / "INBOX_APTITUDE.yaml"
    raise ValueError(f"Unknown case '{case}'. Use social or aptitude.")


def speaker_order(roster: dict[str, Any], case: str, order: str) -> list[str]:
    try:
        return list(roster["orders"][case][order])
    except KeyError as exc:
        raise ValueError(f"No speaker order for case={case} order={order}") from exc


def apply_fallback(roster: dict[str, Any], fallback: str | None) -> dict[str, Any]:
    """If fallback is groq, rewrite missing-key providers onto Groq models."""
    if not fallback:
        return roster
    if fallback.lower() != "groq":
        raise ValueError("Only fallback='groq' is supported.")
    students = {}
    for agent_id, spec in roster["students"].items():
        row = dict(spec)
        if not provider_has_credentials(row["provider"]):
            row["provider"] = "groq"
            row["model_id"] = row["groq_fallback_model"]
            row["used_fallback"] = True
        students[agent_id] = row
    out = dict(roster)
    out["students"] = students
    return out


def build_experiment_dict(
    case: str,
    order: str = "default",
    question_path: str | Path | None = None,
    fallback: str | None = None,
    roster_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (experiment_section, task_section) ready for ExperimentLoader.build."""
    roster = apply_fallback(load_roster(roster_path), fallback)
    question = load_question(question_path or default_question_path(case))
    roles = roster["social_roles"] if case == "social" else roster["aptitude_roles"]
    order_ids = speaker_order(roster, case, order)
    students = roster["students"]

    support_means = question.get("support_means", "support the proposal or claimed answer")
    reject_means = question.get("reject_means", "reject the proposal or claimed answer")
    system_prompt = (
        f"{roster['shared_brief']} support means {support_means}. "
        f"reject means {reject_means}."
    )

    agent_models = {aid: students[aid]["model_id"] for aid in order_ids}
    agent_providers = {aid: students[aid]["provider"] for aid in order_ids}
    agent_roles = {aid: roles[aid]["role"] for aid in order_ids}
    agent_prompts = {
        aid: f"{system_prompt}\nYour seminar role is {roles[aid]['role']}. {roles[aid]['prompt']}"
        for aid in order_ids
    }

    default_provider = agent_providers[order_ids[0]]
    default_model = agent_models[order_ids[0]]
    adjudicators = list(roster.get("adjudicators", {}).get(case, []))

    experiment = {
        "run_id": f"seminar-{case}-{order}-{question.get('id', 'custom')}",
        "task_id": str(question.get("id", f"seminar-{case}")),
        "seed": 42,
        "model_id": default_model,
        "provider": default_provider,
        "temperature": 0.2,
        "max_tokens": 256,
        "architecture": "seminar",
        "adjudicator_ids": adjudicators,
        "system_prompt": system_prompt,
        "number_of_agents": len(order_ids),
        "number_of_rounds": 2,
        "topology": {"kind": "complete"},
        "speaker_order": {"order": order_ids, "deterministic": True},
        "visibility": {
            "previous_messages": True,
            "confidence": True,
            "majority_position": True,
        },
        "intervention": {"type": "none", "target_id": order_ids[0]},
        "parser_version": "structured",
        "stopping_rule": "max_rounds",
        "agent_models": agent_models,
        "agent_providers": agent_providers,
        "agent_roles": agent_roles,
        "agent_prompts": agent_prompts,
    }

    task = {
        "task_id": experiment["task_id"],
        "question": question["question"],
        "ground_truth": question["ground_truth"],
        "difficulty": question.get("difficulty", "medium"),
        "reference_solution": question.get("reference_solution", ""),
        "evidence": list(question.get("evidence") or []),
    }
    return experiment, task


def build(
    case: str,
    order: str = "default",
    question_path: str | Path | None = None,
    fallback: str | None = None,
    roster_path: Path | None = None,
):
    """Return a BuiltExperiment for the seminar pack."""
    experiment_data, task_data = build_experiment_dict(
        case, order, question_path, fallback, roster_path
    )
    config = ExperimentConfig(**experiment_data)
    built = ExperimentLoader.build(config, task_data)
    students = apply_fallback(load_roster(roster_path), fallback)["students"]
    for agent in built.society.agents:
        score = students.get(agent.agent_id, {}).get("capability_score")
        if score is not None:
            agent.capability_score = float(score)
    return built
