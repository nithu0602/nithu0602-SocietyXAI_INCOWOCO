from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


class ExperimentDocument:
    """Append-only markdown log of every experiment turn. No model is used."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            stamp = datetime.now(timezone.utc).isoformat()
            self.path.write_text(
                f"# SocietyXAI Experiment Log\n\nStarted: {stamp}\n\n",
                encoding="utf-8",
            )

    def write(self, text: str) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(text.rstrip() + "\n")
            handle.flush()

    def heading(self, title: str) -> None:
        self.write(f"\n## {title}\n")

    def turn(
        self,
        *,
        round_num: int,
        turn_index: int,
        agent_id: str,
        role: str,
        model_id: str,
        provider: str,
        position: str,
        confidence: float,
        evidence_ids: list[str],
        reasoning: str,
        response: str,
    ) -> None:
        self.write(
            f"### Round {round_num} · turn {turn_index} · `{agent_id}` ({role})\n"
            f"- provider: `{provider}` model: `{model_id}`\n"
            f"- position: **{position}** confidence: {confidence:.2f}\n"
            f"- evidence_ids: {evidence_ids}\n"
            f"- reasoning: {reasoning}\n"
            f"- raw:\n\n```\n{response[:4000]}\n```\n"
        )
