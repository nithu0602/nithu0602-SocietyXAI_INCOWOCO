# SocietyXAI — Project Document

**Paper working title:** causal explainability of belief dynamics and consensus in multi-agent LLM societies.

This file is the **final project record**: what the system is, what was built, what was removed, and **every live experiment so far** — Phase 1 homogeneous Groq niches and Phase 2 five-family heterogeneous seminar (results in §9–§10). A manuscript-shaped cut of the hetero tables also lives in [`paper-results.md`](paper-results.md).

Turn-by-turn Groq logs: [`societyxai/docs/EXPERIMENT_LOG.md`](../societyxai/docs/EXPERIMENT_LOG.md). Groq traces: [`societyxai/runs/`](../societyxai/runs/). Seminar traces and full logs: [`societyxai/student_seminar/runs/`](../societyxai/student_seminar/runs/).

Last updated: **31 August 2026**. Groq complete runs: **24 August 2026**. Heterogeneous seminar: **31 August 2026**. Benchmark freeze for the *parked* paid mix: **27 August 2026**.

---

## 1. What the project is

SocietyXAI studies how a small society of LLM agents **forms, shifts, and locks beliefs** on a high-stakes yes/no decision. The product angle is an **audit of thinking quality**, not a second “judge” model:

- each agent holds a position (`support` / `reject`), a confidence, cited evidence, and a short reasoning trace
- the society talks on a **complete topology** (everyone can see prior messages, confidence, and the current majority)
- the orchestrator is code: visibility filters, speaker order, interventions, parsers, majority vote vs ground truth
- **no judge LLM**. The only models are the agents themselves

Four case-study niches, taken from the original plan ([`original-plan.pdf`](original-plan.pdf)):

| Niche | Architecture | Decision |
|---|---|---|
| Healthcare | specialist consultation | steroids now vs wait for MRI |
| Legal | adversarial hearing | strike a non-compete or keep it |
| Finance | risk committee | aggressive long vs abort |
| ESG | stakeholder negotiation | terminate a supplier or keep the contract |

Each niche is designed for **homogeneous vs heterogeneous** panels, with **counterfactual interventions** (remove an agent, hide majority/confidence, reorder speakers, identity swap). Phase 1 executed the four niches on Groq GPT-OSS (one lab, two sizes). Phase 2 executed a **five-family** student seminar (Meta, Google, DeepSeek, Alibaba, OpenAI-OSS) on aptitude items plus one social vignette.

---

## 2. What we did until now

### 2.1 Two codebases, then one

1. **Early prototype** (this workspace, mid-August 2026) lived under `src/societyxai/`. Groq + dummy backends, four scenario packs, an audit report. Groq later **retired** `llama-3.3-70b-versatile` and `llama-3.1-8b-instant`. That tree is **deleted** (see §8).
2. **Canonical engine** cloned from [nithu0602/societyxai](https://github.com/nithu0602/societyxai): YAML experiments, Ollama, topologies, interventions, traces, paper metrics, 350+ tests.
3. **Merge:** Groq backend, complete-topology YAML packs, markdown experiment log, position normalisation (`approve`/`yes` → `support`), env loading from `.env`.

The runnable project is **`societyxai/`**. Root `README.md` only points here.

### 2.2 Engine behaviour that matters for results

- YAML → `ExperimentLoader` → Society + Task + backend → `Orchestrator.run()`
- Per turn: topology visibility → Groq chat (JSON mode, 429 retries) → `StructuredBeliefParser` → `AgentTrace` + `MessageTrace`
- Agents listed in `adjudicator_ids` (treatment planner, judge, CIO) **speak only in the last round**
- Final decision = majority vote of last-round positions vs `ground_truth`
- Consensus score (paper metric): \(1 - (d-1)/(n-1)\) where \(d\) is the number of distinct final positions and \(n\) is the number of agents. Unanimous → **1.00**. One dissenter in a 5-agent panel → **0.75**

Live model after the Groq retirement:

| Slot | Model |
|---|---|
| Strong / default | `openai/gpt-oss-120b` |
| Weak (heterogeneous) | `openai/gpt-oss-20b` |

Tests after the merge: **359 passed**. Later additions (per-agent providers, OpenRouter, independent first round): seminar pack tests green; visibility test for independent-then-debate included.

### 2.3 Phase 1 — live Groq experiments

All six runs below used:

- provider `groq`
- temperature `0.2`, `max_tokens` 256
- topology **complete**
- visibility: previous messages **on**, confidence **on**, majority **on**
- seed `42`
- 2 rounds
- date **24 August 2026** (UTC timestamps on the JSON traces)

| # | Run | Architecture | Mix | Final | Correct | Consensus |
|---|---|---|---|---|---|---|
| 1 | Healthcare consultation | consultation | homogeneous 120B | **reject** (wait for MRI) | yes | **1.00** |
| 2 | Legal adversarial | adversarial | homogeneous 120B | **support** (strike non-compete) | yes | **0.75** |
| 3 | Finance committee | committee | homogeneous 120B | **reject** (abort the long) | yes | **1.00** |
| 4 | ESG negotiation | negotiation | homogeneous 120B | **support** (terminate) | yes | **1.00** |
| 5 | ESG minus finance | same + agent-removal | homogeneous 120B | **support** | yes | **1.00** |
| 6 | ESG heterogeneous | negotiation | 120B + 20B | **support** | yes | **1.00** |

6 / 6 majority-correct. The only incomplete consensus is **legal**: defence never flipped.

### 2.4 Heterogeneous seminar pack (31 Aug 2026)

Prepaid Anthropic / OpenAI / DeepSeek-direct wallets were not funded. The live five-family mix uses **Groq (free)**, **Gemini free tier**, and **OpenRouter pay-as-you-go**. India cannot open a new DashScope account; Qwen is called through OpenRouter (`sk-or-` key accepted in `DASHSCOPE_API_KEY` or `OPENROUTER_API_KEY`).

Pack: [`societyxai/student_seminar/`](../societyxai/student_seminar/README.md). Engine additions: `agent_providers`, OpenAI-compatible backends (OpenAI, DeepSeek, Qwen/DashScope, OpenRouter), Anthropic, Gemini, and `independent_first_round` on visibility (round 1 hides messages, majority, and confidence).

---

## 3. Example 1 — Healthcare consultation

**Config:** `societyxai/configs/experiments/complete_healthcare_consultation.yaml`  
**Trace:** `societyxai/runs/complete-healthcare-consultation.json`  
**Timestamp:** 2026-08-24T10:32:03Z

**Question.** Adult with sudden bilateral leg weakness and severe back pain. Osteoarthritis and neuropathy history. Imaging is not back. Start high-dose steroids now, or wait?

**Ground truth:** `reject` (wait for imaging unless a confirmed compressive protocol independently mandates steroids).

**Evidence.** Red-flag cord / cauda equina (e1); acute back pain with motor loss (e2); mixed evidence for steroids before imaging (e3); infection/fracture on the differential (e4).

**Cast (complete graph, 5 agents, 2 rounds).** GP and neurology specialist start **support**. Evidence analyst, risk officer, and treatment planner start **reject**. The treatment planner is the adjudicator and speaks only in round 2.

| Agent | Role | Initial | Round 1 | Round 2 (final) | Confidence |
|---|---|---|---|---|---|
| `gp` | general practitioner | support 0.62 | *parse failure* → recorded **neutral** 1.00 | **reject** | 0.74 |
| `specialist` | neurology specialist | support 0.70 | reject (empty parse, conf 1.00) | **reject** | 0.81 |
| `evidence_analyst` | evidence analyst | reject 0.58 | reject | **reject** | 0.73 |
| `risk_agent` | clinical risk officer | reject 0.74 | reject | **reject** | 0.86 |
| `treatment_planner` | chief treatment planner | reject 0.55 | *(silent)* | **reject** | 0.78 |

**Outcome.** Final **reject**, correctness **true**, consensus **1.00**. Both clinicians who began “treat now” moved to wait-for-MRI after seeing e3/e4 and the panel.

**Note on logging.** An earlier Groq attempt truncated JSON (`{"` only) and was retried. The JSON trace above is the completed run. Round-1 GP still lost a parse; the agent recovered in round 2.

---

## 4. Example 2 — Legal adversarial

**Config:** `societyxai/configs/experiments/complete_legal_adversarial.yaml`  
**Trace:** `societyxai/runs/complete-legal-adversarial.json`  
**Timestamp:** 2026-08-24T10:33:26Z

**Question.** Startup contract: two-year **statewide** non-compete plus assignment of all side-project IP. Strike the non-compete as unenforceable?

**Ground truth:** `support` (strike it).

**Evidence.** State limits/bans on overbroad non-competes (e1); off-hours IP assignment (e2); courts void statewide clauses without customer nexus (e3); employer claim of access to unreleased weights and customer lists (e4).

**Cast.** Prosecution (employee) starts support. Defence (startup) starts reject. Evidence analyst and precedent researcher start support. Judge starts reject and speaks only in round 2.

| Agent | Role | Initial | Round 1 | Round 2 (final) | Confidence |
|---|---|---|---|---|---|
| `prosecution` | employee counsel | support 0.82 | support 0.78 | **support** | 0.76 |
| `defence` | startup counsel | reject 0.78 | reject (empty parse in R1) | **reject** | 0.66 |
| `evidence_analyst` | evidence analyst | support 0.60 | support (empty parse in R1) | **support** | 0.73 |
| `precedent_researcher` | precedent researcher | support 0.66 | support 0.71 | **support** | 0.72 |
| `judge` | adjudicating judge | reject 0.50 | *(silent)* | **support** | 0.78 |

**Outcome.** Final **support**, correctness **true**, consensus **0.75** (4 support, 1 reject).

**What this example shows.** Majority and the judge moved to strike the clause. **Defence never flipped.** In round 2 it argued e4 + e2 (trade secrets + IP assignment justify the restriction). This is the only live complete architecture that did not reach unanimity. Adversarial role-lock survived full visibility of majority and confidence.

---

## 5. Example 3 — Finance committee

**Config:** `societyxai/configs/experiments/complete_finance_committee.yaml`  
**Trace:** `societyxai/runs/complete-finance-committee.json`  
**Timestamp:** 2026-08-24T10:35:38Z

**Question.** Ticker ACME, mixed sentiment after an SEC comment letter, 61% paper win rate on a bullish overlay. Execute an aggressive long?

**Ground truth:** `reject` (abort).

**Evidence.** SEC letter + mixed sentiment (e1); 61% paper win rate without costs (e2); paper stats omit gap/halt risk (e3); book already long cyclicals (e4).

**Cast.** Only **growth** starts support. Risk, portfolio, macro, CIO start reject. CIO speaks only in round 2.

| Agent | Role | Initial | Round 1 | Round 2 (final) | Confidence |
|---|---|---|---|---|---|
| `growth` | growth analyst | support 0.71 | reject (empty parse in R1) | **reject** | 0.71 |
| `risk` | chief risk officer | reject 0.84 | reject 0.86 | **reject** | 0.84 |
| `portfolio` | portfolio manager | reject 0.63 | reject 0.81 | **reject** | 0.78 |
| `macro` | macro economist | reject 0.60 | reject 0.75 | **reject** | 0.77 |
| `cio` | chief investment officer | reject 0.55 | *(silent)* | **reject** | 0.81 |

**Outcome.** Final **reject**, correctness **true**, consensus **1.00**. The sole bullish agent (growth) joined the abort. Round-2 reasoning consistently weighted e1/e3/e4 over the 61% backtest.

---

## 6. Example 4 — ESG negotiation (homogeneous)

**Config:** `societyxai/configs/experiments/complete_esg_negotiation.yaml`  
**Trace:** `societyxai/runs/complete-esg-negotiation.json`  
**Timestamp:** 2026-08-24T10:37:16Z

**Question.** Supplier Northwind Textiles promised zero discharge. Reports: chemical spill and unpaid overtime. Contract saves **$4.2M/year**. Terminate immediately?

**Ground truth:** `support` (terminate).

**Evidence.** Spill into a river (e1); unpaid overtime / blocked exit (e2); $4.2M savings vs next mill (e3); scorecard still “preferred”, no on-site audit this year (e4).

**Cast.** Sustainability, legal, community start **support**. Finance and operations start **reject**. No adjudicator — all five speak both rounds.

| Agent | Role | Initial | Final | Confidence |
|---|---|---|---|---|
| `sustainability` | sustainability officer | support 0.86 | **support** | 0.86 |
| `finance` | financial officer | reject 0.80 | **support** | 0.81 |
| `operations` | operations manager | reject 0.58 | **support** | 0.84 |
| `legal` | legal compliance | support 0.64 | **support** | 0.88 |
| `community` | community advocate | support 0.88 | **support** | 0.92 |

**Outcome.** Final **support**, correctness **true**, consensus **1.00**. Finance and operations **flipped** from keep-the-contract to terminate. Homogeneous 120B, complete visibility, two rounds.

---

## 7. Example 5 — ESG counterfactual (remove finance)

**Config:** `societyxai/configs/experiments/complete_esg_remove_finance.yaml`  
**Trace:** `societyxai/runs/complete-esg-negotiation-remove-finance.json`  
**Timestamp:** 2026-08-24T10:38:29Z

Same task and ground truth as Example 4. Intervention: **agent removal**, target `finance`. Four remaining agents, 8 turns.

| Agent | Final | Confidence |
|---|---|---|
| `sustainability` | support | 0.93 |
| `operations` | support | 1.00 |
| `legal` | support | 0.88 |
| `community` | support | 0.90 |

**Outcome.** Final **support**, correctness **true**, consensus **1.00**.

**Causal reading (this single pair).** Removing finance **did not change** the society decision. In the baseline, finance itself had already flipped to terminate. Finance was not a necessary cause of the terminate consensus on this seed. A fuller causal claim needs more seeds and other interventions (hide majority, reorder, identity swap).

---

## 8. Example 6 — ESG heterogeneous (120B + 20B)

**Config:** `societyxai/configs/experiments/complete_esg_heterogeneous.yaml`  
**Trace:** `societyxai/runs/complete-esg-heterogeneous.json`  
**Timestamp:** 2026-08-24T10:40:21Z

Same ESG terminate question. Model mix (still one lab, two sizes):

| Agent | Model | Initial | Final | Confidence |
|---|---|---|---|---|
| `sustainability` | gpt-oss-120b | support | **support** | 1.00 |
| `finance` | **gpt-oss-20b** | reject | **support** | 0.72 |
| `operations` | **gpt-oss-20b** | reject | **support** | 1.00 |
| `legal` | gpt-oss-120b | support | **support** | 0.78 then 1.00 |
| `community` | gpt-oss-120b | support | **support** | 1.00 |

**Outcome.** Final **support**, correctness **true**, consensus **1.00**.

The two weaker agents (finance, operations) still flipped to terminate. Round 1 had several empty parses (position recorded, reasoning blank); round 2 filled in. This run is **size diversity**, not **lab diversity**.

---

## 9. Heterogeneous five-family society (Phase 2 — run)

Groq 120B vs 20B was **size diversity inside one lab**. Phase 2 uses **five model families**. Prepaid Sonnet / Luna / DeepSeek-direct wallets were parked (India DashScope signup is closed; OpenAI and Anthropic need a first credit pack). The **live** mix is free Groq + Gemini free tier + OpenRouter pay-as-you-go. Thinking stays off; seminar aptitude items used `max_tokens` 512.

**Grok is left out.** Grok 4.6 scores **60.9** on the Artificial Analysis Intelligence Index (27 Aug 2026) — stronger than every model in our five. It is omitted because (1) we only have five seats, (2) it is another US closed lab on top of Anthropic / OpenAI / Google, and (3) list price (~$2 / $6 per 1M) is several times Luna. Dropping DeepSeek or Qwen for Grok would erase the East/West mix. Grok can be a later “fluent but high-hallucination” condition.

Early Groq-only cheap mix (historical; figure kept):

![Budget mix considered earlier](figures/heterogeneous-mix-budget.png)

### 9.1 Live roster (what actually sat in the room)

Fixed identities. Hats change by case. Speaker orders: `default` / `reverse` / `weak_first`. Do not publish from one order.

| Student | Role (social / aptitude) | Model | Family | Billing |
|---|---|---|---|---|
| Asha | moderator / closer | `openai/gpt-oss-120b` | OpenAI OSS via Groq | Free |
| Rahul | advocate / solver | `meta-llama/llama-3.3-70b-instruct` | Meta via OpenRouter | PAYG |
| Mei | critic / skeptic | `gemini-3.6-flash` | Google | Free tier |
| Ilya | fact-checker / alt. path | `deepseek/deepseek-chat` | DeepSeek via OpenRouter | PAYG |
| Noor | impact / formalizer | `qwen/qwen3.5-flash-02-23` | Alibaba via OpenRouter | PAYG |

Gemini 2.5 Flash is closed to new AI Studio keys; Mei uses 3.6 Flash. Keys: `GROQ_API_KEY`, `GEMINI_API_KEY`, and `OPENROUTER_API_KEY` (or an `sk-or-` key in `DASHSCOPE_API_KEY`).

**Parked paid contrast** (not used in the live tables below). Intended if those wallets are funded later: Sonnet 5 (strong), GPT-5.6 Luna (strong), Gemini 2.5 Flash (weak), DeepSeek V4 Flash (strong), Qwen 3.5 Flash via DashScope (weak). Grok is left out (AA Index 60.9; seat/budget/lab-balance). Scores for that parked mix stay in §9.4.

### 9.2 Cases that were run

**Case A — social inbox (one item).** Campus 72-hour freeze on anonymous posts. Gold: `reject`. Default order, majority visible both rounds (not independent-first). Log: [`student_seminar/runs/FULL_LOG_social-campus-messaging-ban.md`](../societyxai/student_seminar/runs/FULL_LOG_social-campus-messaging-ban.md).

**Case B — aptitude audit (five items).** Independent round 1, debate round 2, all five speak both rounds, `max_tokens` 512. Items: mislabeled boxes; affirming the consequent; sequence \(2,6,12,20,30,?\); unreliable witnesses; unique line A–E–B–D–C. Questions: [`student_seminar/questions/audit/`](../societyxai/student_seminar/questions/audit/). Full logs: [`student_seminar/runs/audit/`](../societyxai/student_seminar/runs/audit/). Manuscript cut: [`paper-results.md`](paper-results.md).

The older plan (GPQA Diamond + LSAT + AIME as Case B) was not used; the five INCoWoCo items above are the live Case B. Do not mix a policy vignette and an exam item in one run.

### 9.3 Why these public benchmarks

The scores below label the **parked** paid mix (frozen 27 Aug 2026) so strong/weak is not fitted after those runs. They do **not** describe the live Groq/OpenRouter/Gemini roster in §9.1. Composite IQ alone is not enough: Luna is cheap but strong on GPQA; DeepSeek V4 is strong on GPQA and weak on hallucination; Gemini 2.5 Flash is weak on the composite.

| Benchmark | What it measures | Why we use it for this paper |
|---|---|---|
| **Artificial Analysis Intelligence Index v4.1.1** | Weighted composite: GDPval-AA, τ³-Banking, Terminal-Bench, SciCode, HLE, GPQA Diamond, CritPt, AA-Omniscience, AA-LCR | One reviewer-known ranking. Labels overall **capability** so we can test whether the high-index model actually pulls the society. |
| **GPQA Diamond** | Graduate science MCQ; Google-proof by design | Directly predicts **Case B** item 1. Separates “sounds smart in debate” from “can solve a hard closed-form question.” |
| **Humanity’s Last Exam (HLE)** | Very hard reasoning/knowledge | Stress test. A model can look aligned in a legal vignette and still fail HLE-class items. |
| **AA-Omniscience** | Knowledge reliability: rewards correct, penalizes hallucination, no penalty for abstaining (−100 to 100) | Process audit: fluent wrong answers are the mechanism for **false consensus**. |
| **MMLU-Pro / LegalBench (or Harvey LAB-AA)** | Broad professional knowledge; legal agentic work | Domain competence for **Case A**. A model can win GPQA and still be a weak lawyer. |
| **IFEval / JSON parse-success (ours)** | Instruction following and schema | We already saw empty `reasoning_trace` on gpt-oss. Dominance that is just “failed to emit JSON” is not intellectual dominance. |

We **do not** use LMSYS Arena Elo as the primary label (preference, not truth) or SWE-Bench as the primary label (this is not a coding paper).

### 9.4 Logged public scores (frozen 27 August 2026)

Sources: [Artificial Analysis Intelligence Index](https://artificialanalysis.ai/models?intelligence=artificial-analysis-intelligence-index) via ModelCap snapshot 27 Aug 2026; AA head-to-head pages for Sonnet 5 / Luna / DeepSeek V4 Flash; [OpenRouter GPQA Diamond](https://openrouter.ai/benchmarks/gpqa-diamond) last run 27 Aug 2026 03:11 UTC; DeepSeek HLE / Omniscience from the AA-cited V4 Flash 0731 card (ofox snapshot); Qwen Flash-tier from Artificial Analysis / BenchmarkList for **Qwen3.5 Omni Flash**.

A dash means we did not find a same-source number for that exact model id. Do not fill those from a different model in the same family.

**Artificial Analysis Intelligence Index (higher = stronger composite)**

| Model | AA Index | Source rank (ModelCap / 609) | Notes |
|---|---|---|---|
| Claude Sonnet 5 | **55.3** | #24 | AA head-to-head vs Luna/DeepSeek reports **55** (max-effort rounding) |
| GPT-5.6 Luna | **52.3** | #34 | AA head-to-head reports **52** (max) |
| DeepSeek V4 Flash 0731 | **52** | (AA comparison; not in ModelCap’s 154-row extract) | Same ballpark as Luna |
| Qwen 3.5 Flash (Omni Flash card) | **19.0** | ~#262 on AA-derived lists | Flash **tier**, not Qwen3.8 Max (58.1) |
| Gemini 2.5 Flash | **14.2** | #339 | Keep 2.5; Gemini 3.7 Flash is 56.0 and would be Strong |
| *Grok 4.6 (not in society)* | *60.9* | *#6* | Left out; stronger than all five |

**GPQA Diamond accuracy (OpenRouter, 27 Aug 2026)**

| Model | GPQA Diamond | Rank on that board |
|---|---|---|
| GPT-5.6 Luna (Pareto) | **88.4%** | #17 |
| DeepSeek V4 Flash 0731 | **86.4%** ±1.2 | #26 |
| Claude Sonnet 5 | **84.1%** ±1.0 | #37 |
| Qwen3.5-35B-A3B (Flash-class open weight) | **82.0%** ±3.6 | #51 |
| Qwen3.5 Omni Flash | **74.2%** | BenchmarkList / AA |
| Gemini 2.5 Flash | **72.2%** | #84 |

**Reliability and extra reasoning (same freeze; incomplete by design)**

| Model | HLE | AA-Omniscience Index | Read |
|---|---|---|---|
| DeepSeek V4 Flash 0731 | 37% | **−16** | Strong reasoner, still net-negative omniscience |
| Qwen3.5 Omni Flash | 7.1% | **−65.6** | Weak reasoning and high hallucination |
| Claude Sonnet 5 | — | — | Freeze from AA on run day |
| GPT-5.6 Luna | — | — | Freeze from AA on run day |
| Gemini 2.5 Flash | — | — | Freeze from AA on run day |

### 9.5 Comparison: who is strong vs weak

**Label rule (fixed before any multi-lab run):** among these five, **Strong** if Intelligence Index ≥ 50; **Weak** if Intelligence Index < 30.

| Label | Models | Why |
|---|---|---|
| **Strong** | Sonnet 5, GPT-5.6 Luna, DeepSeek V4 Flash | Composite ~52–55. On GPQA they cluster 84–88%. Luna is **not** the weak OpenAI slot. |
| **Weak** | Gemini 2.5 Flash, Qwen 3.5 Flash | Composite 14 and 19. GPQA 72% and ~74–82% depending on the exact Qwen Flash id. |

**What the comparison is *not*.** Price is not strength: Luna is ~$0.20 / $1.20 and still GPQA-stronger than Sonnet 5 on OpenRouter (88.4% vs 84.1%). Family name is not strength: Gemini **3.7** Flash (56.0) would be Strong; we keep **2.5** Flash (14.2) as the weak Google seat. Grok is stronger than the whole mix and still excluded for slot/budget/lab-balance, not because it is weak.

**Hypothesis this labeling is for.** If the society follows Sonnet/Luna/DeepSeek to the gold answer, that is capability-driven dominance. If Gemini (weak, defence/judge-swap) still locks the outcome, dominance is **role, speaking order, or majority visibility**, not IQ. DeepSeek’s negative Omniscience score is the test for “strong on GPQA, still poisons the audit with fluent error.”

### 9.6 Live results — Case A (social)

Campus 72-hour anonymous-post freeze. Gold `reject`. Default order. Majority + confidence visible from turn 1 (not independent-first). 31 Aug 2026.

| | |
|---|---|
| Final | **reject** (correct) |
| Consensus | **0.75** (Noor unparsed / `neutral`) |
| First gold-aligned vote | Rahul (Llama 3.3 70B) |
| Empty-reasoning rate | 0.44 |

Rahul, Ilya, and Asha wrote full arguments for reject. Mei truncated JSON. Noor returned garbage (`-1e+77`). Same parse pattern as Case B.

### 9.7 Live results — Case B (five-family aptitude audit)

Independent then debate. Seed 42. Default order Rahul → Mei → Ilya → Noor → Asha. All five speak both rounds. Consensus \(1-(d-1)/(n-1)\). Empty-reasoning rate is empty `reasoning_trace` over ten turns.

**Table A.** Society outcomes. *First gold-aligned vote* need not be a worked solution.

| Item | Task | Gold | Final | Correct | Consensus | Empty-reason. | First gold-aligned vote |
|---|---|---|---|---|---|---|---|
| 1 | Mislabeled boxes | support | support | yes | 0.75 | 0.40 | Llama (solver) |
| 4 | Late \(\Rightarrow\) penalty | reject | reject | yes | 0.75 | 0.30 | Llama (solver) |
| 5 | Sequence to \(42\) | support | support | yes | 0.75 | 0.60 | DeepSeek (alt. path) |
| 6 | Unreliable witnesses | support | support | yes | 0.75 | 0.40 | Llama (solver) |
| 8 | Line arrangement | support | **reject** | **no** | 0.50 | 0.60 | Gemini (empty trace) |

**4 / 5 majority-correct.** Consensus never hits \(1.00\) because Qwen is `neutral` on every item.

**Table B.** Last-round position and confidence. S = support, R = reject, N = neutral.

| Item | Llama 3.3 70B | Gemini 3.6 Flash | DeepSeek Chat | Qwen 3.5 Flash | GPT-OSS 120B |
|---|---|---|---|---|---|
| 1 Boxes | S \(0.98\) | S \(1.00\) | S \(0.99\) | N \(1.00\) | S \(0.97\) |
| 4 Penalty | R \(0.99\) | R \(1.00\) | R \(1.00\) | N \(1.00\) | R \(0.99\) |
| 5 Sequence | S \(0.95\) | S \(1.00\) | S \(0.95\) | N \(1.00\) | S \(0.93\) |
| 6 Witnesses | S \(1.00\) | S \(1.00\) | S \(1.00\) | N \(1.00\) | S \(1.00\) |
| 8 Line | R \(0.90\) | S \(1.00\) | R \(0.90\) | N \(1.00\) | S \(1.00\) |

**Table C.** Independent (R1) → debate (R2). Bold = flip.

| Item | Llama | Gemini | DeepSeek | Qwen | GPT-OSS 120B |
|---|---|---|---|---|---|
| 1 Boxes | S \(\to\) S | S \(\to\) S | S \(\to\) S | N \(\to\) N | S \(\to\) S |
| 4 Penalty | R \(\to\) R | R \(\to\) R | R \(\to\) R | N \(\to\) N | R \(\to\) R |
| 5 Sequence | **R \(\to\) S** | **N \(\to\) S** | S \(\to\) S | N \(\to\) N | S \(\to\) S |
| 6 Witnesses | S \(\to\) S | S \(\to\) S | S \(\to\) S | N \(\to\) N | S \(\to\) S |
| 8 Line | R \(\to\) R | S \(\to\) S | R \(\to\) R | N \(\to\) N | **R \(\to\) S** |

**Table D.** Process. Conformity is the paper index on turns that move toward the visible majority.

| Item | Conformity | First *worked* gold argument | Flips in debate | Shared process error |
|---|---|---|---|---|
| 1 Boxes | 0.00 | DeepSeek (correct relabel chain) | none | Llama: right box, wrong relabel of the other two |
| 4 Penalty | 0.00 | Llama, DeepSeek, GPT-OSS (name the fallacy) | none | none in written traces |
| 5 Sequence | **1.00** | DeepSeek (two patterns \(\to\) \(42\)) | Llama R\(\to\)S; Gemini N\(\to\)S | Llama independent vote wrong / empty |
| 6 Witnesses | 0.00 | Llama, DeepSeek, GPT-OSS (B+D consistent) | none | `support` gloss named the gold pair (verification, not search) |
| 8 Line | 1.00 | none that survive e3 | GPT-OSS R\(\to\)S (empty text) | Llama + DeepSeek treat A–B–D–E–C as valid; C is adjacent to E |

**Table E.** Audit-grade writing (five items, ten turns each). Usable = non-empty trace that states a constraint, derivation, or named fallacy.

| Seat | Model | Usable arguments | Independent errors | Debate |
|---|---|---|---|---|
| Solver | Llama 3.3 70B | 8/10 | wrong relabel (1); wrong uniqueness (8); empty/wrong on 5 R1 | flips to gold on 5 |
| Skeptic | Gemini 3.6 Flash | \(\approx 1/10\) | almost no text | truncated JSON; conf \(1.00\) |
| Alt. path | DeepSeek Chat | **10/10** | item 8 adjacency (shared) | cites evidence ids |
| Formalizer | Qwen 3.5 Flash | **0/10** | unparsed every turn | no vote |
| Closer | GPT-OSS 120B | 6/10 | empty on 5 R1 and both 8 turns | empty-text flip on 8 |

**Reading.** Item 5 is the intended process result: solver wrong alone, DeepSeek writes \(n(n+1)\) and even increments, solver flips after visibility returns. Item 8 is the complementary failure: two fluent writers share an illegal extra permutation and raise confidence. Item 1 is outcome-correct and process-mixed (Llama skips the mixed box when relabelling). Item 6 is a verification success, not a search success. Consensus \(0.75\) on the four wins is Qwen’s parse failure, not dissent. Do not credit Gemini with “solving” item 8.

Phase 1 Groq \(6/6\) is a **different** mix and is not pooled with Table A.

---

## 10. Cross-example findings

**Phase 1 (Groq, one lab).**

1. Complete topology + visible majority is strongly aligning. Five of six runs ended unanimous.
2. Correct majority is reachable from mixed initial beliefs on the four applied vignettes with gpt-oss-120b.
3. Role-locked dissent exists. Legal defence kept `reject` against a 4–1 majority.
4. Removing ESG finance did not change the terminate decision on seed 42.
5. Weaker 20B agents still followed the ESG terminate consensus. Size mix ≠ lab mix.
6. JSON parse failures are real on gpt-oss; some agents recovered next turn.
7. Adjudicators vote last. Judge flipped to strike; CIO stayed with abort.

**Phase 2 (five families).**

8. A cheap five-family society majority-solves four short reasoning items and one social freeze item without a judge model.
9. Independent first round is load-bearing (item 5 flip; item 8 shared error visible before debate).
10. Binary majority is an incomplete audit (item 1 wrong relabel; item 8 illegal extra line).
11. Empty-reasoning rate belongs in the results table. Two of five seats (Gemini, Qwen) are not producing audit-grade traces at this decoding setup.
12. DeepSeek Chat was the only seat with a usable argument on every aptitude item.

All of this is **n = 1 seed**. Reverse order is still required before claiming a model dominated.

---

## 11. How to reproduce

```bash
cd societyxai
pip install -e .
python -m pytest -q
```

**Phase 1 (Groq niches).** `GROQ_API_KEY` in parent `.env`.

```bash
python -m societyxai run --config configs/experiments/complete_healthcare_consultation.yaml --log-doc docs/EXPERIMENT_LOG.md
python scripts/run_complete_architectures.py
```

**Phase 2 (heterogeneous seminar).** Also `GEMINI_API_KEY` and `OPENROUTER_API_KEY` (or `sk-or-` in `DASHSCOPE_API_KEY`).

```bash
python student_seminar/ping_keys.py
python student_seminar/run.py --case social --order default
python student_seminar/run_audit.py
```

| File | Purpose |
|---|---|
| `societyxai/configs/experiments/complete_*.yaml` | Six Groq complete-architecture packs |
| `societyxai/docs/EXPERIMENT_LOG.md` | Groq turn log |
| `societyxai/runs/complete-*.json` | Groq traces |
| `societyxai/student_seminar/roster.yaml` | Live five-family identities |
| `societyxai/student_seminar/questions/audit/` | Five aptitude items |
| `societyxai/student_seminar/runs/audit/` | Case B full logs, monitors, `AUDIT_EVAL.md` |
| `docs/paper-results.md` | Manuscript-shaped Results cut |
| `societyxai/experiments/pilot_protocol.md` | Earlier Ollama minority-correct protocol |

---

## 12. Repo layout (31 Aug 2026)

```
nithu0602-SocietyXAI_INCOWOCO/   ← this git repository
  README.md
  .env / .env.example            ← secrets; never commit .env
  docs/
    PROJECT.md                   ← full project record + results
    paper-results.md
    original-plan.pdf
    figures/heterogeneous-mix-budget.png
  societyxai/                    ← engine, Groq packs, student_seminar, traces
```

**Removed (24 Aug):** old `src/societyxai/`, root prototype tests/examples, `New folder/`, root `pyproject.toml`.

**Kept:** friend’s YAML pilots; `societyxai/.git`; seminar pack and audit traces.

---

## 13. What is still open

- **`--order reverse`** on aptitude items 5 and 8 (flip vs error-cascade).
- Social Case A reverse (and optional `weak_first`).
- Fix Mei/Noor JSON (thinking off, retry on truncated `{`) or replace those seats.
- Score item 8 with an explicit adjacency check, not only majority bits.
- Stop putting the gold pair in `support_means` on search puzzles (item 6).
- Parked paid five-lab mix (Sonnet / Luna / DeepSeek V4 / Gemini 2.5 / DashScope) if those wallets are funded; then identity-swap.
- Hidden-majority interventions; more seeds.
- Freeze remaining HLE / Omniscience cells for the parked mix on that run day.
