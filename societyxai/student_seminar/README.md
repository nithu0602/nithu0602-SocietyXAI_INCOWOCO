# Student seminar (heterogeneous, free / pay-as-you-go)

Five named students discuss **one question you drop in**. Same people and models on every run. Hats change by case. The engine is still SocietyXAI (complete topology, JSON beliefs, paper metrics). There is no judge model.

This mix avoids prepaid Anthropic / OpenAI / DeepSeek wallets. Hosts: Groq (free), Gemini (free tier), OpenRouter (pay-as-you-go).

## Should we fix speaker order?

**No. Do not publish from a single order.**

First speaker can lock the table (the Groq legal run already showed role-lock). If Asha (Sonnet, Strong) always speaks last as closer, you cannot tell “Sonnet is strong” from “the last seat wins.”

Run at least two:

| Flag | What it does |
|---|---|
| `--order default` | Role-natural. Advocate/solver first, **moderator/closer last**. Use this as the baseline. |
| `--order reverse` | Same five people, opposite sequence. Required before you claim a model dominated. |
| `--order weak_first` | Noor then Rahul (weaker / mid) speak before Mei, Ilya, Asha. Tests whether a weak opener still anchors. |

Default is the reporting order. Reverse is the control.

## Give the group a question

Edit **one** of these. That is the inbox.

- Social issue: [`questions/INBOX_SOCIAL.yaml`](questions/INBOX_SOCIAL.yaml)
- Aptitude / reasoning: [`questions/INBOX_APTITUDE.yaml`](questions/INBOX_APTITUDE.yaml)

Required fields: `question`, `ground_truth` (`support` or `reject`), `evidence`.  
Optional: `support_means`, `reject_means`, `reference_solution`.

Do not mix a policy vignette and an exam item in the same run. Do not paste copyrighted GPQA/LSAT stems.

## Who sits where

| Student | Model | Family | Cost | Social hat | Aptitude hat |
|---|---|---|---|---|---|
| Asha | GPT-OSS 120B (Groq) | OpenAI OSS | Free | moderator (last) | closer (last) |
| Rahul | Llama 3.3 70B (OpenRouter) | Meta | PAYG | advocate | solver |
| Mei | Gemini 3.6 Flash | Google | Free tier | critic | skeptic |
| Ilya | DeepSeek Chat (OpenRouter) | DeepSeek | PAYG | fact_checker | alt_path |
| Noor | Qwen 3.5 Flash (OpenRouter) | Alibaba | PAYG | impact_analyst | formalizer |

Identities stay fixed so influence can be compared across cases. Gemini 2.5 Flash is closed to new Studio keys; Mei uses 3.6 Flash.

## Run

From `societyxai/`:

```bash
# Structure check (no API): pytest tests/test_student_seminar.py -q

# Live, Groq only (maps missing lab keys onto gpt-oss-120b / 20b by strength)
python student_seminar/run.py --case social --order default --fallback groq
python student_seminar/run.py --case social --order reverse --fallback groq
python student_seminar/run.py --case aptitude --order default --fallback groq
```

Need `GROQ_API_KEY`, `GEMINI_API_KEY`, and `OPENROUTER_API_KEY` (or an OpenRouter `sk-or-` key in `DASHSCOPE_API_KEY`). Then drop `--fallback groq`.

Outputs:

- turns: `student_seminar/EXPERIMENT_LOG.md`
- trace: `student_seminar/runs/*.json`
- monitor: `student_seminar/runs/*-monitor.md` (consensus, conformity, first-correct proposer, influence totals, empty-reasoning rate)

## Metrics the monitor writes

Outcome: final vs gold, consensus score, divergence, convergence round.  
Dominance: first correct proposer, influence totals (who was visible when someone flipped).  
Process: conformity index, empty reasoning / empty evidence rates.

After default **and** reverse exist, compare whether the same model still leads. If the leader changes with order, the finding is speaking-order, not IQ.
