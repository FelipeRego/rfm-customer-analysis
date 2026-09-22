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
# Every combination used below meets WCAG AA against the surface it sits on:
# 4.5:1 for body text, 3:1 for large text (>=18pt, or >=14pt bold).
#
# Two colours are surface-dependent. Gold and pale blue read well on navy and are
# unusable on white or light grey — gold on light grey is 1.47:1, which is why
# "$599" was effectively invisible. Each therefore has an ON-LIGHT variant, and the
# bright originals are reserved for navy backgrounds.
NAVY       = RGBColor(0x00, 0x33, 0x66)   # 12.6:1 on white
BLUE       = RGBColor(0x00, 0x70, 0xC0)   #  4.6:1 on light grey
WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
DARK       = RGBColor(0x1A, 0x1A, 0x1A)   # 15.6:1 on light grey
GRAY       = RGBColor(0x59, 0x59, 0x59)   #  6.3:1 on light grey
LGRAY      = RGBColor(0xF2, 0xF2, 0xF2)
RED        = RGBColor(0xC0, 0x00, 0x00)   #  5.8:1 on light grey
GREEN      = RGBColor(0x00, 0x70, 0x50)   #  5.5:1 on light grey
DIVIDER    = RGBColor(0xD6, 0xD6, 0xD6)

# On navy only.
LIGHT_BLUE = RGBColor(0xBD, 0xD7, 0xEE)   #  8.5:1 on navy,  1.3:1 on light — navy only
GOLD       = RGBColor(0xFF, 0xC0, 0x00)   #  7.7:1 on navy,  1.5:1 on light — navy only

# On white / light grey only.
GOLD_ON_LIGHT = RGBColor(0x8A, 0x68, 0x00)   # 4.6:1 on light grey
SKY_ON_LIGHT  = RGBColor(0x00, 0x76, 0xA1)   # 4.6:1 on light grey
GOLD_DARK     = GOLD_ON_LIGHT                # previous name, kept for call sites

# ── TYPE SCALE ────────────────────────────────────────────────────────────────
# Sized for projection: legible from the back of a room, not from a laptop. The
# previous deck ran at 8-9pt with 6.5pt footnotes, which is a document, not a slide.
# Nothing here goes below 12pt, and no content the audience must read is under 16pt.
T_HERO      = 44   # title slide
T_TITLE     = 28   # slide title
T_SUBTITLE  = 15   # line under the title
T_KPI_VAL   = 40   # the single number on a card
T_KPI_LABEL = 15
T_KPI_SUB   = 13
T_H2        = 22   # card / column heading
T_BODY      = 18   # default body copy
T_DENSE     = 16   # tables and multi-column blocks
T_CAPTION   = 14   # chart captions, secondary notes
T_LABEL     = 13   # small-caps section labels
T_MICRO     = 12   # footer, slide number, disclosures — floor for the deck

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

SYNTHETIC_NOTE = ('Customer messages are illustrative sample text, not real customer data. '
                  'Replace with real support and survey data before acting on named accounts.')

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

def txt(s, text, x, y, w, h, size=T_BODY, bold=False, color=DARK, align=PP_ALIGN.LEFT,
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

TITLE_CHAR_LIMIT = 46   # roughly one line at T_TITLE across the 12.5in title box


def header_band(s, title, subtitle=None):
    """Navy band with the slide title and an optional supporting line.

    The title box is sized for ONE line. Previously the band gave a 20pt title
    0.55in and several titles ran to 100 characters, so they wrapped and the
    second line printed straight through the subtitle. Anything over the limit
    is caught at build time rather than discovered in the PDF.
    """
    if len(title) > TITLE_CHAR_LIMIT:
        raise ValueError(
            f'Slide title is {len(title)} chars, over the {TITLE_CHAR_LIMIT} that fit '
            f'on one line at {T_TITLE}pt — it will overlap the subtitle. '
            f'Move the detail into the subtitle: {title!r}')
    box(s, 0, 0, 13.33, 1.15, fill=NAVY)
    txt(s, title, 0.4, 0.09, 12.5, 0.52, size=T_TITLE, bold=True, color=WHITE)
    if subtitle:
        txt(s, subtitle, 0.4, 0.62, 12.5, 0.34, size=T_SUBTITLE, color=LIGHT_BLUE)

def slide_number(s, n):
    txt(s, str(n), 12.7, 7.03, 0.5, 0.3, size=T_MICRO, color=GRAY, align=PP_ALIGN.RIGHT)

def footer_line(s):
    ln = s.shapes.add_connector(1,
        Inches(0.4), Inches(7.08), Inches(12.93), Inches(7.08))
    ln.line.color.rgb = DIVIDER
    ln.line.width = Pt(0.5)
    txt(s, 'CONFIDENTIAL — RFM Customer Analysis', 0.4, 7.12, 6, 0.28,
        size=T_MICRO, color=GRAY)

def kpi_card(s, x, y, w, h, label, value, sub=None, bg=LGRAY, val_color=NAVY):
    box(s, x, y, w, h, fill=bg)
    txt(s, label, x+0.18, y+0.12, w-0.36, 0.46, size=T_KPI_LABEL, color=GRAY)
    txt(s, value, x+0.18, y+0.62, w-0.36, 0.78, size=T_KPI_VAL, bold=True, color=val_color)
    if sub:
        txt(s, sub, x+0.18, y+1.44, w-0.36, 0.40, size=T_KPI_SUB, color=GRAY)

def bullet(tf, text, size=T_BODY, bold=False, color=DARK, indent=0):
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
    txt(s, text.upper(), x, y, 6.5, 0.28, size=T_LABEL, bold=True, color=BLUE)

# ── SLIDE 1 — TITLE ───────────────────────────────────────────────────────────
s1 = slide()
box(s1, 0, 0, 13.33, 7.5, fill=NAVY)
box(s1, 0, 3.6, 13.33, 0.04, fill=GOLD)
# accent stripe
box(s1, 0, 0, 0.18, 7.5, fill=BLUE)

txt(s1, 'Unlocking Customer Value Through\nBehavioural Segmentation',
    0.55, 1.4, 9.5, 1.9, size=T_HERO, bold=True, color=WHITE)
txt(s1, 'RFM Analysis — Customer Intelligence Report',
    0.55, 3.25, 9, 0.45, size=T_H2, color=LIGHT_BLUE)
txt(s1, f'Analysis across {total} customers  |  {len(seg_summary)} of 11 behavioural segments present  |  {LIFESPAN_LABEL} CLV horizon',
    0.55, 3.85, 10, 0.35, size=T_BODY, color=LIGHT_BLUE, italic=True)
txt(s1, 'March 2026', 0.55, 6.9, 4, 0.35, size=T_BODY, color=LIGHT_BLUE)
txt(s1, 'CONFIDENTIAL', 10.5, 6.9, 2.5, 0.35, size=T_DENSE, color=GOLD,
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
    box(s2, 0.4, y, 0.07, 1.56, fill=col)
    txt(s2, num, 0.62, y+0.02, 0.7, 0.42, size=T_BODY, bold=True, color=col)
    txt(s2, headline, 1.35, y, 11.5, 0.46, size=T_H2, bold=True, color=DARK)
    txt(s2, detail,   1.35, y+0.88, 11.5, 0.9, size=T_BODY, color=GRAY)

# ── SLIDE 3 — METHODOLOGY ─────────────────────────────────────────────────────
s3 = slide()
header_band(s3, 'Methodology',
            'RFM scoring translates transactional data into actionable behavioural profiles')
footer_line(s3)
slide_number(s3, 3)

# Copy shortened to fit ~36 characters a line in a 2.35in column at projection
# size, and the CLV description corrected — it still described the old formula,
# which cancelled its own frequency terms.
steps = [
    ('R — Recency',   'Days since the last purchase.\nMore recent scores higher.\nRanked by percentile.',      BLUE),
    ('F — Frequency', 'Number of purchases.\n1 purchase scores 1,\n5 or more scores 5.',                       NAVY),
    ('M — Monetary',  'Total spend to date.\nHigher spend scores higher.\nRanked by percentile.',              BLUE),
    ('Segmentation',  '11 possible segments from\nthe R x F matrix, Champions\nthrough to Lost.',              NAVY),
    ('CLV Estimate',  'Annual profit, multiplied by\nthe chance they stay, over a\ndiscounted 3-year horizon.', BLUE),
]

for i, (title, body, col) in enumerate(steps):
    x = 0.4 + i * 2.52
    box(s3, x, 1.30, 2.35, 0.07, fill=col)
    txt(s3, f'{i+1}', x, 1.48, 0.6, 0.46, size=T_TITLE, bold=True, color=col)
    txt(s3, title,   x, 2.02, 2.35, 0.36, size=T_BODY, bold=True, color=DARK)
    txt(s3, body,    x, 2.48, 2.35, 1.75, size=T_DENSE, color=GRAY)

box(s3, 0.4, 4.45, 12.5, 0.04, fill=DIVIDER)

txt(s3, 'Configuration', 0.4, 4.68, 4, 0.34, size=T_BODY, bold=True, color=NAVY)
configs = [
    ('Input file',         'rfm_mockup.csv'),
    ('Customers analysed', f'{total}'),
    ('CLV lifespan',       '3 years'),
    ('Margin assumption',  '20%'),
    ('Segments present',   f'{len(seg_summary)} of 11'),
    ('Output file',        'rfm_analysis.csv'),
]
for i, (k, v) in enumerate(configs):
    col_x = 0.4 + (i % 3) * 4.2
    row_y = 5.12 + (i // 3) * 0.58
    txt(s3, f'{k}:', col_x, row_y, 2.4, 0.36, size=T_DENSE, color=GRAY)
    txt(s3, v, col_x + 2.25, row_y, 1.9, 0.36, size=T_DENSE, bold=True, color=DARK)

# ── SLIDE 4 — SEGMENT LANDSCAPE ───────────────────────────────────────────────
s4 = slide()
header_band(s4, 'Segment Landscape',
            f'{total} customers across {len(seg_summary)} active segments · ${total_clv:,.0f} total estimated CLV')
footer_line(s4)
slide_number(s4, 4)

# Rebuilt for projection. "Share" was dropped: with 100 customers it restated the
# count. The priority column was long prose that wrapped into the row below, and it
# carried its urgency in colour alone — the word now says it, and colour reinforces.
headers = ['Segment', 'Customers', 'Avg CLV', 'Total CLV', 'Avg Recency', 'Priority']
col_xs  = [0.35, 3.45, 5.00, 6.75, 8.60, 10.65]
col_ws  = [3.05, 1.50, 1.70, 1.80, 2.00, 2.25]

ROW_Y, ROW_H, ROW_PITCH = 1.92, 0.60, 0.62

box(s4, 0.35, 1.32, 12.6, 0.52, fill=NAVY)
for hdr, cx, cw in zip(headers, col_xs, col_ws):
    txt(s4, hdr, cx+0.08, 1.42, cw, 0.34, size=T_DENSE, bold=True, color=WHITE)

priorities = {
    'Champions':          ('Protect',   GREEN),
    'Loyal':              ('Reward',    GREEN),
    'Potential Loyalist': ('Nudge',     BLUE),
    'Promising':          ('Onboard',   BLUE),
    'New Customer':       ('Welcome',   BLUE),
    'Need Attention':     ('Review',    GOLD_ON_LIGHT),
    'Hibernating':        ('Re-engage', RED),
    'Lost':               ('Win back',  RED),
}

for i, seg in enumerate(seg_order):
    d    = seg_summary[seg]
    pri, pcol = priorities.get(seg, ('Monitor', GRAY))
    bg = LGRAY if i % 2 == 0 else WHITE
    y  = ROW_Y + i * ROW_PITCH
    box(s4, 0.35, y, 12.6, ROW_H, fill=bg)

    vals = [
        (seg,                                   DARK,  True),
        (str(d['count']),                       DARK,  False),
        (f"${d['avg_clv']:,.0f}",               NAVY,  True),
        (f"${d['total_clv']:,.0f}",             NAVY,  False),
        (f"{d['avg_recency']:.0f} days",        GRAY,  False),
        (pri,                                   pcol,  True),
    ]
    for (v, vc, vb), cx, cw in zip(vals, col_xs, col_ws):
        txt(s4, v, cx+0.08, y+0.14, cw-0.12, 0.34, size=T_DENSE, bold=vb, color=vc)

# ── SLIDE 5 — VALUE CONCENTRATION ─────────────────────────────────────────────
s5 = slide()
header_band(s5,
    'Where the Value Is Concentrated',
    f'Champions and Loyal are {value_pct_c}% of the base and {value_pct_v}% of portfolio CLV — '
    f'an asset and a risk at once')
footer_line(s5)
slide_number(s5, 5)

kpis = [
    ('Champions — Avg CLV',    f'${champ["avg_clv"]:,.0f}',  f'{champ["count"]} customers  |  avg recency {champ["avg_recency"]:.0f} days'),
    ('Loyal — Avg CLV',        f'${loyal["avg_clv"]:,.0f}',  f'{loyal["count"]} customers  |  avg recency {loyal["avg_recency"]:.0f} days'),
    ('Portfolio Total CLV',    f'${total_clv:,.0f}',          f'Across all {total} customers'),
    ('Value Seg. CLV Share',   f'{value_pct_v}%',             f'Delivered by {value_pct_c}% of customers'),
]
for i, (lbl, val, sub) in enumerate(kpis):
    kpi_card(s5, 0.4 + i*3.15, 1.25, 3.0, 1.95, lbl, val, sub)

box(s5, 0.4, 3.30, 12.5, 0.04, fill=DIVIDER)

# Horizontal CLV bar chart (manual)
txt(s5, 'Total CLV by Segment', 0.4, 3.40, 6, 0.34, size=T_BODY, bold=True, color=NAVY)
max_clv = max(d['total_clv'] for d in seg_summary.values())
bar_w_max = 7.5
seg_colors = {
    'Champions': BLUE, 'Loyal': GREEN, 'Potential Loyalist': GOLD_ON_LIGHT,
    'Promising': SKY_ON_LIGHT, 'New Customer': RGBColor(0x00, 0x5F, 0x73),
    'Need Attention': RGBColor(0x7B, 0x6F, 0xB0),
    'Hibernating': RGBColor(0xCC, 0x79, 0xA7), 'Lost': GRAY,
}
for i, seg in enumerate(seg_order):
    d  = seg_summary[seg]
    y  = 3.84 + i * 0.40
    bw = bar_w_max * (d['total_clv'] / max_clv)
    col = seg_colors.get(seg, GRAY)
    txt(s5, seg, 0.4, y, 2.4, 0.34, size=T_DENSE, color=DARK)
    box(s5, 2.85, y+0.04, max(bw, 0.05), 0.28, fill=col)
    txt(s5, f'${d["total_clv"]:,.0f}', 2.85 + bw + 0.12, y, 1.8, 0.34, size=T_DENSE, color=DARK)

# ── SLIDE 6 — AT-RISK COHORT ──────────────────────────────────────────────────
s6 = slide()
header_band(s6,
    'The Lapsing Cohort',
    f'{at_risk_pct_c}% of customers are drifting and ${at_risk_clv:,.0f} of CLV is at risk — '
    f'the window for intervention is closing')
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
    txt(s6, seg_name,         x+0.25, 1.35, 5.5, 0.38, size=T_H2, bold=True, color=DARK)
    txt(s6, f'{d["count"]} customers',  x+0.25, 1.78, 5.5, 0.3,  size=T_BODY, color=GRAY)
    txt(s6, f'Avg CLV: ${d["avg_clv"]:,.0f}',    x+0.25, 2.08, 2.5, 0.35, size=T_H2, bold=True, color=col)
    txt(s6, f'Total CLV at risk: ${d["total_clv"]:,.0f}', x+0.25, 2.48, 5.5, 0.3, size=T_DENSE, color=DARK)
    txt(s6, f'Avg recency: {d["avg_recency"]} days',       x+0.25, 2.82, 5.5, 0.3, size=T_DENSE, color=DARK)
    txt(s6, desc, x+0.25, 3.25, 5.5, 0.9, size=T_DENSE, color=GRAY)

box(s6, 0.4, 5.9, 12.5, 0.55, fill=RGBColor(0xFF,0xF2,0xCC))
txt(s6, f'⚠  Recommended action: Launch a re-engagement sequence within 30 days for Hibernating customers. '
        f'Prioritise the top quartile by CLV (above ${seg_clv_p75("Hibernating"):,.0f}). '
        f'A/B test discount vs. content-led reactivation.',
    0.6, 5.97, 12.1, 0.4, size=T_DENSE, color=RGBColor(0x7F, 0x60, 0x00))

# ── SLIDE 7 — GROWTH PIPELINE ─────────────────────────────────────────────────
s7 = slide()
header_band(s7,
    'The Growth Pipeline',
    f'{growth_pct_c}% of the base is early-stage — New Customer, Promising and Potential '
    f'Loyalist are where future CLV is made')
footer_line(s7)
slide_number(s7, 7)

growth_detail = [
    ('New Customer',       new_cust,  'Very recent, first purchase only.\nPriority: onboarding experience, second purchase incentive.', BLUE),
    ('Promising',          promising, 'Recent, 1–2 purchases. Positive engagement signal.\nPriority: loyalty programme invitation, category expansion.', SKY_ON_LIGHT),
    ('Potential Loyalist', pot_loyal, '2 purchases, moderate recency.\nPriority: reward next purchase, introduce referral mechanic.', GOLD_ON_LIGHT),
]

for i, (seg_name, d, desc, col) in enumerate(growth_detail):
    x = 0.4 + i * 4.2
    box(s7, x, 1.25, 3.95, 4.8, fill=LGRAY)
    box(s7, x, 1.25, 3.95, 0.07, fill=col)
    txt(s7, seg_name,                      x+0.22, 1.45, 3.5, 0.44, size=T_H2, bold=True, color=DARK)
    txt(s7, f'{d["count"]} customers',     x+0.22, 1.95, 3.5, 0.32, size=T_DENSE,  color=GRAY)
    txt(s7, f'${d["avg_clv"]:,.0f}',       x+0.22, 2.34, 3.5, 0.78, size=T_KPI_VAL, bold=True, color=col)
    txt(s7, 'avg CLV',                     x+0.22, 3.08, 3.5, 0.30, size=T_CAPTION, color=GRAY)
    txt(s7, f'Avg recency: {d["avg_recency"]:.0f} days\nAvg frequency: {d["avg_frequency"]}x',
        x+0.22, 3.46, 3.5, 0.62, size=T_DENSE, color=DARK)
    txt(s7, desc, x+0.22, 4.18, 3.5, 1.55, size=T_DENSE, color=GRAY)

txt(s7, 'Migration target: move Promising and Potential Loyalist customers to Loyal status within 12 months',
    0.4, 6.3, 12.5, 0.35, size=T_BODY, bold=True, color=NAVY)

# ── SLIDE 8 — WHAT THE NUMBERS COULD NOT SEE ─────────────────────────────────
if blind_spots:
    s7b = slide()
    header_band(s7b, 'What the Numbers Could Not See',
                'Still buying normally — and telling us they are unhappy')
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
        kpi_card(s7b, 0.4 + i * 3.18, 1.25, 3.0, 1.95, label, value, sub, val_color=col)

    section_label(s7b, 'Flagged by what they said, not what they bought', 0.4, 3.42)

    cols = [('Customer', 0.4, 1.7), ('Segment', 2.1, 2.2), ('Lifetime value', 4.3, 1.7),
            ('What is driving it', 6.0, 2.2), ('Why RFM missed them', 8.2, 4.7)]
    for name, cx, cw in cols:
        txt(s7b, name.upper(), cx + 0.05, 3.76, cw - 0.1, 0.3, size=T_LABEL, bold=True, color=GRAY)

    # Kept under ~44 characters: that is one line in a 4.7in column at T_DENSE,
    # and a second line is clipped by the row beneath.
    WHY = {
        'service':      'Buying on schedule, failure unresolved',
        'competitor':   'Buying, but weighing up a competitor',
        'price':        'Buying, but the cost is hard to justify',
        'product':      'Buying, but the product does not fit',
        'circumstance': 'Paused on their side, not ours',
    }
    for i, p in enumerate(blind_spots[:6]):
        y  = 4.14 + i * 0.50
        bg = LGRAY if i % 2 == 0 else WHITE
        box(s7b, 0.35, y, 12.6, 0.48, fill=bg)
        vals = [p['customerid'], p['segment'], f"${p['clv']:,.0f}",
                p['driver'].title(), WHY.get(p['driver'], 'Behaviour looks healthy')]
        for v, (_, cx, cw) in zip(vals, cols):
            txt(s7b, v, cx + 0.05, y + 0.11, cw - 0.1, 0.34, size=T_DENSE, color=DARK)

    # The "why RFM misses these" explanation moved into the subtitle: at projection
    # size a 230-character paragraph could not share the page with the table.
    txt(s7b, SYNTHETIC_NOTE, 0.4, 6.82, 12.5, 0.28, size=T_MICRO, italic=True, color=GRAY)

# Alt text for the chart images. Read aloud by screen readers and shown when an
# image fails to load, so each one states what the chart actually shows.
CHART_ALT = {
    'jev_chart_1_blindspots.png':
        "Scatter plot. Horizontal axis: risk visible in the purchase history. Vertical "
        "axis: risk stated in the customer's own words. Marker size shows lifetime value. "
        "Five customers sit in the upper-left region of low behavioural risk and high "
        "stated risk — CUS5907I, CUSCRUYF, CUS65KXV, CUSKOIXN and CUSOR56F — together "
        "worth $3,502, or 8.5% of portfolio value.",
    'jev_chart_2_intent_vs_severity.png':
        "Paired-dot chart comparing two scores for each type of customer message. An "
        "unresolved service failure scores 0.90 on problem severity but only 0.22 on "
        "intent to leave. Quietly closing the account is the reverse: 0.78 on intent to "
        "leave and 0.14 on severity. The two measures move independently of each other.",
    'jev_chart_3_drivers.png':
        "Horizontal bar chart of the dominant reason behind each of 100 customer messages. "
        "Nothing, they are content: 36. The product itself: 26. Cost: 19. How we handled "
        "them: 8. Something on their side: 7. A competitor: 4.",
    'jev_chart_4_confidence.png':
        "Horizontal bar chart of how certain the model was about the recommended action for "
        "each customer group, against a 0.50 review threshold. Hibernating 1.00, Need "
        "Attention 0.98, Lost 0.94, New Customer 0.92, Promising 0.64, Champions 0.64, "
        "Loyal 0.49 and Potential Loyalist 0.45. The last two fall below the threshold and "
        "are flagged for analyst review.",
}


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
        pic = s.shapes.add_picture(path, Inches(x), Inches(1.42), width=Inches(6.2))
        # python-pptx defaults alt text to the file name, so a screen reader would
        # announce "jev_chart_1_blindspots.png". Describe what the chart shows.
        pic._element._nvXxPr.cNvPr.set('descr', CHART_ALT.get(path, caption))
        txt(s, caption, x + 0.05, 5.62, 6.1, 1.1, size=T_CAPTION, color=GRAY)
    txt(s, SYNTHETIC_NOTE, 0.45, 6.78, 12.5, 0.26, size=T_MICRO, italic=True, color=GRAY)
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
    """Render the top segments by portfolio value as recommendation cards.

    Three bullets, not four: at projection size a fourth line pushed the card past
    the half-slide it has. Urgency and confidence share a line, which reads better
    anyway — how urgent it is and how sure we are belong together.
    """
    cards = []
    for seg, p in sorted(plays.items(), key=lambda kv: -kv[1]['total_clv'])[:top_n]:
        certainty = (f"ANALYST REVIEW · confidence {p['confidence']:.2f}"
                     if p['needs_review'] else
                     f"confidence {p['confidence']:.2f}")
        bullets = [
            p['deck'],
            f"{p['count']} customers  ·  ${p['total_clv']:,.0f} CLV  ·  {p['channel']}",
            f"Urgency {p['urgency']:.1f} of {p['urgency_max']}  ·  {certainty}",
        ]
        cards.append((p['horizon'].upper(), seg.upper(),
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

# The tag used to be "DEFEND · CHAMPIONS" in a 1.5in box, which wrapped onto the
# title. Horizon and segment now sit on one wide line, and bullets are pitched to
# clear two wrapped lines at projection size.
CARD_W, CARD_H = 6.15, 2.72
BULLET_PITCH   = 0.56

for i, (horizon, seg_name, col, title, bullets) in enumerate(recs):
    x = 0.4  + (i % 2) * 6.42
    y = 1.30 + (i // 2) * 2.95
    box(s8, x, y, CARD_W, CARD_H, fill=LGRAY)
    box(s8, x, y, 0.09, CARD_H, fill=col)
    txt(s8, f'{horizon}  ·  {seg_name}', x+0.28, y+0.09, CARD_W-0.5, 0.3,
        size=T_LABEL, bold=True, color=col)
    txt(s8, title, x+0.28, y+0.38, CARD_W-0.5, 0.42, size=T_H2, bold=True, color=DARK)
    for j, b in enumerate(bullets):
        txt(s8, f'–  {b}', x+0.28, y+0.88 + j*BULLET_PITCH, CARD_W-0.5, 0.52,
            size=T_DENSE, color=GRAY)

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
    txt(s9, phase, x+0.2, 1.42, 3.5, 0.6, size=T_BODY, bold=True, color=col)
    for j, item in enumerate(items):
        box(s9, x+0.22, 2.34+j*1.02, 0.20, 0.20, fill=col)
        txt(s9, item, x+0.58, 2.24+j*1.02, 3.20, 0.92, size=T_DENSE, color=DARK)

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
    txt(s10, hdr, cx+0.05, 1.24, cw, 0.3, size=T_CAPTION, bold=True, color=WHITE)

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
        txt(s10, v, cx+0.05, y+0.12, cw-0.1, 0.28, size=T_DENSE, color=DARK)

# ── SLIDE 14 — HOW THIS WAS BUILT ────────────────────────────────────────────
if blind_spots:
    s12 = slide()
    header_band(s12, 'How This Was Built',
                'Reading customer language without training a model')
    footer_line(s12)
    slide_number(s12, 14)

    low_conf = [s for s, p in jev_plays.items() if p['needs_review']] if jev_plays else []

    # Trimmed for projection. The previous copy ran to 200-character bullets, which
    # at 14pt in a 3.65in column is six wrapped lines — the columns overflowed their
    # own boxes and collided with the strip beneath.
    columns = [
        ('WHAT WE ASKED', BLUE,
         'Five plain questions about\neach customer message', [
            'Are they signalling they want to leave?',
            'How serious is the problem?',
            'What is driving it — service, price, the product, a competitor?',
            'Could we still keep them if we acted now?',
            'Does this need a person, or a campaign?',
            'Answers come back as numbers, so ordinary code can use them.',
         ]),
        ('WHY NOT A TRAINED MODEL', RED,
         'The usual approach did not fit\nthe problem we had', [
            'A trained classifier learns from examples. It needs thousands of '
            'messages, each labelled by hand.',
            'We have 100 customers and no labels at all.',
            'Every new question would mean another labelled set and another '
            'training run. Here it took minutes.',
            'Our first scoring rule was wrong. Fixing it cost nothing, because '
            'the answers were already saved.',
         ]),
        ('WHAT STAYED ORDINARY CODE', GREEN,
         'The model never touches\na single calculation', [
            'Every number is plain arithmetic: the scores, the lifetime value, '
            'the thresholds, the weights.',
            'The model reads meaning. Code owns every calculation that follows.',
            'This is the step before machine learning, not a replacement for it.',
            'Pair enough of these judgments with real outcomes and they become '
            'inputs to a conventional model.',
         ]),
    ]

    for i, (tag, col, strap, points) in enumerate(columns):
        x = 0.4 + i * 4.32
        box(s12, x, 1.25, 4.05, 4.95, fill=LGRAY)
        box(s12, x, 1.25, 4.05, 0.08, fill=col)
        txt(s12, tag, x + 0.22, 1.42, 3.7, 0.25, size=T_CAPTION, bold=True, color=col)
        txt(s12, strap, x + 0.22, 1.74, 3.7, 0.95, size=T_BODY, bold=True, color=DARK)

        CHARS_PER_LINE = 39          # 3.65in column at T_CAPTION
        LINE_H         = 0.235       # T_CAPTION line height in inches
        y = 2.82
        for point in points:
            lines = max(1, -(-len(point) // CHARS_PER_LINE))
            txt(s12, '–  ' + point, x + 0.22, y, 3.65, lines * LINE_H + 0.1,
                size=T_CAPTION, color=GRAY)
            y += lines * LINE_H + 0.20

    box(s12, 0.4, 6.34, 12.5, 0.62, fill=RGBColor(0xED, 0xF3, 0xFA))
    txt(s12, f'The model reports how sure it is — {len(low_conf)} of '
             f'{len(jev_plays) if jev_plays else 0} plays fell below our confidence bar '
             f'and are flagged for review.',
        0.6, 6.48, 12.1, 0.36, size=T_DENSE, bold=True, color=NAVY)

    txt(s12, SYNTHETIC_NOTE, 0.4, 6.82, 12.5, 0.28, size=T_MICRO, italic=True, color=GRAY)

# ── SAVE ──────────────────────────────────────────────────────────────────────
out = 'RFM_Customer_Analysis.pptx'
prs.save(out)
print(f'Saved: {out}')
