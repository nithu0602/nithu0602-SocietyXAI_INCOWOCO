"""Run a student seminar from the question inbox.

Examples (from the societyxai/ folder)::

    python student_seminar/run.py --case social --order default --fallback groq
    python student_seminar/run.py --case aptitude --question student_seminar/questions/INBOX_APTITUDE.yaml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PACK_DIR = Path(__file__).resolve().parent
ROOT = PACK_DIR.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from societyxai.config.loader import ExperimentLoaderError
from societyxai.core.orchestrator import Orchestrator
from societyxai.utils.document_log import ExperimentDocument
from societyxai.utils.envfile import load_env_file

from student_seminar.build import build, default_question_path
from student_seminar.monitor import format_report, report, write_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the five-student heterogeneous seminar."
    )
    parser.add_argument("--case", choices=("social", "aptitude"), required=True)
    parser.add_argument(
        "--order",
        choices=("default", "reverse", "weak_first"),
        default="default",
        help="default=role-natural (closer last). Also run reverse before claiming dominance.",
    )
    parser.add_argument(
        "--question",
        default=None,
        help="YAML question file. Defaults to questions/INBOX_SOCIAL.yaml or INBOX_APTITUDE.yaml.",
    )
    parser.add_argument(
        "--fallback",
        default=None,
        help="Use groq when a lab key is missing (openai/gpt-oss-120b vs 20b by strength).",
    )
    parser.add_argument("--output-dir", default=str(PACK_DIR / "runs"))
    parser.add_argument("--log-doc", default=str(PACK_DIR / "EXPERIMENT_LOG.md"))
    args = parser.parse_args(argv)

    load_env_file(
        ROOT / ".env",
        ROOT.parent / ".env",
        Path.cwd() / ".env",
    )

    question_path = Path(args.question) if args.question else default_question_path(args.case)
    print(f"Question file: {question_path}")
    print(f"Case={args.case}  order={args.order}  fallback={args.fallback or 'none'}")

    try:
        experiment = build(
            case=args.case,
            order=args.order,
            question_path=question_path,
            fallback=args.fallback,
        )
    except (ExperimentLoaderError, ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    log_doc = ExperimentDocument(args.log_doc)
    orchestrator = Orchestrator.from_experiment(experiment)
    orchestrator.log_sink = log_doc
    log_doc.heading(
        f"{experiment.config.run_id} · seminar · order={args.order} · "
        f"provider={experiment.config.provider}"
    )
    log_doc.write(
        f"- task: {experiment.task.question}\n- ground_truth: {experiment.task.ground_truth}"
    )

    try:
        result = orchestrator.run()
    except Exception as exc:
        print(f"Error running seminar: {exc}", file=sys.stderr)
        return 1

    if result.trace is None:
        print("No trace produced.", file=sys.stderr)
        return 1

    trace_path = result.save_trace(directory=args.output_dir)
    report_path = write_report(
        result.trace,
        Path(args.output_dir) / f"{experiment.config.run_id}-monitor.md",
    )
    print(format_report(report(result.trace)))
    print(f"Trace   : {trace_path}")
    print(f"Monitor : {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
