# Research Protocol: Pilot Experiment 1 — Minority Correctness in Heterogeneous vs. Homogeneous AI Societies

## Research Question

Does model diversity (heterogeneous vs. homogeneous agent composition) change the dynamics of consensus accuracy, false-consensus formation, belief diversity, convergence speed, influence concentration, and minority recovery when a correct minority faces an incorrect majority?

This experiment directly supports RQ4 (consensus accuracy), RQ5 (false consensus), and RQ6 (minority influence) from the research specification.

## Independent Variable

**Model composition** (2 levels):
- **Homogeneous**: All 5 agents use `llama3.1:8b`
- **Heterogeneous**: 3 agents use `llama3.1:8b`, 2 agents use `qwen2.5-coder:1.5b-base`

## Controlled Variables

All variables held constant across conditions:

| Variable | Value |
|---|---|
| Number of agents | 5 |
| Number of rounds | 3 |
| Topology | complete (all agents see all messages) |
| Temperature | 0.0 |
| Seed | 42 |
| Max tokens | 256 |
| System prompt | Identical across all conditions |
| Task question | Identical across all conditions |
| Evidence (4 items) | Identical across all conditions |
| Ground truth | "approve" |
| Speaker order | agent_0 → agent_1 → agent_2 → agent_3 → agent_4 |
| Belief parser | structured (JSON with heuristic fallback) |
| Stopping rule | max_rounds |
| Visibility | previous_messages=true, confidence=false, majority_position=false |

## Task Design

**Question**: "Should the committee approve the proposed funding initiative?"

**Ground truth**: "approve"

**Evidence** (4 items, unanimously supporting approval):
1. Pilot study exceeded benchmarks by 15-20%
2. Two independent reviewers recommend full funding
3. Budget efficiency at 92% (above 80% threshold)
4. University committed matching funds

**Initial bias**: System prompt introduces cost-overrun concerns to create initial rejection tendency.

**Minority-correct structure**: agent_0 is positioned to speak first and must process all 4 evidence items before the majority hears them. The correct position is "approve"; the initial bias favors "reject."

## Agent Model Assignment

### Homogeneous condition
| Agent | Model | Role |
|---|---|---|
| agent_0 | llama3.1:8b | Correct minority |
| agent_1 | llama3.1:8b | Incorrect majority |
| agent_2 | llama3.1:8b | Incorrect majority |
| agent_3 | llama3.1:8b | Incorrect majority |
| agent_4 | llama3.1:8b | Incorrect majority |

### Heterogeneous condition
| Agent | Model | Role |
|---|---|---|
| agent_0 | llama3.1:8b | Correct minority (stronger model) |
| agent_1 | llama3.1:8b | Incorrect majority (stronger model) |
| agent_2 | llama3.1:8b | Incorrect majority (stronger model) |
| agent_3 | qwen2.5-coder:1.5b-base | Incorrect majority (weaker/base model) |
| agent_4 | qwen2.5-coder:1.5b-base | Incorrect majority (weaker/base model) |

**Model capability note**: `qwen2.5-coder:1.5b-base` is a 1.5B-parameter base model (not instruction-tuned). It is significantly weaker than `llama3.1:8b` and may produce less structured, less evidence-responsive outputs. This is a limitation of the current pilot — the model diversity difference confounds model family with instruction-tuning level.

## Intervention Condition (Counterfactual)

The counterfactual condition modifies the heterogeneous setup:

- **Baseline**: agent_0 participates normally, presenting evidence-based approval reasoning
- **Counterfactual intervention**: In round 1, agent_0 receives an overriding instruction injected into their prompt that forces them to respond with "reject" instead of their natural evidence-based "approve"

This tests: *What happens to the group outcome when the correct minority's contribution is suppressed?*

**Intervention mechanism**: `MessageInjectionIntervention` targeting agent_0 in round 1, injecting a forced-response override.

## YAML Configuration Files

| Condition | Config file |
|---|---|
| Homogeneous baseline | `configs/experiments/homogeneous_minority_correct.yaml` |
| Heterogeneous baseline | `configs/experiments/heterogeneous_minority_correct.yaml` |
| Heterogeneous counterfactual | `configs/experiments/heterogeneous_minority_counterfactual.yaml` |

## Metrics Collected

From the existing framework (no new metrics):

| Metric | Source | What it measures |
|---|---|---|
| `consensus_score` | `societyxai.utils.metrics` | Final agreement level [0-1] |
| `belief_divergence` | `societyxai.utils.metrics` | Fraction of agent pairs with different positions |
| `convergence_round` | `societyxai.utils.metrics` | Earliest round of full agreement (-1 if never) |
| `influence_matrix` | `societyxai.utils.influence` | Candidate influence screening (observational) |
| `final_decision` | RunTrace | Group's final position |
| `correctness` | RunTrace | Whether final decision matches ground truth |
| Per-agent belief trajectories | AgentTrace entries | Position changes across rounds |
| Per-turn model routing | ExecutionTurn entries | Which model was used for each turn |
| Intervention metadata | InterventionTrace | Confirmation intervention was applied |

## What Constitutes a Successful/Interesting Outcome

### Consensus accuracy
- If heterogeneous society reaches correct consensus more often → diversity may improve accuracy
- If homogeneous society reaches correct consensus more often → model capability may matter more than diversity

### False consensus
- High consensus_score but correctness=False → false consensus
- Compare false-consensus rates between homogeneous and heterogeneous conditions

### Minority recovery
- Track agent_0's belief trajectory across rounds
- If agent_0 shifts from correct to incorrect under majority pressure → minority capitulation
- If agent_0 maintains correct position despite pressure → minority resilience

### Influence concentration
- If influence_matrix shows disproportionate influence from one model family → unequal influence
- If influence is more evenly distributed in heterogeneous society → diversity promotes balanced discourse

### Convergence speed
- Compare convergence_round between conditions
- Faster convergence may indicate groupthink; slower may indicate productive deliberation

## Methodological Limitations

1. **Single seed**: Results are from a single deterministic run (seed=42). Statistical claims require multiple seeds.
2. **Model asymmetry**: The heterogeneous condition mixes an 8B instruction-tuned model with a 1.5B base model. Model family and capability level are confounded.
3. **Observational influence**: `influence_matrix` is a screening metric, not causal evidence. True causal claims require the counterfactual intervention comparison.
4. **Base model limitations**: `qwen2.5-coder:1.5b-base` may not reliably produce structured JSON responses, potentially falling back to heuristic parsing.
5. **System prompt bias**: The initial rejection bias is embedded in the system prompt, not derived from evidence assessment.

## Running the Experiments

### Mock validation (no Ollama required)
```bash
python -m pytest tests/test_heterogeneous.py -v
```

### Real-model execution
```bash
# Homogeneous condition
python -m societyxai run --config configs/experiments/homogeneous_minority_correct.yaml

# Heterogeneous condition
python -m societyxai run --config configs/experiments/heterogeneous_minority_correct.yaml

# Counterfactual condition (heterogeneous + intervention)
python -m societyxai run --config configs/experiments/heterogeneous_minority_counterfactual.yaml
```

### Trace analysis
Traces are saved as JSON under `runs/` and can be loaded programmatically:
```python
from societyxai.traces.persistence import load_trace
from societyxai.utils.metrics import consensus_score, belief_divergence, convergence_round
from societyxai.utils.influence import influence_matrix

trace = load_trace("runs/pilot-heterogeneous.json")
print(consensus_score(trace))
print(belief_divergence(trace))
print(convergence_round(trace))
print(influence_matrix(trace))
```
