# SocietyXAI

Causal explainability of belief dynamics and consensus in multi-agent LLM societies.

The **final project document** (history, Phase 1 Groq niches, Phase 2 five-family seminar, all result tables) is:

**[docs/PROJECT.md](docs/PROJECT.md)**

Manuscript-shaped Results cut: **[docs/paper-results.md](docs/paper-results.md)**.

There is **no judge model**. Agents debate; the orchestrator is code.

## Layout

```
docs/PROJECT.md            final record + all live results
docs/paper-results.md      paper Results section
docs/original-plan.pdf     source research plan
societyxai/                canonical runnable package
```

## Run

```bash
cd societyxai
pip install -e .
python -m pytest -q
```

**Phase 1 (Groq complete architectures).** Set `GROQ_API_KEY` in the repo-root `.env` (this folder).

```bash
python -m societyxai run --config configs/experiments/complete_healthcare_consultation.yaml --log-doc docs/EXPERIMENT_LOG.md
```

**Phase 2 (heterogeneous seminar).** Also `GEMINI_API_KEY` and `OPENROUTER_API_KEY` (or an OpenRouter `sk-or-` key in `DASHSCOPE_API_KEY`).

```bash
python student_seminar/ping_keys.py
python student_seminar/run.py --case social --order default
python student_seminar/run_audit.py
```

Groq traces: `societyxai/runs/complete-*.json`.  
Seminar / audit logs: `societyxai/student_seminar/runs/`.
