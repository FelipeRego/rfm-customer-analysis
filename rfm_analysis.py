import csv
import math
import statistics

# ── CONFIG ────────────────────────────────────────────────────────────────────
INPUT_FILE  = 'rfm_mockup.csv'
OUTPUT_FILE = 'rfm_analysis.csv'

LIFESPAN_YEARS = 3
MARGIN         = 0.20

# The window the source extract covers. This is an assumption about how the data was
# pulled, not something derivable from it — recency, frequency and spend say nothing
# about the observation period. Set it to your real extract window. (In rfm_mockup.csv
# the maximum recency is exactly 365, which is what a one-year window looks like.)
OBSERVATION_DAYS = 365

# Annual discount rate applied to future margin, so a dollar in year three is not
# counted as a dollar today.
DISCOUNT_RATE = 0.10

# How sharply the chance a customer is still active falls away once they are overdue.
# p_active = exp(-LAPSE_DECAY * lapse_ratio), so at 0.5 a customer exactly one full
# purchase-cycle silent sits at 0.61, two cycles at 0.37, four at 0.14.
LAPSE_DECAY = 0.5

# ── LOAD ──────────────────────────────────────────────────────────────────────
with open(INPUT_FILE, 'r') as f:
    data = list(csv.DictReader(f))

for row in data:
    row['recency']       = int(row['recency'])
    row['frequency']     = int(row['frequency'])
    row['monetaryValue'] = float(row['monetaryValue'])

# ── #1 RFM SCORING ────────────────────────────────────────────────────────────
n         = len(data)
recencies = sorted(r['recency'] for r in data)
monetaries = sorted(r['monetaryValue'] for r in data)

def r_score(recency):
    pct = recencies.index(recency) / n
    if pct < 0.20: return 5
    elif pct < 0.40: return 4
    elif pct < 0.60: return 3
    elif pct < 0.80: return 2
    else: return 1

def f_score(freq):
    if freq == 1: return 1
    elif freq == 2: return 2
    elif freq == 3: return 3
    elif freq == 4: return 4
    else: return 5  # 5 or 6

def m_score(monetary):
    pct = monetaries.index(monetary) / n
    if pct < 0.20: return 1
    elif pct < 0.40: return 2
    elif pct < 0.60: return 3
    elif pct < 0.80: return 4
    else: return 5

for row in data:
    row['r_score']   = r_score(row['recency'])
    row['f_score']   = f_score(row['frequency'])
    row['m_score']   = m_score(row['monetaryValue'])
    row['rfm_score'] = row['r_score'] + row['f_score'] + row['m_score']

# ── #2 SEGMENTATION ───────────────────────────────────────────────────────────
def segment(r, f):
    """Assign a segment from the R and F scores. FIRST MATCH WINS.

    This is an ordered chain, not a set of independent rules, and the order is
    load-bearing: several conditions below overlap, and an earlier one deliberately
    shadows a later one. 'At Risk' is checked before 'Loyal' precisely so that a
    frequent buyer who has gone quiet (R=2, F>=3) is flagged as lapsing rather than
    filed as loyal.

    Because of that, no single rule can be read on its own — a rule only means
    "this, AND none of the rules above it". The authoritative, unambiguous statement
    of this function is the 5x5 R-by-F grid in README.md, which rfm_audit.py checks
    against on every run. If you reorder anything here, that grid changes and the
    audit will tell you.
    """
    # Validate up front. Several rules below use >= and <=, so an out-of-range score
    # would otherwise be swallowed silently: r=0, f=3 satisfies `r <= 2 and f >= 3`
    # and would come back as a confident 'At Risk' for a customer who has no valid
    # score at all.
    if not (1 <= r <= 5 and 1 <= f <= 5):
        raise ValueError(f'r_score/f_score must each be 1-5, got r={r}, f={f}')

    if r >= 4 and f >= 4:   return 'Champions'
    if r == 1 and f >= 4:   return "Can't Lose Them"
    if r <= 2 and f >= 3:   return 'At Risk'
    if f >= 3 and r >= 2:   return 'Loyal'
    if r >= 4 and f == 1:   return 'New Customer'
    if r == 3 and f == 2:   return 'Need Attention'
    if r >= 3 and f == 2:   return 'Potential Loyalist'
    if r >= 3 and f == 1:   return 'Promising'
    if r == 2 and f == 2:   return 'About to Sleep'
    if r == 2 and f == 1:   return 'Hibernating'
    if r == 1 and f <= 2:   return 'Lost'
    # Unreachable: the 25 valid combinations are fully covered above, and anything
    # outside them was rejected by the range check. Kept so that a future edit which
    # opens a gap fails loudly instead of returning None.
    raise AssertionError(f'segmentation gap at r={r}, f={f}')

for row in data:
    row['segment'] = segment(row['r_score'], row['f_score'])

# ── #3 CLV ────────────────────────────────────────────────────────────────────
# The previous formula was `avg_order * frequency * LIFESPAN_YEARS * MARGIN`. Since
# avg_order is monetaryValue / frequency, the frequency terms cancel and the whole
# thing collapses to monetaryValue * 0.6 — a rescaling of M that told you nothing
# the M column did not already say. A customer who spent $1,000 across ten orders
# scored identically to one who spent $1,000 once and never came back.
#
# The fix is not a bigger multiplier. Any formula shaped like AOV x frequency x k
# collapses the same way, because AOV x frequency IS total spend. To say something
# new, CLV has to answer a question the spend total cannot: will they keep buying?
#
#   CLV = observed annual profit  x  P(still active)  x  discounted horizon
#
# Frequency now enters through P(still active) rather than through the spend term.
# Two customers with identical total spend get different CLV when one buys monthly
# and has been silent 90 days (badly overdue) and the other buys twice a year and
# has been silent 90 days (perfectly normal).

# An expected gap between purchases needs at least two purchases to observe. For
# single-purchase customers there is no observed cadence at all — 65 of the 100
# customers here are in that position — so borrow the median cadence of those who
# did repeat rather than treating the whole window as one giant gap, which would
# make a one-time buyer look punctual right up to day 364.
repeat_gaps = sorted(OBSERVATION_DAYS / r['frequency'] for r in data if r['frequency'] >= 2)
default_gap = statistics.median(repeat_gaps) if repeat_gaps else OBSERVATION_DAYS

observation_years = OBSERVATION_DAYS / 365
horizon = sum(1 / (1 + DISCOUNT_RATE) ** y for y in range(1, LIFESPAN_YEARS + 1))

for row in data:
    # Observed rate of spend, not a per-order figure — this is the term that used
    # to cancel, kept explicit so it cannot quietly reintroduce the same bug.
    annual_profit = (row['monetaryValue'] / observation_years) * MARGIN

    expected_gap = (OBSERVATION_DAYS / row['frequency']) if row['frequency'] >= 2 else default_gap
    lapse_ratio  = row['recency'] / expected_gap
    p_active     = math.exp(-LAPSE_DECAY * lapse_ratio)

    row['aov']           = round(row['monetaryValue'] / row['frequency'], 2)
    row['expected_gap']  = round(expected_gap, 1)
    row['p_active']      = round(p_active, 4)
    row['clv']           = round(annual_profit * p_active * horizon, 2)

# ── WRITE OUTPUT ──────────────────────────────────────────────────────────────
fieldnames = ['customerid', 'recency', 'frequency', 'monetaryValue',
              'r_score', 'f_score', 'm_score', 'rfm_score', 'segment',
              'aov', 'expected_gap', 'p_active', 'clv']

with open(OUTPUT_FILE, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)

# ── SUMMARY ───────────────────────────────────────────────────────────────────
print("=== Segment Distribution ===")
seg_counts, seg_clv = {}, {}
for row in data:
    s = row['segment']
    seg_counts[s] = seg_counts.get(s, 0) + 1
    seg_clv.setdefault(s, []).append(row['clv'])

for seg, count in sorted(seg_counts.items(), key=lambda x: -x[1]):
    avg_clv = round(statistics.mean(seg_clv[seg]), 2)
    print(f"  {seg:<22} {count:>3} customers   avg CLV: ${avg_clv:>8,.2f}")

clvs = [row['clv'] for row in data]
print(f"\n=== CLV Summary ===")
print(f"  Min:  ${min(clvs):>8,.2f}")
print(f"  Max:  ${max(clvs):>8,.2f}")
print(f"  Mean: ${statistics.mean(clvs):>8,.2f}")
print(f"  Total portfolio CLV: ${sum(clvs):>10,.2f}")
print(f"\nSaved: {OUTPUT_FILE}")
