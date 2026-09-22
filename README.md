# RFM Customer Analysis

Customer segmentation that scores 100 customers on Recency, Frequency and Monetary
value, estimates lifetime value — and then reads what those customers actually
*wrote*, to catch the ones the numbers cannot.

Python does the arithmetic. [Jev](https://docs.typesafe.ai) reads the language.
Neither does the other's job.

**[What it found](#what-it-found)** · **[The idea](#the-idea)** ·
**[How it works](#how-it-works)** · **[Running it](#running-it)** ·
**[Limitations](#limitations)**

---

## What it found

**Five customers scoring healthy on every purchase measure while telling us they were
unhappy.** $3,502 of lifetime value — **8.5% of the portfolio.** Four of the five had
an unresolved service complaint sitting there.

RFM ranked every one of them as safe. It had no way not to.

![What the numbers could not see](jev_chart_1_blindspots.png)

RFM is built entirely from purchase history, so it cannot see a customer who has
**decided to leave but has not yet stopped buying.** They score 5 out of 5 on every
dimension, identical to your best account, right up until they are gone. No amount of
tuning fixes that — the evidence is not in the data RFM reads. It is in what they
wrote to you.

### "Angry" and "leaving" are not the same signal

The most useful finding was a distinction, not a customer:

| Message type | Intent to leave | Severity |
|---|---|---|
| "Please close my account" | **0.78** | 0.42 / 3 |
| "Fourth time I've chased this" | **0.22** | **2.71 / 3** |

A furious customer complaining **to** you has not left — they are giving you a chance.
Someone calmly closing their account has already gone. Different problems, different
responses, and most churn scores blend them into one number that loses both.

![Angry is not the same as leaving](jev_chart_2_intent_vs_severity.png)

That distinction also exposed a bug in my own scoring — see
[where the halves meet](#where-the-two-halves-meet).

---

## The idea

> **Code owns every number. The model owns meaning.**

| | **Python** | **Jev** |
|---|---|---|
| **Owns** | Arithmetic, thresholds, weights, ranking, control flow | Reading language, returning a typed judgment |
| **Example** | R/F/M scores, CLV, segments, filters, composite scoring | "Is this customer signalling they want to leave?" |
| **Fails how?** | Loudly and deterministically, in a way you can test | Probabilistically, with a confidence figure attached |
| **A change costs** | A re-run | An API call |

The line is drawn on one test: **could a competent analyst compute this from a clear
definition and a spreadsheet?** If yes it belongs in code, which is auditable,
reproducible and free. If it needs someone to understand a sentence, no threshold will
ever get there.

The temptation with a capable model is to hand it the whole problem — give it the
customer record and ask "how at-risk is this account?" That produces a number nobody
can check or reproduce. Splitting the work means every figure in the deck traces back
to either an explicit formula or an inspectable judgment about a specific sentence.

---

## How it works

### The code half

**Scoring.** Each customer scores 1–5 on Recency, Frequency and Monetary value.
Recency and Monetary are percentile-ranked; Frequency is a direct ladder.

**Segmentation.** An ordered chain where the first matching rule wins. The order is
load-bearing — `At Risk` is tested before `Loyal`, so a frequent buyer who has gone
quiet is flagged as lapsing rather than filed as loyal.

This was originally documented as a flat table of rules, which hid a real defect. The
rules overlap: `R=2, F=3` satisfies both `Loyal` and `At Risk` as written, and **13 of
25 combinations matched more than one documented rule.** A table like that is not a
specification. The result grid is:

|  | F=1 | F=2 | F=3 | F=4 | F=5 |
|---|---|---|---|---|---|
| **R=5** | New Customer | Potential Loyalist | Loyal | Champions | Champions |
| **R=4** | New Customer | Potential Loyalist | Loyal | Champions | Champions |
| **R=3** | Promising | Need Attention | Loyal | Loyal | Loyal |
| **R=2** | Hibernating | About to Sleep | At Risk | At Risk | At Risk |
| **R=1** | Lost | Lost | At Risk | Can't Lose Them | Can't Lose Them |

`rfm_audit.py` regenerates this from the live code every run and diffs it against the
table above. Reorder the chain and the audit fails.

**Lifetime value.** The textbook formula does not work:

```
average_order_value = monetaryValue / frequency

CLV = (monetaryValue / frequency) × frequency × lifespan × margin
    =  monetaryValue × lifespan × margin          ← frequency cancels
```

It collapses to a rescaling of the Monetary column, carrying no information that
column did not already have. A customer who spent $1,000 across ten orders scores
identically to one who spent $1,000 once and never returned. Any `AOV × frequency × k`
formula collapses the same way, because `AOV × frequency` *is* total spend.

So CLV has to answer what spend cannot — **will they keep buying?**

```
CLV = observed annual profit  ×  P(still active)  ×  discounted horizon
```

`P(still active)` decays with how overdue a customer is *relative to their own
purchase cycle*. Frequency enters here instead of in the spend term, which stops it
cancelling and makes silence contextual: 90 days quiet is 1.5 cycles overdue for a
customer who buys every 61 days, and completely normal for one who buys twice a year.
The old formula scored both identically. Correlation with Monetary fell from exactly
1.0 to 0.985.

Defaults: 3-year horizon, 20% margin, 10% discount rate, 365-day observation window —
all at the top of `rfm_analysis.py`. The observation window is the one to check, see
[Limitations](#limitations).

### The model half

Each customer has one recent message attached. Jev answers five questions per message,
batched into a single request because they are independent given the same text:

| Question | Returns |
|---|---|
| Are they signalling they want to leave? | Probability, 0–1 |
| How serious is the problem they describe? | Position on a 4-level scale |
| What is driving it? | service · price · product · competitor · circumstance · none |
| Could we still keep them if we acted now? | Probability, 0–1 |
| Does this need a person, or a campaign? | Probability, 0–1 |

Answers come back as **numbers, not prose** — values code can threshold, weight and
rank without parsing anything.

**Why not a trained classifier?** It learns from examples: thousands of messages, each
labelled by hand by someone who already knew the answer. This dataset has 100
customers and no labels, so there is nothing to train on. Beyond that cold start,
adding a question here takes minutes rather than a new labelled set, and each answer
carries a confidence figure the pipeline acts on.

That is not a claim it beats supervised learning. At high volume where per-call cost
dominates, or on a narrow task with abundant labels, a classifier is the better tool.
**This is the step before machine learning, not a replacement** — pair enough of these
judgments with real retention outcomes and they become features for a conventional
model.

### Where the two halves meet

**Judgments and policy are stored separately.** Inference writes raw judgments to
`rfm_signals.csv`; scoring is a separate step applying weights defined in code.
Changing a weight is not a new question, so re-scoring the base is free:

```bash
python rfm_signals.py --rescore
```

That separation paid for itself. My first composite blended intent and severity 60/40
— and because Jev correctly reads an unresolved failure as *low* intent to leave, that
blend filed a top-tier customer sitting on a maximum-severity failure as **safe.**
Exactly the customer who leaves without warning.

A weighted average is for preferences that trade off against each other. "Either of
these is bad on its own" needs `max`, not a blend. The fix cost **zero API calls**,
because the judgments were already on disk, and moved the blind-spot count from 1 to
5. With a trained model, the equivalent fix is a retrain.

**Confidence is acted on, not discarded.** Recommendations below a confidence floor
are marked ANALYST REVIEW on the slide rather than asserted — 2 of 8 segments in the
current run.

---

## Running it

Python 3, plus `matplotlib`, `seaborn`, `pandas`, `python-pptx` and `typesafe-sdk`.
The core analysis engine uses only the standard library.

```bash
export TYPESAFE_API_KEY=sk-...   # from https://console.typesafe.ai/
```

```bash
python rfm_analysis.py     # scores, segments, CLV
python make_verbatims.py   # sample customer messages
python rfm_signals.py      # language signals + composite priority
python rfm_plays.py        # recommended action per segment
python jev_dashboard.py    # charts of what the model did
python build_pptx.py       # 14-slide deck
python rfm_audit.py        # verification
```

Add `--offline` to any Jev step to run it without a key, using clearly-labelled stub
answers. Stubs cache to a separate directory from live results — sharing one cache
would let an offline run poison a later real one, since the cache key covers the
model, state and questions, none of which change when a key appears.

`python rfm_audit.py --rules-only` verifies the code against its own documentation
with no model involved, and no cost. A rule-ordering defect is a code bug and gets
fixed in code, never papered over with a probability.

---

## Repository map

| File | Role | Owner |
|---|---|---|
| `rfm_analysis.py` | Scoring, segmentation, CLV | Python |
| `rfm_dashboard.py` | The four RFM charts | Python |
| `make_verbatims.py` | Generates the sample customer messages | Python |
| `jev.py` | Shared client, caching, offline stubs | Python |
| `rfm_signals.py` | Five judgments per customer, then composite scoring | Both |
| `rfm_plays.py` | Selects a play per segment from a code-owned library | Both |
| `rfm_query.py` | Plain-English questions against the customer base | Both |
| `rfm_audit.py` | Code-versus-documentation verification | Both |
| `jev_dashboard.py` | Charts of what the model did | Python |
| `build_pptx.py` | The 14-slide deck | Python |

---

## Limitations

- **The customer messages are synthetic.** The source dataset is numeric only, so the
  verbatims were generated to demonstrate the method. The pipeline is real; the text
  it reads is not. About one customer in five was deliberately given a message that
  contradicts their RFM standing — that is what the blind-spot detection is tested
  against.
- **One dataset, 100 customers, 8 of 11 possible segments.** Nothing is validated
  against real retention outcomes. The confidence floor, blind-spot cut-offs and
  composite weights are reasoned starting points, not tuned ones.
- **`OBSERVATION_DAYS` is an assumption, not a measurement.** Recency, frequency and
  spend say nothing about how long the extract covered, so it is stated rather than
  derived. Every CLV figure scales with it.
- **Typed output guarantees the interface, not the truth.** A judgment arriving as a
  clean number between 0 and 1 says nothing about whether it is right. Any real
  deployment needs its performance measured on its own domain.

---

## License

MIT
