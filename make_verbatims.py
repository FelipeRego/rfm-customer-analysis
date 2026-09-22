"""Generate synthetic customer verbatims for the RFM dataset.

`rfm_mockup.csv` is purely numeric, which means RFM can only ever see behaviour.
This script attaches a plausible free-text touchpoint to each customer — a support
ticket, survey response, or account note — so the pipeline has language to judge.

The assignment is deliberately adversarial. Roughly one customer in five gets a
verbatim that CONTRADICTS their RFM standing:

  * Champions and Loyal customers who are quietly furious and about to leave.
    RFM cannot see these — by construction, they still look like top customers.
  * Lost and Hibernating customers who are warm and recoverable, and who a
    behaviour-only model would write off.

Those contradiction cases are the whole point: they are where a stated-intent
signal earns its place alongside the behavioural one. The `contradicts_rfm`
column marks them so you can measure whether the composite score catches them.

    python make_verbatims.py

Output: rfm_verbatims.csv
"""

import csv
import random

INPUT_FILE  = 'rfm_analysis.csv'
OUTPUT_FILE = 'rfm_verbatims.csv'
SEED        = 20260922

# ── VERBATIM POOLS ────────────────────────────────────────────────────────────
POOLS = {
    'happy': [
        "Third order this quarter and the quality has been spot on every time. Whoever handles your packing deserves a raise.",
        "Just wanted to say the team sorted my delivery question in about four minutes. Refreshing.",
        "We've standardised on you for the whole office now. Easy decision.",
        "Been recommending you to everyone who'll listen. Keep doing what you're doing.",
        "The new range is exactly what I was after. Already planning the next order.",
        "No issues at all — just renewing. Same as last time please.",
        "Honestly the most painless supplier we deal with. Long may it continue.",
    ],
    'admin': [
        "Can you update the delivery address on my account? Moved offices last month.",
        "Do you have a copy of the invoice for order 4471? Finance needs it for reconciliation.",
        "Quick one — what's the current lead time on bulk orders?",
        "Need to change the card on file before the next order goes through.",
        "Is there a way to get a consolidated statement for the financial year?",
        "Can I add a second user to the account so my colleague can order directly?",
        "What's your returns window? Nothing wrong, just want to know before I order.",
    ],
    'service_failure': [
        "This is the fourth time I've had to chase this. Nobody calls back, nobody emails, and I'm still waiting on a resolution three weeks later. I've been a customer for years and this is how it goes.",
        "Order arrived damaged, I reported it the same day, and I've heard nothing since. I've spent a lot of money with you and I'm genuinely reconsidering.",
        "Your support team closed my ticket without fixing anything. I reopened it. They closed it again. I don't know what else to do here.",
        "Three separate people have given me three different answers. At this point I just want someone to own it.",
        "I've asked twice for a callback from a manager. Still nothing. That tells me everything I need to know about where I sit as a customer.",
        "Promised delivery date came and went with no notification. I had to find out from my own team that it hadn't arrived. Not good enough.",
        "The refund was supposed to be processed a month ago. I'm still out of pocket and still chasing. Losing patience fast.",
    ],
    'price': [
        "The price increase landed without much warning. Hard to justify internally at that level.",
        "We're getting quoted noticeably less elsewhere for the same spec. What can you do?",
        "Budget's been cut for next year so I'll need to review what we're spending with you.",
        "Love the product, but the freight charges are getting difficult to absorb.",
        "Renewal came through 18% higher. Can we talk about that before I sign anything?",
    ],
    'competitor': [
        "We've been trialling another supplier alongside you for the last two months. Their turnaround has been faster.",
        "A competitor approached us with a bundled deal that's hard to ignore. Wanted to give you the chance to respond.",
        "Procurement is running a formal tender this quarter. You'll be invited but so will three others.",
        "Honestly, the only reason we haven't switched is inertia. That won't hold forever.",
    ],
    'product_gap': [
        "Do you have anything in a larger format? The current size doesn't quite work for our use case.",
        "The product's fine but the online ordering experience is painful. Takes me ten minutes to do something that should take two.",
        "We need integration with our inventory system. Without it we're doing double entry every week.",
        "Missing the one SKU we order most. Had to go elsewhere for it, which rather defeats the purpose.",
        "Quality's been inconsistent across the last two batches. Not a dealbreaker yet but worth flagging.",
    ],
    'quiet_churn': [
        "Please close my account and remove me from the mailing list. Thanks.",
        "We've moved our business elsewhere. No hard feelings, it just wasn't working for us.",
        "Don't need anything further. You can stop the reminder emails.",
        "We've wound down the part of the business that used your products, so we won't be ordering again.",
        "Cancel the subscription please. I don't want to be charged again.",
    ],
    'winback': [
        "Sorry for going quiet — we had a restructure and everything got paused. Looking to start ordering again next quarter.",
        "Haven't ordered in a while because our project was on hold. It's back on now, so expect to hear from me.",
        "Still here! Just haven't had the need. Send me the new catalogue when it's out.",
        "We had a change of ops manager and things slipped. Keen to pick back up where we left off.",
        "Been using up old stock, that's all. We'll be back in the market shortly.",
    ],
}

# Normal verbatim mix per segment, and what a contradiction looks like for it.
SEGMENT_PROFILE = {
    'Champions':          {'normal': ['happy', 'happy', 'admin'],            'against': ['service_failure', 'competitor']},
    'Loyal':              {'normal': ['happy', 'admin', 'product_gap'],      'against': ['service_failure', 'competitor']},
    'Potential Loyalist': {'normal': ['admin', 'happy', 'product_gap'],      'against': ['service_failure']},
    'New Customer':       {'normal': ['admin', 'happy', 'product_gap'],      'against': ['service_failure']},
    'Promising':          {'normal': ['admin', 'product_gap', 'price'],      'against': ['quiet_churn']},
    'Hibernating':        {'normal': ['price', 'product_gap', 'admin'],      'against': ['winback']},
    'Lost':               {'normal': ['quiet_churn', 'price', 'competitor'], 'against': ['winback']},
    'At Risk':            {'normal': ['service_failure', 'price'],           'against': ['winback']},
    "Can't Lose Them":    {'normal': ['service_failure', 'competitor'],      'against': ['happy']},
    'Need Attention':     {'normal': ['product_gap', 'price'],               'against': ['service_failure']},
    'About to Sleep':     {'normal': ['price', 'admin'],                     'against': ['winback']},
}

CONTRADICTION_RATE = 0.20
CHANNELS = ['support ticket', 'survey response', 'account note', 'email to rep']

# ── GENERATE ──────────────────────────────────────────────────────────────────
rng = random.Random(SEED)

with open(INPUT_FILE) as f:
    customers = list(csv.DictReader(f))

rows = []
for c in customers:
    seg     = c['segment']
    profile = SEGMENT_PROFILE.get(seg, {'normal': ['admin'], 'against': ['service_failure']})

    contradicts = rng.random() < CONTRADICTION_RATE
    pool_name   = rng.choice(profile['against'] if contradicts else profile['normal'])

    rows.append({
        'customerid':      c['customerid'],
        'segment':         seg,
        'channel':         rng.choice(CHANNELS),
        'days_ago':        rng.randint(1, min(90, max(2, int(c['recency'])))),
        'verbatim':        rng.choice(POOLS[pool_name]),
        'pool':            pool_name,
        'contradicts_rfm': 'yes' if contradicts else 'no',
    })

with open(OUTPUT_FILE, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)

# ── SUMMARY ───────────────────────────────────────────────────────────────────
pool_counts = {}
for r in rows:
    pool_counts[r['pool']] = pool_counts.get(r['pool'], 0) + 1

print(f"Wrote {len(rows)} verbatims to {OUTPUT_FILE}\n")
print("=== Verbatim mix ===")
for pool, n in sorted(pool_counts.items(), key=lambda x: -x[1]):
    print(f"  {pool:<18} {n:>3}")

flagged = [r for r in rows if r['contradicts_rfm'] == 'yes']
print(f"\n=== Contradiction cases ({len(flagged)}) ===")
print("  Customers whose stated intent cuts against their RFM standing:")
for r in sorted(flagged, key=lambda r: r['segment'])[:12]:
    print(f"  {r['customerid']:<10} {r['segment']:<20} → {r['pool']}")
if len(flagged) > 12:
    print(f"  ... and {len(flagged) - 12} more")
