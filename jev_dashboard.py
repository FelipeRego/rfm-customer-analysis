"""Visualise what Jev actually did — how it scored, and what that surfaced.

Four charts, each answering one question:

  1. Who did the language flag that the numbers did not?   (scatter, two axes of risk)
  2. Is "angry" the same as "leaving"?                     (paired dots per message type)
  3. What is driving dissatisfaction?                      (ranked bars)
  4. How sure was the model about each recommendation?     (ranked bars against a floor)

Palette is the three-colour Okabe-Ito subset, validated for colour-vision deficiency
and for contrast against a white surface. Every series is direct-labelled as well as
coloured, so identity never depends on colour alone.

    python jev_dashboard.py

Requires rfm_signals.py and rfm_plays.py to have run.
"""

import csv
import json
import os

import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import matplotlib.patches as mpatches

import rfm_signals  # thresholds only — the main block is guarded

# ── STYLE ─────────────────────────────────────────────────────────────────────
BLUE   = '#0072B2'   # the ordinary case
ORANGE = '#D55E00'   # the flagged case
GREEN  = '#009E73'   # the reassuring case
MUTED  = '#B0B0B0'
BG     = '#FFFFFF'
SPINE  = '#CCCCCC'
INK    = '#111111'
INK2   = '#444444'

plt.rcParams.update({
    'font.family': 'DejaVu Sans', 'text.color': INK,
    'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2,
    'axes.facecolor': BG, 'figure.facecolor': BG,
    'xtick.labelsize': 9.5, 'ytick.labelsize': 9.5, 'axes.labelsize': 10.5,
})


def clean(ax, keep_left=True):
    ax.grid(False)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    ax.spines['left'].set_color(SPINE if keep_left else 'none')
    ax.spines['bottom'].set_color(SPINE)
    ax.tick_params(axis='both', length=0)


def save(fig, name):
    fig.savefig(name, dpi=150, bbox_inches='tight', facecolor=BG)
    plt.close(fig)
    print(f'Saved: {name}')


# ── LOAD ──────────────────────────────────────────────────────────────────────
with open('rfm_priority.csv') as f:
    priority = list(csv.DictReader(f))
with open('rfm_signals.csv') as f:
    signals = {r['customerid']: r for r in csv.DictReader(f)}
with open('rfm_verbatims.csv') as f:
    verbatims = {r['customerid']: r for r in csv.DictReader(f)}
plays = json.load(open('rfm_plays.json')) if os.path.exists('rfm_plays.json') else {}

for p in priority:
    for k in ('behavioural_risk', 'stated_risk', 'clv'):
        p[k] = float(p[k])

BEHAV_MAX  = rfm_signals.BLINDSPOT_BEHAVIOURAL_MAX
STATED_MIN = rfm_signals.BLINDSPOT_STATED_MIN


# ── 1. WHAT THE NUMBERS MISSED ────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 6))

# The blind-spot region: healthy on behaviour, unhappy in their own words.
ax.add_patch(mpatches.Rectangle((0, STATED_MIN), BEHAV_MAX, 1 - STATED_MIN,
                                facecolor=ORANGE, alpha=0.07, zorder=0))
ax.axvline(BEHAV_MAX, color=MUTED, lw=1, ls='--', zorder=1)
ax.axhline(STATED_MIN, color=MUTED, lw=1, ls='--', zorder=1)

flagged = [p for p in priority if p['blind_spot'] == 'yes']
rest    = [p for p in priority if p['blind_spot'] == 'no']

for group, color, label, z in ((rest, BLUE, 'Consistent — numbers and words agree', 2),
                               (flagged, ORANGE, 'Flagged by language alone', 3)):
    ax.scatter([p['behavioural_risk'] for p in group], [p['stated_risk'] for p in group],
               s=[18 + p['clv'] / 6 for p in group], color=color, alpha=0.8,
               edgecolors='white', linewidth=1.2, zorder=z, label=label)

# Direct labels, so identity never rests on colour alone. Several flagged customers
# sit almost on top of each other, so each label takes the first position — above,
# below, left, right — that does not collide with one already placed.
X_PTS, Y_PTS = 500, 346          # approximate points per axis unit at this figure size
LBL_W, LBL_H = 58, 24            # approximate label footprint in points

placed = []
CANDIDATES = [((0, 15), 'center'), ((0, -30), 'center'),
              ((-13, -4), 'right'), ((13, -4), 'left')]

for p in sorted(flagged, key=lambda p: (-p['stated_risk'], p['behavioural_risk'])):
    mx, my = p['behavioural_risk'] * X_PTS, p['stated_risk'] * Y_PTS
    for (dx, dy), ha in CANDIDATES:
        lx, ly = mx + dx, my + dy
        if all(abs(lx - ox) > LBL_W or abs(ly - oy) > LBL_H for ox, oy in placed):
            break
    placed.append((lx, ly))
    # A label pushed sideways or below is no longer unambiguously "the dot above me",
    # so it gets a thin leader back to its own marker.
    leader = (dict(arrowprops=dict(arrowstyle='-', color=MUTED, lw=0.8,
                                   shrinkA=2, shrinkB=6))
              if (dx, dy) != (0, 15) else {})
    ax.annotate(f"{p['customerid']}\n${p['clv']:,.0f}",
                (p['behavioural_risk'], p['stated_risk']),
                textcoords='offset points', xytext=(dx, dy), ha=ha,
                fontsize=8, color=INK, fontweight='bold', linespacing=1.3, **leader)

ax.text(BEHAV_MAX / 2, 0.97, 'THE BLIND SPOT', ha='center', fontsize=8.5,
        fontweight='bold', color=ORANGE)
ax.text(BEHAV_MAX / 2, 0.925, 'buying normally · telling us they are unhappy',
        ha='center', fontsize=8, color=INK2)

ax.set_xlabel('What the purchase history shows  →  lapsing')
ax.set_ylabel('What the customer told us  →  at risk')
ax.set_title('What the Numbers Could Not See',
             fontsize=13, fontweight='bold', color=INK, pad=12, loc='left')
ax.set_xlim(-0.04, 1.04)
ax.set_ylim(0, 1.04)
ax.legend(fontsize=9, frameon=False, loc='upper center',
          bbox_to_anchor=(0.5, -0.10), ncol=2, columnspacing=2.5)
ax.text(1.0, -0.175, 'Marker size = lifetime value', ha='right', fontsize=8,
        color=INK2, transform=ax.transAxes)
clean(ax)
plt.tight_layout()
save(fig, 'jev_chart_1_blindspots.png')


# ── 2. ANGRY IS NOT THE SAME AS LEAVING ───────────────────────────────────────
LABELS = {
    'quiet_churn':     'Quietly closing the account',
    'competitor':      'Weighing up a competitor',
    'price':           'Objecting to price',
    'service_failure': 'Unresolved service failure',
    'product_gap':     'Product does not fit',
    'winback':         'Paused, intending to return',
    'admin':           'Routine admin request',
    'happy':           'Unprompted praise',
}

pools = {}
for cid, v in verbatims.items():
    s = signals.get(cid)
    if s:
        pools.setdefault(v['pool'], []).append(s)

rows = []
for pool, rs in pools.items():
    intent = sum(float(r['churn_intent']) for r in rs) / len(rs)
    sev    = sum(float(r['severity']) / float(r['severity_max']) for r in rs) / len(rs)
    rows.append((LABELS.get(pool, pool), intent, sev, len(rs)))
rows.sort(key=lambda r: r[1])

fig, ax = plt.subplots(figsize=(9.5, 6))
for i, (label, intent, sev, n) in enumerate(rows):
    ax.plot([intent, sev], [i, i], color=MUTED, lw=2, zorder=1, solid_capstyle='round')
    ax.scatter([intent], [i], s=110, color=ORANGE, zorder=3, edgecolors='white', linewidth=1.2)
    ax.scatter([sev],    [i], s=110, color=BLUE,   zorder=3, edgecolors='white', linewidth=1.2)
    lo, hi = sorted([(intent, ORANGE), (sev, BLUE)], key=lambda t: t[0])
    ax.annotate(f'{lo[0]:.2f}', (lo[0], i), textcoords='offset points', xytext=(-10, -3.5),
                ha='right', fontsize=8.5, color=INK2)
    ax.annotate(f'{hi[0]:.2f}', (hi[0], i), textcoords='offset points', xytext=(10, -3.5),
                ha='left', fontsize=8.5, color=INK2)

ax.set_yticks(range(len(rows)))
ax.set_yticklabels([f'{r[0]}  ({r[3]})' for r in rows], fontsize=9.5)
ax.set_xlim(-0.12, 1.12)
ax.set_xlabel('Score returned by the model  (0 – 1)')
ax.set_title('"Angry" and "leaving" are not the same thing',
             fontsize=13, fontweight='bold', color=INK, pad=40, loc='left')
ax.text(0, 1.025, 'An unresolved failure scores HIGH on severity and LOW on intent to leave — '
                  'the customer is complaining to us, not walking away.',
        transform=ax.transAxes, fontsize=9, color=INK2)
ax.legend(handles=[
    mlines.Line2D([], [], color=ORANGE, marker='o', linestyle='None', markersize=9,
                  label='Intends to leave'),
    mlines.Line2D([], [], color=BLUE, marker='o', linestyle='None', markersize=9,
                  label='Severity of the problem'),
], fontsize=9, frameon=False, loc='lower right')
clean(ax, keep_left=False)
ax.spines['left'].set_visible(False)
plt.tight_layout()
save(fig, 'jev_chart_2_intent_vs_severity.png')


# ── 3. WHAT IS DRIVING IT ─────────────────────────────────────────────────────
DRIVER_LABELS = {
    'service': 'How we handled them', 'price': 'Cost', 'product': 'The product itself',
    'competitor': 'A competitor', 'circumstance': 'Something on their side',
    'none': 'Nothing — content',
}
counts = {}
for p in priority:
    counts[p['driver']] = counts.get(p['driver'], 0) + 1
items = sorted(counts.items(), key=lambda x: x[1])

fig, ax = plt.subplots(figsize=(9, 5.2))
colors = [GREEN if d == 'none' else BLUE for d, _ in items]
bars = ax.barh(range(len(items)), [c for _, c in items], color=colors,
               height=0.58, edgecolor='none')
for i, (d, c) in enumerate(items):
    ax.text(c + 0.6, i, str(c), va='center', fontsize=10, fontweight='bold', color=INK)

ax.set_yticks(range(len(items)))
ax.set_yticklabels([DRIVER_LABELS.get(d, d) for d in [d for d, _ in items]], fontsize=10)
ax.set_xlim(0, max(counts.values()) + 5)
ax.set_xticks([])
ax.set_title('What is driving dissatisfaction',
             fontsize=13, fontweight='bold', color=INK, pad=40, loc='left')
ax.text(0, 1.03, f'Across {len(priority)} customer messages, read one at a time.',
        transform=ax.transAxes, fontsize=9, color=INK2)
ax.legend(handles=[
    mpatches.Patch(color=BLUE, label='Something to act on'),
    mpatches.Patch(color=GREEN, label='No issue raised'),
], fontsize=9, frameon=False, loc='lower right')
clean(ax, keep_left=False)
ax.spines['left'].set_visible(False)
plt.tight_layout()
save(fig, 'jev_chart_3_drivers.png')


# ── 4. HOW SURE WAS IT ────────────────────────────────────────────────────────
if plays:
    FLOOR = 0.50
    items = sorted(plays.items(), key=lambda kv: kv[1]['confidence'])

    fig, ax = plt.subplots(figsize=(9, 5.2))
    colors = [ORANGE if p['confidence'] < FLOOR else BLUE for _, p in items]
    ax.barh(range(len(items)), [p['confidence'] for _, p in items], color=colors,
            height=0.58, edgecolor='none')
    ax.axvline(FLOOR, color=INK2, lw=1.2, ls='--', zorder=3)
    # The threshold line is vertical, so "below" would be wrong — bars that stop
    # short of it are the flagged ones.
    ax.text(FLOOR - 0.015, -0.85, 'anything short of this line is flagged for review',
            fontsize=8.5, color=INK2, ha='right')

    for i, (seg, p) in enumerate(items):
        ax.text(p['confidence'] + 0.015, i, f"{p['confidence']:.2f}  ·  {p['title']}",
                va='center', fontsize=9, color=INK)

    ax.set_yticks(range(len(items)))
    ax.set_yticklabels([seg for seg, _ in items], fontsize=10)
    ax.set_xlim(0, 1.5)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xlabel('How sure the model was about the recommended play')
    ax.set_title('The model says when it is not sure',
                 fontsize=13, fontweight='bold', color=INK, pad=40, loc='left')
    ax.text(0, 1.03, 'Low confidence means several plays were defensible — not that the answer is wrong.',
            transform=ax.transAxes, fontsize=9, color=INK2)
    ax.legend(handles=[
        mpatches.Patch(color=BLUE, label='Recommended as-is'),
        mpatches.Patch(color=ORANGE, label='Flagged for analyst review'),
    ], fontsize=9, frameon=False, loc='lower right')
    clean(ax, keep_left=False)
    ax.spines['left'].set_visible(False)
    plt.tight_layout()
    save(fig, 'jev_chart_4_confidence.png')

print('\nDone. Four charts written.')
