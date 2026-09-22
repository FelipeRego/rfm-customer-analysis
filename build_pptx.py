import csv
import json
import os
import statistics
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
import copy

# ── COLOURS ───────────────────────────────────────────────────────────────────
NAVY       = RGBColor(0x00, 0x33, 0x66)
BLUE       = RGBColor(0x00, 0x70, 0xC0)
LIGHT_BLUE = RGBColor(0xBD, 0xD7, 0xEE)
WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
DARK       = RGBColor(0x1A, 0x1A, 0x1A)
GRAY       = RGBColor(0x59, 0x59, 0x59)
LGRAY      = RGBColor(0xF2, 0xF2, 0xF2)
RED        = RGBColor(0xC0, 0x00, 0x00)
GOLD       = RGBColor(0xFF, 0xC0, 0x00)
GOLD_DARK  = RGBColor(0xB8, 0x86, 0x00)
GREEN      = RGBColor(0x00, 0x70, 0x50)
DIVIDER    = RGBColor(0xD6, 0xD6, 0xD6)

# ── LOAD DATA ─────────────────────────────────────────────────────────────────
with open('rfm_analysis.csv') as f:
    rows = list(csv.DictReader(f))
for r in rows:
    r['clv'] = float(r['clv'])
    r['frequency'] = int(r['frequency'])
    r['recency'] = int(r['recency'])
    r['monetaryValue'] = float(r['monetaryValue'])

total = len(rows)
total_clv = sum(r['clv'] for r in rows)
LIFESPAN_LABEL = '3-year'

seg_data = {}
for r in rows:
    s = r['segment']
    seg_data.setdefault(s, []).append(r)

seg_summary = {
    s: {
        'count': len(v),
        'avg_clv': round(statistics.mean(x['clv'] for x in v), 0),
        'total_clv': round(sum(x['clv'] for x in v), 0),
        'avg_recency': round(statistics.mean(x['recency'] for x in v), 0),
        'avg_frequency': round(statistics.mean(x['frequency'] for x in v), 1),
    }
    for s, v in seg_data.items()
}

seg_order = sorted(seg_summary, key=lambda s: -seg_summary[s]['avg_clv'])


def seg_clv_p75(seg):
    """Top-quartile CLV within a segment.

    These thresholds used to be hardcoded at $450, which silently stopped selecting
    anyone the moment the CLV formula changed scale. A percentile moves with the data.
    """
    vals = sorted(x['clv'] for x in seg_data.get(seg, []))
    return vals[int(len(vals) * 0.75)] if vals else 0


# ── JEV SIGNAL DATA (optional) ────────────────────────────────────────────────
# Written by rfm_signals.py. Absent until that has run, in which case the two
# language slides are skipped and the deck builds exactly as before.
PRIORITY_FILE = 'rfm_priority.csv'
priority = []
if os.path.exists(PRIORITY_FILE):
    with open(PRIORITY_FILE) as f:
        priority = list(csv.DictReader(f))
    for p in priority:
        for k in ('clv', 'stated_risk', 'behavioural_risk', 'priority', 'churn_intent'):
            p[k] = float(p[k])

# Raw judgments, for figures that need severity rather than the composite score.
signals = {}
if os.path.exists('rfm_signals.csv'):
    with open('rfm_signals.csv') as f:
        signals = {r['customerid']: r for r in csv.DictReader(f)}

blind_spots = sorted([p for p in priority if p['blind_spot'] == 'yes'],
                     key=lambda p: -p['clv'])
blind_clv   = sum(p['clv'] for p in blind_spots)
needs_human = [p for p in priority if p['route'] == 'human']

driver_counts = {}
for p in priority:
    if p['driver'] != 'none':
        driver_counts[p['driver']] = driver_counts.get(p['driver'], 0) + 1

SYNTHETIC_NOTE = ('Customer messages in this analysis are illustrative sample text, '
                  'generated to demonstrate the method. Replace with real support '
                  'and survey data before acting on named accounts.')

champ = seg_summary.get('Champions', {})
loyal = seg_summary.get('Loyal', {})
lost  = seg_summary.get('Lost', {})
hiber = seg_summary.get('Hibernating', {})
promising = seg_summary.get('Promising', {})
new_cust = seg_summary.get('New Customer', {})
pot_loyal = seg_summary.get('Potential Loyalist', {})

value_segs = ['Champions', 'Loyal']
value_count = sum(seg_summary[s]['count'] for s in value_segs if s in seg_summary)
value_clv   = sum(seg_summary[s]['total_clv'] for s in value_segs if s in seg_summary)
value_pct_c = round(value_count / total * 100)
value_pct_v = round(value_clv / total_clv * 100)

at_risk_segs = ['At Risk', "Can't Lose Them", 'Hibernating', 'Lost']
at_risk_count = sum(seg_summary[s]['count'] for s in at_risk_segs if s in seg_summary)
at_risk_clv   = sum(seg_summary[s]['total_clv'] for s in at_risk_segs if s in seg_summary)
at_risk_pct_c = round(at_risk_count / total * 100)

growth_segs = ['New Customer', 'Promising', 'Potential Loyalist']
growth_count = sum(seg_summary[s]['count'] for s in growth_segs if s in seg_summary)
growth_pct_c = round(growth_count / total * 100)

# ── HELPERS ───────────────────────────────────────────────────────────────────
prs = Presentation()
prs.slide_width  = Inches(13.33)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]

def slide():
    return prs.slides.add_slide(BLANK)

def box(s, x, y, w, h, fill=None, line=None):
    sh = s.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.line.fill.background() if line is None else None
    if fill:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
    else:
        sh.fill.background()
    if line is None:
        sh.line.fill.background()
    return sh

def txt(s, text, x, y, w, h, size=11, bold=False, color=DARK, align=PP_ALIGN.LEFT,
        italic=False, wrap=True):
    txb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    txb.word_wrap = wrap
    tf = txb.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return txb

def header_band(s, title, subtitle=None):
    box(s, 0, 0, 13.33, 1.1, fill=NAVY)
    txt(s, title, 0.4, 0.12, 11, 0.55, size=20, bold=True, color=WHITE)
    if subtitle:
        txt(s, subtitle, 0.4, 0.65, 11, 0.38, size=11, color=LIGHT_BLUE)

def slide_number(s, n):
    txt(s, str(n), 12.8, 7.1, 0.4, 0.3, size=9, color=GRAY, align=PP_ALIGN.RIGHT)

def footer_line(s):
    ln = s.shapes.add_connector(1,
        Inches(0.4), Inches(7.15), Inches(12.93), Inches(7.15))
    ln.line.color.rgb = DIVIDER
    ln.line.width = Pt(0.5)
    txt(s, 'CONFIDENTIAL — RFM Customer Analysis', 0.4, 7.18, 6, 0.25,
        size=7, color=GRAY)

def kpi_card(s, x, y, w, h, label, value, sub=None, bg=LGRAY, val_color=NAVY):
    box(s, x, y, w, h, fill=bg)
    txt(s, label, x+0.15, y+0.1, w-0.3, 0.3, size=9, color=GRAY)
    txt(s, value, x+0.15, y+0.38, w-0.3, 0.55, size=22, bold=True, color=val_color)
    if sub:
        txt(s, sub, x+0.15, y+0.9, w-0.3, 0.25, size=8, color=GRAY)

def bullet(tf, text, size=10.5, bold=False, color=DARK, indent=0):
    p = tf.add_paragraph()
    p.alignment = PP_ALIGN.LEFT
    p.level = indent
    run = p.add_run()
    run.text = ('    ' * indent) + text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return p

def section_label(s, text, x, y):
    txt(s, text.upper(), x, y, 3, 0.22, size=7.5, bold=True, color=BLUE)

# ── SLIDE 1 — TITLE ───────────────────────────────────────────────────────────
s1 = slide()
box(s1, 0, 0, 13.33, 7.5, fill=NAVY)
box(s1, 0, 3.6, 13.33, 0.04, fill=GOLD)
# accent stripe
box(s1, 0, 0, 0.18, 7.5, fill=BLUE)

txt(s1, 'Unlocking Customer Value Through\nBehavioural Segmentation',
    0.55, 1.4, 9.5, 1.9, size=36, bold=True, color=WHITE)
txt(s1, 'RFM Analysis — Customer Intelligence Report',
    0.55, 3.25, 9, 0.45, size=14, color=LIGHT_BLUE)
txt(s1, f'Analysis across {total} customers  |  {len(seg_summary)} of 11 behavioural segments present  |  {LIFESPAN_LABEL} CLV horizon',
    0.55, 3.85, 10, 0.35, size=11, color=LIGHT_BLUE, italic=True)
txt(s1, 'March 2026', 0.55, 6.9, 4, 0.35, size=10, color=LIGHT_BLUE)
txt(s1, 'CONFIDENTIAL', 10.5, 6.9, 2.5, 0.35, size=9, color=GOLD,
    align=PP_ALIGN.RIGHT)

# ── SLIDE 2 — EXECUTIVE SUMMARY ───────────────────────────────────────────────
s2 = slide()
header_band(s2, 'Executive Summary',
            'Three findings define the commercial opportunity in this customer base')
footer_line(s2)
slide_number(s2, 2)

findings = [
    (BLUE,  '01',
     f'Champions & Loyal represent {value_pct_c}% of customers but deliver {value_pct_v}% of total portfolio CLV',
     f'{value_count} customers — avg CLV ${champ["avg_clv"]:,.0f} (Champions) and ${loyal["avg_clv"]:,.0f} (Loyal). '
     'Protecting and deepening these relationships is the highest-return priority.'),
    (RED,   '02',
     f'{at_risk_pct_c}% of the base shows lapsing signals — representing recoverable CLV at risk',
     f'{at_risk_count} customers across Hibernating, Lost, At Risk, and Can\'t Lose Them segments. '
     'Targeted win-back programmes could recapture a meaningful share of this value before permanent churn.'),
    (GREEN, '03',
     f'{growth_pct_c}% of customers are in early-stage growth segments with conversion potential',
     f'{growth_count} customers across New Customer, Promising, and Potential Loyalist. '
     'Structured onboarding and loyalty nudges can migrate these cohorts toward higher-value segments.'),
]

for i, (col, num, headline, detail) in enumerate(findings):
    y = 1.3 + i * 1.85
    box(s2, 0.4, y, 0.06, 1.4, fill=col)
    txt(s2, num, 0.6, y, 0.6, 0.4, size=11, bold=True, color=col)
    txt(s2, headline, 1.3, y, 11.2, 0.42, size=12.5, bold=True, color=DARK)
    txt(s2, detail,   1.3, y+0.42, 11.2, 0.9, size=10, color=GRAY)

# ── SLIDE 3 — METHODOLOGY ─────────────────────────────────────────────────────
s3 = slide()
header_band(s3, 'Methodology',
            'RFM scoring translates transactional data into actionable behavioural profiles')
footer_line(s3)
slide_number(s3, 3)

steps = [
    ('R — Recency', 'Days since last purchase.\nLower recency = higher score (1–5).\nCustomers scored via percentile rank.',         BLUE),
    ('F — Frequency', 'Number of distinct purchases.\nDirect ladder: 1 tx → score 1,\n5+ tx → score 5.',                            NAVY),
    ('M — Monetary', 'Total spend to date.\nHigher spend = higher score (1–5).\nCustomers scored via percentile rank.',              BLUE),
    ('Segmentation', '11 segments assigned via\nR×F score matrix — from\nChampions to Lost.',                                        NAVY),
    ('CLV Estimate', 'avg_order × freq × 3 yrs × 20%\nmargin. Consistent 3-year\nhorizon for comparability.',                       BLUE),
]

for i, (title, body, col) in enumerate(steps):
    x = 0.4 + i * 2.55
    box(s3, x, 1.25, 2.35, 0.06, fill=col)
    txt(s3, f'{i+1}', x, 1.45, 0.4, 0.38, size=18, bold=True, color=col)
    txt(s3, title,   x, 1.9,  2.2, 0.35, size=11, bold=True, color=DARK)
    txt(s3, body,    x, 2.32, 2.2, 1.0,  size=9.5, color=GRAY)

box(s3, 0.4, 3.55, 12.5, 0.04, fill=DIVIDER)

txt(s3, 'Configuration', 0.4, 3.75, 3, 0.3, size=9, bold=True, color=NAVY)
configs = [
    ('Input file', 'rfm_mockup.csv'),
    ('Customers analysed', f'{total}'),
    ('CLV lifespan', '3 years'),
    ('Margin assumption', '20%'),
    ('Segments', '11'),
    ('Output file', 'rfm_analysis.csv'),
]
for i, (k, v) in enumerate(configs):
    col_x = 0.4 + (i % 3) * 4.1
    row_y = 4.05 + (i // 3) * 0.45
    txt(s3, f'{k}:  ', col_x, row_y, 1.8, 0.35, size=9.5, color=GRAY)
    txt(s3, v, col_x + 1.55, row_y, 2.3, 0.35, size=9.5, bold=True, color=DARK)

# ── SLIDE 4 — SEGMENT LANDSCAPE ───────────────────────────────────────────────
s4 = slide()
header_band(s4, 'Segment Landscape',
            f'The {total}-customer base spans 11 segments with a total estimated portfolio CLV of ${total_clv:,.0f}')
footer_line(s4)
slide_number(s4, 4)

headers = ['Segment', 'Customers', 'Share', 'Avg CLV', 'Total CLV', 'Avg Recency', 'Strategic Priority']
col_xs  = [0.35, 2.85, 3.75, 4.75, 5.95, 7.35, 8.55]
col_ws  = [2.45, 0.85, 0.95, 1.15, 1.35, 1.15, 4.3]

box(s4, 0.35, 1.2, 12.6, 0.38, fill=NAVY)
for hdr, cx, cw in zip(headers, col_xs, col_ws):
    txt(s4, hdr, cx+0.05, 1.24, cw, 0.3, size=8.5, bold=True, color=WHITE)

priorities = {
    'Champions':          ('Protect & deepen — highest CLV, highest loyalty',       GREEN),
    'Loyal':              ('Reward & upsell — consistent, high-value base',          GREEN),
    'Potential Loyalist': ('Nudge to loyalty — targeted incentives',                 BLUE),
    'Promising':          ('Onboard & engage — early-stage, high conversion upside', BLUE),
    'New Customer':       ('Welcome & educate — first impression drives LTV',        BLUE),
    'Hibernating':        ('Re-engage — time-sensitive before permanent churn',      RED),
    'Lost':               ('Win-back — selective recovery, low probability',         RED),
}

for i, seg in enumerate(seg_order):
    d    = seg_summary[seg]
    pri, pcol = priorities.get(seg, ('Monitor', GRAY))
    bg = LGRAY if i % 2 == 0 else WHITE
    y  = 1.62 + i * 0.52
    box(s4, 0.35, y, 12.6, 0.5, fill=bg)

    vals = [
        (seg,                                                 DARK,  True),
        (str(d['count']),                                     DARK,  False),
        (f"{round(d['count']/total*100)}%",                   GRAY,  False),
        (f"${d['avg_clv']:,.0f}",                             NAVY,  True),
        (f"${d['total_clv']:,.0f}",                           NAVY,  False),
        (f"{d['avg_recency']} days",                          GRAY,  False),
        (pri,                                                 pcol,  False),
    ]
    for (v, vc, vb), cx, cw in zip(vals, col_xs, col_ws):
        txt(s4, v, cx+0.05, y+0.1, cw-0.1, 0.3, size=9, bold=vb, color=vc)

# ── SLIDE 5 — VALUE CONCENTRATION ─────────────────────────────────────────────
s5 = slide()
header_band(s5,
    f'Champions and Loyal customers ({value_pct_c}% of base) generate {value_pct_v}% of total portfolio CLV',
    'The classic 80/20 dynamic is present — concentration at the top is both an asset and a risk')
footer_line(s5)
slide_number(s5, 5)

kpis = [
    ('Champions — Avg CLV',    f'${champ["avg_clv"]:,.0f}',  f'{champ["count"]} customers  |  avg recency {champ["avg_recency"]} days'),
    ('Loyal — Avg CLV',        f'${loyal["avg_clv"]:,.0f}',  f'{loyal["count"]} customers  |  avg recency {loyal["avg_recency"]} days'),
    ('Portfolio Total CLV',    f'${total_clv:,.0f}',          f'Across all {total} customers'),
    ('Value Seg. CLV Share',   f'{value_pct_v}%',             f'Delivered by {value_pct_c}% of customers'),
]
for i, (lbl, val, sub) in enumerate(kpis):
    kpi_card(s5, 0.4 + i*3.15, 1.25, 3.0, 1.25, lbl, val, sub)

box(s5, 0.4, 2.7, 12.5, 0.04, fill=DIVIDER)

# Horizontal CLV bar chart (manual)
txt(s5, 'Total CLV by Segment', 0.4, 2.85, 6, 0.3, size=10, bold=True, color=NAVY)
max_clv = max(d['total_clv'] for d in seg_summary.values())
bar_w_max = 7.5
seg_colors = {
    'Champions': BLUE, 'Loyal': GREEN, 'Potential Loyalist': GOLD,
    'Promising': LIGHT_BLUE, 'New Customer': RGBColor(0x00,0xB0,0xF0),
    'Hibernating': RGBColor(0xCC,0x79,0xA7), 'Lost': GRAY,
}
for i, seg in enumerate(seg_order):
    d  = seg_summary[seg]
    y  = 3.25 + i * 0.48
    bw = bar_w_max * (d['total_clv'] / max_clv)
    col = seg_colors.get(seg, GRAY)
    txt(s5, seg, 0.4, y, 2.4, 0.36, size=9, color=DARK)
    box(s5, 2.85, y+0.05, max(bw, 0.05), 0.32, fill=col)
    txt(s5, f'${d["total_clv"]:,.0f}', 2.85 + bw + 0.1, y, 1.8, 0.36, size=9, color=DARK)

# ── SLIDE 6 — AT-RISK COHORT ──────────────────────────────────────────────────
s6 = slide()
header_band(s6,
    f'{at_risk_pct_c}% of customers show lapsing behaviour — ${at_risk_clv:,.0f} in CLV is at risk of permanent loss',
    'Hibernating and Lost segments require time-sensitive intervention to prevent irreversible churn')
footer_line(s6)
slide_number(s6, 6)

at_risk_detail = [
    ('Hibernating', hiber,  'Last purchase 193–280 days ago. Single-purchase customers.\nHigh reactivation potential with targeted offer.',          RED),
    ('Lost',        lost,   'Last purchase 280–365 days ago. Lowest recency scores.\nSelective win-back only — focus on higher CLV profiles.',        GRAY),
]

for i, (seg_name, d, desc, col) in enumerate(at_risk_detail):
    x = 0.4 + i * 6.3
    box(s6, x, 1.25, 6.0, 4.5, fill=LGRAY)
    box(s6, x, 1.25, 0.08, 4.5, fill=col)
    txt(s6, seg_name,         x+0.25, 1.35, 5.5, 0.38, size=14, bold=True, color=DARK)
    txt(s6, f'{d["count"]} customers',  x+0.25, 1.78, 5.5, 0.3,  size=10, color=GRAY)
    txt(s6, f'Avg CLV: ${d["avg_clv"]:,.0f}',    x+0.25, 2.08, 2.5, 0.35, size=13, bold=True, color=col)
    txt(s6, f'Total CLV at risk: ${d["total_clv"]:,.0f}', x+0.25, 2.48, 5.5, 0.3, size=9.5, color=DARK)
    txt(s6, f'Avg recency: {d["avg_recency"]} days',       x+0.25, 2.82, 5.5, 0.3, size=9.5, color=DARK)
    txt(s6, desc, x+0.25, 3.25, 5.5, 0.9, size=9.5, color=GRAY)

box(s6, 0.4, 5.9, 12.5, 0.55, fill=RGBColor(0xFF,0xF2,0xCC))
txt(s6, f'⚠  Recommended action: Launch a re-engagement sequence within 30 days for Hibernating customers. '
        f'Prioritise the top quartile by CLV (above ${seg_clv_p75("Hibernating"):,.0f}). '
        f'A/B test discount vs. content-led reactivation.',
    0.6, 5.97, 12.1, 0.4, size=9.5, color=RGBColor(0x7F, 0x60, 0x00))

# ── SLIDE 7 — GROWTH PIPELINE ─────────────────────────────────────────────────
s7 = slide()
header_band(s7,
    f'{growth_pct_c}% of the base are early-stage customers — structured nurture can convert them to high-value segments',
    'New Customer, Promising, and Potential Loyalist cohorts represent the pipeline for future CLV growth')
footer_line(s7)
slide_number(s7, 7)

growth_detail = [
    ('New Customer',       new_cust,  'Very recent, first purchase only.\nPriority: onboarding experience, second purchase incentive.', BLUE),
    ('Promising',          promising, 'Recent, 1–2 purchases. Positive engagement signal.\nPriority: loyalty programme invitation, category expansion.', RGBColor(0x00,0xB0,0xF0)),
    ('Potential Loyalist', pot_loyal, '2 purchases, moderate recency.\nPriority: reward next purchase, introduce referral mechanic.', GOLD),
]

for i, (seg_name, d, desc, col) in enumerate(growth_detail):
    x = 0.4 + i * 4.2
    box(s7, x, 1.25, 3.95, 4.8, fill=LGRAY)
    box(s7, x, 1.25, 3.95, 0.07, fill=col)
    txt(s7, seg_name,                      x+0.2, 1.42, 3.5, 0.38, size=12, bold=True, color=DARK)
    txt(s7, f'{d["count"]} customers',     x+0.2, 1.83, 3.5, 0.28, size=9,  color=GRAY)
    txt(s7, f'${d["avg_clv"]:,.0f}',       x+0.2, 2.15, 3.5, 0.5,  size=22, bold=True, color=col)
    txt(s7, 'avg CLV',                     x+0.2, 2.65, 3.5, 0.25, size=8,  color=GRAY)
    txt(s7, f'Avg recency: {d["avg_recency"]} days  |  Avg freq: {d["avg_frequency"]}x',
        x+0.2, 2.95, 3.5, 0.28, size=8.5, color=DARK)
    txt(s7, desc, x+0.2, 3.35, 3.5, 0.95, size=9, color=GRAY)

txt(s7, 'Migration target: move Promising and Potential Loyalist customers to Loyal status within 12 months',
    0.4, 6.3, 12.5, 0.35, size=10, bold=True, color=NAVY)

# ── SLIDE 8 — WHAT THE NUMBERS COULD NOT SEE ─────────────────────────────────
if blind_spots:
    s7b = slide()
    header_band(s7b, 'What the Numbers Could Not See',
                'Reading what customers wrote, alongside what they did')
    footer_line(s7b)
    slide_number(s7b, 8)

    # Level 2+ on the severity scale: something genuinely went wrong, not merely
    # an unmet preference. Counting stated_risk here would sweep in price and
    # competitor cases where nothing has actually failed.
    serious = [c for c, s in signals.items() if float(s['severity']) >= 2.0]
    kpis = [
        ('Customers flagged by language', str(len(blind_spots)),
         'Healthy on every purchase measure', BLUE),
        ('Lifetime value exposed', f'${blind_clv:,.0f}',
         f'{blind_clv / total_clv * 100:.1f}% of portfolio', RED),
        ('Need a person, not a campaign', str(len(needs_human)),
         f'of {total} customers reviewed', NAVY),
        ('Raised a serious problem', str(len(serious)),
         'Something went wrong, unresolved', GOLD_DARK),
    ]
    for i, (label, value, sub, col) in enumerate(kpis):
        kpi_card(s7b, 0.4 + i * 3.18, 1.25, 3.0, 1.25, label, value, sub, val_color=col)

    section_label(s7b, 'Flagged by what they said, not what they bought', 0.4, 2.72)

    cols = [('Customer', 0.4, 1.5), ('Segment', 1.9, 2.0), ('Lifetime value', 3.9, 1.6),
            ('What is driving it', 5.5, 2.1), ('Why RFM missed them', 7.6, 5.3)]
    for name, cx, cw in cols:
        txt(s7b, name.upper(), cx + 0.05, 3.0, cw - 0.1, 0.25, size=7.5, bold=True, color=GRAY)

    WHY = {
        'service': 'Still buying on schedule, but sitting on an unresolved failure',
        'competitor': 'Still buying, while actively weighing up another supplier',
        'price': 'Still buying, but the cost has become hard to justify',
        'product': 'Still buying, though the product is not meeting the need',
        'circumstance': 'Paused for reasons on their side, not ours',
    }
    for i, p in enumerate(blind_spots[:6]):
        y  = 3.3 + i * 0.44
        bg = LGRAY if i % 2 == 0 else WHITE
        box(s7b, 0.35, y, 12.6, 0.42, fill=bg)
        vals = [p['customerid'], p['segment'], f"${p['clv']:,.0f}",
                p['driver'].title(), WHY.get(p['driver'], 'Behaviour looks healthy')]
        for v, (_, cx, cw) in zip(vals, cols):
            txt(s7b, v, cx + 0.05, y + 0.09, cw - 0.1, 0.3, size=9, color=DARK)

    box(s7b, 0.4, 6.0, 12.5, 0.75, fill=RGBColor(0xED, 0xF3, 0xFA))
    txt(s7b, 'Why this is invisible to RFM:  the model is built entirely from past purchases. '
             'A customer who has decided to leave but has not yet stopped buying looks identical '
             'to a loyal one — right up until they go. Their words are the only early warning.',
        0.6, 6.12, 12.1, 0.55, size=9.5, color=NAVY)

    txt(s7b, SYNTHETIC_NOTE, 0.4, 6.87, 12.5, 0.25, size=6.5, italic=True, color=GRAY)

# ── SLIDES 9 & 10 — HOW THE MODEL READ THE BASE ──────────────────────────────
def chart_slide(title, subtitle, number, panels):
    """Two charts side by side, each with a caption underneath."""
    s = slide()
    header_band(s, title, subtitle)
    footer_line(s)
    slide_number(s, number)
    for i, (path, caption) in enumerate(panels):
        if not os.path.exists(path):
            continue
        x = 0.45 + i * 6.42
        s.shapes.add_picture(path, Inches(x), Inches(1.45), width=Inches(6.2))
        txt(s, caption, x + 0.05, 5.95, 6.1, 0.75, size=9, color=GRAY)
    txt(s, SYNTHETIC_NOTE, 0.45, 6.92, 12.5, 0.25, size=6.5, italic=True, color=GRAY)
    return s


if blind_spots and os.path.exists('jev_chart_1_blindspots.png'):
    chart_slide(
        'How the Model Read Your Customers',
        'Every customer message scored on two separate questions',
        9,
        [('jev_chart_1_blindspots.png',
          'Each dot is a customer. Across: what their buying history shows. Up: what they '
          'told us. The shaded corner holds customers who are still buying normally while '
          'saying they are unhappy — the group a behavioural model cannot surface.'),
         ('jev_chart_2_intent_vs_severity.png',
          'The two questions do not move together. An unresolved failure scores near the '
          'top on severity and near the bottom on intent to leave: those customers are '
          'complaining to us, not walking away. Treating the two as one number hides both.')])

    chart_slide(
        'What It Found, and How Sure It Was',
        'The reasons behind the numbers, and where the model declined to commit',
        10,
        [('jev_chart_3_drivers.png',
          'Each message was sorted into a single dominant reason. Just over a third raised '
          'no issue at all, which is itself useful: it separates the genuinely content from '
          'the merely quiet.'),
         ('jev_chart_4_confidence.png',
          'The model reports its own certainty. Where one play was clearly right it says so; '
          'where several were defensible it does not pretend otherwise, and those go to an '
          'analyst rather than onto a recommendation slide.')])

# ── SLIDE 11 — STRATEGIC RECOMMENDATIONS ──────────────────────────────────────
# Plays chosen by rfm_plays.py from the current data, when that file exists.
# Without it, the built-in recommendations below are used unchanged.
PLAYS_FILE    = 'rfm_plays.json'
HORIZON_COLOR = {'Defend': BLUE, 'Grow': GREEN, 'Recover': RED}

jev_plays = None
if os.path.exists(PLAYS_FILE):
    with open(PLAYS_FILE) as f:
        jev_plays = json.load(f)


def plays_to_recs(plays, top_n=4):
    """Render the top segments by portfolio value as recommendation cards."""
    cards = []
    for seg, p in sorted(plays.items(), key=lambda kv: -kv[1]['total_clv'])[:top_n]:
        bullets = [
            p['deck'],
            f"{p['count']} customers  ·  ${p['total_clv']:,.0f} CLV  ·  {p['channel']}  ·  cost: {p['cost']}",
            f"Urgency {p['urgency']:.1f} of {p['urgency_max']}  ·  {p['urgency_label'].split('.')[0]}",
        ]
        bullets.append(
            f"ANALYST REVIEW — confidence {p['confidence']:.2f}, runner-up was '{p['runner_up']}'"
            if p['needs_review'] else
            f"Selected with {p['confidence']:.2f} confidence"
        )
        cards.append((f"{p['horizon'].upper()}  ·  {seg.upper()}",
                      HORIZON_COLOR.get(p['horizon'], NAVY), p['title'], bullets))
    return cards


s8 = slide()
header_band(s8, 'Strategic Recommendations',
            'Plays selected against current data, highest portfolio value first'
            if jev_plays else
            'Four prioritised actions across defend, grow, and recover horizons')
footer_line(s8)
slide_number(s8, 11)

recs = [
    ('DEFEND',  BLUE,  'Protect the Champions and Loyal base',
     [
         f'Implement VIP programme for {champ["count"]+loyal["count"]} Champions and Loyal customers',
         'Personalised outreach cadence — minimum quarterly touchpoint',
         'Early access to new products and exclusive pricing tiers',
         'Monitor recency drift — flag any Champion with recency > 60 days for immediate intervention',
     ]),
    ('GROW',    GREEN, 'Accelerate conversion of the growth pipeline',
     [
         f'Design a second-purchase incentive programme targeting {new_cust["count"]} New Customers',
         f'Loyalty programme onboarding for {promising["count"]} Promising customers',
         'Set migration KPI: 30% of Promising → Loyal within 12 months',
         'A/B test onboarding email sequences to identify highest-converting content',
     ]),
    ('RECOVER', RED,   'Execute a time-bound win-back programme',
     [
         f'Prioritise {hiber["count"]} Hibernating customers — reactivation window closing',
         'Segment by CLV: premium offer for top 25%, content-led for remainder',
         'Set 90-day sunset policy — customers who do not respond move to Lost',
         f'For {lost["count"]} Lost customers: selective outreach only above ${seg_clv_p75("Lost"):,.0f} CLV (top quartile)',
     ]),
    ('MEASURE', NAVY,  'Establish ongoing RFM tracking and governance',
     [
         'Refresh RFM scores monthly — segment drift is a leading indicator of churn',
         'Define OKRs: Champion retention rate, Promising → Loyal conversion rate',
         'Build a CLV dashboard to track portfolio value over time',
         'Quarterly business review cadence aligned to segment performance',
     ]),
]

if jev_plays:
    recs = plays_to_recs(jev_plays)

for i, (tag, col, title, bullets) in enumerate(recs):
    x = 0.4  + (i % 2) * 6.3
    y = 1.25 + (i // 2) * 2.9
    box(s8, x, y, 6.0, 2.65, fill=LGRAY)
    box(s8, x, y, 0.08, 2.65, fill=col)
    txt(s8, tag,   x+0.25, y+0.08, 1.5, 0.3,  size=8,  bold=True, color=col)
    txt(s8, title, x+0.25, y+0.38, 5.5, 0.35, size=10.5, bold=True, color=DARK)
    for j, b in enumerate(bullets):
        txt(s8, f'–  {b}', x+0.25, y+0.82+j*0.42, 5.55, 0.38, size=8.5, color=GRAY)

# ── SLIDE 12 — NEXT STEPS ──────────────────────────────────────────────────────
s9 = slide()
header_band(s9, 'Next Steps',
            'Proposed 90-day roadmap to operationalise findings')
footer_line(s9)
slide_number(s9, 12)

phases = [
    ('Days 1–30\nFoundation', BLUE, [
        'Validate RFM scores against CRM and transaction data',
        'Socialise segmentation with Marketing, CRM, and Analytics teams',
        'Define success metrics and baseline KPIs per segment',
        'Brief CRM team on Champions & Loyal VIP programme design',
    ]),
    ('Days 31–60\nActivation', NAVY, [
        'Launch Hibernating win-back email sequence (test vs. control)',
        'Deploy second-purchase incentive to New Customer cohort',
        'Onboard Promising customers into loyalty programme',
        'Set up monthly RFM refresh cadence in data pipeline',
    ]),
    ('Days 61–90\nOptimise', GREEN, [
        'Review win-back programme results — iterate messaging and offer',
        'Track segment migration rates vs. targets',
        'Present first monthly CLV dashboard to leadership',
        'Define Phase 2 scope: predictive churn modelling, CLV uplift testing',
    ]),
]

for i, (phase, col, items) in enumerate(phases):
    x = 0.4 + i * 4.2
    box(s9, x, 1.25, 3.95, 5.5, fill=LGRAY)
    box(s9, x, 1.25, 3.95, 0.07, fill=col)
    txt(s9, phase, x+0.2, 1.42, 3.5, 0.6, size=11, bold=True, color=col)
    for j, item in enumerate(items):
        box(s9, x+0.2, 2.2+j*0.88, 0.22, 0.22, fill=col)
        txt(s9, item, x+0.55, 2.17+j*0.88, 3.2, 0.6, size=9, color=DARK)

# ── SLIDE 13 — APPENDIX / DATA SNAPSHOT ──────────────────────────────────────
s10 = slide()
header_band(s10, 'Appendix — Full Segment Data',
            'Source: rfm_analysis.csv  |  100 customers  |  Analysis date: March 2026')
footer_line(s10)
slide_number(s10, 13)

hdrs2 = ['Segment', '# Customers', '% Base', 'Avg CLV', 'Total CLV', 'Avg Recency', 'Avg Frequency', 'Avg Monetary']
cxs2  = [0.35, 2.7, 3.55, 4.45, 5.55, 6.85, 8.15, 9.55]
cws2  = [2.3,  0.8,  0.85,  1.05,  1.25,  1.25,  1.35,  3.2]

box(s10, 0.35, 1.2, 12.6, 0.38, fill=NAVY)
for hdr, cx, cw in zip(hdrs2, cxs2, cws2):
    txt(s10, hdr, cx+0.05, 1.24, cw, 0.3, size=8, bold=True, color=WHITE)

for i, seg in enumerate(seg_order):
    d   = seg_summary[seg]
    avg_mon = round(statistics.mean(r['monetaryValue'] for r in seg_data[seg]), 0)
    bg  = LGRAY if i % 2 == 0 else WHITE
    y   = 1.62 + i * 0.52
    box(s10, 0.35, y, 12.6, 0.5, fill=bg)
    vals2 = [
        seg,
        str(d['count']),
        f"{round(d['count']/total*100)}%",
        f"${d['avg_clv']:,.0f}",
        f"${d['total_clv']:,.0f}",
        f"{d['avg_recency']} days",
        f"{d['avg_frequency']}x",
        f"${avg_mon:,.0f}",
    ]
    for v, cx, cw in zip(vals2, cxs2, cws2):
        txt(s10, v, cx+0.05, y+0.12, cw-0.1, 0.28, size=8.5, color=DARK)

# ── SLIDE 14 — HOW THIS WAS BUILT ────────────────────────────────────────────
if blind_spots:
    s12 = slide()
    header_band(s12, 'How This Was Built',
                'Reading customer language without training a model')
    footer_line(s12)
    slide_number(s12, 14)

    low_conf = [s for s, p in jev_plays.items() if p['needs_review']] if jev_plays else []

    columns = [
        ('WHAT WE ASKED', BLUE,
         'Five plain questions about each\ncustomer\'s most recent message', [
            'Are they signalling they want to leave?',
            'How serious is the problem they describe?',
            'What is driving it — service, price, the product, a competitor, '
            'or something on their side?',
            'Could we still keep them if we acted this fortnight?',
            'Does this need a person, or will a campaign do?',
            'Answers come back as numbers, not paragraphs, so ordinary code can '
            'use them directly.',
         ]),
        ('WHY NOT A TRAINED MODEL', RED,
         'The usual approach did not fit\nthe problem we actually had', [
            'A trained classifier learns from examples. It needs thousands of past '
            'messages, each labelled by hand by someone who already knew the answer. '
            'We have 100 customers and no labels at all.',
            'Every new question would mean another labelled set and another training '
            'run. Here, adding a question took minutes.',
            'Our first scoring rule was wrong — it treated a furious customer as safe. '
            'Fixing it cost nothing, because the answers were already saved and we '
            'simply re-scored them. Retraining a model would have meant starting again.',
         ]),
        ('WHAT STAYED ORDINARY CODE', GREEN,
         'The model never touches\na single calculation', [
            'Every number is plain arithmetic: the RFM scores, lifetime value, the '
            'thresholds, the weights, who makes the list.',
            'The model judges meaning. Code owns every calculation and every decision '
            'that follows from it.',
            'This is the step before machine learning, not a replacement for it. Once '
            'enough of these judgments are paired with real outcomes, they become '
            'inputs to a conventional model.',
         ]),
    ]

    for i, (tag, col, strap, points) in enumerate(columns):
        x = 0.4 + i * 4.32
        box(s12, x, 1.25, 4.05, 4.55, fill=LGRAY)
        box(s12, x, 1.25, 4.05, 0.07, fill=col)
        txt(s12, tag, x + 0.22, 1.42, 3.7, 0.25, size=8, bold=True, color=col)
        txt(s12, strap, x + 0.22, 1.70, 3.7, 0.6, size=10, bold=True, color=DARK)

        y = 2.42
        for point in points:
            txt(s12, '–  ' + point, x + 0.22, y, 3.65, 0.9, size=8, color=GRAY)
            y += 0.24 + 0.135 * max(1, (len(point) // 52) + 1)

    box(s12, 0.4, 5.95, 12.5, 0.9, fill=RGBColor(0xED, 0xF3, 0xFA))
    txt(s12, 'The model reports how sure it is.', 0.6, 6.05, 3.0, 0.28,
        size=9.5, bold=True, color=NAVY)
    txt(s12, f'{len(low_conf)} of {len(jev_plays) if jev_plays else 0} recommended plays came back below our '
             f'confidence bar. Those are marked for analyst review rather than presented as settled. '
             f'A model that says "I am not sure" is more useful than one that guesses confidently — '
             f'and it is the difference between a slide you can defend and one you cannot.',
        0.6, 6.30, 12.1, 0.5, size=9, color=NAVY)

    txt(s12, SYNTHETIC_NOTE, 0.4, 6.92, 12.5, 0.25, size=6.5, italic=True, color=GRAY)

# ── SAVE ──────────────────────────────────────────────────────────────────────
out = 'RFM_Customer_Analysis.pptx'
prs.save(out)
print(f'Saved: {out}')
