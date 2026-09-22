"""Add a stated-intent signal to RFM, and combine the two in code.

RFM is a behavioural model. It reads what a customer DID — how recently, how often,
how much. That makes it structurally blind to what a customer has SAID. A Champion
who just had a billing dispute go unanswered for three weeks still scores 5/5/5 the
day before they leave.

This script asks Jev a small set of independent judgments about each customer's
most recent verbatim, writes the raw answers to rfm_signals.csv, and then combines
them with the RFM scores using weights that live in WEIGHTS below.

The split matters. Inference produces reusable raw judgments; policy applies weights
to them. Changing a weight is not a new question, so:

    python rfm_signals.py            # ask Jev, write raw judgments, then score
    python rfm_signals.py --rescore  # re-apply weights to existing judgments, no API calls
    python rfm_signals.py --offline  # exercise the plumbing with stub answers

Outputs: rfm_signals.csv (raw judgments), rfm_priority.csv (scored + ranked)
"""

import csv
import sys

from typesafe_sdk import Choice, Noul, NoulCriteria, Score

import jev

# ── CONFIG ────────────────────────────────────────────────────────────────────
ANALYSIS_FILE  = 'rfm_analysis.csv'
VERBATIM_FILE  = 'rfm_verbatims.csv'
SIGNALS_FILE   = 'rfm_signals.csv'
PRIORITY_FILE  = 'rfm_priority.csv'

# Policy lives here, not in the questions. Tune freely and re-run with --rescore.
WEIGHTS = {
    'value':            0.30,   # how much of the portfolio walks out the door
    'behavioural_risk': 0.25,   # what RFM alone can see
    'stated_risk':      0.45,   # what the customer actually told us
}

# How much an unresolved top-severity problem counts as risk on its own, with no
# stated intent to leave at all. At 0.9 a 3-of-3 failure outranks most spoken threats.
SEVERITY_WEIGHT = 0.90

# A customer is a blind spot when RFM says they're fine and they told us otherwise.
BLINDSPOT_BEHAVIOURAL_MAX = 0.40
BLINDSPOT_STATED_MIN      = 0.55

RESCORE_ONLY = '--rescore' in sys.argv


# ── QUESTIONS ─────────────────────────────────────────────────────────────────
def questions_for():
    """The judgments asked about each verbatim.

    All five are independent given the same state, so they go in one request and
    run in parallel. None of them re-derives anything code already knows: recency,
    frequency, spend and segment are facts, and they stay facts.
    """
    return {
        'churn_intent': Noul(
            instructions=(
                "Read `verbatim`, the customer's most recent message to us. Is the customer "
                "signalling that they intend to stop buying from us, reduce their spend, or "
                "take their business elsewhere? Judge what this message conveys about their "
                "intent, not whether their purchase history looks healthy."
            ),
            criteria=NoulCriteria(
                true=("States or clearly implies they are leaving, cancelling, winding down, "
                      "actively comparing suppliers, or reconsidering the relationship — "
                      "including polite or indirect versions of this."),
                false=("Routine request, praise, a specific complaint they plainly expect us to "
                       "fix, or an explanation for a quiet period that says they intend to "
                       "return. Frustration on its own is not an intent to leave."),
            ),
        ),

        'severity': Score(
            instructions=(
                "Read `verbatim`. How serious is the problem this customer is describing, "
                "from our side of the relationship? Judge the problem described, not the "
                "customer's tone or how valuable the account is."
            ),
            criteria=[
                "No problem at all. Praise, a routine question, or an administrative request.",
                "A minor irritation or an unmet preference. Nothing has gone wrong that costs "
                "the customer money or time in any material way.",
                "Something has genuinely gone wrong — a failure, an error, or a cost increase "
                "the customer has to absorb — but it is contained and still fixable.",
                "A serious or repeated failure. The customer has already been let down more "
                "than once, is out of pocket, or has escalated without resolution.",
            ],
        ),

        'driver': Choice(
            instructions=(
                "Read `verbatim`. What is the primary thing driving this customer's "
                "dissatisfaction or hesitation? Choose the single dominant driver."
            ),
            criteria={
                'service': {
                    'what': "How we handled them — delays, no response, unresolved tickets, "
                            "repeated chasing, errors in fulfilment.",
                    'not_for': "Dissatisfaction with the product itself.",
                },
                'price': {
                    'what': "Cost — price rises, freight charges, budget pressure, or being "
                            "quoted less elsewhere for the same thing.",
                },
                'product': {
                    'what': "The product or platform itself — gaps in the range, quality "
                            "inconsistency, missing features, a painful ordering experience.",
                },
                'competitor': {
                    'what': "Another supplier is actively in the picture — trialling, tendering, "
                            "or an approach they are weighing up.",
                    'not_for': "Merely mentioning that something is expensive.",
                },
                'circumstance': {
                    'what': "Something on their side, not ours — a restructure, a paused project, "
                            "a wound-down business line, or using up existing stock.",
                },
                'none': {
                    'what': "No dissatisfaction or hesitation is present.",
                    'examples': ["Praise", "A routine admin request"],
                },
            },
        ),

        'recoverable': Noul(
            instructions=(
                "Read `verbatim`. If we acted on this in the next two weeks — a call from a "
                "person, a fix, or a concrete offer — is it plausible we keep or reactivate "
                "this customer?"
            ),
            criteria=NoulCriteria(
                true=("They are still engaged enough to respond: complaining to us rather than "
                      "about us, inviting a response, giving us a chance to fix it, or "
                      "explaining a pause they expect to end."),
                false=("Already gone or decided — account closed, business moved, or the "
                       "relationship discussed in the past tense with nothing asked of us."),
            ),
        ),

        'needs_human': Noul(
            instructions=(
                "Read `verbatim`. Does responding to this require a person, rather than an "
                "automated campaign email or a standard offer?"
            ),
            criteria=NoulCriteria(
                true="Escalated, emotionally charged, commercially complex, or asking for a callback.",
                false="A routine request or a sentiment that a well-targeted campaign could address.",
            ),
        ),
    }


# ── INFERENCE ─────────────────────────────────────────────────────────────────
def gather_signals(customers, verbatims):
    """One request per customer, five parallel judgments each. Cached by jev.ask."""
    qs   = questions_for()
    rows = []

    for i, c in enumerate(customers, 1):
        v = verbatims.get(c['customerid'])
        if not v:
            continue

        # Only the verbatim and its framing go in. The RFM numbers are deliberately
        # withheld: if the model could see a 5/5/5 profile it would be tempted to
        # reason from the behaviour we are trying to cross-check it against.
        state = {
            'verbatim': v['verbatim'],
            'channel':  v['channel'],
            'days_ago': int(v['days_ago']),
        }

        answers = jev.ask(state, qs)
        sev     = answers['severity']
        weak_id, weak_conf = jev.weakest(answers)

        rows.append({
            'customerid':       c['customerid'],
            'churn_intent':     round(answers['churn_intent']['noul'], 3),
            'severity':         round(sev['score'], 3),
            'severity_max':     len(qs['severity'].criteria) - 1,
            'driver':           answers['driver']['choice'],
            'driver_conf':      round(answers['driver']['confidence'], 3),
            'recoverable':      round(answers['recoverable']['noul'], 3),
            'needs_human':      round(answers['needs_human']['noul'], 3),
            'weakest_question': weak_id,
            'weakest_conf':     round(weak_conf, 3),
        })

        if i % 20 == 0:
            print(f"  ...{i}/{len(customers)}")

    with open(SIGNALS_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote raw judgments: {SIGNALS_FILE}\n")
    return rows


# ── COMPOSITE SCORING ─────────────────────────────────────────────────────────
def behavioural_risk(c):
    """What RFM alone can see. 0 = healthy, 1 = badly lapsed.

    Recency carries more weight than frequency: a customer who has gone quiet is a
    clearer warning than one who simply buys in small numbers.
    """
    r_risk = 1 - (int(c['r_score']) - 1) / 4
    f_risk = 1 - (int(c['f_score']) - 1) / 4
    return round(r_risk * 0.6 + f_risk * 0.4, 3)


def stated_risk(s):
    """What the customer told us. 0 = content, 1 = we are about to lose them.

    There are two independent ways to be in danger, and averaging them hides both:

      1. They told us they are leaving.  ("Please close my account.")
      2. Something serious went wrong and is not fixed.  ("Fourth time I've chased
         this.")  Jev reads these as LOW intent to leave — correctly, because the
         customer is complaining TO us rather than walking away. But an unresolved
         3-out-of-3 failure is the classic silent departure: no warning, just gone.

    This first shipped as `churn_intent * 0.6 + severity * 0.4`, which scored a
    Champion sitting on a maximum-severity failure at 0.39 — filed as safe. A
    weighted average is for preferences that genuinely trade off against each other.
    "Either of these is bad on its own" needs `max`, not a blend.
    """
    severity_norm = float(s['severity']) / float(s['severity_max'])
    intent_risk   = float(s['churn_intent'])
    failure_risk  = severity_norm * SEVERITY_WEIGHT

    raw = max(intent_risk, failure_risk)
    # Someone we can plausibly still reach is a smaller loss risk than someone gone.
    return round(raw * (1 - 0.25 * float(s['recoverable'])), 3)


def score(customers, signals):
    by_id   = {s['customerid']: s for s in signals}
    max_clv = max(float(c['clv']) for c in customers)
    scored  = []

    for c in customers:
        s = by_id.get(c['customerid'])
        if not s:
            continue

        value = round(float(c['clv']) / max_clv, 3)
        b     = behavioural_risk(c)
        st    = stated_risk(s)

        priority = (WEIGHTS['value'] * value
                    + WEIGHTS['behavioural_risk'] * b
                    + WEIGHTS['stated_risk'] * st)

        scored.append({
            'customerid':       c['customerid'],
            'segment':          c['segment'],
            'clv':              float(c['clv']),
            'value':            value,
            'behavioural_risk': b,
            'stated_risk':      st,
            'priority':         round(priority, 3),
            'driver':           s['driver'],
            'churn_intent':     float(s['churn_intent']),
            'recoverable':      float(s['recoverable']),
            'needs_human':      float(s['needs_human']),
            'blind_spot':       ('yes' if b <= BLINDSPOT_BEHAVIOURAL_MAX
                                 and st >= BLINDSPOT_STATED_MIN else 'no'),
            'route':            ('human' if float(s['needs_human']) > 0.6 else 'campaign'),
        })

    scored.sort(key=lambda r: -r['priority'])
    with open(PRIORITY_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(scored[0]))
        writer.writeheader()
        writer.writerows(scored)
    return scored


# ── REPORT ────────────────────────────────────────────────────────────────────
def report(scored):
    print("=== Weights in force ===")
    for k, v in WEIGHTS.items():
        print(f"  {k:<18} {v:.2f}")

    print(f"\n=== Top 15 by retention priority ===")
    print(f"  {'customer':<10} {'segment':<20} {'CLV':>9}  {'behav':>6} {'stated':>6} "
          f"{'prio':>6}  {'driver':<12} route")
    for r in scored[:15]:
        flag = ' *' if r['blind_spot'] == 'yes' else '  '
        print(f"{flag}{r['customerid']:<10} {r['segment']:<20} ${r['clv']:>8,.0f}  "
              f"{r['behavioural_risk']:>6.2f} {r['stated_risk']:>6.2f} {r['priority']:>6.3f}  "
              f"{r['driver']:<12} {r['route']}")

    blind = [r for r in scored if r['blind_spot'] == 'yes']
    print(f"\n=== RFM blind spots ({len(blind)}) ===")
    print("  Healthy on behaviour, telling us they're unhappy. RFM alone ranks these safe.")
    for r in blind:
        print(f"  {r['customerid']:<10} {r['segment']:<20} ${r['clv']:>8,.0f}  "
              f"stated risk {r['stated_risk']:.2f}  driver: {r['driver']}")
    exposure = sum(r['clv'] for r in blind)
    print(f"\n  CLV sitting in the blind spot: ${exposure:,.0f} "
          f"({exposure / sum(r['clv'] for r in scored) * 100:.1f}% of portfolio)")

    drivers = {}
    for r in scored:
        drivers[r['driver']] = drivers.get(r['driver'], 0) + 1
    print(f"\n=== Primary drivers across the base ===")
    for d, n in sorted(drivers.items(), key=lambda x: -x[1]):
        print(f"  {d:<14} {n:>3}")

    humans = [r for r in scored if r['route'] == 'human']
    print(f"\n  {len(humans)} customers routed to a person, {len(scored) - len(humans)} to campaign.")
    print(f"\nWrote: {PRIORITY_FILE}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    jev.banner()

    with open(ANALYSIS_FILE) as f:
        customers = list(csv.DictReader(f))
    with open(VERBATIM_FILE) as f:
        verbatims = {r['customerid']: r for r in csv.DictReader(f)}

    if RESCORE_ONLY:
        with open(SIGNALS_FILE) as f:
            signals = list(csv.DictReader(f))
        print(f"Re-scoring {len(signals)} cached judgments — no API calls.\n")
    else:
        print(f"Asking Jev about {len(customers)} verbatims "
              f"({len(questions_for())} questions each, batched per customer)...")
        signals = gather_signals(customers, verbatims)

    report(score(customers, signals))
