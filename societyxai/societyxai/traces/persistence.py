from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from societyxai.traces.schema import RunTrace


def save_trace(
    trace: RunTrace,
    directory: str | Path = "runs",
    filename: str | None = None,
) -> Path:
    """Serialize a RunTrace to JSON and save it to the specified directory.

    Args:
        trace: The RunTrace instance to persist.
        directory: Target directory (default: 'runs').
        filename: Optional custom filename (default: '{trace.run_id}.json').

    Returns:
        The Path to the saved JSON file.
    """
    target_dir = Path(directory)
    target_dir.mkdir(parents=True, exist_ok=True)

    actual_filename = filename if filename is not None else f"{trace.run_id}.json"
    if not actual_filename.endswith(".json"):
        actual_filename = f"{actual_filename}.json"

    file_path = target_dir / actual_filename
    file_path.write_text(trace.model_dump_json(indent=2), encoding="utf-8")
    return file_path


def load_trace(path: str | Path) -> RunTrace:
    """Load and validate a RunTrace from a JSON file.

    Args:
        path: Path to the JSON trace file.

    Returns:
        A validated RunTrace instance.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValidationError: If the JSON content does not match the RunTrace schema.
    """
    from societyxai.traces.schema import RunTrace

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Trace file not found: {file_path}")

    content = file_path.read_text(encoding="utf-8")
    return RunTrace.model_validate_json(content)
