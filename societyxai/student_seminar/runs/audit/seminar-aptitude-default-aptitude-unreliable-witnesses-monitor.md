# Seminar monitor — seminar-aptitude-default-aptitude-unreliable-witnesses

- task: `aptitude-unreliable-witnesses`
- ground_truth: **support**
- final: **support** correct=True
- consensus: 0.75
- divergence: 0.4
- converged: round -1
- conformity: 0.0
- first correct proposer: rahul
- influence totals: {}
- empty reasoning rate: 0.4

## Final positions

- `rahul` (solver, meta-llama/llama-3.3-70b-instruct): **support** conf=1.0 evidence=['e1', 'e2', 'e3']
- `mei` (skeptic, gemini-3.6-flash): **support** conf=1.0 evidence=[]
- `ilya` (alt_path, deepseek/deepseek-chat): **support** conf=1.0 evidence=['e1', 'e2', 'e3']
- `noor` (formalizer, qwen/qwen3.5-flash-02-23): **neutral** conf=1.0 evidence=[]
- `asha` (closer, openai/gpt-oss-120b): **support** conf=1.0 evidence=['e1', 'e2', 'e3']
