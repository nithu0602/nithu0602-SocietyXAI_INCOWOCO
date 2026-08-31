# SocietyXAI

Canonical research framework for **causal explainability of belief dynamics** in multi-agent LLM societies.

Project-level history and **all live experiment results:** [`../docs/PROJECT.md`](../docs/PROJECT.md).

This package is the unified engine: YAML experiments, complete topologies, Groq + Ollama, counterfactual interventions, paper metrics, and four complete architectures (consultation, adversarial, committee, negotiation).

**No judge model.** The only LLMs are the experiment agents.

```bash
cd societyxai
pip install -e .
python -m pytest -q
```

Set `GROQ_API_KEY` in `.env` (this folder or the repo root one level up).

```bash
python -m societyxai run --config configs/experiments/complete_healthcare_consultation.yaml --log-doc docs/EXPERIMENT_LOG.md
python scripts/run_complete_architectures.py
```

## Complete architectures

| Config | Architecture | Topology | Question |
|---|---|---|---|
| `complete_healthcare_consultation.yaml` | specialist consultation | complete | steroids now vs wait |
| `complete_legal_adversarial.yaml` | adversarial hearing | complete | strike the non-compete |
| `complete_finance_committee.yaml` | risk committee | complete | aggressive long? |
| `complete_esg_negotiation.yaml` | stakeholder negotiation | complete | terminate supplier? |
| `complete_esg_remove_finance.yaml` | same + agent-removal | complete | counterfactual |
| `complete_esg_heterogeneous.yaml` | 120B + 20B mix | complete | size diversity |

Every turn is appended to `docs/EXPERIMENT_LOG.md`. JSON traces go to `runs/`.

Ollama remains supported (`provider: ollama`) for local replication.

The five-student heterogeneous pack (question inbox, seminar roles, speaker-order controls, monitor metrics) lives in [`student_seminar/`](student_seminar/README.md).
