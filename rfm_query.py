"""Ask the customer base questions in plain English.

    python rfm_query.py "who's worth emailing this week?"
    python rfm_query.py "top 10 champions by lifetime value"
    python rfm_query.py "which lapsed customers are complaining about service?"

Jev chooses the shape of the query; code executes it. Every threshold — what counts
as "lapsed", where the high-value band starts, how ranking works — is defined below
in Python and never asked of the model. The model's job is to decide that you meant
"lapsed and valuable, ranked by value", not to decide that lapsed means 63 days.

All questions go out in a single request (speculative fan-out). Most of the answers
are discarded: if you asked for a segment summary, the sort and limit answers are
irrelevant and are simply not read.
"""

import csv
import os
import sys

from typesafe_sdk import Choice, Noul

import jev

# ── CONFIG ────────────────────────────────────────────────────────────────────
ANALYSIS_FILE = 'rfm_analysis.csv'
PRIORITY_FILE = 'rfm_priority.csv'   # optional; enables driver filters and priority sort

# Code owns every threshold. The model picks a band name, not a number.
RECENCY_BANDS = {
    'recent':  lambda r: r <= 30,
    'lapsed':  lambda r: 30 < r <= 90,
    'dormant': lambda r: r > 90,
    'any':     lambda r: True,
}

CONFIDENCE_FLOOR = 0.45   # below this, show the query interpretation but warn


# ── QUESTIONS ─────────────────────────────────────────────────────────────────
def build_questions(segments, drivers):
    qs = {
        'on_topic': Noul(
            instructions=(
                "`request` is typed into a tool that queries a customer database. That "
                "database holds, per customer: days since last purchase, purchase count, "
                "total spend, an RFM segment, and an estimated lifetime value. Is the "
                "request asking for something this database could answer?"
            ),
        ),

        'action': Choice(
            instructions="What does `request` want the tool to produce?",
            criteria={
                'list_customers': "A list of individual customers matching some description.",
                'segment_summary': "A per-segment breakdown — counts and averages by segment, "
                                   "rather than named individuals.",
                'portfolio_overview': "Totals across the whole customer base.",
                'count_only': "Just how many customers match, with no listing.",
            },
        ),

        'segment_filter': Choice(
            instructions=(
                "Which RFM segment is `request` asking about? Choose 'any' unless the request "
                "names a segment or describes one unmistakably."
            ),
            criteria={**{s: None for s in segments}, 'any': "No particular segment."},
        ),

        'recency_band': Choice(
            instructions="How recently active are the customers `request` is asking about?",
            criteria={
                'recent':  "Currently active — bought very recently.",
                'lapsed':  "Has gone quiet, but not long ago. Slipping away.",
                'dormant': "Silent for a long stretch. Likely gone.",
                'any':     "The request says nothing about how recently they bought.",
            },
        ),

        'value_band': Choice(
            instructions="What spending level is `request` asking about?",
            criteria={
                'high': "The most valuable customers — big spenders, top accounts.",
                'mid':  "Middling spend. Explicitly the middle, not the top or bottom.",
                'low':  "Low spenders, or small accounts.",
                'any':  "The request says nothing about spend level.",
            },
        ),

        'sort_by': Choice(
            instructions="If `request` produces a ranked list, what should it be ranked on?",
            criteria={
                'clv':       "Estimated lifetime value. The default sense of 'best' or 'worth most'.",
                'recency':   "How long since they bought.",
                'frequency': "How many times they've bought.",
                'monetary':  "Total historical spend.",
                'priority':  "Urgency of acting — who needs attention first, who to contact now.",
            },
        ),

        'direction': Choice(
            instructions="Should the ranked list lead with the highest values or the lowest?",
            criteria={
                'high_first': "Largest, best, most, longest-lapsed first.",
                'low_first':  "Smallest, least, most recent first.",
            },
        ),

        'limit': Choice(
            instructions="How many rows does `request` want back?",
            criteria={
                '5': "A short list — a handful, the top few.",
                '10': "A standard top-ten style list, or no number given.",
                '25': "A longer working list.",
                'all': "Explicitly everything matching, with no cut-off.",
            },
        ),
    }

    if drivers:
        qs['driver_filter'] = Choice(
            instructions=(
                "Each customer has a recorded reason for dissatisfaction. Is `request` asking "
                "about one particular reason?"
            ),
            criteria={**{d: None for d in drivers},
                      'any': "The request does not single out a reason."},
        )
    return qs


# ── EXECUTION (deterministic) ─────────────────────────────────────────────────
def value_bounds(rows):
    clvs = sorted(float(r['clv']) for r in rows)
    n    = len(clvs)
    return clvs[int(n * 0.75)], clvs[int(n * 0.25)]


def execute(rows, plan):
    hi, lo   = value_bounds(rows)
    in_band  = RECENCY_BANDS[plan['recency_band']]
    matching = []

    for r in rows:
        clv = float(r['clv'])
        if plan['segment_filter'] != 'any' and r['segment'] != plan['segment_filter']:
            continue
        if not in_band(int(r['recency'])):
            continue
        if plan['value_band'] == 'high' and clv < hi:
            continue
        if plan['value_band'] == 'low' and clv > lo:
            continue
        if plan['value_band'] == 'mid' and not (lo <= clv <= hi):
            continue
        if plan.get('driver_filter', 'any') != 'any' and r.get('driver') != plan['driver_filter']:
            continue
        matching.append(r)

    keys = {'clv': 'clv', 'recency': 'recency', 'frequency': 'frequency',
            'monetary': 'monetaryValue', 'priority': 'priority'}
    key = keys[plan['sort_by']]
    if key in (matching[0] if matching else {}):
        matching.sort(key=lambda r: float(r[key]),
                      reverse=(plan['direction'] == 'high_first'))
    return matching


# ── OUTPUT ────────────────────────────────────────────────────────────────────
def show(rows, matching, plan, answers):
    bits = [f"{plan['action']}"]
    if plan['segment_filter'] != 'any':   bits.append(f"segment={plan['segment_filter']}")
    if plan['recency_band'] != 'any':     bits.append(f"recency={plan['recency_band']}")
    if plan['value_band'] != 'any':       bits.append(f"value={plan['value_band']}")
    if plan.get('driver_filter', 'any') != 'any': bits.append(f"driver={plan['driver_filter']}")
    bits.append(f"sort={plan['sort_by']} {plan['direction']}")
    print(f"Interpreted as:  {'  '.join(bits)}")

    weak_id, weak_conf = jev.weakest(answers)
    if weak_conf < CONFIDENCE_FLOOR:
        print(f"  ! Least certain: '{weak_id}' at {weak_conf:.2f} confidence. "
              f"Rephrase if that part looks wrong.")
    print()

    if plan['action'] == 'count_only':
        print(f"{len(matching)} customers match.")
        return

    if plan['action'] == 'portfolio_overview':
        total = sum(float(r['clv']) for r in matching)
        print(f"  Customers:  {len(matching)}")
        print(f"  Total CLV:  ${total:,.2f}")
        print(f"  Avg CLV:    ${total / len(matching):,.2f}" if matching else "")
        return

    if plan['action'] == 'segment_summary':
        by_seg = {}
        for r in matching:
            by_seg.setdefault(r['segment'], []).append(float(r['clv']))
        print(f"  {'segment':<22} {'n':>4} {'avg CLV':>11} {'total CLV':>12}")
        for seg, clvs in sorted(by_seg.items(), key=lambda x: -sum(x[1])):
            print(f"  {seg:<22} {len(clvs):>4} ${sum(clvs)/len(clvs):>10,.2f} ${sum(clvs):>11,.2f}")
        return

    limit = len(matching) if plan['limit'] == 'all' else int(plan['limit'])
    shown = matching[:limit]
    print(f"  {'customer':<11} {'segment':<20} {'rec':>5} {'freq':>5} {'CLV':>10}"
          + ("  driver" if 'driver' in (shown[0] if shown else {}) else ""))
    for r in shown:
        line = (f"  {r['customerid']:<11} {r['segment']:<20} {int(r['recency']):>5} "
                f"{int(r['frequency']):>5} ${float(r['clv']):>9,.2f}")
        if 'driver' in r:
            line += f"  {r['driver']}"
        print(line)
    print(f"\n  {len(shown)} of {len(matching)} matching customers shown.")


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    request = ' '.join(a for a in sys.argv[1:] if not a.startswith('--')).strip()
    if not request:
        raise SystemExit('Usage: python rfm_query.py "your question about the customer base"')

    jev.banner()

    with open(ANALYSIS_FILE) as f:
        rows = list(csv.DictReader(f))

    # Fold in Jev's churn signals when rfm_signals.py has already run.
    drivers = []
    if os.path.exists(PRIORITY_FILE):
        with open(PRIORITY_FILE) as f:
            extra = {r['customerid']: r for r in csv.DictReader(f)}
        for r in rows:
            e = extra.get(r['customerid'])
            if e:
                r['driver']   = e['driver']
                r['priority'] = e['priority']
        drivers = sorted({e['driver'] for e in extra.values()})

    segments = sorted({r['segment'] for r in rows})
    qs       = build_questions(segments, drivers)
    answers  = jev.ask({'request': request}, qs)

    # A stub on_topic value is a coin flip, and would block the path offline mode
    # exists to exercise. The gate is skipped rather than faked.
    if jev.OFFLINE:
        print("  (on-topic gate skipped — stub answers carry no signal)\n")
    elif answers['on_topic']['noul'] < 0.5:
        raise SystemExit(
            f"That doesn't look like a question this data can answer "
            f"({answers['on_topic']['noul']:.2f}).\n"
            f"The database holds recency, frequency, spend, RFM segment and CLV per customer."
        )

    plan = {k: a['choice'] for k, a in answers.items()
            if isinstance(a, dict) and a.get('type') == 'choice'}

    if plan['sort_by'] == 'priority' and 'priority' not in rows[0]:
        print("  (priority ranking needs rfm_signals.py to have run — falling back to CLV)\n")
        plan['sort_by'] = 'clv'

    show(rows, execute(rows, plan), plan, answers)
