import csv
import statistics

# ── CONFIG ────────────────────────────────────────────────────────────────────
INPUT_FILE  = 'rfm_mockup.csv'
OUTPUT_FILE = 'rfm_analysis.csv'

LIFESPAN_YEARS = 3
MARGIN         = 0.20

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
    if r >= 4 and f >= 4:   return 'Champions'
    if r == 1 and f >= 4:   return "Can't Lose Them"
    if r <= 2 and f >= 3:   return 'At Risk'
    if f >= 3 and r >= 2:   return 'Loyal'
    if r >= 4 and f == 1:   return 'New Customer'
    if r == 3 and f in (2, 3): return 'Need Attention'
    if r >= 3 and f == 2:   return 'Potential Loyalist'
    if r >= 3 and f == 1:   return 'Promising'
    if r == 2 and f == 2:   return 'About to Sleep'
    if r == 2 and f == 1:   return 'Hibernating'
    if r == 1 and f <= 2:   return 'Lost'
    return 'Promising'

for row in data:
    row['segment'] = segment(row['r_score'], row['f_score'])

# ── #3 CLV ────────────────────────────────────────────────────────────────────
for row in data:
    avg_order  = row['monetaryValue'] / row['frequency']
    row['clv'] = round(avg_order * row['frequency'] * LIFESPAN_YEARS * MARGIN, 2)

# ── WRITE OUTPUT ──────────────────────────────────────────────────────────────
fieldnames = ['customerid', 'recency', 'frequency', 'monetaryValue',
              'r_score', 'f_score', 'm_score', 'rfm_score', 'segment', 'clv']

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
