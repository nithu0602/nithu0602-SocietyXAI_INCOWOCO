# Keys for the free / pay-as-you-go seminar mix

Put keys in the **repo-root** `.env` next to this package’s parent folder (never commit that file). Names must match exactly.

This mix needs **three** keys:

```
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=...
OPENROUTER_API_KEY=sk-or-v1-...
```

If the OpenRouter key is already in `DASHSCOPE_API_KEY` and starts with `sk-or-`, the engine accepts that. You can leave it there.

Until Groq + Gemini + OpenRouter are present, run with `--fallback groq`.

---

## 1. Groq — Asha (GPT-OSS 120B), free

- Console: https://console.groq.com/keys
- Env: `GROQ_API_KEY`
- Model: `openai/gpt-oss-120b`
- Cost: free / developer tier (rate limits only)

## 2. Google Gemini — Mei (3.6 Flash), free tier

- Studio: https://aistudio.google.com/apikey
- Env: `GEMINI_API_KEY`
- Model: `gemini-3.6-flash` (2.5 Flash is closed to new keys)
- Cost: AI Studio free tier. Rate-limited; no card required.

## 3. OpenRouter — Rahul, Ilya, Noor, pay-as-you-go

- https://openrouter.ai → API keys. Add a small credit pack ($5 covers this seminar many times).
- Env: `OPENROUTER_API_KEY`
- Models:
  - Rahul: `meta-llama/llama-3.3-70b-instruct` (Meta)
  - Ilya: `deepseek/deepseek-chat` (DeepSeek, no DeepSeek wallet)
  - Noor: `qwen/qwen3.5-flash-02-23` (Alibaba, no DashScope India signup)

Cheap precheck from `societyxai/`:

```bash
python student_seminar/ping_keys.py
```

---

## Parked (not used until you fund those wallets)

- Anthropic Claude Sonnet 5 — Asha’s old seat
- OpenAI GPT-5.6 Luna — Rahul’s old seat
- DeepSeek platform key — Ilya’s old seat
- Alibaba DashScope — blocked for new India accounts
