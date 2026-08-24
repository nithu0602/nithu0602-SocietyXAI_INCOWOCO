# SocietyXAI

Causal explainability of belief dynamics and consensus in multi-agent LLM societies.

The **full project record** (what was built, every live run, every example) is:

**[docs/PROJECT.md](docs/PROJECT.md)**

The budget heterogeneous mix figure is kept at [`image.png`](image.png) and [`docs/figures/heterogeneous-mix-budget.png`](docs/figures/heterogeneous-mix-budget.png).

## Layout

```
docs/PROJECT.md          project history + all Groq results
docs/original-plan.pdf   source research plan
societyxai/              canonical runnable package
```

## Run

```bash
cd societyxai
pip install -e .
python -m pytest -q
```

Set `GROQ_API_KEY` in `.env` (this folder). Then:

```bash
python -m societyxai run --config configs/experiments/complete_healthcare_consultation.yaml --log-doc docs/EXPERIMENT_LOG.md
python scripts/run_complete_architectures.py
```

There is **no judge model**. Agents debate; the orchestrator is code.

Live complete-architecture traces: `societyxai/runs/complete-*.json`.
Turn logs: `societyxai/docs/EXPERIMENT_LOG.md`.
