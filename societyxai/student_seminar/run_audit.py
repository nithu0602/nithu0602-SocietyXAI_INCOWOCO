"""Run the five INCoWoCo aptitude items and write a full log per question."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PACK_DIR = Path(__file__).resolve().parent
ROOT = PACK_DIR.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from societyxai.core.orchestrator import Orchestrator
from societyxai.utils.document_log import ExperimentDocument
from societyxai.utils.envfile import load_env_file

from student_seminar.build import build
from student_seminar.monitor import format_report, report, write_report

AUDIT_DIR = PACK_DIR / "questions" / "audit"
OUT_DIR = PACK_DIR / "runs" / "audit"
QUESTIONS = [
    "01-mislabeled-boxes.yaml",
    "04-late-penalty.yaml",
    "05-sequence.yaml",
    "06-unreliable-witnesses.yaml",
    "08-line-arrangement.yaml",
]


def _prepare(experiment) -> None:
    experiment.config.adjudicator_ids = []
    experiment.config.max_tokens = 512
    experiment.society.visibility.independent_first_round = True


def _write_full_log(question_path: Path, monitor_text: str, turn_log: Path, trace_path: Path) -> Path:
    dest = OUT_DIR / f"FULL_LOG_{trace_path.stem}.md"
    parts = [
        f"# Full seminar log — {question_path.name}\n",
        f"Question file: `{question_path}`\n",
        "Round 1 is independent (no messages, no majority, no confidence). "
        "Round 2 is the debate. All five students speak both rounds. max_tokens=512.\n",
        "\n---\n\n# Monitor\n\n",
        monitor_text,
        "\n---\n\n# Turn-by-turn experiment log\n\n",
        turn_log.read_text(encoding="utf-8"),
        "\n---\n\n# Machine trace (JSON)\n\n```json\n",
        trace_path.read_text(encoding="utf-8"),
        "\n```\n",
    ]
    dest.write_text("".join(parts), encoding="utf-8")
    return dest


def run_one(filename: str) -> dict:
    question_path = AUDIT_DIR / filename
    print(f"\n=== {filename} ===", flush=True)
    experiment = build(
        case="aptitude",
        order="default",
        question_path=question_path,
    )
    _prepare(experiment)
    turn_log = OUT_DIR / f"{experiment.config.run_id}-turns.md"
    if turn_log.exists():
        turn_log.unlink()
    log_doc = ExperimentDocument(turn_log)
    orchestrator = Orchestrator.from_experiment(experiment)
    orchestrator.log_sink = log_doc
    log_doc.heading(
        f"{experiment.config.run_id} · independent-then-debate · order=default"
    )
    log_doc.write(
        f"- task: {experiment.task.question}\n- ground_truth: {experiment.task.ground_truth}"
    )
    result = orchestrator.run()
    if result.trace is None:
        raise RuntimeError(f"No trace for {filename}")
    trace_path = result.save_trace(directory=OUT_DIR)
    payload = report(result.trace)
    monitor_path = write_report(result.trace, OUT_DIR / f"{experiment.config.run_id}-monitor.md")
    monitor_text = format_report(payload)
    print(monitor_text, flush=True)
    full = _write_full_log(question_path, monitor_text, turn_log, Path(trace_path))
    print(f"Full log: {full}", flush=True)
    summary = {
        "question_file": filename,
        "task_id": payload.get("task_id"),
        "ground_truth": payload.get("ground_truth"),
        "final_decision": payload.get("final_decision"),
        "correct": payload.get("correct"),
        "consensus_score": payload.get("consensus_score"),
        "conformity_index": payload.get("conformity_index"),
        "first_correct_proposer": payload.get("first_correct_proposer"),
        "empty_reasoning_rate": payload.get("parse_quality", {}).get("empty_reasoning_rate"),
        "position_counts": payload.get("position_counts"),
        "finalists": {
            aid: {
                "position": row.get("position"),
                "confidence": row.get("confidence"),
                "model_id": row.get("model_id"),
                "reasoning": (row.get("reasoning") or "")[:400],
            }
            for aid, row in (payload.get("finalists") or {}).items()
        },
        "full_log": str(full),
        "monitor": str(monitor_path),
        "trace": str(trace_path),
    }
    return summary


def main() -> int:
    load_env_file(ROOT / ".env", ROOT.parent / ".env", Path.cwd() / ".env")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summaries = []
    for name in QUESTIONS:
        summaries.append(run_one(name))
    index = OUT_DIR / "AUDIT_INDEX.json"
    index.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print(f"\nIndex: {index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
