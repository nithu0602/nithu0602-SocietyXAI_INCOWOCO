# Seminar monitor — seminar-social-default-social-campus-messaging-ban

- task: `social-campus-messaging-ban`
- ground_truth: **reject**
- final: **reject** correct=True
- consensus: 0.75
- divergence: 0.4
- converged: round -1
- conformity: 0.0
- first correct proposer: rahul
- influence totals: {'rahul': 4, 'mei': 3, 'ilya': 2, 'noor': 1}
- empty reasoning rate: 0.4444444444444444

## Final positions

- `rahul` (advocate, meta-llama/llama-3.3-70b-instruct): **reject** conf=0.9 evidence=['e1', 'e2', 'e3', 'e4']
- `mei` (critic, gemini-3.6-flash): **reject** conf=1.0 evidence=[]
- `ilya` (fact_checker, deepseek/deepseek-chat): **reject** conf=0.95 evidence=['e1', 'e2', 'e3', 'e4']
- `noor` (impact_analyst, qwen/qwen3.5-flash-02-23): **neutral** conf=1.0 evidence=[]
- `asha` (moderator, openai/gpt-oss-120b): **reject** conf=0.92 evidence=['e1', 'e2', 'e3', 'e4']
