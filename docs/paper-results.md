# Results

*Manuscript-shaped cut of the Phase 2 aptitude audit. The **full project record** (Groq Phase 1 + hetero Phase 2 + these tables) is [`PROJECT.md`](PROJECT.md) §9–§10. One seed (`42`), default speaker order, live run 31 August 2026. Traces: `societyxai/student_seminar/runs/audit/`.*

This section reports a five-item aptitude seminar. Five heterogeneous agents answered independently in round 1 (no peer messages, no majority cue, no confidence cue) and then debated in round 2 on a complete topology with majority and confidence visible. All five agents spoke in both rounds. The orchestrator scored a binary position (`support` / `reject`) against a gold label; it is not a judge model. Final society decision is last-round majority vote. Consensus is \(1-(d-1)/(n-1)\), where \(d\) is the number of distinct final positions and \(n=5\).

**Society.** Solver: Llama 3.3 70B Instruct (OpenRouter). Skeptic: Gemini 3.6 Flash. Alternative path: DeepSeek Chat (OpenRouter). Formalizer: Qwen 3.5 Flash (OpenRouter). Closer: GPT-OSS 120B (Groq). Temperature \(0.2\), \(512\) completion tokens, JSON belief objects.

**Items.** (1) mislabeled boxes; (4) affirming the consequent; (5) sequence \(2,6,12,20,30,?\) with a required alternative pattern; (6) five witnesses, exactly two truth-tellers; (8) unique seating line. Gold encodings: (1) draw from *Apples & Oranges*; (4) cannot infer lateness; (5) next term \(42\); (6) B and D; (8) unique order A–E–B–D–C.

---

## 5.1 Society-level outcomes

The society was majority-correct on four of five items (Table 1). Consensus never reached \(1.00\). On the four correct items \(d=2\) (gold-aligned vote plus a persistent `neutral` from the formalizer), so consensus is \(0.75\). On item 8, last-round positions split \(2\)–\(2\)–\(1\) (`reject` / `support` / `neutral`); majority recorded `reject` against gold `support`, and consensus fell to \(0.50\).

Empty-reasoning rate is the share of the ten turns (five agents \(\times\) two rounds) whose `reasoning_trace` was empty after parse. It is not a secondary quality note: two seats produced almost no usable text (Section 5.4).

**Table 1.** Society outcomes on five aptitude items. *First gold-aligned vote* is the earliest turn whose parsed position matches gold; it need not be a worked solution.

| Item | Task | Gold | Final vote | Correct | Consensus | Empty-reason. | First gold-aligned vote |
|---|---|---|---|---|---|---|---|
| 1 | Mislabeled boxes | support | support | yes | 0.75 | 0.40 | Llama (solver) |
| 4 | Late \(\Rightarrow\) penalty | reject | reject | yes | 0.75 | 0.30 | Llama (solver) |
| 5 | Sequence to \(42\) | support | support | yes | 0.75 | 0.60 | DeepSeek (alt. path) |
| 6 | Unreliable witnesses | support | support | yes | 0.75 | 0.40 | Llama (solver) |
| 8 | Line arrangement | support | **reject** | **no** | 0.50 | 0.60 | Gemini (empty trace) |

**Table 2.** Last-round position and confidence. S = support, R = reject, N = neutral (unparsed or abstain).

| Item | Llama 3.3 70B | Gemini 3.6 Flash | DeepSeek Chat | Qwen 3.5 Flash | GPT-OSS 120B |
|---|---|---|---|---|---|
| 1 Boxes | S \(0.98\) | S \(1.00\) | S \(0.99\) | N \(1.00\) | S \(0.97\) |
| 4 Penalty | R \(0.99\) | R \(1.00\) | R \(1.00\) | N \(1.00\) | R \(0.99\) |
| 5 Sequence | S \(0.95\) | S \(1.00\) | S \(0.95\) | N \(1.00\) | S \(0.93\) |
| 6 Witnesses | S \(1.00\) | S \(1.00\) | S \(1.00\) | N \(1.00\) | S \(1.00\) |
| 8 Line | R \(0.90\) | S \(1.00\) | R \(0.90\) | N \(1.00\) | S \(1.00\) |

Qwen 3.5 Flash is `neutral` on every item. That single parse failure is what caps consensus at \(0.75\) on otherwise unanimous gold-aligned panels. Gemini reports confidence \(1.00\) on every scored turn, usually with a truncated JSON body and an empty reasoning field.

---

## 5.2 Belief dynamics: independent round versus debate

Table 3 shows the independent (R1) position and the post-debate (R2) position. A dash means no change. The design question is whether debate *repairs* an independent error or *locks* a shared mistake.

**Table 3.** Position by round (R1 \(\to\) R2). Bold cells are flips.

| Item | Llama | Gemini | DeepSeek | Qwen | GPT-OSS 120B |
|---|---|---|---|---|---|
| 1 Boxes | S \(\to\) S | S \(\to\) S | S \(\to\) S | N \(\to\) N | S \(\to\) S |
| 4 Penalty | R \(\to\) R | R \(\to\) R | R \(\to\) R | N \(\to\) N | R \(\to\) R |
| 5 Sequence | **R \(\to\) S** | **N \(\to\) S** | S \(\to\) S | N \(\to\) N | S \(\to\) S |
| 6 Witnesses | S \(\to\) S | S \(\to\) S | S \(\to\) S | N \(\to\) N | S \(\to\) S |
| 8 Line | R \(\to\) R | S \(\to\) S | R \(\to\) R | N \(\to\) N | **R \(\to\) S** |

**Table 4.** Process metrics. Conformity is the paper index over turns that change toward the visible majority. Influence totals are empty when nobody flips.

| Item | Conformity | First *worked* gold argument | Flips in debate | Shared process error |
|---|---|---|---|---|
| 1 Boxes | 0.00 | DeepSeek (correct relabel chain) | none | Llama: right box, wrong relabel of the other two |
| 4 Penalty | 0.00 | Llama, DeepSeek, GPT-OSS (name the fallacy) | none | none observed in written traces |
| 5 Sequence | **1.00** | DeepSeek (two patterns \(\to\) \(42\)) | Llama R\(\to\)S; Gemini N\(\to\)S | Llama independent vote was wrong / empty |
| 6 Witnesses | 0.00 | Llama, DeepSeek, GPT-OSS (B+D consistent) | none | prompt mapped `support` to the gold pair (verification, not search) |
| 8 Line | 1.00 | none that survive e3 | GPT-OSS R\(\to\)S (empty text) | Llama + DeepSeek treat A–B–D–E–C as valid; C is adjacent to E |

Item 5 is the intended process result. Independently, the solver voted against \(42\). The alternative-path agent wrote \(n(n+1)\) and the even-increment rule, both giving \(42\). After visibility was restored, the solver flipped and restated those patterns. Majority accuracy would hide that the first speaker was wrong.

Item 8 is the complementary failure. Independently, solver and alternative-path both rejected uniqueness and listed A–B–D–E–C beside the gold A–E–B–D–C. A–B–D–E–C violates “C is not adjacent to E.” Debate raised their confidence (\(0.80\to 0.90\)) without repairing the constraint. Gemini’s gold-aligned vote and the closer’s empty-text flip do not constitute a worked group solution. Majority recorded the wrong decision.

---

## 5.3 Outcome-correct is not process-correct

On item 1 the binary score is a true positive, but the solver’s independent (and final) relabeling is false: if the mixed-label box yields an apple, he assigned the remaining boxes as Oranges and Apples and omitted the mixed box. The alternative-path agent stated the standard chain (mixed-label box is pure; the box labelled Oranges cannot be oranges or apples, hence mixed). A metric that only compares `support` to gold would pass the solver.

On item 6, written traces check consistency of the pair B and D. They do not search the space of pairs. `support` was defined as “B and D are the two truth-tellers,” so the gold pair was available in the decision mapping. We treat this item as a *verification* success, not as evidence that the society discovered the pair.

---

## 5.4 Agent-level process quality

**Table 5.** Audit-grade writing across five items (ten turns each). *Usable argument* = non-empty `reasoning_trace` that states a constraint, derivation, or named fallacy.

| Seat (role) | Model | Usable written arguments | Independent errors | Debate behaviour |
|---|---|---|---|---|
| Solver | Llama 3.3 70B | 8/10 turns (empty on item 5 R1) | wrong relabel (item 1); wrong uniqueness (item 8); wrong/empty on item 5 R1 | flips to gold on item 5 |
| Skeptic | Gemini 3.6 Flash | \(\approx 1/10\) (item 4 R1 only) | n/a (almost no text) | truncated JSON; confidence stuck at \(1.00\) |
| Alt. path | DeepSeek Chat | **10/10** | item 8 adjacency miss (shared) | most complete traces; cites evidence ids |
| Formalizer | Qwen 3.5 Flash | **0/10** | unparsed every turn | no participation in the vote |
| Closer | GPT-OSS 120B | 6/10 | empty on item 5 R1 and both item 8 turns | empty-text flip to gold on item 8 |

DeepSeek Chat is the only seat that produced an inspectable argument on every item. Llama 3.3 70B is the main *readable* opener and also the main source of fluent, checkable mistakes. Gemini 3.6 Flash and Qwen 3.5 Flash cannot support a thinking-quality claim at this decoding setup: one truncates, the other never parses. GPT-OSS 120B is mixed—clear on items 1, 4, and 6, silent on the two items that most need a closer.

---

## 5.5 What the tables support

1. **A five-family society can majority-solve four short reasoning items** under independent-then-debate, without a judge model.
2. **Consensus \(0.75\) is not dissent.** It is one persistent parse failure (Qwen).
3. **Independent first round is load-bearing.** Item 5’s solver error is only visible because peers were hidden. Item 8’s shared adjacency error is only visible because both strong writers made it *before* debate.
4. **Binary majority is an incomplete audit.** Item 1 (wrong relabel) and item 8 (illegal extra permutation) would be misread as “solved” / “unsolved” without the traces.
5. **Empty-reasoning rate belongs in the results table**, not the appendix. Two of five seats are not contributing process evidence.

---

## 5.6 Limits of this result set

These tables are **one seed and one speaker order**. We have not yet run reverse order on items 5 and 8 (the flip case and the error-cascade case). Gold was injected into the `support`/`reject` gloss on items 6 and 8; item 6 should be read as verification. We do not claim Gemini “solved” item 8. We do not claim the prepaid five-lab mix (Sonnet 5, GPT-5.6 Luna, DeepSeek V4 Flash, Gemini 2.5 Flash, DashScope Qwen) was used here.

A complementary, earlier result set (homogeneous Groq GPT-OSS 120B, four applied niches, 24 August 2026) is \(6/6\) majority-correct, with legal the only non-unanimous panel (consensus \(0.75\), defence never flipped). That run is a different architecture and model mix; it is not pooled with Table 1.

---

## Camera-ready notes

- Table 1 is the main results table. Table 3 is the process table. Table 5 is the heterogeneity table.
- If space is tight: keep Tables 1, 3, and 5; move Table 2 to the appendix; keep Table 4 as a short paragraph.
- Before camera-ready: reverse order on items 5 and 8; retry or replace Gemini/Qwen; score item 8 with an explicit adjacency check, not only majority bits.
