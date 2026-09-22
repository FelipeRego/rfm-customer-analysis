"""Choose a retention/growth play for each segment, instead of hardcoding one.

Slide 8 of the deck used to carry four fixed recommendations written for this
particular dataset. Point the pipeline at real data and they quietly stop being
true, because nothing recomputes them.

This script keeps the play library in code — every play, its channel, its cost and
who owns it are facts we decide, not things a model invents — and asks Jev only the
judgment part: given what this segment looks like and what these customers have been
telling us, which play fits, and how urgent is it?

Low-confidence picks are not silently rendered. They are marked for analyst review
on the slide itself, which is the honest thing to put in front of a board.

    python rfm_plays.py            # choose plays, write rfm_plays.json
    python rfm_plays.py --offline  # stub answers, exercises build_pptx wiring

Output: rfm_plays.json (consumed by build_pptx.py; the deck falls back to its
built-in recommendations if this file is absent)
"""

import csv
import json
import os
import statistics

from typesafe_sdk import Choice, Score

import jev

# ── CONFIG ────────────────────────────────────────────────────────────────────
ANALYSIS_FILE = 'rfm_analysis.csv'
PRIORITY_FILE = 'rfm_priority.csv'   # optional, adds driver context from rfm_signals.py
OUTPUT_FILE   = 'rfm_plays.json'

# Below this, the deck prints "ANALYST REVIEW" rather than asserting the play.
CONFIDENCE_FLOOR = 0.50

# ── PLAY LIBRARY ──────────────────────────────────────────────────────────────
# Facts about each play live here. Jev selects among them; it does not define them.
PLAYS = {
    'vip_programme': {
        'title':   'Formalise a VIP tier',
        'deck':    "Dedicated contact, early access, exclusive pricing tier",
        'what':    "Dedicated contact, early access to new range, exclusive pricing tier, "
                   "minimum quarterly touchpoint.",
        'best_for': "A healthy, high-value group that is still buying happily. The default for segments with strong recency, strong frequency and no complaint on record.",
        'not_for': "Any group with an unresolved complaint, or one that has already gone quiet. A loyalty perk is not an answer to a failure, and it cannot reach the absent.",
        'horizon': 'Defend', 'channel': 'Account management', 'cost': 'High',
    },
    'service_recovery': {
        'title':   'Run a service recovery',
        'deck':    "Name the failure, fix it, compensate, manager closes the loop",
        'what':    "Acknowledge the failure by name, fix it, compensate, and have a manager "
                   "close the loop personally.",
        'best_for': "A group whose dominant theme is service — unresolved tickets, repeated chasing, fulfilment errors. Use whenever service is the leading driver, regardless of how healthy their purchase history looks.",
        'not_for': "Groups with no service complaint. Price, product gaps and quiet lapsing each need their own answer.",
        'horizon': 'Defend', 'channel': 'Human — manager', 'cost': 'Medium',
    },
    'exec_outreach': {
        'title':   'Senior relationship call',
        'deck':    "Senior person calls to understand the account. No offer attached",
        'what':    "A senior person calls to understand the relationship. No offer attached, "
                   "no campaign framing.",
        'best_for': "A SMALL number of individually large accounts showing a specific, named commercial threat — a live competitor or a contract under review — where the relationship itself is the thing at stake.",
        'not_for': "Content, healthy groups with nothing wrong — there is nothing for a senior call to address, and it burns expensive time. Also not for large groups or low-value accounts, where the cost per call cannot be justified. If the issue is a service failure, a price objection or simple inactivity, the dedicated play for that beats a general relationship call.",
        'horizon': 'Defend', 'channel': 'Human — senior', 'cost': 'High',
    },
    'price_review': {
        'title':   'Proactive commercial review',
        'deck':    "Open the pricing and terms conversation before they do",
        'what':    "Open the pricing and terms conversation before they do — review freight, "
                   "volume breaks, and contract structure.",
        'best_for': "A group whose dominant theme is cost — price rises, freight, budget pressure, or being quoted less elsewhere.",
        'not_for': "Groups whose issue is service quality or product fit. Discounting a service failure does not fix it.",
        'horizon': 'Defend', 'channel': 'Account management', 'cost': 'Medium',
    },
    'second_purchase': {
        'title':   'Drive the second purchase',
        'deck':    "Time-limited incentive to convert first-time buyers to repeat",
        'what':    "Time-limited incentive aimed squarely at converting a first-time buyer "
                   "into a repeat one.",
        'best_for': "Recent first-time buyers who have not yet bought again. The single highest-leverage moment in the customer lifecycle.",
        'not_for': "Established repeat buyers, and anyone who has already lapsed.",
        'horizon': 'Grow', 'channel': 'Email campaign', 'cost': 'Low',
    },
    'loyalty_onboarding': {
        'title':   'Onboard into the loyalty programme',
        'deck':    "Structured nurture sequence into the loyalty programme",
        'what':    "Structured nurture sequence that builds a buying habit and enrols them "
                   "into the loyalty scheme.",
        'best_for': "Recent buyers with two or three purchases — the habit is forming but not set.",
        'not_for': "One-time buyers, who need a second purchase first, and lapsed customers, whom nurture does not reach.",
        'horizon': 'Grow', 'channel': 'Email campaign', 'cost': 'Low',
    },
    'cross_sell': {
        'title':   'Targeted cross-sell',
        'deck':    "Adjacent-product recommendations to lift order value",
        'what':    "Recommend adjacent products based on what this group already buys, to "
                   "raise order value rather than order count.",
        'best_for': "Active, content buyers where the opportunity is a bigger basket rather than more visits or retention.",
        'not_for': "Any group signalling dissatisfaction or drifting away. Selling into a complaint makes it worse.",
        'horizon': 'Grow', 'channel': 'Email campaign', 'cost': 'Low',
    },
    'referral_ask': {
        'title':   'Ask for referrals',
        'deck':    "Invite satisfied customers to refer, rewarding both sides",
        'what':    "Invite genuinely satisfied customers to refer, with a reward for both sides.",
        'best_for': "Groups that are explicitly happy, with praise on record and no open issues.",
        'not_for': "Anyone with an unresolved issue, and anyone who has gone quiet.",
        'horizon': 'Grow', 'channel': 'Email campaign', 'cost': 'Low',
    },
    'winback_offer': {
        'title':   'Time-boxed win-back',
        'deck':    "Expiring reactivation offer, with a measured control group",
        'what':    "A concrete, expiring reactivation offer with a defined window and a "
                   "measured control group.",
        'best_for': "Lapsed groups that are still plausibly reachable — gone quiet, but not gone for good, and still worth a concrete offer.",
        'not_for': "Currently active customers, who would simply be discounted for buying anyway, and groups already written off.",
        'horizon': 'Recover', 'channel': 'Email campaign', 'cost': 'Medium',
    },
    'content_nurture': {
        'title':   'Low-cost content nurture',
        'deck':    "Light, useful, no-offer presence at near-zero cost",
        'what':    "Keep a light, useful presence with no offer attached, so the relationship "
                   "stays warm at near-zero cost.",
        'best_for': "Low-value or uncertain groups worth staying in front of cheaply, where a paid offer cannot be justified but writing them off is premature.",
        'not_for': "Urgent situations, high-value accounts at real risk, and anything needing a person this week. It is the cheap option, not the safe one.",
        'horizon': 'Recover', 'channel': 'Email campaign', 'cost': 'Low',
    },
    'sunset': {
        'title':   'Sunset and stop spending',
        'deck':    "Cease active spend, retain minimal list, redirect budget",
        'what':    "Stop active marketing spend, retain on a minimal list, and redirect the "
                   "budget to recoverable groups.",
        'best_for': "Groups that are gone and not coming back, where continued spend is waste.",
        'not_for': "Anyone still responding, anyone recoverable, and any group with meaningful lifetime value still attached.",
        'horizon': 'Recover', 'channel': 'None — cease spend', 'cost': 'None',
    },
}


# ── SEGMENT PROFILE ───────────────────────────────────────────────────────────
def profile(seg, members, signals):
    """Describe a segment the way a person would, for judgment rather than arithmetic."""
    n        = len(members)
    avg_rec  = statistics.mean(int(m['recency']) for m in members)
    avg_freq = statistics.mean(int(m['frequency']) for m in members)
    avg_clv  = statistics.mean(float(m['clv']) for m in members)
    tot_clv  = sum(float(m['clv']) for m in members)

    # Whether a group is lapsed depends on their own rhythm, not a fixed number of
    # days. A group that buys twice a year and last bought 70 days ago is not lapsed;
    # one that buys monthly and last bought 70 days ago is. Without this the model
    # reads any largish recency as "gone" and reaches for a win-back offer.
    avg_gap    = statistics.mean(float(m['expected_gap']) for m in members)
    avg_active = statistics.mean(float(m['p_active']) for m in members)
    overdue    = avg_rec / avg_gap

    if overdue < 0.75:
        cadence = (f"That is well within their normal rhythm — this group is currently "
                   f"active and buying on schedule, not lapsed.")
    elif overdue < 1.25:
        cadence = (f"That is right around their normal rhythm, so they are due about now. "
                   f"They have not lapsed yet, but they are at the point where they either "
                   f"buy again or start drifting.")
    elif overdue < 2.5:
        cadence = (f"That is roughly {overdue:.1f} times their normal gap, so this group is "
                   f"genuinely overdue and slipping away.")
    else:
        cadence = (f"That is about {overdue:.0f} times their normal gap. This group has "
                   f"stopped buying rather than merely paused.")

    text = (f"This group holds {n} customers. On average they have bought "
            f"{avg_freq:.1f} times, and their last purchase was {avg_rec:.0f} days ago. "
            f"Customers in this group typically buy about every {avg_gap:.0f} days. "
            f"{cadence} "
            f"Each is worth about ${avg_clv:,.0f} in estimated lifetime value "
            f"(${tot_clv:,.0f} across the group).")

    state = {'segment_name': seg, 'segment_profile': text}

    # What these customers have actually said, when rfm_signals.py has run.
    mine = [s for s in signals if s['customerid'] in {m['customerid'] for m in members}]
    if mine:
        drivers = {}
        for s in mine:
            drivers[s['driver']] = drivers.get(s['driver'], 0) + 1
        top   = sorted(drivers.items(), key=lambda x: -x[1])
        churn = statistics.mean(float(s['churn_intent']) for s in mine)
        human = sum(1 for s in mine if float(s['needs_human']) > 0.6)
        state['what_they_told_us'] = (
            f"Across {len(mine)} recent messages from this group, the dominant themes were: "
            + ", ".join(f"{d} ({c})" for d, c in top[:3]) + ". "
            f"On average they read as {churn:.0%} likely to be signalling an intent to leave, "
            f"and {human} of them look like they need a person rather than a campaign email."
        )
    return state


# ── QUESTIONS ─────────────────────────────────────────────────────────────────
QUESTIONS = {
    'play': Choice(
        instructions=(
            "`segment_profile` describes a group of customers, and `what_they_told_us` "
            "summarises what they have recently said to us, where we have it. Which single "
            "play should we run on this group next? Pick the play whose `best_for` actually "
            "describes this group, and rule out any whose `not_for` applies. Prefer the "
            "specific play for this group's dominant problem over a general-purpose one."
        ),
        criteria={k: {'what': v['what'], 'best_for': v['best_for'], 'not_for': v['not_for']}
                  for k, v in PLAYS.items()},
    ),
    'urgency': Score(
        instructions=(
            "How urgently does this group need acting on? Judge the cost of waiting — "
            "how much is lost, and how fast, if nothing is done."
        ),
        criteria=[
            "No urgency. The group is stable and nothing is being lost by waiting.",
            "Worth planning. Act this quarter, but nothing breaks if it slips a few weeks.",
            "Act this month. Value is actively leaking and the window is closing.",
            "Act this week. High-value customers are on the point of leaving.",
        ],
    ),
    'reversibility': Score(
        instructions=(
            "If we do nothing for this group for six months, how recoverable will they "
            "still be? Judge how far gone they would be by then."
        ),
        criteria=[
            "Fully recoverable. They would still be here and still buying.",
            "Mostly recoverable, but it would take real effort and cost to re-engage them.",
            "Largely gone. A minority might return; most would not.",
        ],
    ),
}


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    jev.banner()

    with open(ANALYSIS_FILE) as f:
        customers = list(csv.DictReader(f))

    signals = []
    if os.path.exists(PRIORITY_FILE):
        with open(PRIORITY_FILE) as f:
            signals = list(csv.DictReader(f))
        print(f"Using churn signals from {PRIORITY_FILE} as extra context.\n")
    else:
        print(f"No {PRIORITY_FILE} — choosing plays on RFM profile alone.\n"
              f"Run rfm_signals.py first for materially better context.\n")

    by_seg = {}
    for c in customers:
        by_seg.setdefault(c['segment'], []).append(c)

    order   = sorted(by_seg, key=lambda s: -sum(float(m['clv']) for m in by_seg[s]))
    results = {}

    print(f"Choosing a play for each of {len(order)} segments...\n")
    print(f"  {'segment':<22} {'play':<32} {'urg':>5} {'conf':>6}  flag")

    for seg in order:
        members = by_seg[seg]
        answers = jev.ask(profile(seg, members, signals), QUESTIONS)

        pick    = answers['play']
        urgency = answers['urgency']
        rev     = answers['reversibility']
        play    = PLAYS[pick['choice']]
        low     = pick['confidence'] < CONFIDENCE_FLOOR

        runner_up = sorted(pick['probabilities'].items(), key=lambda x: -x[1])[1:2]

        results[seg] = {
            'count':            len(members),
            'total_clv':        round(sum(float(m['clv']) for m in members), 2),
            'play':             pick['choice'],
            'title':            play['title'],
            'what':             play['what'],
        'deck':             play['deck'],
            'horizon':          play['horizon'],
            'channel':          play['channel'],
            'cost':             play['cost'],
            'confidence':       round(pick['confidence'], 3),
            'runner_up':        runner_up[0][0] if runner_up else None,
            'urgency':          round(urgency['score'], 2),
            'urgency_max':      len(QUESTIONS['urgency'].criteria) - 1,
            'urgency_label':    urgency['legend'].get(str(round(urgency['score'])))
                                or urgency['legend'].get(round(urgency['score']), ''),
            'reversibility':    round(rev['score'], 2),
            'needs_review':     low,
        }

        flag = 'ANALYST REVIEW' if low else ''
        print(f"  {seg:<22} {play['title']:<32} {urgency['score']:>5.1f} "
              f"{pick['confidence']:>6.2f}  {flag}")

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(results, f, indent=2)

    review = [s for s, r in results.items() if r['needs_review']]
    print(f"\nWrote {OUTPUT_FILE}")
    if review:
        print(f"  {len(review)} segment(s) below the {CONFIDENCE_FLOOR} confidence floor and")
        print(f"  marked for analyst review on the slide: {', '.join(review)}")
    print(f"\n  Rebuild the deck to pick these up:  python build_pptx.py")
