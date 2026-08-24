"""Run the four complete architectures on Groq and append every turn to the log doc."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from societyxai.__main__ import main
from societyxai.utils.envfile import load_env_file

CONFIGS = [
    "configs/experiments/complete_healthcare_consultation.yaml",
    "configs/experiments/complete_legal_adversarial.yaml",
    "configs/experiments/complete_finance_committee.yaml",
    "configs/experiments/complete_esg_negotiation.yaml",
    "configs/experiments/complete_esg_remove_finance.yaml",
    "configs/experiments/complete_esg_heterogeneous.yaml",
]


def run() -> int:
    load_env_file(ROOT / ".env", ROOT.parent / ".env")
    log_doc = ROOT / "docs" / "EXPERIMENT_LOG.md"
    for config in CONFIGS:
        print(f"\n=== {config} ===")
        code = main(
            [
                "run",
                "--config",
                str(ROOT / config),
                "--output-dir",
                str(ROOT / "runs"),
                "--log-doc",
                str(log_doc),
            ]
        )
        if code != 0:
            print(f"FAILED {config} exit={code}")
            return code
        time.sleep(12)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
