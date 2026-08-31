# Aptitude audit — results and process evaluation

Live run: 31 Aug 2026. Five INCoWoCo items. Round 1 independent (no peer messages, no majority, no confidence). Round 2 debate. All five students spoke both rounds. `max_tokens=512`. Order: Rahul → Mei → Ilya → Noor → Asha.

Seats: Rahul Llama 3.3 70B, Mei Gemini 3.6 Flash, Ilya DeepSeek Chat, Noor Qwen 3.5 Flash, Asha GPT-OSS 120B.

Full turn logs (one file per question):

- `FULL_LOG_seminar-aptitude-default-aptitude-mislabeled-boxes.md`
- `FULL_LOG_seminar-aptitude-default-aptitude-late-penalty.md`
- `FULL_LOG_seminar-aptitude-default-aptitude-sequence.md`
- `FULL_LOG_seminar-aptitude-default-aptitude-unreliable-witnesses.md`
- `FULL_LOG_seminar-aptitude-default-aptitude-line-arrangement.md`

Index: `AUDIT_INDEX.json`

---

## Scoreboard

| # | Item | Gold | Society final | Correct? | Consensus | Empty reasoning | First gold vote |
|---|---|---|---|---|---|---|---|
| 1 | Mislabeled boxes | take from Apples & Oranges | support | **yes** | 0.75 | 0.40 | Rahul |
| 4 | Late → penalty | cannot conclude late | reject | **yes** | 0.75 | 0.30 | Rahul |
| 5 | 2,6,12,20,30,? | 42 | support | **yes** | 0.75 | 0.60 | Ilya |
| 6 | Unreliable witnesses | B and D | support | **yes** | 0.75 | 0.40 | Rahul |
| 8 | Line A–E | unique A-E-B-D-C | **reject** | **no** | 0.50 | 0.60 | Mei (empty text) |

**4 / 5 majority-correct.** Consensus never reached 1.0 because Noor never produced a parseable position (always `neutral`).

---

## Per-question audit

### 1. Mislabeled boxes — majority right, Rahul’s relabeling is wrong

Gold: draw from the box labelled **Apples & Oranges**, then deduce the other two.

Independent round: Rahul, Ilya, Asha all vote **support**. Mei matches the vote with truncated JSON. Noor fails to parse.

Process issue: Rahul picked the right **box** and then mis-relabelled. He wrote: if the draw is an apple, the Apples box is Oranges and the Oranges box is Apples. That skips the mixed box. Correct: mixed-label box is pure apples; the box labelled Oranges cannot be oranges and cannot be apples, so it is mixed; the last box is oranges. Ilya stated that chain. Rahul never corrected himself in round 2. The society still “got it right” on the binary label.

**Audit takeaway:** outcome-correct is not process-correct. A judge that only scores support/reject would pass Rahul.

### 4. Conditional reasoning — cleanest item

Gold: **cannot** conclude Pranay was late (affirming the consequent).

Rahul, Mei, Ilya, Asha all reject independently. Several name the fallacy. Confidence rises in debate (Rahul 0.80 → 0.99) without anyone flipping. That is agreement, not conformity-to-error.

**Audit takeaway:** on a named fallacy with a binary mapping, this mix is reliable. Empty-reasoning Mei still voted reject; we cannot tell if she understood or echoed the option list.

### 5. Sequence — first speaker wrong, then flipped

Gold: **42** (`n(n+1)` or +4,+6,+8,+10,+12).

Independent: Rahul **reject** with empty reasoning (wrong). Mei **neutral** (parse fail). Ilya **support** with two patterns (n(n+1) and even increments). Asha **support** with empty text. Debate: Rahul flips to **support** and then lists several equivalent 42-patterns. Conformity index **1.0**.

Ilya is the first **worked** correct solution. The monitor’s “first correct proposer” is Ilya, which matches the usable argument, not Rahul’s later flip.

**Audit takeaway:** this is the intended INCoWoCo finding. Independent first round caught that the solver seat was wrong; debate repaired the majority. Without independent round 1, Rahul speaking first could have anchored 40/36.

### 6. Unreliable witnesses — correct pair, mostly verification not search

Gold: truth-tellers **B and D**.

Rahul, Ilya, Asha independently support B+D and check consistency. They **assume** the gold pair (the question mapped support to that pair) rather than ruling out other pairs first. The mapping leaked the candidate. Still, the consistency check is valid.

**Audit takeaway:** for liars puzzles, do not put the gold pair in `support_means` if you want search. Next run should ask a free-form pair and score after.

### 8. Line arrangement — majority wrong; fake extra solutions

Gold: unique **A E B D C**.

Independent: Rahul and Ilya **reject** uniqueness. Both list `A B D E C` **and** `A E B D C`. `A B D E C` has E at 4 and C at 5, so **C is adjacent to E**, which the problem forbids. They did not apply e3. Mei votes support with empty JSON. Asha round 1 reject with empty text; round 2 support with empty text.

Final: Rahul reject, Mei support, Ilya reject, Noor neutral, Asha support → 2–2–1. Majority vote recorded **reject** (incorrect).

**Audit takeaway:** the hard enumeration item is where fluent models share a near-miss and reinforce it. Empty-text Gemini happened to be gold; empty-text Groq flipped to gold in debate without showing work. Do not credit those seats as solvers.

---

## Cross-cutting process eval

### Who actually reasoned

| Student | Model | Usable written arguments | Pattern |
|---|---|---|---|
| Ilya | DeepSeek Chat | 5/5 items | Best process. Alternative path, cites e-ids, survives Q8’s miss on adjacency. |
| Rahul | Llama 3.3 70B | 4/5 (empty on Q5 r1) | Strong opener; wrong relabel on Q1; wrong uniqueness on Q8; flipped on Q5. |
| Asha | GPT-OSS 120B | 3/5 | Good on Q1, Q4, Q6; empty on Q5 r1 and Q8. |
| Mei | Gemini 3.6 Flash | almost none | Position often correct, JSON truncated, confidence stuck at 1.0. Unusable for a thinking-quality paper. |
| Noor | Qwen 3.5 Flash | none | Every item `neutral` / empty. Same failure mode as the social freeze run. |

### Metrics vs the paper story

- **Majority accuracy 4/5** would look strong in a results table. Q8 shows the table would hide a shared constraint error.
- **Consensus 0.75** on the four wins is an artifact of Noor’s parse failure, not dissent.
- **Conformity 1.0 on Q5** is the useful cell: solver flipped after seeing a correct alt-path.
- **Influence totals** were `{}` on items where nobody flipped. Independent round 1 is working (no r1 leakage).
- **Empty-reasoning rate 0.3–0.6** is a first-class result, not noise. Two of five seats are not producing audit-grade traces at 512 tokens (Gemini truncation + Qwen garbage).

### What this mix can and cannot claim

Can claim: a cheap five-family society can majority-solve classic boxes, affirming-the-consequent, a short sequence, and a 2-of-5 liars puzzle, with independent-then-debate.

Cannot claim: “the group understood the line puzzle,” “Gemini reasoned,” or “Qwen participated.” Cannot treat binary support/reject as the full answer on Q1 (wrong relabel) or Q6 (gold pair was in the prompt mapping).

---

## What to change before the next pack

1. **Fix Noor and Mei JSON** (thinking off / longer output / retry on truncated `{`) or replace those seats. Otherwise every consensus score is capped at 0.75.
2. **Stop putting the gold answer in `support_means`** on search puzzles (Q6, Q8). Score free-form after, or use a hidden gold.
3. **Add a constraint-check scorer** for Q8: reject `ABDEC` because C–E adjacency. Outcome labels are not enough.
4. Run **`--order reverse`** on Q5 and Q8. Q5 is the flip case; Q8 is the error-cascade case.
5. Keep independent first round. It is what made Q5’s flip visible.
